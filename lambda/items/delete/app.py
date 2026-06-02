import json
from shared_utils import build_response, get_logger, get_table

logger = get_logger()

def lambda_handler(event, context):
    """Lambda function to delete an item from DynamoDB by ID."""
    logger.info("Received delete item event: %s", json.dumps(event))
    
    path_parameters = event.get("pathParameters") or {}
    item_id = path_parameters.get("id")
    
    if not item_id:
        logger.warning("Attempted deletion without id path parameter")
        return build_response(400, {"message": "Missing required 'id' parameter in path"})
    
    try:
        table = get_table()
        table.delete_item(Key={"id": item_id})
        logger.info("Successfully deleted item: %s", item_id)
        return build_response(200, {"message": "Item deleted successfully", "id": item_id})
    except Exception as e:
        logger.exception("Database error while deleting item: %s", item_id)
        return build_response(500, {"message": f"Internal database error: {str(e)}"})
