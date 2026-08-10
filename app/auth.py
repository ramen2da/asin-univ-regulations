import os
import secrets
from datetime import datetime, timezone

from fastapi import Cookie, HTTPException

from db import get_connection

_env_password = os.environ.get("ADMIN_PASSWORD")
if _env_password:
    ADMIN_PASSWORD = _env_password
else:
    ADMIN_PASSWORD = secrets.token_urlsafe(9)
    print(f"[auth] ADMIN_PASSWORD not set - generated a temporary password for this run: {ADMIN_PASSWORD}")

SESSION_COOKIE_NAME = "admin_session"


def verify_password(password: str) -> bool:
    return password.strip() == ADMIN_PASSWORD


def create_session() -> str:
    token = secrets.token_hex(32)
    conn = get_connection()
    conn.execute(
        "INSERT INTO admin_sessions (token, created_at) VALUES (?, ?)",
        (token, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    return token


def destroy_session(token: str):
    conn = get_connection()
    conn.execute("DELETE FROM admin_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def require_admin(admin_session: str | None = Cookie(default=None)):
    if not admin_session:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM admin_sessions WHERE token = ?", (admin_session,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다")
