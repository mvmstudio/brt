"""
Authentication API — register, login, get current user.
JWT tokens stored on client, password hashed with bcrypt.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from app.config import settings
from app.db.connection import get_db

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)


class TokenResponse(BaseModel):
    token: str
    user: dict


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    return jwt.encode(
        {"sub": str(user_id), "username": username, "exp": expire},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """Returns user dict or None if not authenticated."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = int(payload["sub"])
        username = payload["username"]
        return {"id": user_id, "username": username}
    except (JWTError, KeyError, ValueError):
        return None


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Returns user dict or raises 401."""
    user = await get_current_user(credentials)
    if user is None:
        raise HTTPException(401, "Not authenticated")
    return user


@router.post("/auth/register")
async def register(body: AuthRequest):
    db = await get_db()
    existing = await db.execute_fetchall(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    )
    if existing:
        raise HTTPException(409, "Username already taken")

    password_hash = pwd_context.hash(body.password)
    cursor = await db.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (body.username, password_hash),
    )
    await db.commit()
    user_id = cursor.lastrowid

    token = create_token(user_id, body.username)
    return {"token": token, "user": {"id": user_id, "username": body.username}}


@router.post("/auth/login")
async def login(body: AuthRequest):
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (body.username,),
    )
    if not rows:
        raise HTTPException(401, "Invalid username or password")

    user = dict(rows[0])
    if not pwd_context.verify(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid username or password")

    token = create_token(user["id"], user["username"])
    return {"token": token, "user": {"id": user["id"], "username": user["username"]}}


@router.get("/auth/me")
async def me(user: dict = Depends(require_user)):
    return user
