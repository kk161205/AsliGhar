import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.models.db import User, async_session

logger = logging.getLogger(__name__)

USER_ID_LENGTH = 12
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        # Fail closed — never sign a token with an empty/guessable secret.
        logger.error("Cannot issue session: JWT_SECRET is not configured")
        raise RuntimeError("JWT_SECRET is not configured")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    if not settings.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


async def get_user_by_email(email: str) -> User | None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()


async def get_user_by_id(user_id: str) -> User | None:
    async with async_session() as session:
        return await session.get(User, user_id)


async def create_user(email: str, password: str, full_name: str, city: str) -> User:
    user = User(
        id=uuid.uuid4().hex[:USER_ID_LENGTH],
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        city=city,
    )
    async with async_session() as session:
        session.add(user)
        await session.commit()
        await session.refresh(user)
    logger.info("User %s signed up", user.id)
    return user


async def authenticate_user(email: str, password: str) -> User | None:
    user = await get_user_by_email(email)
    if user is None:
        # Still hash something so the failure path takes roughly the same
        # time whether the email exists or not — avoids leaking account
        # existence through response timing.
        bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        logger.warning("Login failed: no account for email=%s", email)
        return None
    if not verify_password(password, user.password_hash):
        logger.warning("Login failed: wrong password for user=%s", user.id)
        return None
    logger.info("User %s logged in", user.id)
    return user
