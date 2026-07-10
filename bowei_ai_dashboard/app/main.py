from contextlib import asynccontextmanager
import logging
import os
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import inspect, text

from . import models
from .auth import (
    _check_password,
    create_session,
    delete_session,
    get_session_user,
    hash_password,
    invalidate_user_sessions,
    login_block_reason,
    record_login_attempt,
    validate_password_policy,
    verify_password,
)
from .database import Base, SessionLocal, engine
from .excel_importer import read_project_assignments
from .llm_config import PROVIDERS, load_configs
from .permissions import get_all_project_roles, get_user_context_from_db, system_role_label
from .routers import (
    accounts,
    achievement_submissions,
    achievements,
    admin,
    confirmations,
    dashboard,
    issues,
    llm_config,
    logs,
    meetings,
    notifications,
    people,
    platform_settings,
    projects,
    setup,
    subtask_drafts,
    subtasks,
    tasks,
    transcribe,
    updates,
)
from .seed import EXCEL_SEED, seed
from .settings import get_settings
from .time_utils import utc_now

logging.basicConfig(
    level=get_settings().log_level,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bowei")


def _startup():
    Base.metadata.create_all(bind=engine)
    _ensure_phase1_schema()
    with SessionLocal() as db:
        db.query(models.AuthSession).filter(models.AuthSession.expires_at <= utc_now()).delete(synchronize_session=False)
        db.query(models.AuthSession).filter(models.AuthSession.session_token_hash == None).delete(synchronize_session=False)
        db.commit()

    if os.getenv("BOWEI_DEV_MODE", "").lower() == "true":
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()

    logger.info("Moways-SOP backend started")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup()
    yield


app = FastAPI(title="Moways-SOP project collaboration platform", version="0.3", lifespan=lifespan)
_runtime_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(_runtime_settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

_PUBLIC_PREFIXES = ("/api/auth/", "/api/llm-config/enabled", "/api/health", "/api/setup", "/login", "/setup")
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_FORCE_PASSWORD_ALLOWED_PREFIXES = ("/api/auth/me", "/api/auth/logout", "/api/auth/change-password", "/api/accounts/me/change-password")


def _origin_from_referer(referer: str | None) -> str:
    if not referer:
        return ""
    parsed = urlparse(referer)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _request_origin(request: Request) -> str:
    origin = request.headers.get("origin", "").strip().rstrip("/")
    if origin:
        return origin
    return _origin_from_referer(request.headers.get("referer")).rstrip("/")


def _is_account_forced_to_change_password(username: str) -> bool:
    with SessionLocal() as db:
        account = db.query(models.Account).filter(models.Account.username == username).first()
        return bool(account and account.must_change_password)


def _default_route(account: models.Account | None, context: dict) -> str:
    if account and account.must_change_password:
        return "/change-password"
    if account and account.status != "active":
        return "/login?reason=account"
    # tech_admin / CEO / can_view_all 统一默认进入 dashboard（与前端 authFlow 保持一致）
    if context.get("is_tech_admin") or context.get("is_ceo") or context.get("can_view_all"):
        return "/home/dashboard"
    if context.get("visible_projects"):
        return "/projects"
    return "/home"


def _public_project_roles(raw_roles: list[str], *, is_ceo: bool = False) -> list[str]:
    mapping = {
        "owner": "project_owner",
        "coordinator": "project_coordinator",
        "member": "project_member",
        "project_ceo": "project_ceo",
    }
    result: list[str] = []
    seen: set[str] = set()
    for role in raw_roles or []:
        public_role = mapping.get(role, role)
        if public_role and public_role not in seen:
            seen.add(public_role)
            result.append(public_role)
    # 兼容保留 is_ceo 参数，但不再把全局 CEO 自动映射成 project_ceo。
    return result


def _auth_me_projects(account: models.Account, context: dict, db) -> list[dict]:
    person_id = context.get("person_id") or account.person_id
    include_all = bool(context.get("can_view_all") or context.get("is_ceo"))
    if include_all:
        rows = (
            db.query(models.Project)
            .filter(models.Project.status != "archived")
            .order_by(models.Project.sort_order, models.Project.id)
            .all()
        )
    elif person_id:
        rows = (
            db.query(models.Project)
            .join(models.ProjectMember, models.ProjectMember.project_id == models.Project.id)
            .filter(models.ProjectMember.person_id == person_id, models.Project.status != "archived")
            .group_by(models.Project.id, models.Project.name, models.Project.sort_order)
            .order_by(models.Project.sort_order, models.Project.id)
            .all()
        )
    else:
        rows = []

    projects: list[dict] = []
    for project in rows:
        raw_roles = get_all_project_roles(int(person_id), int(project.id), db) if person_id else []
        public_roles = _public_project_roles(raw_roles, is_ceo=bool(context.get("is_ceo")))
        projects.append(
            {
                "id": project.id,
                "name": project.name,
                "roles": public_roles,
            }
        )
    return projects


def _auth_me_payload(username: str) -> dict | None:
    with SessionLocal() as db:
        account = db.query(models.Account).filter(models.Account.username == username).first()
        if not account:
            return None
        context = get_user_context_from_db(username, db)
        locked = bool(account.locked_until and account.locked_until > models.now())
        projects = _auth_me_projects(account, context, db)
        return {
            "account_id": account.id,
            "person_id": context.get("person_id"),
            "username": username,
            "name": context.get("name") or username,
            "account_status": account.status,
            "locked_until": account.locked_until.isoformat() if account.locked_until else None,
            "is_locked": locked,
            "is_ceo": context.get("is_ceo", False),
            "is_tech_admin": bool(account.is_tech_admin) or context.get("is_tech_admin", False),
            "is_coordinator": context.get("is_coordinator", False),
            "role_scope": context.get("role_scope", ""),
            "can_view_all": context.get("can_view_all", False),
            "can_confirm_all": context.get("can_confirm_all", False),
            "can_assign_all": context.get("can_assign_all", False),
            "can_view_settings": context.get("can_view_settings", False),
            "can_view_confirmation_center": context.get("can_view_confirmation_center", False),
            "can_view_approval_reminders": context.get("can_view_approval_reminders", False),
            "can_view_decision_items": context.get("can_view_decision_items", False),
            "can_view_risk_items": context.get("can_view_risk_items", False),
            "can_view_issue_decisions": context.get("can_view_issue_decisions", False),
            "can_view_issue_risks": context.get("can_view_issue_risks", False),
            "can_view_progress": context.get("can_view_progress", True),
            "visible_projects": context.get("visible_projects", []),
            "owned_projects": context.get("owned_projects", []),
            "coordinated_projects": context.get("coordinated_projects", []),
            "collaborated_projects": context.get("collaborated_projects", []),
            "project_roles": context.get("project_roles", {}),
            "system_role": context.get("system_role", ""),
            "system_role_label": system_role_label(context.get("system_role", "")),
            "must_change_password": bool(account.must_change_password),
            "default_route": _default_route(account, context),
            "projects": projects,
        }


def _ensure_phase1_schema() -> None:
    inspector = inspect(engine)
    if inspector.has_table("auth_sessions"):
        columns = {col["name"] for col in inspector.get_columns("auth_sessions")}
        with engine.begin() as conn:
            if "session_token_hash" not in columns:
                conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN session_token_hash VARCHAR(64)"))
            if "revoked_at" not in columns:
                conn.execute(text("ALTER TABLE auth_sessions ADD COLUMN revoked_at DATETIME"))


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "server_error"}, status_code=500)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    settings = get_settings()
    path = request.url.path
    if request.method in _UNSAFE_METHODS and path.startswith("/api/"):
        origin = _request_origin(request)
        if not origin:
            logger.warning("unsafe request without Origin/Referer: %s %s", request.method, path)
        elif origin not in settings.cors_allowed_origins:
            logger.warning("blocked unsafe request from origin=%s path=%s", origin, path)
            return JSONResponse({"detail": "origin_not_allowed"}, status_code=403)

    if any(path == prefix or path.startswith(prefix) for prefix in _PUBLIC_PREFIXES):
        return await call_next(request)

    session_id = request.cookies.get(settings.session_cookie_name)
    user = get_session_user(session_id) if session_id else None
    if not user:
        if path.startswith("/api/"):
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return RedirectResponse("/login", status_code=302)
    if (
        path.startswith("/api/")
        and not any(path == prefix or path.startswith(prefix) for prefix in _FORCE_PASSWORD_ALLOWED_PREFIXES)
        and _is_account_forced_to_change_password(user)
    ):
        return JSONResponse({"detail": "must_change_password"}, status_code=403)
    return await call_next(request)


