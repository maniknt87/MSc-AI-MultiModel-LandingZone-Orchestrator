import json
import re
import time
import uuid

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from config.settings import (
    AWS_PROFILE,
    AWS_REGION,
    AWS_SAGEMAKER_ENDPOINT_NAME,
    AWS_SAGEMAKER_MODEL_VERSION,
    AWS_SAGEMAKER_REQUEST_TIMEOUT,
    AZURE_ML_DEPLOYMENT_NAME,
    AZURE_ML_CREDENTIAL_CACHE_SECONDS,
    AZURE_ML_ENDPOINT_KEY,
    AZURE_ML_ENDPOINT_NAME,
    AZURE_ML_MODEL_VERSION,
    AZURE_ML_REQUEST_TIMEOUT,
    AZURE_ML_SCORING_URI,
    AZURE_SUBSCRIPTION_ID,
)
from database.database import get_connection


_azure_runtime_cache = {}


def _aws_session(region=None):
    return boto3.Session(profile_name=AWS_PROFILE or None, region_name=region or AWS_REGION)


def _aws_is_configured():
    if not AWS_SAGEMAKER_ENDPOINT_NAME:
        return False
    try:
        return _aws_session().get_credentials() is not None
    except (BotoCoreError, ClientError):
        return False


def _azure_slug(value):
    return re.sub(r"[^a-z0-9-]+", "-", str(value).strip().lower()).strip("-")


def _resource_name(prefix, deployment_name, environment):
    value = re.sub(r"[^a-z0-9-]", "-", f"{prefix}-{deployment_name}-{environment}".lower())
    return re.sub(r"-+", "-", value).strip("-")[:63]


def _aws_region_code(region):
    return {
        "South India": "ap-south-1",
        "US East (N. Virginia)": "us-east-1",
        "Europe (Ireland)": "eu-west-1",
    }.get(region, region or AWS_REGION)


def _has_deployment_history(cloud):
    connection = get_connection()
    try:
        return connection.execute(
            "SELECT 1 FROM deployments WHERE cloud = ? LIMIT 1", (cloud,)
        ).fetchone() is not None
    finally:
        connection.close()


def _workload_definition(workload):
    subscription_suffix = AZURE_SUBSCRIPTION_ID.replace("-", "")[:8]
    return {
        "sentiment-analysis": {
            "prefix": "sentiment",
            "azure_endpoint": AZURE_ML_ENDPOINT_NAME,
            "azure_deployment": AZURE_ML_DEPLOYMENT_NAME,
            "model_name": "Validated Sentiment Analysis Model",
            "model_version": AZURE_ML_MODEL_VERSION,
        },
        "named-entity-recognition": {
            "prefix": "ner",
            "azure_endpoint": f"ner-ai-{subscription_suffix}",
            "azure_deployment": "ner-v1",
            "model_name": "Validated NER Model",
            "model_version": "1",
        },
    }.get(str(workload).strip().lower())


