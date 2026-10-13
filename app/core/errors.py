import logging
from datetime import datetime, timezone
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.retry_utils import TerminusException, ErrorCode
from app.schemas.error import StandardErrorResponse, ErrorDetail

logger = logging.getLogger(__name__)


def register_error_handlers(app):
    """Registers global exception handlers enforcing standardized error responses."""

    @app.exception_handler(TerminusException)
    async def terminus_exception_handler(request: Request, exc: TerminusException):
        logger.warning(f"Domain exception on {request.url.path}: {exc.message}")
        payload = StandardErrorResponse(
            success=False,
            error=ErrorDetail(
                error_code=exc.error_code,
                message=exc.message,
                recovery_hint=exc.recovery_hint,
                details=exc.details,
                timestamp=datetime.now(timezone.utc).isoformat(),
                path=request.url.path
            )
        )
        
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        if exc.error_code == ErrorCode.CIRCUIT_OPEN:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif exc.error_code == ErrorCode.DUPLICATE_TRANSACTION:
            status_code = status.HTTP_409_CONFLICT
        elif exc.error_code in (ErrorCode.RPC_FAILURE, ErrorCode.RPC_TIMEOUT):
            status_code = status.HTTP_502_BAD_GATEWAY
            
        return JSONResponse(status_code=status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.info(f"Validation error on {request.url.path}: {exc.errors()}")
        payload = StandardErrorResponse(
            success=False,
            error=ErrorDetail(
                error_code="VALIDATION_ERROR",
                message="Request payload or parameters failed validation.",
                recovery_hint="Inspect request body and query parameters against endpoint schema.",
                details={"errors": exc.errors()},
                timestamp=datetime.now(timezone.utc).isoformat(),
                path=request.url.path
            )
        )
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        payload = StandardErrorResponse(
            success=False,
            error=ErrorDetail(
                error_code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                recovery_hint="Check HTTP status code and request path.",
                details={},
                timestamp=datetime.now(timezone.utc).isoformat(),
                path=request.url.path
            )
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
        payload = StandardErrorResponse(
            success=False,
            error=ErrorDetail(
                error_code="INTERNAL_SERVER_ERROR",
                message="An unexpected server error occurred.",
                recovery_hint="Please contact support or retry later.",
                details={"error": str(exc)},
                timestamp=datetime.now(timezone.utc).isoformat(),
                path=request.url.path
            )
        )
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=payload.model_dump())
