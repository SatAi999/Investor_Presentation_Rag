from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

# ── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = "rag-secret-key-change-in-production-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

# ── Demo users (in production: use a real DB) ─────────────────────────────────
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

USERS: dict[str, dict] = {
    "admin": {"hashed": _pwd.hash("admin123"), "role": "admin"},
    "user":  {"hashed": _pwd.hash("user123"),  "role": "user"},
}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Helpers ───────────────────────────────────────────────────────────────────

def authenticate(username: str, password: str) -> dict | None:
    record = USERS.get(username)
    if not record or not _pwd.verify(password, record["hashed"]):
        return None
    return {"username": username, "role": record["role"]}


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": username, "role": role, "exp": expire},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        role = payload.get("role")
        if not username or not role:
            raise exc
        return {"username": username, "role": role}
    except JWTError:
        raise exc


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
