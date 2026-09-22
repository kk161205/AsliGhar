import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    # Starlette's own default handler for an unhandled exception returns a
    # bare "Internal Server Error" with no JSON body and logs nothing — the
    # frontend can't show anything but a generic "Request failed with status
    # 500" (its ApiError parses response.json(), which fails on plain text),
    # and production gives no clue what broke. Every other error response in
    # this API already uses a "detail" JSON body (see rate_limit.py); this
    # makes an unexpected server error consistent with that and logs the
    # traceback where it can actually be found.
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )
