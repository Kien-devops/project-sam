import base64
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from shared_utils import build_response, get_logger, get_db_connection

logger = get_logger()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_AUTHOR_NAME_LENGTH = 80
MAX_CONTENT_LENGTH = 2000

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

def _email_display(email):
    normalized = str(email or "").strip().lower()
    if "@" not in normalized:
        return ""

    local_part, domain = normalized.split("@", 1)
    if len(local_part) <= 2:
        masked_local = local_part[:1] + "*"
    else:
        masked_local = f"{local_part[:2]}***"
    return f"{masked_local}@{domain}"

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

def _public_comment(row):
    if not row:
        return None
    return {
        "comment_id": row["comment_id"],
        "parent_comment_id": row.get("parent_comment_id"),
        "type": row["type"],
        "author_name": row.get("author_name") or "Anonymous",
        "author_email": _email_display(row.get("author_email")),
        "content": row.get("content") or "",
        "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else row["created_at"],
        "reply_count": int(row.get("reply_count") or 0),
        "replies": [],
    }

def _list_comments(event):
    blog_id_str = _blog_id(event)
    if not blog_id_str:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
        
    try:
        blog_id = int(blog_id_str)
    except ValueError:
        return build_response(200, {"items": [], "count": 0})
        
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute(
        "SELECT * FROM [dbo].[comments] WHERE blog_id = %d AND status = 'approved' ORDER BY created_at ASC",
        (blog_id,)
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    items_by_id = {}
    root_comments = []
    
    for row in rows:
        public_item = _public_comment(row)
        items_by_id[row["comment_id"]] = public_item
        
    for item in items_by_id.values():
        if item.get("type") == "comment":
            root_comments.append(item)
        else:
            parent = items_by_id.get(item.get("parent_comment_id"))
            if parent:
                parent["replies"].append(item)
                
    return build_response(200, {"items": root_comments, "count": len(root_comments)})

def _create_comment(event):
    blog_id_str = _blog_id(event)
    if not blog_id_str:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
        
    try:
        blog_id = int(blog_id_str)
    except ValueError:
        return build_response(400, {"message": "Invalid 'id' path parameter: must be an integer"})
        
    data = _body(event)
    validation_error = _validate_payload(data)
    if validation_error:
        return build_response(400, {"message": validation_error})
        
    created_at = datetime.now(timezone.utc)
    comment_id = f"cmt_{uuid.uuid4().hex}"
    email = data["email"].strip().lower()
    author_name = _public_author_name(data)
    content = data["content"].strip()
    email_hash = _email_hash(email)
    
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute(
        """
        INSERT INTO [dbo].[comments] (comment_id, blog_id, parent_comment_id, [type], author_name, author_email, author_email_hash, content, created_at, reply_count, status)
        VALUES (%s, %d, NULL, 'comment', %s, %s, %s, %s, %s, 0, 'approved')
        """,
        (
            comment_id,
            blog_id,
            author_name,
            email,
            email_hash,
            content,
            created_at
        )
    )
    conn.commit()
    
    cursor.execute("SELECT * FROM [dbo].[comments] WHERE comment_id = %s", (comment_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(
        201,
        {
            "message": "Comment created successfully",
            "comment": _public_comment(row)
        }
    )

def _create_reply(event):
    blog_id_str = _blog_id(event)
    parent_comment_id = _comment_id(event)
    if not blog_id_str:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
    if not parent_comment_id:
        return build_response(400, {"message": "Missing required 'commentId' path parameter"})
        
    try:
        blog_id = int(blog_id_str)
    except ValueError:
        return build_response(400, {"message": "Invalid 'id' path parameter: must be an integer"})
        
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    cursor.execute(
        "SELECT * FROM [dbo].[comments] WHERE comment_id = %s AND blog_id = %d AND status = 'approved'",
        (parent_comment_id, blog_id)
    )
    parent = cursor.fetchone()
    if not parent:
        cursor.close()
        conn.close()
        return build_response(404, {"message": "Parent comment not found"})
        
    data = _body(event)
    validation_error = _validate_payload(data)
    if validation_error:
        cursor.close()
        conn.close()
        return build_response(400, {"message": validation_error})
        
    created_at = datetime.now(timezone.utc)
    reply_id = f"rep_{uuid.uuid4().hex}"
    email = data["email"].strip().lower()
    author_name = _public_author_name(data)
    content = data["content"].strip()
    email_hash = _email_hash(email)
    
    cursor.execute(
        """
        INSERT INTO [dbo].[comments] (comment_id, blog_id, parent_comment_id, [type], author_name, author_email, author_email_hash, content, created_at, reply_count, status)
        VALUES (%s, %d, %s, 'reply', %s, %s, %s, %s, %s, 0, 'approved')
        """,
        (
            reply_id,
            blog_id,
            parent_comment_id,
            author_name,
            email,
            email_hash,
            content,
            created_at
        )
    )
    
    cursor.execute(
        "UPDATE [dbo].[comments] SET reply_count = reply_count + 1 WHERE comment_id = %s",
        (parent_comment_id,)
    )
    
    conn.commit()
    
    cursor.execute("SELECT * FROM [dbo].[comments] WHERE comment_id = %s", (reply_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(
        201,
        {
            "message": "Reply created successfully",
            "reply": _public_comment(row)
        }
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
