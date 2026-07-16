"""Canonical project lifecycle states and close-flow helpers."""

S_DRAFT = "draft"
S_DISPATCHED = "dispatched"
S_PENDING_REVIEW = "pending_review"
S_RETURNED = "returned"
S_ACTIVE = "active"
S_PENDING_CLOSE = "pending_close"
S_ENDED = "ended"
S_ARCHIVED = "archived"

ALL_STATUSES = {
    S_DRAFT,
    S_DISPATCHED,
    S_PENDING_REVIEW,
    S_RETURNED,
    S_ACTIVE,
    S_PENDING_CLOSE,
    S_ENDED,
    S_ARCHIVED,
}

CLOSE_FROZEN_STATUSES = {S_PENDING_CLOSE, S_ENDED}


def normalize(value: object, default: str = S_DRAFT) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALL_STATUSES else default


def is_close_frozen(value: object) -> bool:
    return normalize(value) in CLOSE_FROZEN_STATUSES


def is_archived(value: object) -> bool:
    return normalize(value) == S_ARCHIVED
