"""Identity-safe lookup helpers for business records with legacy name fields."""

from sqlalchemy import and_, false, or_
from sqlalchemy.orm import Session

from .. import models


def unique_active_person_id_for_name(db: Session, name: str | None) -> int | None:
    normalized = (name or "").strip()
    if not normalized:
        return None
    rows = (
        db.query(models.Person.id)
        .filter(models.Person.name == normalized, models.Person.is_active.is_(True))
        .limit(2)
        .all()
    )
    return int(rows[0][0]) if len(rows) == 1 else None


def legacy_person_identity_values(
    db: Session,
    *,
    person_id: int | None,
    person_name: str | None,
    account_username: str | None = None,
) -> set[str]:
    """Return safe legacy strings for one person, rejecting ambiguous name/account collisions."""
    if person_id is None:
        return set()
    values: set[str] = set()
    normalized_name = (person_name or "").strip()
    if normalized_name and unique_active_person_id_for_name(db, normalized_name) == person_id:
        values.add(normalized_name)

    username = (account_username or "").strip()
    if username:
        account = db.query(models.Account.person_id).filter(
            models.Account.username == username,
            models.Account.status == "active",
        ).first()
        if account and account[0] is not None and int(account[0]) == int(person_id):
            name_rows = (
                db.query(models.Person.id)
                .filter(models.Person.name == username, models.Person.is_active.is_(True))
                .limit(2)
                .all()
            )
            if not name_rows or (len(name_rows) == 1 and int(name_rows[0][0]) == int(person_id)):
                values.add(username)
    return values


def person_identity_scope(
    db: Session,
    *,
    person_id: int | None,
    person_name: str | None,
    id_column,
    name_column,
    account_username: str | None = None,
):
    """Match a stable person ID, or a legacy name only when it uniquely identifies that person."""
    if person_id is None:
        return false()
    clauses = [id_column == person_id]
    legacy_values = legacy_person_identity_values(
        db,
        person_id=person_id,
        person_name=person_name,
        account_username=account_username,
    )
    if legacy_values:
        clauses.append(and_(id_column.is_(None), name_column.in_(legacy_values)))
    return or_(*clauses)


def person_identity_matches(
    db: Session,
    *,
    person_id: int | None,
    person_name: str | None,
    stored_person_id: int | None,
    stored_name: str | None,
    account_username: str | None = None,
) -> bool:
    if person_id is None:
        return False
    if stored_person_id == person_id:
        return True
    legacy_values = legacy_person_identity_values(
        db,
        person_id=person_id,
        person_name=person_name,
        account_username=account_username,
    )
    return bool(
        stored_person_id is None
        and (stored_name or "").strip() in legacy_values
    )
