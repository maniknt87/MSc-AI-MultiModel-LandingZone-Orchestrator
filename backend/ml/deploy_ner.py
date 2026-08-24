import os

from azure.ai.ml import MLClient
from azure.ai.ml.entities import (
    CodeConfiguration,
    Environment,
    ManagedOnlineDeployment,
    ManagedOnlineEndpoint,
    Model,
)
from azure.core.exceptions import HttpResponseError
from azure.identity import DefaultAzureCredential


SUBSCRIPTION_ID = os.environ["AZURE_SUBSCRIPTION_ID"]
RESOURCE_GROUP = os.environ.get("AZURE_RESOURCE_GROUP", "rg-ai-development")
WORKSPACE_NAME = os.environ.get("AZURE_ML_WORKSPACE", "aml-development")
SUBSCRIPTION_SUFFIX = SUBSCRIPTION_ID.replace("-", "")[:8]
ENDPOINT_NAME = f"ner-ai-{SUBSCRIPTION_SUFFIX}"
DEPLOYMENT_NAME = "ner-v1"
MODEL_PATH = os.environ["AZURE_MODEL_PATH"]
INSTANCE_TYPE = os.environ.get("AZURE_ML_INSTANCE_TYPE", "Standard_DS2_v2")


def main():
    print("Azure ML Named Entity Recognition Deployment")
    print(f"Resource Group : {RESOURCE_GROUP}")
    print(f"Workspace      : {WORKSPACE_NAME}")
    print(f"Endpoint       : {ENDPOINT_NAME}")

    ml_client = MLClient(
        credential=DefaultAzureCredential(),
        subscription_id=SUBSCRIPTION_ID,
        resource_group_name=RESOURCE_GROUP,
        workspace_name=WORKSPACE_NAME,
    )
    workspace = ml_client.workspaces.get(WORKSPACE_NAME)
    network_status = getattr(getattr(workspace, "managed_network", None), "status", None)
    status_value = getattr(network_status, "value", network_status)
    if str(status_value).lower() != "succeeded":
        ml_client.workspaces.begin_provision_network(
            workspace_name=WORKSPACE_NAME, include_spark=False
        ).result()

    environment = Environment(
        name="ner-inference-env",
        description="Environment for named entity recognition inference",
        image="mcr.microsoft.com/azureml/openmpi4.1.0-ubuntu20.04:latest",
        conda_file="backend/ml/ner/environment.yml",
    )
    environment = ml_client.environments.create_or_update(environment)
    model = ml_client.models.create_or_update(Model(
        path=MODEL_PATH,
        name="ner-bert-base",
        version="1",
        description="Cached dslim/bert-base-NER model",
        type="custom_model",
    ))
    endpoint = ManagedOnlineEndpoint(
        name=ENDPOINT_NAME,
        description="Named Entity Recognition managed online endpoint",
        auth_mode="key",
    )
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    deployment = ManagedOnlineDeployment(
        name=DEPLOYMENT_NAME,
        endpoint_name=ENDPOINT_NAME,
        environment=environment,
        model=model,
        code_configuration=CodeConfiguration(
            code="backend/ml/ner", scoring_script="score.py"
        ),
        instance_type=INSTANCE_TYPE,
        instance_count=1,
    )
    try:
        ml_client.online_deployments.begin_create_or_update(deployment).result()
    except HttpResponseError as error:
        if "unrecoverable state" not in str(error).lower():
            raise
        ml_client.online_deployments.begin_delete(
            name=DEPLOYMENT_NAME, endpoint_name=ENDPOINT_NAME
        ).result()
        ml_client.online_deployments.begin_create_or_update(deployment).result()

    endpoint = ml_client.online_endpoints.get(ENDPOINT_NAME)
    endpoint.traffic = {DEPLOYMENT_NAME: 100}
    ml_client.online_endpoints.begin_create_or_update(endpoint).result()
    print("NER model deployment completed.")


if __name__ == "__main__":
    main()
