from typing import Any
from datetime import datetime
from google.cloud import firestore
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds
from pydantic import BaseModel
import json

def custom_encoder(obj: Any) -> Any:
    """カスタムエンコーダー"""
    if isinstance(obj, (datetime, DatetimeWithNanoseconds)):
        return obj.isoformat()
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    return obj

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, DatetimeWithNanoseconds)):
            return obj.isoformat()
        return super().default(obj)

def custom_json_response(content: Any) -> JSONResponse:
    """カスタムJSONレスポンスの生成"""
    if isinstance(content, BaseModel):
        content = content.model_dump()
    elif isinstance(content, dict):
        content = {k: custom_encoder(v) for k, v in content.items()}
    else:
        content = custom_encoder(content)
    
    return JSONResponse(content=jsonable_encoder(content)) 