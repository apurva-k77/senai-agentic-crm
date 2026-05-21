from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, error_code: str, message: str, details: dict | None = None, status: int = 400):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.status = status


def error_envelope(error_code: str, message: str, details: dict | None = None):
    return {"error_code": error_code, "message": message, "details": details or {}}


async def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status,
        content=error_envelope(exc.error_code, exc.message, exc.details),
    )


async def http_error_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=error_envelope("HTTP_ERROR", str(exc.detail), {"status": exc.status_code}),
    )
