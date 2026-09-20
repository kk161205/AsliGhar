from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

MIN_PASSWORD_LENGTH = 8
# bcrypt silently ignores bytes past 72 — reject longer passwords up front
# rather than let them collide with a shorter password on hash comparison.
MAX_PASSWORD_LENGTH = 72
MAX_NAME_LENGTH = 100
MAX_CITY_LENGTH = 100


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    full_name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    city: str = Field(min_length=1, max_length=MAX_CITY_LENGTH)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None
    city: str | None
    created_at: datetime
