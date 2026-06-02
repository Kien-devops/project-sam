import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_dynamodb_resource = None


def get_logger():
    return logger


def get_table():
    global _dynamodb_resource
    if not _dynamodb_resource:
        import boto3

        _dynamodb_resource = boto3.resource("dynamodb")

    table_name = os.environ.get("TABLE_NAME")
    if not table_name:
        raise ValueError("TABLE_NAME environment variable is not set")
    return _dynamodb_resource.Table(table_name)


def build_response(status_code: int, body_dict: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
        },
        "body": json.dumps(body_dict),
    }
