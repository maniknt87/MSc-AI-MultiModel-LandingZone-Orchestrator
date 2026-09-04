from datetime import datetime, timezone
import json

from database.database import get_connection
from services.azure_devops import get_pipeline_run


ACTIVE_STATUSES = {"Queued", "Running", "Cancelling"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _serialize(row):
    if row is None:
        return None
    record = dict(row)
    record["deployment_id"] = f"DEP-{record.pop('id'):05d}"
    record["pipeline_id"] = record["pipeline_run_id"]
    payload = record.pop("request_payload", None)
    record["request"] = json.loads(payload) if payload else None
    record["can_destroy"] = bool(
        record.get("action", "apply") == "apply"
        and record["status"] == "Completed"
        and record["request"]
    )
    record["can_retry"] = bool(
        record.get("action", "apply") == "apply"
        and record["status"] == "Failed"
        and record["request"]
    )
    if record.get("retry_of_deployment_id"):
        record["retry_of"] = f"DEP-{record['retry_of_deployment_id']:05d}"
    if record.get("parent_deployment_id"):
        record["destroy_of"] = f"DEP-{record['parent_deployment_id']:05d}"
    return record


def _numeric_id(deployment_id):
    try:
        prefix, value = deployment_id.split("-", 1)
        if prefix != "DEP":
            raise ValueError
        return int(value)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("Invalid deployment ID") from error


def save_deployment(
    deployment,
    pipeline,
    action="apply",
    parent_deployment_id=None,
    retry_of_deployment_id=None,
):
    now = _now()
    connection = get_connection()
    cursor = connection.execute(
        """
        INSERT INTO deployments (
            cloud, workload, environment, region, status, pipeline_name,
            pipeline_definition_id, pipeline_run_id, pipeline_url, provider,
            result, sync_error, created_time, updated_time, finished_time,
            action, request_payload, parent_deployment_id, retry_of_deployment_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            deployment.cloud,
            deployment.workload,
            deployment.environment,
            deployment.region,
            pipeline["status"],
            pipeline["pipeline_name"],
            pipeline.get("pipeline_definition_id"),
            pipeline["pipeline_id"],
            pipeline.get("pipeline_url", ""),
            pipeline["provider"],
            pipeline.get("result"),
            now,
            now,
            action,
            json.dumps(deployment.model_dump()),
            parent_deployment_id,
            retry_of_deployment_id,
        ),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM deployments WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    connection.close()
    return _serialize(row)


def _sync_active_deployments(connection):
    rows = connection.execute(
        """
        SELECT * FROM deployments
        -- A failed Azure DevOps job can be rerun within the same pipeline run.
        -- Recheck failed application records so a successful DevOps rerun can
        -- promote the local lifecycle record to Completed.
        WHERE status IN ('Queued', 'Running', 'Cancelling', 'Failed')
        ORDER BY id DESC
        """
    ).fetchall()
    for row in rows:
        try:
            run = get_pipeline_run(
                cloud=row["cloud"],
                run_id=row["pipeline_run_id"],
                pipeline_definition_id=row["pipeline_definition_id"],
            )
            connection.execute(
                """
                UPDATE deployments
                SET status = ?, result = ?, pipeline_url = ?, sync_error = NULL,
                    updated_time = ?, finished_time = COALESCE(?, finished_time)
                WHERE id = ?
                """,
                (
                    run["status"],
                    run.get("result"),
                    run.get("pipeline_url") or row["pipeline_url"],
                    _now(),
                    run.get("finished_time"),
                    row["id"],
                ),
            )
            if (
                row["action"] == "destroy"
                and row["parent_deployment_id"]
                and run["status"] == "Completed"
            ):
                connection.execute(
                    "UPDATE deployments SET status = 'Destroyed', updated_time = ? WHERE id = ?",
                    (_now(), row["parent_deployment_id"]),
                )
        except Exception as error:
            connection.execute(
                "UPDATE deployments SET sync_error = ?, updated_time = ? WHERE id = ?",
                (str(error)[:500], _now(), row["id"]),
            )
    connection.commit()


def get_deployment_history(sync=True):
    connection = get_connection()
    if sync:
        _sync_active_deployments(connection)
    rows = connection.execute(
        "SELECT * FROM deployments ORDER BY id DESC"
    ).fetchall()
    connection.close()
    return [_serialize(row) for row in rows]


def update_deployment_status(deployment_id, new_status):
    numeric_id = _numeric_id(deployment_id)
    connection = get_connection()
    connection.execute(
        "UPDATE deployments SET status = ?, updated_time = ? WHERE id = ?",
        (new_status, _now(), numeric_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM deployments WHERE id = ?", (numeric_id,)
    ).fetchone()
    connection.close()
    return _serialize(row)


def get_deployment(deployment_id, sync=True):
    numeric_id = _numeric_id(deployment_id)
    connection = get_connection()
    row = connection.execute(
        "SELECT * FROM deployments WHERE id = ?", (numeric_id,)
    ).fetchone()
    if row and sync and row["status"] in ACTIVE_STATUSES:
        _sync_active_deployments(connection)
        row = connection.execute(
            "SELECT * FROM deployments WHERE id = ?", (numeric_id,)
        ).fetchone()
    connection.close()
    return _serialize(row)


def get_destroy_source(deployment_id):
    numeric_id = _numeric_id(deployment_id)
    connection = get_connection()
    row = connection.execute("SELECT * FROM deployments WHERE id = ?", (numeric_id,)).fetchone()
    if row is None:
        connection.close()
        return None, None
    active_destroy = connection.execute(
        """
        SELECT id FROM deployments
        WHERE parent_deployment_id = ? AND action = 'destroy'
          AND status IN ('Queued', 'Running', 'Cancelling')
        LIMIT 1
        """,
        (numeric_id,),
    ).fetchone()
    connection.close()
    return _serialize(row), bool(active_destroy)


def get_retry_source(deployment_id):
    numeric_id = _numeric_id(deployment_id)
    connection = get_connection()
    row = connection.execute("SELECT * FROM deployments WHERE id = ?", (numeric_id,)).fetchone()
    if row is None:
        connection.close()
        return None, None
    active_retry = connection.execute(
        """
        SELECT id FROM deployments
        WHERE retry_of_deployment_id = ?
          AND status IN ('Queued', 'Running', 'Cancelling')
        LIMIT 1
        """,
        (numeric_id,),
    ).fetchone()
    connection.close()
    return _serialize(row), bool(active_retry)
