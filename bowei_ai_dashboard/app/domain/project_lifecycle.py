"""Canonical project lifecycle states and close-flow helpers."""

S_DRAFT = "draft"
S_DISPATCHED = "dispatched"
S_PENDING_REVIEW = "pending_review"
S_PENDING_KICKOFF = "pending_kickoff"
S_RETURNED = "returned"
S_ACTIVE = "active"
S_PENDING_CLOSE = "pending_close"
S_ENDED = "ended"
S_ARCHIVED = "archived"

ALL_STATUSES = {
    S_DRAFT,
    S_DISPATCHED,
    S_PENDING_REVIEW,
    S_PENDING_KICKOFF,
    S_RETURNED,
    S_ACTIVE,
    S_PENDING_CLOSE,
    S_ENDED,
    S_ARCHIVED,
}

CLOSE_FROZEN_STATUSES = {S_PENDING_CLOSE, S_ENDED}

# ``pending_kickoff`` and ``dispatched`` are retained in the compatibility
# vocabulary because older projects may still carry them in the database. New
# transitions must not use either state as a lifecycle gate.
EXECUTION_AVAILABLE_STATUSES = {S_ACTIVE, S_PENDING_KICKOFF, S_DISPATCHED}
OWNER_PLAN_EDITABLE_STATUSES = {S_DISPATCHED, S_RETURNED}


def normalize(value: object, default: str = S_DRAFT) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in ALL_STATUSES else default


def is_close_frozen(value: object) -> bool:
    return normalize(value) in CLOSE_FROZEN_STATUSES


def is_archived(value: object) -> bool:
    return normalize(value) == S_ARCHIVED


def is_execution_available(value: object) -> bool:
    """Whether execution data can be edited for current or legacy projects."""
    return normalize(value) in EXECUTION_AVAILABLE_STATUSES


def is_owner_plan_editable(value: object) -> bool:
    """Whether the owner can complete or resubmit the project plan."""
    return normalize(value) in OWNER_PLAN_EDITABLE_STATUSES
