import json
import logging
import os
import pymssql

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_logger():
    return logger

def get_db_connection():
    return pymssql.connect(
        server='100.112.150.56',
        user='sa',
        password='Abcd1234@',
        database='portfolio'
    )

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        import decimal
        from datetime import datetime, date
        if isinstance(obj, decimal.Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super(CustomJSONEncoder, self).default(obj)

def build_response(status_code: int, body_dict: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,GET,POST,PUT,DELETE",
        },
        "body": json.dumps(body_dict, cls=CustomJSONEncoder),
    }
