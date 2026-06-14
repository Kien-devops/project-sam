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

def _map_project(row, details_rows=None):
    if not row:
        return None
    tech_stack = []
    if row.get('tech_stack'):
        try:
            tech_stack = json.loads(row['tech_stack'])
        except Exception:
            tech_stack = [t.strip() for t in row['tech_stack'].split(',') if t.strip()]
            
    details = []
    if details_rows:
        for detail in details_rows:
            details.append({
                "detail_title": detail.get("detail_title") or "",
                "detail_description": detail.get("detail_description") or "",
                "icon": detail.get("icon") or ""
            })
            
    return {
        "id": str(row['id']),
        "project_number": row.get('project_number') or "",
        "name": row.get('title') or "",
        "title": row.get('title') or "",
        "summary": row.get('summary') or "",
        "description": row.get('description') or "",
        "githubUrl": row.get('github_url') or "",
        "github_url": row.get('github_url') or "",
        "demoUrl": row.get('demo_url') or "",
        "demo_url": row.get('demo_url') or "",
        "imageUrl": row.get('image_url') or "",
        "image_url": row.get('image_url') or "",
        "slug": row.get('slug') or "",
        "status": row.get('status') or "draft",
        "techStack": tech_stack,
        "tech_stack": tech_stack,
        "details": details,
        "createdAt": row.get('created_at').isoformat() if row.get('created_at') else None,
        "updatedAt": row.get('updated_at').isoformat() if row.get('updated_at') else None,
    }

def _list_projects():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[projects] ORDER BY id")
    project_rows = cursor.fetchall()
    
    cursor.execute("SELECT * FROM [dbo].[project_details]")
    detail_rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Group details by project_id
    details_by_project = {}
    for detail in detail_rows:
        pid = detail['project_id']
        if pid not in details_by_project:
            details_by_project[pid] = []
        details_by_project[pid].append(detail)
        
    items = []
    for prow in project_rows:
        pid = prow['id']
        pdetails = details_by_project.get(pid, [])
        items.append(_map_project(prow, pdetails))
        
    return build_response(200, {"items": items, "count": len(items)})

def _get_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})
        
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    cursor.execute("SELECT * FROM [dbo].[projects] WHERE id = %s", (project_id,))
    prow = cursor.fetchone()
    if not prow:
        cursor.close()
        conn.close()
        return build_response(404, {"message": "Project not found", "id": project_id})
        
    cursor.execute("SELECT * FROM [dbo].[project_details] WHERE project_id = %s", (project_id,))
    pdetails = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return build_response(200, {"project": _map_project(prow, pdetails)})

