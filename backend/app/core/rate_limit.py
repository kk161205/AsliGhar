import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


def log_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # slowapi's default handler returns the 429 but logs nothing — rate-limit
    # hits on /scan (quota abuse) and /auth/login|signup (brute force /
    # enumeration) are exactly the events worth seeing in production logs,
    # not silently swallowed. Otherwise mirrors the default handler exactly:
    # same rate-limit headers via _inject_headers, same status code — except
    # the body key is "detail", not the default handler's "error", to match
    # every other error response in this API (and what the frontend's
    # ApiErrorBody type actually reads — "error" was silently never parsed).
    logger.warning(
        "Rate limit exceeded: ip=%s path=%s limit=%s",
        get_remote_address(request),
        request.url.path,
        exc.detail,
    )
    response = JSONResponse(
        status_code=429, content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)
