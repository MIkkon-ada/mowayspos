"""First-time system initialization.

Phase 1 keeps the existing /api/setup/status and /api/setup/init contract, but
the real initialization fact is now whether any tech-admin account exists.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from .. import models
from ..auth import hash_password, validate_password_policy
from ..database import get_db
from ..permissions import ROLE_SUPER_ADMIN

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _is_initialized(db: Session) -> bool:
    return db.query(models.Account).filter(models.Account.is_tech_admin == True).first() is not None


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return {"initialized": _is_initialized(db)}


class InitRequest(BaseModel):
    username: str
    password: str

    @field_validator("username", "password")
    @classmethod
    def not_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("required")
        return value.strip()

    @model_validator(mode="after")
    def password_policy(self):
        try:
            validate_password_policy(self.username, self.password)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


@router.post("/init")
def init(payload: InitRequest, db: Session = Depends(get_db)):
    if _is_initialized(db):
        raise HTTPException(409, "系统已初始化，不可重复执行")

    person = models.Person(
        name=payload.username,
        system_role=ROLE_SUPER_ADMIN,
        is_admin=True,
        permission="管理",
        is_active=True,
    )
    db.add(person)
    db.flush()

    db.add(
        models.Account(
            username=payload.username,
            password_hash=hash_password(payload.password),
            person_id=person.id,
            status="active",
            is_tech_admin=True,
            last_password_changed_at=person.created_at,
        )
    )
    db.commit()
    return {"ok": True}
