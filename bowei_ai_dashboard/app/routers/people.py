import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models, schemas
from ..database import get_db
from ..permissions import ROLE_CEO, ROLE_NORMAL, ROLE_SUPER_ADMIN, ensure_default_projects, get_current_user_name, get_user_context_from_db, normalize_system_role, system_role_label

router = APIRouter(prefix="/api/people", tags=["people"])


def _require_admin(current_user: str, db: Session):
    ctx = get_user_context_from_db(current_user, db)
    if not ctx["is_tech_admin"]:
        raise HTTPException(403, "浠呮妧鏈鐞嗗憳鍙墽琛屾鎿嶄綔")


def _split_names(value) -> list[str]:
    if isinstance(value, list):
        source = "、".join(str(item or "").strip() for item in value if str(item or "").strip())
    else:
        source = str(value or "").strip()
    if not source:
        return []
    return [item.strip() for item in re.split(r"[,，、/;\n]+", source) if item.strip()]


def _join_names(names: list[str]) -> str:
    seen = []
    for name in names:
        text = str(name or "").strip()
        if text and text not in seen:
            seen.append(text)
    return "、".join(seen)


def _payload_project_sets(payload: schemas.PersonPayload) -> tuple[list[str], list[str], list[str]]:
    coordinated = list(dict.fromkeys(payload.coordinated_projects or []))
    owned = [name for name in dict.fromkeys(payload.owned_projects or []) if name not in coordinated]
    collaborated = [
        name for name in dict.fromkeys(payload.collaborated_projects or [])
        if name not in coordinated and name not in owned
    ]
    return coordinated, owned, collaborated


def _all_assigned_projects(coordinated: list[str], owned: list[str], collaborated: list[str]) -> str:
    return "、".join(dict.fromkeys([*coordinated, *owned, *collaborated]))


def _rebuild_person_duties(db: Session):
    # 从 project_members 正规表读取，而非旧字符串字段（单源真相）
    members = (
        db.query(models.ProjectMember)
        .join(models.Project, models.ProjectMember.project_id == models.Project.id)
        .filter(models.Project.status != "archived")
        .all()
    )
    person_projects: dict[int, set[str]] = {}
    project_cache: dict[int, str] = {}
    for m in members:
        if m.project_id not in project_cache:
            proj = db.get(models.Project, m.project_id)
            project_cache[m.project_id] = proj.name if proj else ""
        proj_name = project_cache[m.project_id]
        if proj_name:
            person_projects.setdefault(m.person_id, set()).add(proj_name)

    for person in db.query(models.Person).all():
        assigned = sorted(person_projects.get(person.id, set()))
        person.special_project_duty = "、".join(assigned) if assigned else ""


def _sync_person_assignments(
    db: Session,
    person_name: str,
    coordinated_projects: list[str],
    owned_projects: list[str],
    collaborated_projects: list[str],
):
    projects = db.query(models.Project).all()
    for project in projects:
        if project.coordinator == person_name:
            project.coordinator = ""

        owners = [name for name in _split_names(project.owners) if name != person_name]
        collaborators = [name for name in _split_names(project.collaborators) if name != person_name]

        if project.name in coordinated_projects:
            project.coordinator = person_name
        if project.name in owned_projects:
            owners.append(person_name)
        if project.name in collaborated_projects:
            collaborators.append(person_name)

        project.owners = _join_names(owners)
        project.collaborators = _join_names(collaborators)

    # 同步到 project_members 正式表（解决旧字段有记录但 project_members 缺失的问题）
    person = db.query(models.Person).filter(models.Person.name == person_name).first()
    if person:
        managed_roles = ["coordinator", "owner", "member"]
        db.query(models.ProjectMember).filter(
            models.ProjectMember.person_id == person.id,
            models.ProjectMember.role.in_(managed_roles),
        ).delete(synchronize_session=False)

        for project in projects:
            entries: list[tuple[str, str]] = []
            if project.name in coordinated_projects:
                entries.append(("coordinator", person_name))
            if project.name in owned_projects:
                entries.append(("owner", person_name))
            if project.name in collaborated_projects:
                entries.append(("member", person_name))
            for role, snapshot in entries:
                db.add(models.ProjectMember(
                    project_id=project.id,
                    person_id=person.id,
                    person_name_snapshot=snapshot,
                    role=role,
                ))

    _rebuild_person_duties(db)


