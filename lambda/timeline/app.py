import base64
import json
import uuid
from datetime import datetime, timezone

from shared_utils import build_response, get_logger, get_table

logger = get_logger()

ALLOWED_FIELDS = {
    "type",
    "role",
    "company",
    "duration",
    "location",
    "description",
    "title",
    "issuer",
    "badge_url",
    "icon",
    "order",
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


def _list_timeline():
    result = get_table().scan()
    items = result.get("Items", [])
    # Sort items by order attribute (default to 0 if not present)
    items.sort(key=lambda x: int(x.get("order", 0)))
    return build_response(200, {"items": items, "count": len(items)})


def _get_timeline(event):
    item_id = _item_id(event)
    if not item_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    result = get_table().get_item(Key={"id": item_id})
    item = result.get("Item")
    if not item:
        return build_response(404, {"message": "Timeline item not found", "id": item_id})
    return build_response(200, {"item": item})


def _create_timeline(event):
    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})
    if not data.get("type"):
        return build_response(400, {"message": "Missing required field: 'type'"})

    timestamp = _now()
    item = {
        "id": data.get("id") or str(uuid.uuid4()),
        "type": data["type"],
        "role": data.get("role", ""),
        "company": data.get("company", ""),
        "duration": data.get("duration", ""),
        "location": data.get("location", ""),
        "description": data.get("description", ""),
        "title": data.get("title", ""),
        "issuer": data.get("issuer", ""),
        "badge_url": data.get("badge_url", ""),
        "icon": data.get("icon", ""),
        "order": int(data.get("order", 0)),
        "createdAt": data.get("createdAt", timestamp),
        "updatedAt": timestamp,
    }

    get_table().put_item(Item=item)
    return build_response(201, {"message": "Timeline item created successfully", "item": item})


def _update_timeline(event):
    item_id = _item_id(event)
    if not item_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})

    updates = {key: value for key, value in data.items() if key in ALLOWED_FIELDS}
    if "order" in updates:
        updates["order"] = int(updates["order"])
    updates["updatedAt"] = _now()

    expression_names = {f"#{key}": key for key in updates}
    expression_values = {f":{key}": value for key, value in updates.items()}
    update_expression = "SET " + ", ".join(
        f"#{key} = :{key}" for key in updates
    )

    result = get_table().update_item(
        Key={"id": item_id},
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_names,
        ExpressionAttributeValues=expression_values,
        ReturnValues="ALL_NEW",
    )
    return build_response(200, {"message": "Timeline item updated successfully", "item": result["Attributes"]})


def _delete_timeline(event):
    item_id = _item_id(event)
    if not item_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    get_table().delete_item(Key={"id": item_id})
    return build_response(200, {"message": "Timeline item deleted successfully", "id": item_id})


def lambda_handler(event, context):
    logger.info("Received timeline event: %s", json.dumps(event))

    try:
        method = _method(event)
        item_id = _item_id(event)

        if method == "GET" and item_id:
            return _get_timeline(event)
        if method == "GET":
            return _list_timeline()
        if method == "POST":
            return _create_timeline(event)
        if method == "PUT":
            return _update_timeline(event)
        if method == "DELETE":
            return _delete_timeline(event)

        return build_response(405, {"message": f"Method not allowed: {method}"})
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON payload in body"})
    except Exception as exc:
        logger.exception("Timeline handler failed")
        return build_response(500, {"message": "Internal server error", "error": str(exc)})
