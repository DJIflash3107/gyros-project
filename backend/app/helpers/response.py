from typing import Any, Dict, List, Optional
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def success_response(
    message: str,
    data: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Build standardized success response."""
    payload = {
        "message": {"success": message},
        "error": {},
        "data": jsonable_encoder(data) if data is not None else {},
    }
    return JSONResponse(status_code=status_code, content=payload)


def paginated_response(
    message: str,
    items: List[Any],
    resource_key: str,
    pagination: Dict[str, Any],
    status_code: int = 200,
) -> JSONResponse:
    """Build standardized paginated list response."""
    payload = {
        "message": {"success": message},
        "error": {},
        "data": {
            resource_key: jsonable_encoder(items),
            "pagination": jsonable_encoder(pagination),
        },
    }
    return JSONResponse(status_code=status_code, content=payload)


def error_response(
    message: str,
    errors: Optional[Dict[str, Any]] = None,
    status_code: int = 400,
    data: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Build standardized error response."""
    payload = {
        "message": {"error": message},
        "error": errors if errors is not None else {},
        "data": data if data is not None else {},
    }
    return JSONResponse(status_code=status_code, content=payload)