@app.get("/api/health")
def health_check():
    settings = get_settings()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "app": "bowei-ai-dashboard",
            "env": settings.app_env,
            "database": "ok",
        }
    except Exception:
        logger.warning("health check database probe failed")
        return JSONResponse(
            {
                "status": "error",
                "app": "bowei-ai-dashboard",
                "env": settings.app_env,
                "database": "error",
            },
            status_code=503,
        )


@app.get("/login")
def login_page():
    return PlainTextResponse(
        "Legacy UI removed. Open the new frontend at http://127.0.0.1:6001",
        status_code=200,
    )


@app.post("/api/auth/login")
async def auth_login(request: Request):
    settings = get_settings()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"detail": "invalid_request"}, status_code=400)

    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    if not username or not password:
        return JSONResponse({"detail": "username_or_password_required"}, status_code=400)

    attempt_meta = {
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", ""),
    }
    blocked = login_block_reason(username)
    if blocked:
        status_code, detail = blocked
        logger.warning("login blocked: %s status=%s", username, status_code)
        record_login_attempt(username, success=False, failure_reason="blocked", **attempt_meta)
        return JSONResponse({"detail": detail}, status_code=status_code)

    if not verify_password(username, password):
        logger.warning("login failed: %s", username)
        record_login_attempt(username, success=False, failure_reason="bad_credentials", **attempt_meta)
        return JSONResponse({"detail": "账号或密码错误，请重试"}, status_code=401)

    sid = create_session(username)
    record_login_attempt(username, success=True, **attempt_meta)
    logger.info("user login: %s", username)
    payload = {
        "ok": True,
        "user": username,
        "username": username,
        "default_route": _auth_me_payload(username)["default_route"] if _auth_me_payload(username) else "/home",
    }
    resp = JSONResponse(payload)
    resp.set_cookie(
        settings.session_cookie_name,
        sid,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_seconds,
        path="/",
    )
    return resp