def _create_project(event):
    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})
    if not data.get("name"):
        return build_response(400, {"message": "Missing required field: 'name'"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    timestamp = datetime.now(timezone.utc)
    tech_stack_json = json.dumps(data.get("techStack", []))
    
    project_id = data.get("id")
    is_numeric_id = False
    if project_id:
        try:
            project_id = int(project_id)
            is_numeric_id = True
        except ValueError:
            pass
            
    if is_numeric_id:
        cursor.execute("SET IDENTITY_INSERT [dbo].[projects] ON")
        cursor.execute(
            """
            INSERT INTO [dbo].[projects] (id, project_number, title, summary, github_url, tech_stack, demo_url, image_url, description, slug, status, created_at, updated_at)
            VALUES (%d, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                project_id,
                data.get("project_number") or "",
                data["name"],
                data.get("summary") or "",
                data.get("githubUrl") or "",
                tech_stack_json,
                data.get("demoUrl") or "",
                data.get("imageUrl") or "",
                data.get("description") or "",
                data.get("slug") or "",
                data.get("status") or "draft",
                timestamp,
                timestamp
            )
        )
        cursor.execute("SET IDENTITY_INSERT [dbo].[projects] OFF")
        inserted_id = project_id
    else:
        cursor.execute(
            """
            INSERT INTO [dbo].[projects] (project_number, title, summary, github_url, tech_stack, demo_url, image_url, description, slug, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data.get("project_number") or "",
                data["name"],
                data.get("summary") or "",
                data.get("githubUrl") or "",
                tech_stack_json,
                data.get("demoUrl") or "",
                data.get("imageUrl") or "",
                data.get("description") or "",
                data.get("slug") or "",
                data.get("status") or "draft",
                timestamp,
                timestamp
            )
        )
        cursor.execute("SELECT @@IDENTITY")
        inserted_id = int(cursor.fetchone()[0])
        
    details = data.get("details", [])
    for detail in details:
        cursor.execute(
            """
            INSERT INTO [dbo].[project_details] (project_id, icon, detail_title, detail_description)
            VALUES (%d, %s, %s, %s)
            """,
            (
                inserted_id,
                detail.get("icon") or "",
                detail.get("detail_title") or "",
                detail.get("detail_description") or ""
            )
        )
        
    conn.commit()
    
    cursor.execute("SELECT * FROM [dbo].[projects] WHERE id = %d", (inserted_id,))
    prow = cursor.fetchone()
    cursor.execute("SELECT * FROM [dbo].[project_details] WHERE project_id = %d", (inserted_id,))
    pdetails = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return build_response(201, {"message": "Project created successfully", "project": _map_project(prow, pdetails)})

def _update_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    data = _body(event)
    if not data:
        return build_response(400, {"message": "Invalid request: missing body"})

    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)
    
    cursor.execute("SELECT 1 FROM [dbo].[projects] WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        cursor.close()
        conn.close()
        return build_response(404, {"message": "Project not found", "id": project_id})

    timestamp = datetime.now(timezone.utc)
    updates = []
    params = []
    
    if "project_number" in data:
        updates.append("project_number = %s")
        params.append(data["project_number"])
    if "name" in data:
        updates.append("title = %s")
        params.append(data["name"])
    if "summary" in data:
        updates.append("summary = %s")
        params.append(data["summary"])
    if "githubUrl" in data:
        updates.append("github_url = %s")
        params.append(data["githubUrl"])
    if "techStack" in data:
        updates.append("tech_stack = %s")
        params.append(json.dumps(data["techStack"]))
    if "demoUrl" in data:
        updates.append("demo_url = %s")
        params.append(data["demoUrl"])
    if "imageUrl" in data:
        updates.append("image_url = %s")
        params.append(data["imageUrl"])
    if "description" in data:
        updates.append("description = %s")
        params.append(data["description"])
    if "slug" in data:
        updates.append("slug = %s")
        params.append(data["slug"])
    if "status" in data:
        updates.append("status = %s")
        params.append(data["status"])
        
    updates.append("updated_at = %s")
    params.append(timestamp)
    
    query = f"UPDATE [dbo].[projects] SET {', '.join(updates)} WHERE id = %s"
    params.append(project_id)
    
    cursor.execute(query, tuple(params))
    
    if "details" in data:
        cursor.execute("DELETE FROM [dbo].[project_details] WHERE project_id = %s", (project_id,))
        for detail in data["details"]:
            cursor.execute(
                """
                INSERT INTO [dbo].[project_details] (project_id, icon, detail_title, detail_description)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    project_id,
                    detail.get("icon") or "",
                    detail.get("detail_title") or "",
                    detail.get("detail_description") or ""
                )
            )
            
    conn.commit()
    
    cursor.execute("SELECT * FROM [dbo].[projects] WHERE id = %s", (project_id,))
    prow = cursor.fetchone()
    cursor.execute("SELECT * FROM [dbo].[project_details] WHERE project_id = %s", (project_id,))
    pdetails = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return build_response(200, {"message": "Project updated successfully", "project": _map_project(prow, pdetails)})

def _delete_project(event):
    project_id = _item_id(event)
    if not project_id:
        return build_response(400, {"message": "Missing required 'id' path parameter"})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM [dbo].[project_details] WHERE project_id = %s", (project_id,))
    cursor.execute("DELETE FROM [dbo].[projects] WHERE id = %s", (project_id,))
    conn.commit()
    cursor.close()
    conn.close()
    
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
