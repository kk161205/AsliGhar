import logging

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status

from app.core.auth_deps import ACCESS_TOKEN_COOKIE, get_current_user
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.models.auth_schemas import LoginRequest, SignupRequest, UserResponse
from app.models.db import User
from app.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, email=user.email, full_name=user.full_name, city=user.city,
        created_at=user.created_at,
    )


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def signup(request: Request, body: SignupRequest, response: Response) -> UserResponse:
    existing = await auth_service.get_user_by_email(body.email)
    if existing is not None:
        logger.warning("Signup rejected: email=%s already registered", body.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists."
        )
    user = await auth_service.create_user(body.email, body.password, body.full_name, body.city)
    _set_session_cookie(response, auth_service.create_access_token(user.id))
    return _to_user_response(user)


@router.post("/login", response_model=UserResponse)
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, response: Response) -> UserResponse:
    user = await auth_service.authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password."
        )
    _set_session_cookie(response, auth_service.create_access_token(user.id))
    return _to_user_response(user)


@router.post("/logout")
async def logout(response: Response, access_token: str | None = Cookie(default=None)) -> dict[str, str]:
    # Deliberately doesn't require get_current_user — logging out must always
    # succeed even with an already-expired/invalid cookie. The lookup here is
    # best-effort, purely for the log line; it never blocks the response.
    user_id = auth_service.decode_access_token(access_token) if access_token else None
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/")
    logger.info("User %s logged out", user_id or "(no valid session)")
    return {"status": "ok"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return _to_user_response(current_user)
