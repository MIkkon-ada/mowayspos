from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from .. import crud, models
from ..auth import hash_password, invalidate_user_sessions, _check_password, validate_password_policy
from ..database import get_db
from ..permissions import get_current_user_name, require_tech_admin, ROLE_SUPER_ADMIN, normalize_system_role
from ..time_utils import utc_now
from ..settings import get_legacy_password_file_users, legacy_password_login_enabled, get_settings
from ..services import wecom

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


class AccountUpdateRequest(BaseModel):
    username: str

    @field_validator("username")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("账号名不能为空")
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


@router.patch("/{account_id}")
def update_account(
    account_id: int,
    payload: AccountUpdateRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """更新账号基本信息（如 username）。"""
    _require_admin(current_user, db)
    row = db.get(models.Account, account_id)
    if not row:
        raise HTTPException(404, "account not found")
    new_username = payload.username.strip()
    if len(new_username) > 100:
        raise HTTPException(400, "账号名不能超过100个字符")
    # 唯一性校验
    dup = db.query(models.Account).filter(
        models.Account.username == new_username,
        models.Account.id != account_id,
    ).first()
    if dup:
        raise HTTPException(400, f"账号名 '{new_username}' 已存在")
    if row.username == new_username:
        # unchanged, just return current state
        return _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
    old_username = row.username
    row.username = new_username
    crud.log(db, current_user, "update_username", "account", row.id,
             before=before, after=_account_to_dict(row))
    db.commit()
    db.refresh(row)
    # 清除被改名账号的所有 session
    invalidate_user_sessions(old_username)
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


# === 企微通讯录批量绑定 ===


@router.get("/wecom-users")
def list_wecom_users(
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """拉取企业微信通讯录，附带本地账号的绑定情况。

    返回每个企微成员及其在本地账号中的绑定状态，前端用来做批量绑定 UI。

    自动匹配建议：若 person.name 与企微 name 完全一致，preselect_account_id 自动填上，
    前端可一键「应用推荐」。
    """
    _require_admin(current_user, db)
    if not get_settings().wecom_enabled:
        raise HTTPException(503, "wecom_login_disabled")

    try:
        wecom_users = wecom.list_department_users(department_id=1, fetch_child=True)
    except wecom.WecomError as e:
        raise HTTPException(502, str(e))

    # 本地账号索引：wecom_userid → account，name → account（用于自动推荐）
    accounts = db.query(models.Account).all()
    by_wecom_userid: dict[str, models.Account] = {
        a.wecom_userid: a for a in accounts if a.wecom_userid
    }
    persons = {p.id: p for p in db.query(models.Person).all()} if hasattr(models, "Person") else {}
    by_person_name: dict[str, models.Account] = {}
    for a in accounts:
        if a.person_id and a.person_id in persons:
            pname = persons[a.person_id].name
            if pname and pname not in by_person_name:
                by_person_name[pname] = a

    result = []
    for u in wecom_users:
        userid = u.get("userid") or ""
        name = u.get("name") or ""
        dept_ids = u.get("department") or []
        if not userid:
            continue
        bound = by_wecom_userid.get(userid)
        preselect_id = None
        preselect_username = ""
        if bound:
            preselect_id = bound.id
            preselect_username = bound.username
        elif name and name in by_person_name:
            # 按 Person.name 自动推荐
            preselect_id = by_person_name[name].id
            preselect_username = by_person_name[name].username
        result.append({
            "wecom_userid": userid,
            "wecom_name": name,
            "department_ids": dept_ids,
            "bound_account_id": bound.id if bound else None,
            "bound_username": bound.username if bound else "",
            "preselect_account_id": preselect_id,
            "preselect_username": preselect_username,
        })
    return result


class WecomBatchBindItem(BaseModel):
    account_id: int
    wecom_userid: str


class WecomBatchBindRequest(BaseModel):
    items: list[WecomBatchBindItem]


@router.post("/wecom-bind-batch")
def batch_bind_wecom(
    payload: WecomBatchBindRequest,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """批量绑定企微 userid 到账号。

    - 校验每个 wecom_userid 唯一性（同一 ID 不能绑到多个账号）
    - 一次事务提交，任意一条失败全部回滚
    """
    _require_admin(current_user, db)
    if not get_settings().wecom_enabled:
        raise HTTPException(503, "wecom_login_disabled")

    items = payload.items
    if not items:
        raise HTTPException(400, "items is empty")

    # 预校验：account_id 必须存在；wecom_userid 不能在本次批次内重复
    seen_userids: set[str] = set()
    account_ids = {it.account_id for it in items}
    accounts = db.query(models.Account).filter(models.Account.id.in_(account_ids)).all()
    account_map = {a.id: a for a in accounts}
    for it in items:
        if it.account_id not in account_map:
            raise HTTPException(400, f"account {it.account_id} not found")
        if it.wecom_userid in seen_userids:
            raise HTTPException(400, f"wecom_userid {it.wecom_userid} duplicated in batch")
        seen_userids.add(it.wecom_userid)

    # 校验：wecom_userid 不能已被本次批次外的账号绑定
    existing = (
        db.query(models.Account)
        .filter(models.Account.wecom_userid.in_(seen_userids))
        .all()
    )
    for a in existing:
        if a.id not in account_map:
            raise HTTPException(400, f"wecom_userid {a.wecom_userid} already bound to {a.username}")

    # 应用绑定
    for it in items:
        row = account_map[it.account_id]
        before = _account_to_dict(row, db.get(models.Person, row.person_id) if row.person_id else None)
        row.wecom_userid = it.wecom_userid
        crud.log(db, current_user, "batch_bind_wecom", "account", row.id, before=before, after=_account_to_dict(row))

    db.commit()
    # 返回更新后的账号列表
    updated_ids = list(account_map.keys())
    updated = db.query(models.Account).filter(models.Account.id.in_(updated_ids)).all()
    return [
        _account_to_dict(a, db.get(models.Person, a.person_id) if a.person_id else None)
        for a in updated
    ]
