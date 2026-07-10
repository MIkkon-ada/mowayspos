"""
Submission 状态机 — 单一事实来源

所有接触 confirm_status 的代码都应从这里导入状态集合，
不再在各 router 里各自定义散 set / list。

## 生命周期状态图

  new submission
      │
      ▼
  PENDING_OWNER_REVIEW ◄──────────────────────────────────────────┐
  (待确认 / 待负责人审核)                                          │
      │                                                            │
      ├─── owner: reject ────────► RETURNED_TO_SUBMITTER          │
      │                             (已打回提交人)                  │
      │                                 │ submitter: resubmit      │
      │                                 └────────────────────────► │
      │                                                            │
      ├─── owner: transfer_coordinator ─► WAITING_COORDINATOR     │
      │                                   (已转交统筹人)            │
      │                                       │ coordinator: feedback│
      │                                       └─ COORDINATOR_GIVEN ─┘
      │                                         (统筹人已反馈)
      │
      ├─── owner: escalate_ceo ──────────► WAITING_CEO_DECISION
      │                                    (待CEO决策)
      │                                       │ project_ceo: decide
      │                                       └─ CEO_DECIDED ────► │
      │                                         (CEO已批示)        │
      │                                                            │
      ├─── owner: confirm ───────────────► CONFIRMED_AND_STORED
      │                                    (已入库)
      │
      ├─── owner: reject_final ──────────► PERMANENTLY_REJECTED
      │                                    (不入库)
      │
      └─── submitter: withdraw ──────────► WITHDRAWN
                                           (已撤回)

  NEEDS_REVISION (需修改) — 内部路由状态，
  流转完成后回到 PENDING_OWNER_REVIEW。

## 关键规则

- 状态集合只在这里定义，dashboard / confirmations / tests 都 import
- LEGACY_ALIASES 里的值只出现在历史数据里，不会被当前代码写入
- 统计口径：同一个 submission 不应同时出现在两个"等待"计数里
"""
from __future__ import annotations

# ─────────────────────────────────────────────────────────────────
# 当前代码写入数据库的规范状态值
# ─────────────────────────────────────────────────────────────────

S_NEW                       = "待确认"           # 新提交（updates.create_update）
S_PENDING_OWNER             = "待负责人审核"      # 重新提交后（resubmit）
S_RETURNED                  = "已打回提交人"      # owner reject
S_WITHDRAWN                 = "已撤回"            # submitter withdraw
S_PERMANENTLY_REJECTED      = "不入库"            # owner reject-final
S_WAITING_COORDINATOR       = "已转交统筹人"      # owner transfer-coordinator
S_COORDINATOR_GIVEN         = "统筹人已反馈"      # coordinator feedback
S_WAITING_CEO               = "待CEO决策"         # owner escalate-ceo
S_CEO_DECIDED               = "CEO已批示"         # project_ceo ceo-decide
S_CONFIRMED                 = "已入库"            # owner confirm
S_NEEDS_REVISION            = "需修改"            # 内部路由

# ─────────────────────────────────────────────────────────────────
# 历史别名（老版本写过，现在只在旧数据里存在）
# ─────────────────────────────────────────────────────────────────

LEGACY_ALIASES: dict[str, str] = {
    "pending_owner_review":       S_PENDING_OWNER,
    "resubmitted":                S_PENDING_OWNER,
    "returned_to_submitter":      S_RETURNED,
    "已打回":                     S_RETURNED,
    "withdrawn":                  S_WITHDRAWN,
    "withdrawn_editable":         S_WITHDRAWN,
    "transferred_to_coordinator": S_WAITING_COORDINATOR,
    "coordinator_feedback_given": S_COORDINATOR_GIVEN,
    "pending_ceo_decision":       S_WAITING_CEO,
    "ceo_decided":                S_CEO_DECIDED,
    "stored":                     S_CONFIRMED,
    "approved_for_storage":       S_CONFIRMED,
    "已确认入库":                 S_CONFIRMED,
    "已确认":                     S_CONFIRMED,
    "已归档":                     S_PERMANENTLY_REJECTED,
    "已退回":                     S_PERMANENTLY_REJECTED,
    "提交人已确认":               S_PENDING_OWNER,
    "已重新提交":                 S_PENDING_OWNER,
}


def normalize(status: str | None) -> str:
    """将历史别名规范化为当前规范状态值，未知值原样返回。"""
    raw = (status or "").strip()
    return LEGACY_ALIASES.get(raw, raw)


# ─────────────────────────────────────────────────────────────────
# 业务状态组（用于统计口径 & AI 确认中心 tab 过滤）
# 所有集合包含规范值 + 对应历史别名，保证旧数据也被正确归类。
# ─────────────────────────────────────────────────────────────────

# 等待负责人处理（包括 CEO 批示后回到负责人的状态）
PENDING_OWNER_REVIEW: frozenset[str] = frozenset({
    S_NEW,
    S_PENDING_OWNER,
    S_COORDINATOR_GIVEN,
    S_CEO_DECIDED,
    # legacy
    "pending_owner_review",
    "resubmitted",
    "提交人已确认",
    "已重新提交",
    "coordinator_feedback_given",
    "ceo_decided",
})

# 已退回给提交人补充
RETURNED_TO_SUBMITTER: frozenset[str] = frozenset({
    S_RETURNED,
    # legacy
    "returned_to_submitter",
    "已打回",
})