def _dynamic_azure_deployments():
    """Build the active playground target from completed deployment lifecycle history."""
    if not AZURE_SUBSCRIPTION_ID:
        return []
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, action, environment, request_payload
            FROM deployments
            WHERE cloud = 'Azure'
              AND status = 'Completed'
              AND request_payload IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    deployments = []
    seen = set()
    for row in rows:
        try:
            payload = json.loads(row["request_payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        workload = str(payload.get("workload", "")).strip().lower()
        definition = _workload_definition(workload)
        if not definition:
            continue
        deployment_name = payload.get("deploymentName") or payload.get("deployment_name")
        environment = payload.get("environment") or row["environment"]
        if not deployment_name or not environment:
            continue
        identity = (_azure_slug(deployment_name), _azure_slug(environment))
        if identity in seen:
            continue
        seen.add(identity)
        # The newest completed lifecycle action is authoritative. A completed
        # destroy means this historical deployment must not remain selectable.
        if str(row["action"] or "apply").lower() != "apply":
            continue
        deployments.append({
            "id": f"azure:history:{row['id']}",
            "endpoint_name": definition["azure_endpoint"],
            "deployment_name": definition["azure_deployment"],
            "model_name": definition["model_name"],
            "model_version": definition["model_version"],
            "workload": workload,
            "cloud": "Azure",
            "environment": environment,
            "status": "Ready",
            "configured": True,
            "private": True,
            "subscription_id": AZURE_SUBSCRIPTION_ID,
            "resource_group": f"rg-{_azure_slug(deployment_name)}-ai-{_azure_slug(environment)}",
            "workspace_name": f"aml-{_azure_slug(environment)}",
            "dynamic_credentials": True,
        })
        # Azure deployments currently share one configured endpoint name, so
        # only the newest active deployment can be invoked by this playground.
        break
    return deployments


def _dynamic_aws_deployments():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT id, action, environment, region, request_payload
            FROM deployments
            WHERE cloud = 'AWS'
              AND status = 'Completed'
              AND request_payload IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        connection.close()
    seen = set()
    for row in rows:
        try:
            payload = json.loads(row["request_payload"])
        except (TypeError, json.JSONDecodeError):
            continue
        workload = str(payload.get("workload", "")).strip().lower()
        definition = _workload_definition(workload)
        deployment_name = payload.get("deploymentName") or payload.get("deployment_name")
        environment = payload.get("environment") or row["environment"]
        if not definition or not deployment_name or not environment:
            continue
        identity = (_azure_slug(deployment_name), _azure_slug(environment))
        if identity in seen:
            continue
        seen.add(identity)
        if str(row["action"] or "apply").lower() != "apply":
            continue
        return [{
            "id": f"aws:history:{row['id']}",
            "endpoint_name": _resource_name(definition["prefix"], deployment_name, environment),
            "deployment_name": "AllTraffic",
            "model_name": f"AWS SageMaker {definition['model_name']}",
            "model_version": definition["model_version"],
            "workload": workload,
            "cloud": "AWS",
            "environment": environment,
            "region": _aws_region_code(row["region"]),
            "status": "Ready" if _aws_is_configured() else "AWS credentials required",
            "configured": _aws_is_configured(),
            "private": False,
        }]
    return []


def list_playground_deployments():
    dynamic_azure = _dynamic_azure_deployments()
    dynamic_aws = _dynamic_aws_deployments()
    azure_configured = bool(AZURE_ML_SCORING_URI and AZURE_ML_ENDPOINT_KEY)
    aws_configured = _aws_is_configured()
    static_azure = [] if dynamic_azure or _has_deployment_history("Azure") else [{
            "id": f"azure:{AZURE_ML_ENDPOINT_NAME}",
            "endpoint_name": AZURE_ML_ENDPOINT_NAME,
            "deployment_name": AZURE_ML_DEPLOYMENT_NAME,
            "model_name": "Validated Sentiment Analysis Model",
            "model_version": AZURE_ML_MODEL_VERSION,
            "workload": "sentiment-analysis",
            "cloud": "Azure",
            "environment": "Development",
            "status": "Ready" if azure_configured else "Configuration required",
            "configured": azure_configured,
            "private": True,
        }]
    static_aws = [] if dynamic_aws or _has_deployment_history("AWS") else [{
            "id": f"aws:{AWS_SAGEMAKER_ENDPOINT_NAME}",
            "endpoint_name": AWS_SAGEMAKER_ENDPOINT_NAME,
            "deployment_name": "AllTraffic",
            "model_name": "AWS SageMaker Sentiment Model",
            "model_version": AWS_SAGEMAKER_MODEL_VERSION,
            "workload": "sentiment-analysis",
            "cloud": "AWS",
            "environment": "Development",
            "status": "Ready" if aws_configured else "AWS credentials required",
            "configured": aws_configured,
            "private": False,
        }]
    return dynamic_azure + static_azure + dynamic_aws + static_aws


def _get_azure_runtime(deployment):
    if not deployment.get("dynamic_credentials"):
        if not AZURE_ML_SCORING_URI or not AZURE_ML_ENDPOINT_KEY:
            raise RuntimeError("The Azure ML scoring URI and endpoint key are not configured.")
        return AZURE_ML_SCORING_URI, AZURE_ML_ENDPOINT_KEY

    cache_key = (
        deployment["subscription_id"], deployment["resource_group"],
        deployment["workspace_name"], deployment["endpoint_name"],
    )
    cached = _azure_runtime_cache.get(cache_key)
    if cached and cached["expires_at"] > time.monotonic():
        return cached["scoring_uri"], cached["endpoint_key"]

    # Lazy imports keep the application bootable while dependencies are being installed.
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential

    client = MLClient(
        DefaultAzureCredential(),
        deployment["subscription_id"],
        deployment["resource_group"],
        deployment["workspace_name"],
    )
    endpoint = client.online_endpoints.get(deployment["endpoint_name"])
    keys = client.online_endpoints.get_keys(deployment["endpoint_name"])
    scoring_uri = endpoint.scoring_uri
    endpoint_key = keys.primary_key
    if not scoring_uri or not endpoint_key:
        raise RuntimeError("Azure ML did not return a scoring URI and primary endpoint key.")
    _azure_runtime_cache[cache_key] = {
        "scoring_uri": scoring_uri,
        "endpoint_key": endpoint_key,
        "expires_at": time.monotonic() + AZURE_ML_CREDENTIAL_CACHE_SECONDS,
    }
    return scoring_uri, endpoint_key


def _record_run(record):
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO inference_runs (
                request_id, username, cloud, endpoint_name, deployment_name,
                workload, input_preview, prediction, confidence,
                latency_ms, status, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["request_id"], record["username"], record["cloud"],
                record["endpoint_name"], record["deployment_name"],
                record["workload"], record["input_preview"],
                record.get("prediction"), record.get("confidence"),
                record["latency_ms"], record["status"],
                record.get("error_message"),
            ),
        )
        connection.commit()
    finally:
        connection.close()


def get_recent_inference_runs(limit=20):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT request_id, cloud, endpoint_name, deployment_name, workload,
                   input_preview, prediction, confidence, latency_ms,
                   status, error_message, created_at
            FROM inference_runs ORDER BY id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _normalized_response(base_record, model_version, prediction, confidence, latency_ms):
    _record_run({
        **base_record,
        "prediction": str(prediction),
        "confidence": float(confidence),
        "latency_ms": latency_ms,
        "status": "Succeeded",
    })
    return {
        "request_id": base_record["request_id"],
        "cloud": base_record["cloud"],
        "workload": base_record["workload"],
        "endpoint_name": base_record["endpoint_name"],
        "deployment_name": base_record["deployment_name"],
        "model_version": model_version,
        "prediction": {"label": str(prediction), "confidence": float(confidence)},
        "metrics": {"latency_ms": latency_ms},
    }


def _normalized_ner_response(base_record, model_version, entities, latency_ms):
    normalized = [{
        "text": str(item.get("text") or item.get("word") or ""),
        "label": str(item.get("label") or item.get("entity_group") or "ENTITY"),
        "confidence": float(item.get("confidence", item.get("score", 0))),
        "start": int(item.get("start", 0)),
        "end": int(item.get("end", 0)),
    } for item in entities]
    confidence = max((item["confidence"] for item in normalized), default=0.0)
    _record_run({
        **base_record,
        "prediction": f"{len(normalized)} entities",
        "confidence": confidence,
        "latency_ms": latency_ms,
        "status": "Succeeded",
    })
    return {
        "request_id": base_record["request_id"],
        "cloud": base_record["cloud"],
        "workload": base_record["workload"],
        "endpoint_name": base_record["endpoint_name"],
        "deployment_name": base_record["deployment_name"],
        "model_version": model_version,
        "prediction": {"entities": normalized, "entity_count": len(normalized)},
        "metrics": {"latency_ms": latency_ms},
    }


def _base_record(deployment, text, username):
    return {
        "request_id": str(uuid.uuid4()),
        "username": username,
        "cloud": deployment["cloud"],
        "endpoint_name": deployment["endpoint_name"],
        "deployment_name": deployment["deployment_name"],
        "workload": deployment["workload"],
        "input_preview": text[:160],
    }


def _record_failure(base_record, started, error):
    _record_run({
        **base_record,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "status": "Failed",
        "error_message": str(error)[:500],
    })


def _invoke_azure(deployment, text, username):
    started = time.perf_counter()
    base_record = _base_record(deployment, text, username)
    try:
        scoring_uri, endpoint_key = _get_azure_runtime(deployment)
        response = requests.post(
            scoring_uri,
            headers={"Authorization": f"Bearer {endpoint_key}", "Content-Type": "application/json"},
            json={"text": text},
            timeout=AZURE_ML_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        if isinstance(result, str):
            result = json.loads(result)
        latency_ms = round((time.perf_counter() - started) * 1000)
        if deployment["workload"] == "named-entity-recognition":
            entities = result.get("entities") if isinstance(result, dict) else None
            if not isinstance(entities, list):
                raise ValueError("The Azure NER response is missing its entities list.")
            return _normalized_ner_response(
                base_record, deployment["model_version"], entities, latency_ms
            )
        prediction, confidence = result.get("label"), result.get("score")
        if prediction is None or confidence is None:
            raise ValueError("The Azure model response is missing label or score.")
        return _normalized_response(base_record, deployment["model_version"], prediction, confidence, latency_ms)
    except Exception as error:
        _record_failure(base_record, started, error)
        raise RuntimeError("Azure ML inference failed. Check endpoint health and backend credentials.") from error


def _decode_aws_result(result):
    candidate = result
    for _ in range(4):
        if isinstance(candidate, str):
            candidate = json.loads(candidate)
            continue
        if (
            isinstance(candidate, list) and len(candidate) == 2
            and isinstance(candidate[0], str)
            and candidate[1] == "application/json"
        ):
            candidate = candidate[0]
            continue
        break
    return candidate


def _extract_aws_prediction(result):
    candidate = _decode_aws_result(result)
    if isinstance(candidate, list) and candidate:
        candidate = candidate[0]
    if not isinstance(candidate, dict):
        raise ValueError("The SageMaker sentiment model returned an unsupported response format.")
    prediction, confidence = candidate.get("label"), candidate.get("score")
    if prediction is None or confidence is None:
        raise ValueError("The SageMaker response is missing label or score.")
    return prediction, confidence


def _invoke_aws(deployment, text, username):
    started = time.perf_counter()
    base_record = _base_record(deployment, text, username)
    try:
        client = _aws_session(deployment.get("region")).client(
            "sagemaker-runtime",
            config=Config(connect_timeout=10, read_timeout=AWS_SAGEMAKER_REQUEST_TIMEOUT, retries={"max_attempts": 2}),
        )
        response = client.invoke_endpoint(
            EndpointName=deployment["endpoint_name"],
            ContentType="application/json",
            Body=json.dumps({"inputs": text}).encode("utf-8"),
        )
        result = json.loads(response["Body"].read().decode("utf-8"))
        latency_ms = round((time.perf_counter() - started) * 1000)
        if deployment["workload"] == "named-entity-recognition":
            entities = _decode_aws_result(result)
            if not isinstance(entities, list):
                raise ValueError("The SageMaker NER response is missing its entities list.")
            return _normalized_ner_response(
                base_record, deployment["model_version"], entities, latency_ms
            )
        prediction, confidence = _extract_aws_prediction(result)
        return _normalized_response(base_record, deployment["model_version"], prediction, confidence, latency_ms)
    except (BotoCoreError, ClientError, ValueError, json.JSONDecodeError) as error:
        _record_failure(base_record, started, error)
        raise RuntimeError("AWS SageMaker inference failed. Check endpoint health, region, and backend IAM credentials.") from error


def invoke_model_endpoint(deployment, text, username):
    if deployment["cloud"] == "Azure":
        return _invoke_azure(deployment, text, username)
    if deployment["cloud"] == "AWS":
        return _invoke_aws(deployment, text, username)
    raise RuntimeError(f"Unsupported inference cloud: {deployment['cloud']}")


# Backward-compatible alias for existing callers.
invoke_sentiment_endpoint = invoke_model_endpoint
