from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy.orm import Session

from .. import models
from .meeting_traceability import normalize_action_items_json


_SNAPSHOT_FIELDS = (
    "related_special_project",
    "meeting_type",
    "title",
    "meeting_date",
    "host",
    "participants",
    "transcript_text",
    "summary",
    "task_list_json",
    "decision_items_json",
    "risk_items_json",
    "publish_status",
)


def _snapshot_values(meeting: models.Meeting, changes: Mapping[str, object] | None = None) -> dict[str, object]:
    values = {field: getattr(meeting, field) or "" for field in _SNAPSHOT_FIELDS}
    for field, value in (changes or {}).items():
        if field in _SNAPSHOT_FIELDS and field != "transcript_text":
            values[field] = value if value is not None else ""
    values["task_list_json"] = normalize_action_items_json(
        str(values["task_list_json"] or "[]"),
        str(values["transcript_text"] or ""),
    )
    return values


def _add_revision(
    db: Session,
    meeting: models.Meeting,
    values: dict[str, object],
    *,
    version_no: int,
    saved_by: str,
    is_legacy_snapshot: bool,
) -> models.MeetingRevision:
    revision = models.MeetingRevision(
        meeting_id=meeting.id,
        version_no=version_no,
        saved_by=saved_by,
        is_legacy_snapshot=is_legacy_snapshot,
        **values,
    )
    db.add(revision)
    return revision


def append_meeting_revision(
    db: Session,
    meeting: models.Meeting,
    changes: Mapping[str, object] | None = None,
    *,
    saved_by: str = "",
    preserve_legacy: bool = False,
) -> models.MeetingRevision:
    """Append a full immutable snapshot and project it onto the current meeting row.

    ``preserve_legacy`` is used only when an existing pre-versioning row is first
    edited. The legacy snapshot is kept separate from numbered user revisions.
    The original transcript is intentionally never changed by ``changes``.
    """
    existing = (
        db.query(models.MeetingRevision)
        .filter(models.MeetingRevision.meeting_id == meeting.id)
        .order_by(models.MeetingRevision.version_no.desc(), models.MeetingRevision.id.desc())
        .all()
    )
    if preserve_legacy and not existing:
        _add_revision(
            db,
            meeting,
            _snapshot_values(meeting),
            version_no=0,
            saved_by=saved_by,
            is_legacy_snapshot=True,
        )
        existing = [object()]

    numbered = [row.version_no for row in existing if getattr(row, "version_no", -1) > 0]
    next_version = max(numbered, default=0) + 1
    values = _snapshot_values(meeting, changes)
    revision = _add_revision(
        db,
        meeting,
        values,
        version_no=next_version,
        saved_by=saved_by,
        is_legacy_snapshot=False,
    )
    for field, value in values.items():
        if field != "transcript_text":
            setattr(meeting, field, value)
    db.flush()
    return revision