def _detach_person_from_projects(db: Session, person_name: str):
    projects = db.query(models.Project).all()
    for project in projects:
        if project.coordinator == person_name:
            project.coordinator = ""
        project.owners = _join_names([name for name in _split_names(project.owners) if name != person_name])
        project.collaborators = _join_names([name for name in _split_names(project.collaborators) if name != person_name])

    # 同步清理 project_members 表
    person = db.query(models.Person).filter(models.Person.name == person_name).first()
    if person:
        db.query(models.ProjectMember).filter(
            models.ProjectMember.person_id == person.id,
        ).delete(synchronize_session=False)

    _rebuild_person_duties(db)


def _normalize_system_role(role: str | None) -> str:
    """归一化系统角色，兼容旧中文值，非法值回落为普通成员。"""
    return normalize_system_role(role) or ROLE_NORMAL


def _person_to_dict(row) -> dict:
    """序列化 Person，附带 system_role_label 中文展示名。"""
    d = crud.to_dict(row)
    d["system_role_label"] = system_role_label(d.get("system_role") or "")
    return d


def _is_super_admin_role(system_role: str | None) -> bool:
    return (system_role or "").strip() == ROLE_SUPER_ADMIN


def _sync_person_admin_mirrors(db: Session, person: models.Person):
    """根据 person.system_role 同步镜像字段：
    - person.is_admin
    - 该 person 绑定的所有 accounts.is_tech_admin
    超级管理员 -> True；其余 -> False。
    """
    is_super = _is_super_admin_role(person.system_role)
    person.is_admin = is_super
    if person.id is not None:
        accounts = db.query(models.Account).filter(models.Account.person_id == person.id).all()
        for acc in accounts:
            acc.is_tech_admin = is_super


@router.get("/me")
def me(current_user: str = Depends(get_current_user_name), db: Session = Depends(get_db)):
    context = get_user_context_from_db(current_user, db)
    account = db.query(models.Account).filter(models.Account.username == current_user).first()
    return {
        "account_id": account.id if account else None,
        "person_id": context.get("person_id"),
        "username": current_user,
        "name": context["name"],
        "is_ceo": context["is_ceo"],
        "is_tech_admin": context["is_tech_admin"],
        "is_coordinator": context["is_coordinator"],
        "role_scope": context.get("role_scope", ""),
        "can_view_all": context["can_view_all"],
        "can_confirm_all": context["can_confirm_all"],
        "can_assign_all": context["can_assign_all"],
        "can_view_settings": context.get("can_view_settings", False),
        "can_view_confirmation_center": context.get("can_view_confirmation_center", False),
        "can_view_approval_reminders": context.get("can_view_approval_reminders", False),
        "can_view_decision_items": context.get("can_view_decision_items", False),
        "can_view_risk_items": context.get("can_view_risk_items", False),
        "can_view_issue_decisions": context.get("can_view_issue_decisions", False),
        "can_view_issue_risks": context.get("can_view_issue_risks", False),
        "can_view_progress": context.get("can_view_progress", True),
        "visible_projects": context["visible_projects"],
        "owned_projects": context["owned_projects"],
        "coordinated_projects": context["coordinated_projects"],
        "collaborated_projects": context["collaborated_projects"],
        "project_roles": context.get("project_roles", {}),
        "system_role": context["system_role"],
        "must_change_password": bool(account.must_change_password) if account else False,
    }


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    ensure_default_projects(db)
    projects = db.query(models.Project).filter(models.Project.status != "archived").order_by(models.Project.sort_order, models.Project.id).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "coordinator": row.coordinator or "",
            "owners": _split_names(row.owners),
            "collaborators": _split_names(row.collaborators),
            "sort_order": row.sort_order or 0,
            "is_active": row.is_active,
        }
        for row in projects
    ]


