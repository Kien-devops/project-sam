import json
from shared_utils import build_response, get_logger

logger = get_logger()

def lambda_handler(event, context):
    """Sample Lambda handler that returns a customized Hello greeting."""
    logger.info("Received hello world event: %s", json.dumps(event))
    
    try:
        query_params = event.get("queryStringParameters") or {}
        name = query_params.get("name", "World")
        
        response_body = {
            "message": f"Hello, {name}!",
            "status": "success",
            "runtime": "Python 3.13"
        }
        return build_response(200, response_body)
        
    except Exception as e:
        logger.exception("Exception caught in handler: %s", str(e))
        return build_response(500, {"message": "Internal Server Error", "error": str(e)})
