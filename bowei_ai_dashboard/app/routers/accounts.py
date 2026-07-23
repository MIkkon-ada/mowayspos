from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from .. import crud, models
from ..auth import hash_password, invalidate_user_sessions, _check_password, validate_password_policy
from ..database import get_db
from ..permissions import get_current_user_name, require_tech_admin, ROLE_SUPER_ADMIN, normalize_system_role
from ..time_utils import utc_now
from ..settings import get_legacy_password_file_users, legacy_password_login_enabled

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


def _require_admin(current_user: str, db: Session):
    require_tech_admin(current_user, db)



class AccountCreateRequest(BaseModel):
    username: str
    password: str
    person_id: int | None = None
    is_tech_admin: bool = False
    must_change_password: bool = True

    @field_validator("username", "password")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("不能为空")
        return v.strip()

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("密码至少 6 位")
        return v


class AccountResetPasswordRequest(BaseModel):
    password: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if not v or len(v.strip()) < 6:
            raise ValueError("密码至少 6 位")
        return v.strip()


class AccountStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in {"active", "disabled", "locked"}:
            raise ValueError("status must be active/disabled/locked")
        return v


def _account_to_dict(row: models.Account, person: models.Person | None = None) -> dict:
    def iso(value):
        return value.isoformat() if value else None

    return {
        "id": row.id,
        "username": row.username,
        "person_id": row.person_id,
        "person_name": person.name if person else "",
        "status": row.status,
        "is_tech_admin": bool(row.is_tech_admin),
        "must_change_password": bool(row.must_change_password),
        "wecom_userid": row.wecom_userid or "",
        "last_login_at": iso(row.last_login_at),
        "last_password_changed_at": iso(row.last_password_changed_at),
        "failed_login_count": row.failed_login_count or 0,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


@router.get("")
def list_accounts(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    rows = db.query(models.Account).order_by(models.Account.id.asc()).all()
    person_map = {
        row.id: row
        for row in db.query(models.Person).filter(models.Person.id.in_([a.person_id for a in rows if a.person_id])).all()
    } if rows else {}
    return [_account_to_dict(row, person_map.get(row.person_id)) for row in rows]


@router.get("/legacy-audit")
def legacy_audit(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    legacy_users = get_legacy_password_file_users()
    account_rows = {
        row.username: row
        for row in db.query(models.Account).filter(models.Account.username.in_(legacy_users.keys())).all()
    } if legacy_users else {}
    person_ids = [row.person_id for row in account_rows.values() if row.person_id]
    person_map = {
        row.id: row
        for row in db.query(models.Person).filter(models.Person.id.in_(person_ids)).all()
    } if person_ids else {}

    return {
        "legacy_password_login_enabled": legacy_password_login_enabled(),
        "legacy_accounts": [
            {
                "username": username,
                "has_account": username in account_rows,
                "account_status": account_rows[username].status if username in account_rows else "",
                "person_id": account_rows[username].person_id if username in account_rows else None,
                "person_name": person_map.get(account_rows[username].person_id).name
                if username in account_rows and account_rows[username].person_id in person_map
                else "",
                "bound_to_person": bool(username in account_rows and account_rows[username].person_id),
            }
            for username in sorted(legacy_users.keys())
        ],
    }


@router.post("")
def create_account(
    payload: AccountCreateRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    username = payload.username.strip()
    try:
        validate_password_policy(username, payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if db.query(models.Account).filter(models.Account.username == username).first():
        raise HTTPException(400, "账号已存在")

    person = db.get(models.Person, payload.person_id) if payload.person_id else None
    if payload.person_id and not person:
        raise HTTPException(404, "person not found")

    # 绑定 person 时，is_tech_admin 由 person.system_role 推导，不直接相信前端传值
    if person:
        is_tech_admin = normalize_system_role(person.system_role) == ROLE_SUPER_ADMIN or bool(person.is_admin)
        person.is_admin = is_tech_admin
    else:
        is_tech_admin = bool(payload.is_tech_admin)
    now = utc_now()
    row = models.Account(
        username=username,
        password_hash=hash_password(payload.password),
        person_id=person.id if person else None,
        status="active",
        is_tech_admin=is_tech_admin,
        must_change_password=bool(payload.must_change_password),
        last_password_changed_at=now,
    )
    db.add(row)
    db.flush()
    crud.log(db, current_user, "create", "account", row.id, after=_account_to_dict(row, person))
    db.commit()
    db.refresh(row)
    return _account_to_dict(row, person)


@router.post("/{account_id}/reset-password")
def reset_password(
    account_id: int,
    payload: AccountResetPasswordRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Account, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    try:
        validate_password_policy(row.username, payload.password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    target_username = row.username
    row.password_hash = hash_password(payload.password)
    row.failed_login_count = 0
    row.locked_until = None
    row.must_change_password = True  # 管理员重置后要求用户下次登录改密
    row.status = "active"
    row.last_password_changed_at = utc_now()
    crud.log(db, current_user, "reset_password", "account", row.id, before=before, after=_account_to_dict(row))
    db.commit()
    # 清除被重置账号的所有旧 session
    invalidate_user_sessions(target_username)
    return {"ok": True}


@router.patch("/{account_id}/status")
def patch_status(
    account_id: int,
    payload: AccountStatusRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Account, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    if row.username == current_user and payload.status != "active":
        raise HTTPException(400, "不能禁用当前登录账号")
    before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    row.status = payload.status
    crud.log(db, current_user, "update_status", "account", row.id, before=before, after=_account_to_dict(row))
    db.commit()
    return _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)


class ChangeMyPasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if not v or len(v.strip()) < 6:
            raise ValueError("新密码至少 6 位")
        return v.strip()


@router.post("/me/change-password")
def change_my_password(
    payload: ChangeMyPasswordRequest,
    request: Request,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    from ..settings import get_settings

    row = db.query(models.Account).filter(models.Account.username == current_user).first()
    if not row:
        raise HTTPException(404, "账号不存在")
    if not _check_password(payload.old_password, row.password_hash or ""):
        raise HTTPException(400, "原密码错误")
    if payload.old_password == payload.new_password:
        raise HTTPException(400, "新密码不能与原密码相同")

    try:
        validate_password_policy(current_user, payload.new_password, old_password=payload.old_password)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    row.password_hash = hash_password(payload.new_password)
    row.must_change_password = False
    row.failed_login_count = 0
    row.locked_until = None
    row.last_password_changed_at = utc_now()
    db.commit()

    # 清除该用户的其他所有 session（当前 session 从 cookie 中读取，保留）
    cookie_name = get_settings().session_cookie_name
    current_sid = request.cookies.get(cookie_name) if request else None
    invalidate_user_sessions(current_user, except_session_id=current_sid)
    return {"ok": True}


class AccountWecomBindRequest(BaseModel):
    wecom_userid: str

    @field_validator("wecom_userid")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("企业微信 ID 不能为空")
        return v.strip()


@router.put("/{account_id}/wecom")
def bind_wecom(
    account_id: int,
    payload: AccountWecomBindRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """绑定企业微信 userid 到账号。"""
    _require_admin(current_user, db)
    row = db.get(models.Account, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    wecom_userid = payload.wecom_userid.strip()
    # 唯一性校验：同一企微 ID 不能绑到多个账号
    existing = (
        db.query(models.Account)
        .filter(models.Account.wecom_userid == wecom_userid, models.Account.id != account_id)
        .first()
    )
    if existing:
        raise HTTPException(400, f"该企业微信 ID 已绑定到账号 {existing.username}")
    before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    row.wecom_userid = wecom_userid
    crud.log(db, current_user, "bind_wecom", "account", row.id, before=before, after=_account_to_dict(row))
    db.commit()
    return _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)


@router.delete("/{account_id}/wecom")
def unbind_wecom(
    account_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """解绑企业微信 userid。"""
    _require_admin(current_user, db)
    row = db.get(models.Account, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    row.wecom_userid = None
    crud.log(db, current_user, "unbind_wecom", "account", row.id, before=before, after=_account_to_dict(row))
    db.commit()
    return _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
