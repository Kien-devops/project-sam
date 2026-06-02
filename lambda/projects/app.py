import base64
import json
import uuid
from datetime import datetime, timezone

from shared_utils import build_response, get_logger, get_table

logger = get_logger()

ALLOWED_FIELDS = {
    "name",
    "slug",
    "summary",
    "description",
    "imageUrl",
    "techStack",
    "githubUrl",
    "demoUrl",
    "status",
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _method(event):
    return (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", ""))
        .upper()
    )


def _body(event):
    body = event.get("body")
    if not body:
        return None
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)


def _item_id(event):
    return (event.get("pathParameters") or {}).get("id")


def _list_projects():
    result = get_table().scan()
    items = result.get("Items", [])
    return build_response(200, {"items": items, "count": len(items)})


def _get_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    result = get_table().get_item(Key={"id": project_id})
    item = result.get("Item")
    if not item:
        return build_response(404, {"message": "Project not found", "id": project_id})
    return build_response(200, {"project": item})


def _create_project(event):
    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})
    if not data.get("name"):
        return build_response(400, {"message": "Missing required field: 'name'"})

    timestamp = _now()
    item = {
        "id": data.get("id") or str(uuid.uuid4()),
        "name": data["name"],
        "slug": data.get("slug", ""),
        "summary": data.get("summary", ""),
        "description": data.get("description", ""),
        "imageUrl": data.get("imageUrl", ""),
        "techStack": data.get("techStack", []),
        "githubUrl": data.get("githubUrl", ""),
        "demoUrl": data.get("demoUrl", ""),
        "status": data.get("status", "draft"),
        "createdAt": data.get("createdAt", timestamp),
        "updatedAt": timestamp,
    }

    get_table().put_item(Item=item)
    return build_response(201, {"message": "Project created successfully", "project": item})


def _update_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})

    updates = {key: value for key, value in data.items() if key in ALLOWED_FIELDS}
    updates["updatedAt"] = _now()

    expression_names = {f"#{key}": key for key in updates}
    expression_values = {f":{key}": value for key, value in updates.items()}
    update_expression = "SET " + ", ".join(
        f"#{key} = :{key}" for key in updates
    )

    result = get_table().update_item(
        Key={"id": project_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW",
    )
    return build_response(200, {"message": "Project updated successfully", "project": result["Attributes"]})


def _delete_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    get_table().delete_item(Key={"id": project_id})
    return build_response(200, {"message": "Project deleted successfully", "id": project_id})


def lambda_handler(event, context):
    logger.info("Received projects event: %s", json.dumps(event))

    try:
        method = _method(event)
        project_id = _item_id(event)

        if method == "GET" and project_id:
            return _get_project(event)
        if method == "GET":
            return _list_projects()
        if method == "POST":
            return _create_project(event)
        if method == "PUT":
            return _update_project(event)
        if method == "DELETE":
            return _delete_project(event)

        return build_response(405, {"message": f"Method not allowed: {method}"})
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON payload in body"})
    except Exception as exc:
        logger.exception("Projects handler failed")
        return build_response(500, {"message": "Internal server error", "error": str(exc)})
