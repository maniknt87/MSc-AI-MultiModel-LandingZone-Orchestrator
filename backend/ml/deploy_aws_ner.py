import argparse
import json

import boto3
from sagemaker import Session, image_uris

from deploy_aws_sentiment import delete_resources, resource_name


MODEL_HUB_ID = "dslim/bert-base-NER"


def deploy(args):
    boto_session = boto3.Session(region_name=args.region)
    client = boto_session.client("sagemaker")
    sm_session = Session(boto_session=boto_session)
    endpoint_name = resource_name("ner", args.deployment_name, args.environment)
    endpoint_config_name = resource_name("ner-config", args.deployment_name, args.environment)
    model_name = resource_name("ner-model", args.deployment_name, args.environment)
    delete_resources(client, endpoint_name, endpoint_config_name, model_name)
    image_uri = image_uris.retrieve(
        framework="huggingface",
        region=args.region,
        version="4.37.0",
        py_version="py310",
        image_scope="inference",
        base_framework_version="pytorch2.1.0",
        instance_type=args.instance_type,
    )
    client.create_model(
        ModelName=model_name,
        ExecutionRoleArn=args.execution_role_arn,
        PrimaryContainer={
            "Image": image_uri,
            "ModelDataUrl": args.model_data_url,
            "Environment": {
                "SAGEMAKER_PROGRAM": "inference.py",
                "SAGEMAKER_SUBMIT_DIRECTORY": "/opt/ml/model/code",
            },
        },
    )
    client.create_endpoint_config(
        EndpointConfigName=endpoint_config_name,
        ProductionVariants=[{
            "VariantName": "AllTraffic",
            "ModelName": model_name,
            "InitialInstanceCount": 1,
            "InstanceType": args.instance_type,
            "InitialVariantWeight": 1.0,
        }],
    )
    client.create_endpoint(
        EndpointName=endpoint_name,
        EndpointConfigName=endpoint_config_name,
        Tags=[
            {"Key": "ManagedBy", "Value": "AzureDevOps"},
            {"Key": "Environment", "Value": args.environment},
            {"Key": "Workload", "Value": "named-entity-recognition"},
        ],
    )
    client.get_waiter("endpoint_in_service").wait(
        EndpointName=endpoint_name,
        WaiterConfig={"Delay": 30, "MaxAttempts": 60},
    )
    description = client.describe_endpoint(EndpointName=endpoint_name)
    print(json.dumps({
        "endpoint_name": endpoint_name,
        "endpoint_status": description["EndpointStatus"],
        "model_id": MODEL_HUB_ID,
        "model_data_url": args.model_data_url,
        "instance_type": args.instance_type,
        "region": args.region,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", required=True)
    parser.add_argument("--deployment-name", required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--instance-type", required=True)
    parser.add_argument("--execution-role-arn", required=True)
    parser.add_argument("--model-data-url", required=True)
    deploy(parser.parse_args())


if __name__ == "__main__":
    main()
