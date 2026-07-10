"""
Session-based authentication.
New accounts are stored in the database. passwords.json is retained as a
compatibility fallback for legacy local deployments.

Password hashing: new hashes use bcrypt. Legacy SHA-256 hashes (64-char hex)
are accepted and transparently upgraded to bcrypt on next successful login.
"""
import hashlib
import secrets
from datetime import timedelta

import bcrypt

from .database import SessionLocal
from .models import Account, AuthSession, LoginAttempt, Person
from .time_utils import utc_now
from .settings import get_auth_passwords, get_settings, legacy_password_login_enabled

IMPERSONATE_ALLOWED = {"mowasyadmin"}
_MAX_FAILED_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _now() -> datetime:
    return utc_now()


def _sha256(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def hash_session_token(raw: str) -> str:
    return _sha256(raw)


def _is_bcrypt(h: str) -> bool:
    return h.startswith(("$2b$", "$2a$", "$2y$"))


def _bcrypt_verify(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except Exception:
        return False


def _check_password(raw: str, stored_hash: str) -> bool:
    if _is_bcrypt(stored_hash):
        return _bcrypt_verify(raw, stored_hash)
    return secrets.compare_digest(stored_hash, _sha256(raw))


def verify_password(username: str, password: str) -> bool:
    now = _now()
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.username == username).first()
        if account:
            if account.status != "active":
                return False
            # 锁定检查
            if account.locked_until and account.locked_until > now:
                return False
            ok = _check_password(password, account.password_hash or "")
            if ok:
                account.failed_login_count = 0
                account.locked_until = None
                account.last_login_at = now
                # 旧 SHA-256 哈希透明升级到 bcrypt
                if not _is_bcrypt(account.password_hash or ""):
                    account.password_hash = hash_password(password)
            else:
                count = (account.failed_login_count or 0) + 1
                account.failed_login_count = count
                if count >= _MAX_FAILED_ATTEMPTS:
                    account.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            db.commit()
            return ok

    if not legacy_password_login_enabled():
        return False

    store = get_auth_passwords()
    expected = store.get(username)
    if not expected:
        return False
    ok = _check_password(password, expected)
    if ok:
        _ensure_legacy_account(username, expected)
    return ok


def record_login_attempt(
    username: str,
    *,
    success: bool,
    failure_reason: str = "",
    ip_address: str = "",
    user_agent: str = "",
) -> None:
    with SessionLocal() as db:
        db.add(
            LoginAttempt(
                username=(username or "").strip(),
                success=bool(success),
                failure_reason=failure_reason[:80],
                ip_address=ip_address[:80],
                user_agent=user_agent[:500],
            )
        )
        db.commit()


def login_block_reason(username: str) -> tuple[int, str] | None:
    now = _now()
    with SessionLocal() as db:
        account = db.query(Account).filter(Account.username == username).first()
        if not account:
            return None
        if account.status != "active":
            return 403, "账号已禁用，请联系管理员"
        if account.locked_until and account.locked_until > now:
            return 423, "密码错误次数过多，请稍后再试"
    return None


def _ensure_legacy_account(username: str, password_hash: str) -> None:
    # 将 passwords.json 里的账号迁移进数据库，保留原有哈希（SHA-256）。
    # 下次该账号成功登录时，verify_password 会自动把哈希升级到 bcrypt。
    with SessionLocal() as db:
        if db.query(Account).filter(Account.username == username).first():
            return
        person = db.query(Person).filter(Person.name == username).first()
        account = Account(
            username=username,
            password_hash=password_hash,
            person_id=person.id if person else None,
            status="active",
            is_tech_admin=bool(person.is_admin) if person else False,
            last_login_at=_now(),
            last_password_changed_at=_now(),
        )
        db.add(account)
        db.commit()


def _delete_expired_sessions(db, now=None):
    now = now or _now()
    db.query(AuthSession).filter(AuthSession.expires_at <= now).delete(synchronize_session=False)


def create_session(username: str) -> str:
    token = secrets.token_hex(32)
    row_id = secrets.token_hex(32)
    now = _now()
    ttl_seconds = get_settings().session_ttl_seconds
    with SessionLocal() as db:
        _delete_expired_sessions(db, now)
        db.add(
            AuthSession(
                session_id=row_id,
                session_token_hash=hash_session_token(token),
                username=username,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                last_seen_at=now,
            )
        )
        db.commit()
    return token


def get_session_user(session_id: str) -> str | None:
    if not session_id:
        return None
    now = _now()
    with SessionLocal() as db:
        session = (
            db.query(AuthSession)
            .filter(AuthSession.session_token_hash == hash_session_token(session_id))
            .first()
        )
        if not session:
            return None
        if session.revoked_at or session.expires_at <= now:
            db.delete(session)
            db.commit()
            return None
        session.last_seen_at = now
        db.commit()
        return session.username


def delete_session(session_id: str) -> None:
    if not session_id:
        return
    with SessionLocal() as db:
        session = (
            db.query(AuthSession)
            .filter(AuthSession.session_token_hash == hash_session_token(session_id))
            .first()
        )
        if session:
            db.delete(session)
            db.commit()


def invalidate_user_sessions(username: str, except_session_id: str | None = None) -> None:
    """改密后清除该用户的所有 session（可保留当前 session）。"""
    with SessionLocal() as db:
        q = db.query(AuthSession).filter(AuthSession.username == username)
        if except_session_id:
            q = q.filter(AuthSession.session_token_hash != hash_session_token(except_session_id))
        q.delete(synchronize_session=False)
        db.commit()


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def validate_password_policy(username: str, password: str, *, old_password: str | None = None) -> None:
    raw = (password or "").strip()
    normalized_username = (username or "").strip().lower()
    lowered = raw.lower()
    if len(raw) < 6:
        raise ValueError("password_min_length")
    if old_password is not None and secrets.compare_digest(raw, old_password):
        raise ValueError("password_same_as_old")
    if normalized_username and lowered == normalized_username:
        raise ValueError("password_same_as_username")
    if normalized_username and normalized_username in lowered:
        raise ValueError("password_contains_username")
