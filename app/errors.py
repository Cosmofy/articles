from enum import Enum

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class Code(Enum):
    INVALID_QUERY = (422, "The article query is invalid.")
    ARTICLE_NOT_FOUND = (404, "The requested article was not found.")
    RATE_LIMITED = (
        429,
        "Too many article requests were made. Please try again shortly.",
    )
    INVALID_DATASET = (503, "The article catalog is temporarily unavailable.")
    INTERNAL_ERROR = (500, "An unexpected error occurred.")

    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


class Error(Exception):
    def __init__(self, code: Code, headers: dict[str, str] | None = None):
        self.code = code
        self.headers = headers
        super().__init__(code.name)


async def handle_error(_request: Request, error: Error) -> JSONResponse:
    return JSONResponse(
        status_code=error.code.status,
        headers=error.headers,
        content={"error": {"code": error.code.name, "message": error.code.message}},
    )


async def handle_validation_error(
    request: Request,
    _error: RequestValidationError,
) -> JSONResponse:
    return await handle_error(request, Error(Code.INVALID_QUERY))
