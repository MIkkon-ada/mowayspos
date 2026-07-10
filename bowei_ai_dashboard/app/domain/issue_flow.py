TYPE_ISSUE = "问题"
TYPE_RISK = "风险"
TYPE_COORDINATE = "待协调"
TYPE_DECISION = "需决策"

ALL_TYPES = [TYPE_ISSUE, TYPE_RISK, TYPE_COORDINATE, TYPE_DECISION]

STATUS_PENDING = "待处理"
STATUS_IN_PROGRESS = "处理中"
STATUS_PENDING_DECISION = "待决策"
STATUS_RESOLVED = "已解决"
STATUS_CLOSED = "已关闭"

ALL_STATUSES = [STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_PENDING_DECISION, STATUS_RESOLVED, STATUS_CLOSED]

_TYPE_MAP: dict[str, str] = {
    "决策": TYPE_DECISION,
    "需决策": TYPE_DECISION,
    "决策事项": TYPE_DECISION,
    "需CEO决策": TYPE_DECISION,
    "待CEO决策": TYPE_DECISION,
    "协调": TYPE_COORDINATE,
    "需协调": TYPE_COORDINATE,
    "待协调": TYPE_COORDINATE,
    "风险": TYPE_RISK,
    "问题": TYPE_ISSUE,
}

_STATUS_MAP: dict[str, str] = {
    "已决策": STATUS_RESOLVED,
    "完成": STATUS_RESOLVED,
    "已完成": STATUS_RESOLVED,
    "已解决": STATUS_RESOLVED,
    "关闭": STATUS_CLOSED,
    "已关闭": STATUS_CLOSED,
    "待CEO决策": STATUS_PENDING_DECISION,
    "待决策": STATUS_PENDING_DECISION,
    "处理中": STATUS_IN_PROGRESS,
    "处理": STATUS_IN_PROGRESS,
    "待处理": STATUS_PENDING,
}


def normalize_type(value: str | None) -> str:
    v = (value or "").strip()
    return _TYPE_MAP.get(v, TYPE_ISSUE)


def normalize_status(value: str | None) -> str:
    v = (value or "").strip()
    return _STATUS_MAP.get(v, STATUS_PENDING)


def default_status_for_type(issue_type: str | None) -> str:
    if normalize_type(issue_type) == TYPE_DECISION:
        return STATUS_PENDING_DECISION
    return STATUS_PENDING
