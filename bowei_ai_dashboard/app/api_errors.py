from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class CodedHTTPException(HTTPException):
    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


async def coded_http_exception_handler(_request: Request, exc: CodedHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
        headers=exc.headers,
    )