@router.post("/projects")
def create_project(
    payload: schemas.ProjectPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    if db.query(models.Project).filter_by(name=payload.name.strip()).first():
        raise HTTPException(400, "涓撻」鍚嶇О宸插瓨鍦?")
    row = models.Project(
        name=payload.name.strip(),
        coordinator=payload.coordinator.strip(),
        owners=_join_names(payload.owners),
        collaborators=_join_names(payload.collaborators),
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(row)
    db.flush()
    _rebuild_person_duties(db)
    crud.log(db, current_user, "create", "project", row.id, after=crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "name": row.name,
        "coordinator": row.coordinator,
        "owners": _split_names(row.owners),
        "collaborators": _split_names(row.collaborators),
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


@router.put("/projects/{project_id}")
def update_project(
    project_id: int,
    payload: schemas.ProjectPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Project, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    duplicate = db.query(models.Project).filter(models.Project.name == payload.name.strip(), models.Project.id != project_id).first()
    if duplicate:
        raise HTTPException(400, "涓撻」鍚嶇О宸插瓨鍦?")
    before = crud.to_dict(row)
    row.name = payload.name.strip()
    row.coordinator = payload.coordinator.strip()
    row.owners = _join_names(payload.owners)
    row.collaborators = _join_names(payload.collaborators)
    row.sort_order = payload.sort_order
    row.is_active = payload.is_active
    _rebuild_person_duties(db)
    crud.log(db, current_user, "update", "project", row.id, before=before, after=crud.to_dict(row))
    db.commit()
    return {
        "id": row.id,
        "name": row.name,
        "coordinator": row.coordinator,
        "owners": _split_names(row.owners),
        "collaborators": _split_names(row.collaborators),
        "sort_order": row.sort_order,
        "is_active": row.is_active,
    }


@router.delete("/projects/{project_id}")
def delete_project(
    project_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Project, project_id)
    if not row:
        raise HTTPException(404, "project not found")
    before = crud.to_dict(row)
    db.delete(row)
    _rebuild_person_duties(db)
    crud.log(db, current_user, "delete", "project", project_id, before=before)
    db.commit()
    return {"ok": True}


@router.post("/batch")
def batch_create_people(
    payload: schemas.PersonBatchPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    """批量导入人员，已存在的姓名跳过不报错。"""
    _require_admin(current_user, db)
    created, skipped_names = [], []
    for item in payload.people:
        name = (item.name or "").strip()
        if not name:
            continue
        if db.query(models.Person).filter_by(name=name).first():
            skipped_names.append(name)
            continue
        system_role = _normalize_system_role(item.system_role)
        row = models.Person(
            name=name,
            role=item.role,
            system_role=system_role,
            department=item.department,
            contact=item.contact,
            permission="查看",
            is_active=True,
            is_admin=_is_super_admin_role(system_role),
        )
        db.add(row)
        db.flush()
        _sync_person_admin_mirrors(db, row)
        crud.log(db, current_user, "batch_create", "person", row.id, after={"name": name})
        created.append(name)
    db.commit()
    return {"created": len(created), "skipped": len(skipped_names), "skipped_names": skipped_names, "created_names": created}


@router.get("")
def list_people(db: Session = Depends(get_db)):
    rows = db.query(models.Person).order_by(models.Person.is_active.desc(), models.Person.id.asc()).all()
    return [_person_to_dict(row) for row in rows]


@router.post("")
def create_person(
    payload: schemas.PersonPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    if db.query(models.Person).filter_by(name=payload.name.strip()).first():
        raise HTTPException(400, "浜哄憳宸插瓨鍦?")
    coordinated, owned, collaborated = _payload_project_sets(payload)
    system_role = _normalize_system_role(payload.system_role)
    row = models.Person(
        name=payload.name.strip(),
        role=payload.role,
        system_role=system_role,
        department=payload.department,
        special_project_duty=_all_assigned_projects(coordinated, owned, collaborated) or payload.special_project_duty,
        permission=payload.permission,
        contact=payload.contact,
        is_active=payload.is_active,
        is_admin=_is_super_admin_role(system_role),
    )
    db.add(row)
    db.flush()
    _sync_person_admin_mirrors(db, row)
    _sync_person_assignments(db, row.name, coordinated, owned, collaborated)
    crud.log(db, current_user, "create", "person", row.id, after=crud.to_dict(row))
    db.commit()
    db.refresh(row)
    return _person_to_dict(row)


@router.get("/{row_id}")
def get_person(row_id: int, db: Session = Depends(get_db)):
    row = db.get(models.Person, row_id)
    if not row:
        raise HTTPException(404, "person not found")
    return _person_to_dict(row)


@router.put("/{row_id}")
def update_person(
    row_id: int,
    payload: schemas.PersonPayload,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Person, row_id)
    if not row:
        raise HTTPException(404, "person not found")
    duplicate = db.query(models.Person).filter(models.Person.name == payload.name.strip(), models.Person.id != row_id).first()
    if duplicate:
        raise HTTPException(400, "浜哄憳鍚嶇О宸插瓨鍦?")
    before = crud.to_dict(row)
    old_name = row.name
    coordinated, owned, collaborated = _payload_project_sets(payload)
    row.name = payload.name.strip()
    row.role = payload.role
    new_system_role = _normalize_system_role(payload.system_role)
    # 禁止降级最后一个超级管理员，防止锁死系统
    if _is_super_admin_role(row.system_role) and not _is_super_admin_role(new_system_role):
        other_supers = db.query(models.Person).filter(
            models.Person.system_role == ROLE_SUPER_ADMIN,
            models.Person.is_active == True,
            models.Person.id != row_id,
        ).count()
        if other_supers == 0:
            raise HTTPException(409, "不能降级最后一个超级管理员，请先提升其他人为超级管理员")
    row.system_role = new_system_role
    row.department = payload.department
    row.permission = payload.permission
    row.contact = payload.contact
    row.is_active = payload.is_active
    row.is_admin = _is_super_admin_role(row.system_role)
    row.special_project_duty = _all_assigned_projects(coordinated, owned, collaborated) or payload.special_project_duty
    _sync_person_admin_mirrors(db, row)
    if old_name != row.name:
        _detach_person_from_projects(db, old_name)
    _sync_person_assignments(db, row.name, coordinated, owned, collaborated)
    crud.log(db, current_user, "update", "person", row.id, before=before, after=crud.to_dict(row))
    db.commit()
    return _person_to_dict(row)


@router.delete("/{row_id}")
def delete_person(
    row_id: int,
    current_user: str = Depends(get_current_user_name),
    db: Session = Depends(get_db),
):
    _require_admin(current_user, db)
    row = db.get(models.Person, row_id)
    if not row:
        raise HTTPException(404, "person not found")
    # 防断链：存在绑定账号或项目成员关系时禁止删除
    bound_accounts = db.query(models.Account).filter(models.Account.person_id == row_id).count()
    if bound_accounts:
        raise HTTPException(409, "该人员绑定了登录账号，请先禁用或删除相关账号")
    bound_members = db.query(models.ProjectMember).filter(models.ProjectMember.person_id == row_id).count()
    if bound_members:
        raise HTTPException(409, "该人员存在于项目成员中，请先从项目成员移除")
    before = crud.to_dict(row)
    _detach_person_from_projects(db, row.name)
    db.delete(row)
    crud.log(db, current_user, "delete", "person", row_id, before=before)
    db.commit()
    return {"ok": True}