# 流转中：等待统筹人反馈
WAITING_COORDINATOR_FEEDBACK: frozenset[str] = frozenset({
    S_WAITING_COORDINATOR,
    # legacy
    "transferred_to_coordinator",
})

# 流转中：等待 CEO 决策
# legacy name；当前业务语义是“等待项目企业教练决策”
WAITING_CEO_DECISION: frozenset[str] = frozenset({
    S_WAITING_CEO,
    # legacy
    "pending_ceo_decision",
})

# 流转中（过程保障内部路由）
NEEDS_REVISION: frozenset[str] = frozenset({
    S_NEEDS_REVISION,
})

# 已确认入库
CONFIRMED_AND_STORED: frozenset[str] = frozenset({
    S_CONFIRMED,
    # legacy
    "stored",
    "approved_for_storage",
    "已确认入库",
    "已确认",
})

# 已撤回
WITHDRAWN: frozenset[str] = frozenset({
    S_WITHDRAWN,
    # legacy
    "withdrawn",
    "withdrawn_editable",
})

# 永久拒绝
PERMANENTLY_REJECTED: frozenset[str] = frozenset({
    S_PERMANENTLY_REJECTED,
    # legacy
    "已归档",
    "已退回",
})

# ─────────────────────────────────────────────────────────────────
# 复合集合（多处共用）
# ─────────────────────────────────────────────────────────────────

# AI 确认中心"待审核" tab 所有状态（= 等待负责人处理的全集）
TAB_PENDING_REVIEW: frozenset[str] = PENDING_OWNER_REVIEW

# AI 确认中心"流转中" tab
TAB_IN_FLIGHT: frozenset[str] = (
    RETURNED_TO_SUBMITTER
    | WAITING_COORDINATOR_FEEDBACK
    | WAITING_CEO_DECISION
    | NEEDS_REVISION
)

# AI 确认中心"已完成" tab
TAB_COMPLETED: frozenset[str] = (
    CONFIRMED_AND_STORED
    | WITHDRAWN
    | PERMANENTLY_REJECTED
)

# CEO 决策中心专用：仅等待 CEO 批示的事项
TAB_CEO_PENDING: frozenset[str] = WAITING_CEO_DECISION

# 可撤回的状态（submitter 自行撤回）
WITHDRAWABLE: frozenset[str] = (
    PENDING_OWNER_REVIEW
    | RETURNED_TO_SUBMITTER
)

# owner 待处理队列（确认/打回/转交/升级 CEO 的来源状态）
OWNER_ACTIONABLE: frozenset[str] = frozenset({
    S_NEW,
    S_PENDING_OWNER,
    S_COORDINATOR_GIVEN,
    S_CEO_DECIDED,
    # legacy
    "pending_owner_review",
    "resubmitted",
    "提交人已确认",
    "已重新提交",
    "coordinator_feedback_given",
    "ceo_decided",
})

# owner 可转交统筹人的状态
TRANSFERABLE_TO_COORDINATOR: frozenset[str] = frozenset({
    S_NEW,
    S_PENDING_OWNER,
    # legacy
    "pending_owner_review",
    "resubmitted",
    "已重新提交",
    "提交人已确认",
})

# owner 可上报 CEO 的状态
ESCALATABLE_TO_CEO: frozenset[str] = frozenset({
    S_NEW,
    S_PENDING_OWNER,
    S_COORDINATOR_GIVEN,
    # legacy
    "pending_owner_review",
    "resubmitted",
    "已重新提交",
    "提交人已确认",
    "coordinator_feedback_given",
})

# 所有活跃状态（未最终完成）
ALL_ACTIVE: frozenset[str] = (
    PENDING_OWNER_REVIEW
    | RETURNED_TO_SUBMITTER
    | WAITING_COORDINATOR_FEEDBACK
    | WAITING_CEO_DECISION
    | NEEDS_REVISION
)

# 所有终态
ALL_TERMINAL: frozenset[str] = TAB_COMPLETED


# ─────────────────────────────────────────────────────────────────
# 统计口径 helpers（dashboard 专用）
# ─────────────────────────────────────────────────────────────────

def stats_pending_owner(subs: list) -> int:
    """等待负责人审核/处理的提交数。"""
    return sum(1 for s in subs if (s.confirm_status or "") in PENDING_OWNER_REVIEW)


def stats_returned(subs: list) -> int:
    """已退回给提交人的提交数。"""
    return sum(1 for s in subs if (s.confirm_status or "") in RETURNED_TO_SUBMITTER)


def stats_confirmed(subs: list) -> int:
    """已确认入库的提交数。"""
    return sum(1 for s in subs if (s.confirm_status or "") in CONFIRMED_AND_STORED)


def stats_waiting_ceo(subs: list) -> int:
    """等待 CEO 决策的提交数。"""
    return sum(1 for s in subs if (s.confirm_status or "") in WAITING_CEO_DECISION)


def stats_ceo_decided(subs: list) -> int:
    """
    CEO 已批示（等待 owner 确认入库）的提交数。
    注意：这些提交同时也被 stats_pending_owner 计数，
    因为两个计数是不同维度的视图（CEO视角 vs owner视角）。
    """
    return sum(1 for s in subs if (s.confirm_status or "") in frozenset({S_CEO_DECIDED, "ceo_decided"}))