@app.post("/api/auth/logout")
def auth_logout(request: Request):
    settings = get_settings()
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        delete_session(sid)
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
    )
    return resp


@app.get("/api/auth/me")
def auth_me(request: Request):
    sid = request.cookies.get(get_settings().session_cookie_name)
    user = get_session_user(sid) if sid else None
    if not user:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    payload = _auth_me_payload(user)
    if not payload:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    payload.setdefault("id", payload.get("account_id"))
    payload.setdefault("display_name", payload.get("name"))
    payload.setdefault("global_roles", [payload.get("system_role")] if payload.get("system_role") else [])
    payload.setdefault("projects", payload.get("projects", payload.get("visible_projects", [])))
    payload.setdefault(
        "capabilities",
        {
            "can_view_all": payload.get("can_view_all", False),
            "can_confirm_all": payload.get("can_confirm_all", False),
            "can_assign_all": payload.get("can_assign_all", False),
            "can_view_settings": payload.get("can_view_settings", False),
            "can_view_confirmation_center": payload.get("can_view_confirmation_center", False),
            "can_view_approval_reminders": payload.get("can_view_approval_reminders", False),
            "can_view_decision_items": payload.get("can_view_decision_items", False),
            "can_view_risk_items": payload.get("can_view_risk_items", False),
            "can_view_issue_decisions": payload.get("can_view_issue_decisions", False),
            "can_view_issue_risks": payload.get("can_view_issue_risks", False),
            "can_view_progress": payload.get("can_view_progress", True),
        },
    )
    return payload


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@app.post("/api/auth/change-password")
async def auth_change_password(request: Request):
    sid = request.cookies.get(get_settings().session_cookie_name)
    username = get_session_user(sid) if sid else None
    if not username:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    try:
        payload = ChangePasswordRequest.model_validate(await request.json())
    except Exception:
        return JSONResponse({"detail": "invalid_request"}, status_code=422)

    with SessionLocal() as db:
        account = db.query(models.Account).filter(models.Account.username == username).first()
        if not account:
            return JSONResponse({"detail": "account_not_found"}, status_code=404)
        if not _check_password(payload.old_password, account.password_hash or ""):
            return JSONResponse({"detail": "old_password_incorrect"}, status_code=400)
        try:
            validate_password_policy(username, payload.new_password, old_password=payload.old_password)
        except ValueError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        account.password_hash = hash_password(payload.new_password)
        account.must_change_password = False
        account.failed_login_count = 0
        account.locked_until = None
        account.last_password_changed_at = models.now()
        db.commit()

    invalidate_user_sessions(username, except_session_id=sid)
    return {"ok": True}


@app.get("/")
def index():
    return PlainTextResponse(
        "Legacy UI removed. Open the new frontend at http://127.0.0.1:6001",
        status_code=200,
    )


@app.get("/api/llm-config/enabled")
def llm_config_enabled():
    stored = load_configs()
    return [
        {"provider": provider, "display_name": meta["display"]}
        for provider, meta in PROVIDERS.items()
        if stored.get(provider, {}).get("enabled", False)
    ]


@app.get("/api/project-assignments")
def project_assignments():
    if EXCEL_SEED.exists():
        return read_project_assignments(EXCEL_SEED)
    return []


app.include_router(setup.router)
app.include_router(dashboard.router)
app.include_router(updates.router)
app.include_router(confirmations.router)
app.include_router(tasks.router)
app.include_router(achievements.router)
app.include_router(achievement_submissions.router)
app.include_router(issues.router)
app.include_router(meetings.router)
app.include_router(people.router)
app.include_router(accounts.router)
app.include_router(projects.router)
app.include_router(logs.router)
app.include_router(llm_config.router)
app.include_router(platform_settings.router)
app.include_router(transcribe.router)
app.include_router(subtasks.router)
app.include_router(subtask_drafts.router)
app.include_router(notifications.router)
app.include_router(admin.router)
