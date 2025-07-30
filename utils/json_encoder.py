# utils/json_encoder.py
import json
from bson import ObjectId
from datetime import datetime

class MongoJSONEncoder(json.JSONEncoder):
    """
    A custom JSON encoder for Flask that can handle MongoDB's ObjectId and datetime objects.
    """
    def default(self, o):
        """
        This method is called for any object that the default JSON encoder
        doesn't know how to serialize.
        """
        if isinstance(o, ObjectId):
            # If the object is an ObjectId, convert it to its string representation.
            return str(o)
        if isinstance(o, datetime):
            # If the object is a datetime object, convert it to an ISO 8601 string.
            return o.isoformat()
        # For any other types, fall back to the default encoder.
        return super().default(o)

