"""
通知内核 —— 写入站内通知，后期可在此叠加企业微信/钉钉等渠道。
所有调用方在同一个 db 事务里调用 send()，由调用方负责 commit。

recipient 字段迁移说明：
  旧版：send(recipient="人名或账号名")  → 存入 notifications.recipient
  新版：send(recipient_id=person_id)    → 存入 notifications.recipient_id（首选）
  过渡期两个参数可并存；查询端优先走 recipient_id。
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .. import models
from ..permissions import ROLE_CEO


# ── person_id 解析工具 ─────────────────────────────────────────

def person_id_for_name(name: str, db: Session) -> int | None:
    """person.name → person.id（精确匹配，活跃人员）。"""
    if not name or not name.strip():
        return None
    try:
        row = db.execute(
            text("SELECT id FROM people WHERE name=:n AND is_active=1"),
            {"n": name.strip()},
        ).fetchone()
        return int(row[0]) if row else None
    except Exception:
        return None


def person_id_for_account(username: str, db: Session) -> int | None:
    """account.username → person.id。"""
    if not username or not username.strip():
        return None
    try:
        row = db.execute(
            text("SELECT person_id FROM accounts WHERE username=:u AND status='active'"),
            {"u": username.strip()},
        ).fetchone()
        return int(row[0]) if row and row[0] else None
    except Exception:
        return None


def person_name_for_account(username: str, db: Session) -> str:
    """Account.username → Person.name，找不到时返回 username 本身。"""
    acc = db.query(models.Account).filter(models.Account.username == username).first()
    if acc and acc.person_id:
        person = db.get(models.Person, acc.person_id)
        if person and person.name:
            return person.name
    return username


# ── 发送 ──────────────────────────────────────────────────────

def send(
    db: Session,
    *,
    recipient: str = "",
    recipient_id: int | None = None,
    ntype: str,
    title: str,
    body: str = "",
    link: str = "",
    project_id: int | None = None,
) -> None:
    """
    写入一条站内通知。

    参数：
      recipient_id  优先：person.id，查询时走索引，不受改名影响
      recipient     兼容：person.name 或 account.username（旧调用方过渡期使用）

    两者至少提供其一；都提供时 recipient_id 用于查询，recipient 作为展示备份。
    """
    if not recipient_id and not recipient:
        return
    n = models.Notification(
        recipient=recipient or "",
        recipient_id=recipient_id,
        type=ntype,
        title=title,
        body=body,
        link=link,
        project_id=project_id,
    )
    db.add(n)


# ── 批量收件人查询 ────────────────────────────────────────────

def project_owner_ids(project_id: int, db: Session) -> list[int]:
    """返回项目所有 owner/coordinator 的 person_id 列表。"""
    members = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.role.in_(["owner", "coordinator"]),
        )
        .all()
    )
    return [m.person_id for m in members if m.person_id]


def company_ceo_person_ids(db: Session) -> list[int]:
    """返回系统层 company_ceo 的 person_id 列表（去重）。"""
    ids: list[int] = []
    seen: set[int] = set()

    for person in db.query(models.Person).filter(
        models.Person.system_role == ROLE_CEO,
        models.Person.is_active == True,
    ).all():
        if person.id not in seen:
            seen.add(person.id)
            ids.append(person.id)

    return ids


def project_coach_person_ids(project_id: int, db: Session) -> list[int]:
    """返回当前项目内 project_ceo 的 person_id 列表（去重）。"""
    ids: list[int] = []
    seen: set[int] = set()
    members = (
        db.query(models.ProjectMember)
        .filter(
            models.ProjectMember.project_id == project_id,
            models.ProjectMember.role == "project_ceo",
        )
        .all()
    )
    for member in members:
        if member.person_id and member.person_id not in seen:
            seen.add(member.person_id)
            ids.append(member.person_id)
    return ids


def ceo_person_ids(db: Session) -> list[int]:
    """兼容旧调用方的 company_ceo 收件人查询别名。"""
    return company_ceo_person_ids(db)

