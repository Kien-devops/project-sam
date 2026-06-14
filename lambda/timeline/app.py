import base64
import json
import uuid
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

def _map_timeline(row):
    if not row:
        return None
    return {
        "id": str(row['id']),
        "type": row.get('type') or "experience",
        "role": row.get('role') or "",
        "company": row.get('company') or "",
        "duration": row.get('duration') or "",
        "location": row.get('location') or "",
        "description": row.get('description') or "",
        "title": row.get('title') or "",
        "issuer": row.get('issuer') or "",
        "badge_url": row.get('badge_url') or "",
        "icon": row.get('icon') or "",
        "order": int(row.get('order') or 0),
        "createdAt": row.get('created_at').isoformat() if row.get('created_at') else None,
        "updatedAt": row.get('updated_at').isoformat() if row.get('updated_at') else None,
    }

def _list_timeline():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[timeline] ORDER BY [order] ASC, [id] ASC")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    items = [_map_timeline(r) for r in rows]
    return build_response(200, {"items": items, "count": len(items)})

def _get_timeline(event):
    timeline_id = _item_id(event)
    if not timeline_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
    
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[timeline] WHERE id = %s", (timeline_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        return build_response(404, {"message": "Timeline item not found", "id": timeline_id})
    return build_response(200, {"timeline": _map_timeline(row)})

def _create_timeline(event):
    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})
    if not data.get("type"):
        return build_response(400, {"message": "Missing required field: 'type'"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    timestamp = datetime.now(timezone.utc)
    timeline_id = data.get("id") or f"tl_{uuid.uuid4().hex}"
    
    cursor.execute(
        """
        INSERT INTO [dbo].[timeline] (id, type, role, company, duration, location, description, title, issuer, badge_url, icon, [order], created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %d, %s, %s)
        """,
        (
            timeline_id,
            data["type"],
            data.get("role") or "",
            data.get("company") or "",
            data.get("duration") or "",
            data.get("location") or "",
            data.get("description") or "",
            data.get("title") or "",
            data.get("issuer") or "",
            data.get("badge_url") or "",
            data.get("icon") or "",
            int(data.get("order") or 0),
            timestamp,
            timestamp
        )
    )
    conn.commit()
    
    cursor.execute("SELECT * FROM [dbo].[timeline] WHERE id = %s", (timeline_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(201, {"message": "Timeline item created successfully", "timeline": _map_timeline(row)})

def _update_timeline(event):
    timeline_id = _item_id(event)
    if not timeline_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    cursor.execute("SELECT 1 FROM [dbo].[timeline] WHERE id = %s", (timeline_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return build_response(404, {"message": "Timeline item not found", "id": timeline_id})

    timestamp = datetime.now(timezone.utc)
    updates = []
    params = []
    
    if "type" in data:
        updates.append("type = %s")
        params.append(data["type"])
    if "role" in data:
        updates.append("role = %s")
        params.append(data["role"])
    if "company" in data:
        updates.append("company = %s")
        params.append(data["company"])
    if "duration" in data:
        updates.append("duration = %s")
        params.append(data["duration"])
    if "location" in data:
        updates.append("location = %s")
        params.append(data["location"])
    if "description" in data:
        updates.append("description = %s")
        params.append(data["description"])
    if "title" in data:
        updates.append("title = %s")
        params.append(data["title"])
    if "issuer" in data:
        updates.append("issuer = %s")
        params.append(data["issuer"])
    if "badge_url" in data:
        updates.append("badge_url = %s")
        params.append(data["badge_url"])
    if "icon" in data:
        updates.append("icon = %s")
        params.append(data["icon"])
    if "order" in data:
        updates.append("[order] = %d")
        params.append(int(data["order"]))
        
    updates.append("updated_at = %s")
    params.append(timestamp)
    
    query = f"UPDATE [dbo].[timeline] SET {', '.join(updates)} WHERE id = %s"
    params.append(timeline_id)
    
    cursor.execute(query, tuple(params))
    conn.commit()
    
    # Fetch updated timeline item
    cursor.execute("SELECT * FROM [dbo].[timeline] WHERE id = %s", (timeline_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    return build_response(200, {"message": "Timeline item updated successfully", "timeline": _map_timeline(row)})

def _delete_timeline(event):
    timeline_id = _item_id(event)
    if not timeline_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [dbo].[timeline] WHERE id = %s", (timeline_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
    return build_response(200, {"message": "Timeline item deleted successfully", "id": timeline_id})

def lambda_handler(event, context):
    logger.info("Received timeline event: %s", json.dumps(event))

    try:
        method = _method(event)
        timeline_id = _item_id(event)

        if method == "GET" and timeline_id:
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
