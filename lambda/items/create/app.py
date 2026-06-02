import json
import uuid
from shared_utils import build_response, get_logger, get_table

logger = get_logger()

def lambda_handler(event, context):
    """Lambda function to create a new item in DynamoDB."""
    logger.info("Received create item event: %s", json.dumps(event))
    
    body_str = event.get("body")
    if not body_str:
        return build_response(400, {"message": "Invalid request: missing body"})
    
    try:
        data = json.loads(body_str)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON body: %s", str(e))
        return build_response(400, {"message": "Invalid JSON payload in body"})
    
    # Extract details or generate UUID if missing
    item_id = data.get("id") or str(uuid.uuid4())
    name = data.get("name")
    description = data.get("description", "")
    
    if not name:
        return build_response(400, {"message": "Missing required field: 'name'"})
    
    item = {
        "id": item_id,
        "name": name,
        "description": description
    }
    
    try:
        table = get_table()
        table.put_item(Item=item)
        logger.info("Successfully created item: %s", item_id)
        return build_response(201, {"message": "Item created successfully", "item": item})
    except Exception as e:
        logger.exception("Database error while creating item")
        return build_response(500, {"message": f"Internal database error: {str(e)}"})
