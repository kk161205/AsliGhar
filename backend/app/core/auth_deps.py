import logging

from fastapi import Cookie, HTTPException, status

from app.models.db import User
from app.services import auth_service

logger = logging.getLogger(__name__)

ACCESS_TOKEN_COOKIE = "access_token"


async def get_current_user(access_token: str | None = Cookie(default=None)) -> User:
    # No cookie / an expired-or-malformed token are routine (every anonymous
    # page view hits this) — not logged, or every request to a public page
    # would spam the log. A validly-signed token whose user_id doesn't exist
    # in the DB is unusual enough to be worth knowing about (JWT_SECRET
    # reuse across environments, a deleted account with a still-live
    # session), so that specific case is.
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    user_id = auth_service.decode_access_token(access_token)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session."
        )
    user = await auth_service.get_user_by_id(user_id)
    if user is None:
        logger.warning("Valid session token for user_id=%s, but that user no longer exists", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session."
        )
    return user
