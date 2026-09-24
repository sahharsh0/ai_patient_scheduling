"""
Password hashing and JWT helpers.

Passwords are hashed with bcrypt (via passlib) — never stored or returned in
plaintext. JWTs are signed with HS256 using JWT_SECRET_KEY from environment
config; rotate that secret and shorten ACCESS_TOKEN_EXPIRE_MINUTES for any
real deployment.
"""
import datetime as dt
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(subject: str, role: str, extra_claims: dict[str, Any] | None = None) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    expire = now + dt.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {
        "sub": subject,  # user id, as string
        "role": role,
        "iat": now,
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


class TokenPayload:
    def __init__(self, sub: str, role: str):
        self.sub = sub
        self.role = role


def decode_access_token(token: str) -> TokenPayload | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return TokenPayload(sub=payload["sub"], role=payload["role"])
    except (JWTError, KeyError):
        return None
