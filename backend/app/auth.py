"""Filesystem-backed authentication: users + bearer-token sessions.

Users live in storage/users.json, sessions in storage/sessions.json.
Passwords are hashed with pbkdf2_hmac (stdlib only). Tokens are random
256-bit strings with a 30-day expiry, sent as `Authorization: Bearer <t>`.
"""
import hashlib
import json
import logging
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import HTTPException, Request

from app.config import settings

logger = logging.getLogger(__name__)

SESSION_TTL = 30 * 24 * 3600  # 30 days
PBKDF2_ITERATIONS = 200_000
NICKNAME_RE = re.compile(r"^[a-zA-Z0-9_-]{3,32}$")
MIN_PASSWORD_LEN = 6

_lock = threading.Lock()


def _users_path() -> Path:
    return Path(settings.storage_dir) / "users.json"


def _sessions_path() -> Path:
    return Path(settings.storage_dir) / "sessions.json"


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def register(nickname: str, password: str) -> dict:
    nickname = (nickname or "").strip()
    if not NICKNAME_RE.fullmatch(nickname):
        raise ValueError("Никнейм: 3-32 символа, латиница, цифры, - или _")
    if len(password or "") < MIN_PASSWORD_LEN:
        raise ValueError(f"Пароль минимум {MIN_PASSWORD_LEN} символов")
    with _lock:
        users = _load_json(_users_path(), {})
        if nickname in users:
            raise ValueError("Этот никнейм уже занят")
        salt = secrets.token_hex(16)
        created_at = time.time()
        users[nickname] = {
            "password_hash": _hash_password(password, salt),
            "salt": salt,
            "created_at": created_at,
        }
        _save_json(_users_path(), users)
    logger.info("User registered: %s", nickname)
    return {"nickname": nickname, "created_at": created_at}


def get_user_created(nickname: str) -> float | None:
    with _lock:
        users = _load_json(_users_path(), {})
        u = users.get(nickname)
    return u["created_at"] if u else None


def authenticate(nickname: str, password: str) -> str | None:
    """Returns the nickname if credentials are valid, else None."""
    nickname = (nickname or "").strip()
    with _lock:
        u = _load_json(_users_path(), {}).get(nickname)
    if not u:
        # constant-ish work even for unknown users
        _hash_password(password or "", "0" * 32)
        return None
    if secrets.compare_digest(u["password_hash"], _hash_password(password or "", u["salt"])):
        return nickname
    return None


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _cleanup_expired(sessions: dict) -> None:
    now = time.time()
    for token in [t for t, s in sessions.items() if s.get("expires_at", 0) < now]:
        del sessions[token]


def create_session(nickname: str) -> str:
    token = secrets.token_urlsafe(32)
    with _lock:
        sessions = _load_json(_sessions_path(), {})
        _cleanup_expired(sessions)
        sessions[token] = {"nickname": nickname, "expires_at": time.time() + SESSION_TTL}
        _save_json(_sessions_path(), sessions)
    return token


def validate_token(token: str) -> str | None:
    with _lock:
        sessions = _load_json(_sessions_path(), {})
        entry = sessions.get(token)
        if not entry:
            return None
        if entry.get("expires_at", 0) < time.time():
            del sessions[token]
            _save_json(_sessions_path(), sessions)
            return None
        return entry["nickname"]


def revoke_token(token: str) -> None:
    with _lock:
        sessions = _load_json(_sessions_path(), {})
        if token in sessions:
            del sessions[token]
            _save_json(_sessions_path(), sessions)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

def _token_from_request(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip() or None
    return None


def require_user(request: Request) -> str:
    token = _token_from_request(request)
    nickname = validate_token(token) if token else None
    if not nickname:
        raise HTTPException(status_code=401, detail="Требуется вход")
    request.state.token = token
    return nickname


def optional_user(request: Request) -> str | None:
    token = _token_from_request(request)
    return validate_token(token) if token else None
