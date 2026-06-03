import base64
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from shared_utils import (
    build_response,
    get_content_bucket_name,
    get_logger,
    get_s3_client,
    get_table,
)

logger = get_logger()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_AUTHOR_NAME_LENGTH = 80
MAX_CONTENT_LENGTH = 2000


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


def _path_parameters(event):
    return event.get("pathParameters") or {}


def _blog_id(event):
    return _path_parameters(event).get("id")


def _comment_id(event):
    return _path_parameters(event).get("commentId")


def _public_author_name(data):
    name = str(data.get("author_name") or data.get("name") or "").strip()
    if name:
        return name[:MAX_AUTHOR_NAME_LENGTH]
    email = str(data.get("email") or "").strip()
    return email.split("@", 1)[0][:MAX_AUTHOR_NAME_LENGTH] or "Anonymous"


def _email_hash(email):
    normalized = email.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _validate_payload(data):
    if not data:
        return "Invalid request: missing body"

    email = str(data.get("email") or "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        return "Invalid or missing email"

    content = str(data.get("content") or "").strip()
    if not content:
        return "Missing required field: 'content'"
    if len(content) > MAX_CONTENT_LENGTH:
        return f"Comment content must be {MAX_CONTENT_LENGTH} characters or less"

    return None


def _metadata_pk(blog_id):
    return f"BLOG#{blog_id}"


def _comment_sk(created_at, comment_id):
    return f"COMMENT#{created_at}#{comment_id}"


def _reply_sk(parent_comment_id, created_at, reply_id):
    return f"REPLY#{parent_comment_id}#{created_at}#{reply_id}"


def _put_content(s3_key, payload):
    get_s3_client().put_object(
        Bucket=get_content_bucket_name(),
        Key=s3_key,
        Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json; charset=utf-8",
        ServerSideEncryption="AES256",
    )


def _get_content(s3_key):
    result = get_s3_client().get_object(
        Bucket=get_content_bucket_name(),
        Key=s3_key,
    )
    return json.loads(result["Body"].read().decode("utf-8"))


def _public_comment(metadata, content_payload):
    return {
        "comment_id": metadata["comment_id"],
        "parent_comment_id": metadata.get("parent_comment_id"),
        "type": metadata["type"],
        "author_name": metadata.get("author_name", "Anonymous"),
        "content": content_payload.get("content", ""),
        "created_at": metadata["created_at"],
        "reply_count": int(metadata.get("reply_count", 0)),
        "replies": [],
    }


def _list_comments(event):
    blog_id = _blog_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    result = get_table().query(
        KeyConditionExpression=Key("pk").eq(_metadata_pk(blog_id))
    )

    items_by_id = {}
    root_comments = []

    for item in result.get("Items", []):
        if item.get("status") != "approved":
            continue

        try:
            content_payload = _get_content(item["s3_key"])
        except Exception:
            logger.exception("Failed to load comment content from S3: %s", item.get("s3_key"))
            continue

        public_item = _public_comment(item, content_payload)
        items_by_id[item["comment_id"]] = public_item

    for item in sorted(items_by_id.values(), key=lambda entry: entry["created_at"]):
        if item.get("type") == "comment":
            root_comments.append(item)
            continue

        parent = items_by_id.get(item.get("parent_comment_id"))
        if parent:
            parent["replies"].append(item)

    return build_response(200, {"items": root_comments, "count": len(root_comments)})


def _create_comment(event):
    blog_id = _blog_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    validation_error = _validate_payload(data)
    if validation_error:
        return build_response(400, {"message": validation_error})

    created_at = _now()
    comment_id = f"cmt_{uuid.uuid4().hex}"
    email = data["email"].strip().lower()
    author_name = _public_author_name(data)
    s3_key = f"blogs/{blog_id}/comments/{comment_id}.json"

    content_payload = {
        "blog_id": blog_id,
        "comment_id": comment_id,
        "parent_comment_id": None,
        "author_email": email,
        "author_name": author_name,
        "content": data["content"].strip(),
        "created_at": created_at,
    }
    _put_content(s3_key, content_payload)

    metadata = {
        "pk": _metadata_pk(blog_id),
        "sk": _comment_sk(created_at, comment_id),
        "comment_id": comment_id,
        "parent_comment_id": None,
        "type": "comment",
        "blog_id": blog_id,
        "author_email_hash": _email_hash(email),
        "author_name": author_name,
        "s3_key": s3_key,
        "status": "approved",
        "created_at": created_at,
        "reply_count": 0,
    }
    get_table().put_item(Item=metadata)

    return build_response(
        201,
        {
            "message": "Comment created successfully",
            "comment": _public_comment(metadata, content_payload),
        },
    )


def _find_parent_item(blog_id, parent_comment_id):
    result = get_table().query(
        KeyConditionExpression=Key("pk").eq(_metadata_pk(blog_id))
    )
    for item in result.get("Items", []):
        if item.get("comment_id") == parent_comment_id and item.get("status") == "approved":
            return item
    return None


def _create_reply(event):
    blog_id = _blog_id(event)
    parent_comment_id = _comment_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
    if not parent_comment_id:
        return build_response(400, {"message": "Missing required 'commentId' path parameter"})

    parent = _find_parent_item(blog_id, parent_comment_id)
    if not parent:
        return build_response(404, {"message": "Parent comment not found"})

    data = _body(event)
    validation_error = _validate_payload(data)
    if validation_error:
        return build_response(400, {"message": validation_error})

    created_at = _now()
    reply_id = f"rep_{uuid.uuid4().hex}"
    email = data["email"].strip().lower()
    author_name = _public_author_name(data)
    s3_key = f"blogs/{blog_id}/comments/{parent_comment_id}/replies/{reply_id}.json"

    content_payload = {
        "blog_id": blog_id,
        "comment_id": reply_id,
        "parent_comment_id": parent_comment_id,
        "author_email": email,
        "author_name": author_name,
        "content": data["content"].strip(),
        "created_at": created_at,
    }
    _put_content(s3_key, content_payload)

    metadata = {
        "pk": _metadata_pk(blog_id),
        "sk": _reply_sk(parent_comment_id, created_at, reply_id),
        "comment_id": reply_id,
        "parent_comment_id": parent_comment_id,
        "type": "reply",
        "blog_id": blog_id,
        "author_email_hash": _email_hash(email),
        "author_name": author_name,
        "s3_key": s3_key,
        "status": "approved",
        "created_at": created_at,
        "reply_count": 0,
    }
    table = get_table()
    table.put_item(Item=metadata)
    table.update_item(
        Key={"pk": parent["pk"], "sk": parent["sk"]},
        UpdateExpression="ADD reply_count :inc",
        ExpressionAttributeValues={":inc": 1},
    )

    return build_response(
        201,
        {
            "message": "Reply created successfully",
            "reply": _public_comment(metadata, content_payload),
        },
    )


def lambda_handler(event, context):
    logger.info("Received comments event: %s", json.dumps(event))

    try:
        method = _method(event)
        parent_comment_id = _comment_id(event)

        if method == "OPTIONS":
            return build_response(200, {"message": "ok"})
        if method == "GET" and not parent_comment_id:
            return _list_comments(event)
        if method == "POST" and parent_comment_id:
            return _create_reply(event)
        if method == "POST":
            return _create_comment(event)

        return build_response(405, {"message": f"Method not allowed: {method}"})
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON payload in body"})
    except Exception as exc:
        logger.exception("Comments handler failed")
        return build_response(500, {"message": "Internal server error", "error": str(exc)})
