import base64
import json
from datetime import datetime, timezone
from shared_utils import build_response, get_logger, get_db_connection

logger = get_logger()

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

def _map_blog(row):
    if not row:
        return None
    tags = []
    if row.get('tags'):
        try:
            tags = json.loads(row['tags'])
        except Exception:
            pass
    return {
        "id": str(row['id']),
        "title": row.get('title') or "",
        "slug": row.get('slug') or "",
        "summary": row.get('summary') or "",
        "content": row.get('content') or "",
        "image_url": row.get('image_url') or "",
        "imageUrl": row.get('image_url') or "",
        "coverImage": row.get('image_url') or "",
        "tags": tags,
        "status": row.get('status') or "draft",
        "createdAt": row.get('created_at').isoformat() if row.get('created_at') else None,
        "updatedAt": row.get('updated_at').isoformat() if row.get('updated_at') else None,
    }

def _list_blogs():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[blogs] ORDER BY id")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    items = [_map_blog(r) for r in rows]
    return build_response(200, {"items": items, "count": len(items)})

def _get_blog(event):
    blog_id = _item_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
    
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[blogs] WHERE id = %s", (blog_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        return build_response(404, {"message": "Blog not found", "id": blog_id})
    return build_response(200, {"blog": _map_blog(row)})

def _create_blog(event):
    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})
    if not data.get("title"):
        return build_response(400, {"message": "Missing required field: 'title'"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    timestamp = datetime.now(timezone.utc)
    tags_json = json.dumps(data.get("tags", []))
    image_url = data.get("imageUrl") or data.get("coverImage") or ""
    
    blog_id = data.get("id")
    is_numeric_id = False
    if blog_id:
        try:
            blog_id = int(blog_id)
            is_numeric_id = True
        except ValueError:
            pass
            
    if is_numeric_id:
        cursor.execute("SET IDENTITY_INSERT [dbo].[blogs] ON")
        cursor.execute(
            """
            INSERT INTO [dbo].[blogs] (id, title, slug, summary, content, image_url, tags, status, created_at, updated_at)
            VALUES (%d, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                blog_id,
                data["title"],
                data.get("slug") or "",
                data.get("summary") or "",
                data.get("content") or "",
                image_url,
                tags_json,
                data.get("status") or "draft",
                timestamp,
                timestamp
            )
        )
        cursor.execute("SET IDENTITY_INSERT [dbo].[blogs] OFF")
        inserted_id = blog_id
    else:
        cursor.execute(
            """
            INSERT INTO [dbo].[blogs] (title, slug, summary, content, image_url, tags, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data["title"],
                data.get("slug") or "",
                data.get("summary") or "",
                data.get("content") or "",
                image_url,
                tags_json,
                data.get("status") or "draft",
                timestamp,
                timestamp
            )
        )
        cursor.execute("SELECT @@IDENTITY")
        inserted_id = int(cursor.fetchone()[0])
        
    conn.commit()
    
    # Fetch newly created blog
    cursor.execute("SELECT * FROM [dbo].[blogs] WHERE id = %d", (inserted_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(201, {"message": "Blog created successfully", "blog": _map_blog(row)})

def _update_blog(event):
    blog_id = _item_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    cursor.execute("SELECT 1 FROM [dbo].[blogs] WHERE id = %s", (blog_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return build_response(404, {"message": "Blog not found", "id": blog_id})

    timestamp = datetime.now(timezone.utc)
    updates = []
    params = []
    
    if "title" in data:
        updates.append("title = %s")
        params.append(data["title"])
    if "slug" in data:
        updates.append("slug = %s")
        params.append(data["slug"])
    if "summary" in data:
        updates.append("summary = %s")
        params.append(data["summary"])
    if "content" in data:
        updates.append("content = %s")
        params.append(data["content"])
    if "coverImage" in data or "imageUrl" in data:
        updates.append("image_url = %s")
        params.append(data.get("coverImage") or data.get("imageUrl") or "")
    if "tags" in data:
        updates.append("tags = %s")
        params.append(json.dumps(data["tags"]))
    if "status" in data:
        updates.append("status = %s")
        params.append(data["status"])
        
    updates.append("updated_at = %s")
    params.append(timestamp)
    
    query = f"UPDATE [dbo].[blogs] SET {', '.join(updates)} WHERE id = %s"
    params.append(blog_id)
    
    cursor.execute(query, tuple(params))
    conn.commit()
    
    # Fetch updated blog
    cursor.execute("SELECT * FROM [dbo].[blogs] WHERE id = %s", (blog_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(200, {"message": "Blog updated successfully", "blog": _map_blog(row)})

def _delete_blog(event):
    blog_id = _item_id(event)
    if not blog_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [dbo].[blogs] WHERE id = %s", (blog_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    return build_response(200, {"message": "Blog deleted successfully", "id": blog_id})

def lambda_handler(event, context):
    logger.info("Received blogs event: %s", json.dumps(event))

    try:
        method = _method(event)
        blog_id = _item_id(event)

        if method == "GET" and blog_id:
            return _get_blog(event)
        if method == "GET":
            return _list_blogs()
        if method == "POST":
            return _create_blog(event)
        if method == "PUT":
            return _update_blog(event)
        if method == "DELETE":
            return _delete_blog(event)

        return build_response(405, {"message": f"Method not allowed: {method}"})
    except json.JSONDecodeError:
        return build_response(400, {"message": "Invalid JSON payload in body"})
    except Exception as exc:
        logger.exception("Blogs handler failed")
        return build_response(500, {"message": "Internal server error", "error": str(exc)})
