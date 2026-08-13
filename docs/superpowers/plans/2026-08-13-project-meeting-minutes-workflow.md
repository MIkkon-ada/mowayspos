# 项目会议纪要分析与子计划回写实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现“选择项目→上传 Word 会议纪要→结合项目上下文分析→保存待审核草稿→项目负责人审核→回写关键任务下的执行安排→生成可下载会议纪要”的完整闭环。

**Architecture:** 在现有 `Meeting`、`MeetingRevision`、`MeetingChangeSet` 和 `MeetingChangeProposal` 之上增加项目会议文档运行、原始文件来源、审核事件和 `ExecutionSchedule` 变更提案能力。Word 是会议事实唯一来源，项目快照只用于匹配和校验；分析结果先保存为待审核草稿，只有项目负责人确认的执行安排变更才在一个事务中写回。前端提供项目上下文、纪要草稿、证据和变更建议的审核工作台，下载文件由已保存版本生成。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic v2、python-docx、React/TypeScript、现有项目权限和通知服务、pytest、Node test。

---

## 文件结构与职责

- Create: `bowei_ai_dashboard/app/services/project_meeting_minutes.py` — 项目上下文快照、Word 文档分类、会议纪要结构化分析结果规范化。
- Create: `bowei_ai_dashboard/app/services/meeting_document_storage.py` — 原始 Word 文件安全保存、读取和下载路径校验。
- Create: `bowei_ai_dashboard/app/services/meeting_minutes_export.py` — 从已保存会议版本生成 DOCX；PDF 使用同一结构化数据生成。
- Create: `bowei_ai_dashboard/migrations/versions/a1b2c3d4e5f6_add_project_meeting_document_review.py` — 追加会议来源、运行、审核事件和执行安排变更字段/表。
- Create: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py` — 纯函数和项目快照测试。
- Create: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py` — 上传、分析、草稿、权限、审核、回写和下载 API 测试。
- Modify: `bowei_ai_dashboard/app/models.py` — 新增运行/审核/来源模型，扩展变更提案目标类型。
- Modify: `bowei_ai_dashboard/app/schemas.py` — 文档运行、审核事件、执行安排提案和下载响应 schema。
- Modify: `bowei_ai_dashboard/app/routers/meetings.py` — 新项目会议文档接口；保留旧 `/api/meetings/analyze` 兼容路径，但新 UI 不再调用音频/实时转写路径。
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py` — 增加 `ExecutionSchedule` 快照、校验、冲突检测和事务执行。
- Modify: `frontend/src/api/meetings.ts` — 新运行、审核、执行安排变更和下载 API 类型/方法。
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx` — 改成 Word-only 项目会议输入和待审核草稿入口。
- Create: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx` — 项目上下文、会议草稿、证据和变更建议审核工作台。
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx` — 增加下载、审核状态、原始文档和审核记录展示。
- Modify: `frontend/src/pages/MeetingPage.tsx` — 先选项目，接入项目会议运行和负责人审核入口。
- Create: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs` — 前端结构契约测试。

## 约定的领域映射

```text
Project
  └── Task                 重点工作 / Workstream
       └── SubTask         关键任务 / KeyTask
            └── ExecutionSchedule  子计划 / 周计划或月计划
```

首期回写动作只允许：

- `update_execution_schedule`：更新已有 `ExecutionSchedule`；
- `create_execution_schedule`：在已有 `SubTask` 下新增 `ExecutionSchedule`。

不实现删除计划、修改成员、跨项目移动、创建关键任务、修改重点工作，也不实现实时语音或音频转写。

### Task 1: 建立失败测试和领域契约

**Files:**
- Create: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
- Create: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`
- Create: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: 写纯服务失败测试**

覆盖以下行为：

```python
def test_first_meeting_snapshot_has_no_required_previous_minutes(db_session):
    snapshot = build_project_meeting_snapshot(project_id, db_session)
    assert snapshot["project_id"] == project_id
    assert "members" in snapshot
    assert "workstreams" in snapshot
    assert snapshot["history"]["is_first_meeting"] is True

def test_execution_schedule_change_uses_meeting_evidence_only():
    proposal = validate_execution_schedule_proposal(
        raw={
            "action": "update_execution_schedule",
            "target": {"execution_schedule_id": schedule.id},
            "proposed": {"status": "已完成"},
            "evidence": ["会议文档中明确写出的连续引文"],
            "reason": "会议原文明确说明该计划已完成",
            "confidence": 0.9,
        },
        snapshot=snapshot,
        document_text="会议文档中明确写出的连续引文",
    )
    assert proposal["validation"]["state"] == "ready"
    assert proposal["before"]["status"] == schedule.status

def test_unknown_schedule_target_is_blocked():
    proposal = validate_execution_schedule_proposal(
        raw={"action": "update_execution_schedule", "target": {"execution_schedule_id": 99999}},
        snapshot=snapshot,
        document_text="原文",
    )
    assert proposal["validation"]["state"] == "blocked"
```

- [ ] **Step 2: 写 API 失败测试**

覆盖：Word 上传必须绑定项目；分析后自动保存 `pending_review`；分析阶段不改变 `SubTask` 或 `ExecutionSchedule`；非项目负责人不能审核；退回缺少原因返回 422；审核通过只执行明确选择的计划建议；下载只读取已保存版本。

- [ ] **Step 3: 写前端失败结构测试**

```js
test('project meeting workflow is document-only and exposes owner review', () => {
  const source = readFile('src/features/meeting/ProjectMeetingReviewWorkspace.tsx')
  assert.match(source, /项目上下文/)
  assert.match(source, /待审核草稿/)
  assert.match(source, /退回原因/)
  assert.match(source, /执行安排/)
  assert.match(source, /下载/)
})

test('new meeting input does not expose realtime audio controls', () => {
  const source = readFile('src/features/meeting/NewMeetingModal.tsx')
  assert.doesNotMatch(source, /transcribeAudio|audioFile|实时转写/)
})
```

- [ ] **Step 4: 运行失败测试确认当前实现不满足**

Run:

```powershell
cd bowei_ai_dashboard
python -m pytest tests/test_project_meeting_minutes_service.py tests/test_project_meeting_minutes_api.py -q
cd ..\frontend
node --test tests/projectMeetingMinutesWorkflow.test.mjs
```

Expected: FAIL，因为新运行、执行安排提案和审核工作台尚未实现。

### Task 2: 增加原始 Word 来源和项目会议运行持久化

**Files:**
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Create: `bowei_ai_dashboard/migrations/versions/a1b2c3d4e5f6_add_project_meeting_document_review.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`

- [ ] **Step 1: 增加模型**

新增：

```python
class MeetingDocumentSource(Base, TimestampMixin):
    __tablename__ = "meeting_document_sources"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="SET NULL"), nullable=True, index=True)
    original_name = Column(String(255), nullable=False)
    storage_key = Column(String(255), nullable=False, unique=True)
    mime_type = Column(String(120), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False, index=True)
    uploaded_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)

class ProjectMeetingRun(Base, TimestampMixin):
    __tablename__ = "project_meeting_runs"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    document_source_id = Column(Integer, ForeignKey("meeting_document_sources.id"), nullable=False)
    snapshot_json = Column(Text, nullable=False, default="{}")
    document_text = Column(Text, nullable=False, default="")
    result_json = Column(Text, nullable=False, default="{}")
    status = Column(String(24), nullable=False, default="analyzing", index=True)
    error_message = Column(Text, nullable=False, default="")
    created_by_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)

class MeetingReviewEvent(Base, TimestampMixin):
    __tablename__ = "meeting_review_events"
    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)
    action = Column(String(24), nullable=False)  # submitted | returned | approved | published
    actor_person_id = Column(Integer, ForeignKey("people.id"), nullable=True)
    reason = Column(Text, nullable=False, default="")
    selected_proposal_ids_json = Column(Text, nullable=False, default="[]")
```

Add `Meeting.document_source_id`, `Meeting.review_status`, `Meeting.review_version` and `MeetingChangeProposal.target_type` support for `execution_schedule` without removing legacy values.

- [ ] **Step 2: 创建 Alembic migration**

Migration must be additive, create indexes for project/status and meeting/action lookups, set existing meetings to `review_status='legacy'`, and downgrade only the new tables/columns.

- [ ] **Step 3: 运行模型迁移测试**

Run `cd bowei_ai_dashboard; alembic upgrade head; python -m pytest tests/test_project_meeting_minutes_api.py -k schema -q`.
Expected: PASS after the schema is available.

### Task 3: 实现项目快照、Word-only 运行和规范化输出

**Files:**
- Create: `bowei_ai_dashboard/app/services/project_meeting_minutes.py`
- Create: `bowei_ai_dashboard/app/services/meeting_document_storage.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`

- [ ] **Step 1: 实现项目快照**

`build_project_meeting_snapshot(project_id, db)` must return project metadata, active project members, every non-deleted `Task`, every non-deleted `SubTask`, and every non-deleted `ExecutionSchedule` with IDs and editable fields. It must add:

```python
"history": {
    "is_first_meeting": meeting_count == 0,
    "previous_meeting_ids": previous_ids,
}
```

No project snapshot field may be copied into evidence or treated as a meeting fact.

- [ ] **Step 2: 实现 Word 文件保存**

Use a project-scoped root such as `PROJECT_MEETING_DOCUMENT_ROOT` and generate a server-side UUID storage key. Reject non-`.docx`, files over 20 MiB, invalid paths, and missing content. Save the original bytes and SHA-256 hash. Reuse the defensive path checks from `project_init_ai.py`.

- [ ] **Step 3: 实现文档运行接口**

Add `POST /api/meetings/document-runs` as multipart form with `project_id`, optional `meeting_type`, and `file`. It must require project access, save the source, freeze the snapshot, extract Word text with `meeting_document_text.py`, and create `ProjectMeetingRun(status='analyzing')` before analysis. It must never call `transcribeAudio` or the weekly materials preflight.

- [ ] **Step 4: 实现结构化分析 contract**

Use the existing LLM call path but a new prompt contract:

```text
会议文档原文是唯一事实来源。
项目上下文仅用于识别项目术语、匹配 Task/SubTask/ExecutionSchedule、比较前后值和发现冲突。
不允许从项目上下文补写会议未提及的进度、负责人、日期、产出或决策。
输出 meeting_draft、facts、risks、open_questions、execution_schedule_changes。
每项 fact 和 change 必须携带 document evidence；证据必须是原文连续片段。
只允许 update_execution_schedule/create_execution_schedule。
目标不明确时返回 blocked proposal，不得猜测 ID。
```

Normalize all LLM output through deterministic validation. Empty `execution_schedule_changes` is valid.

- [ ] **Step 5: 自动保存待审核草稿**

Create a `Meeting` with `publish_status='draft'`, `review_status='pending_review'`, `source_mode='standard_minutes'` when the deterministic parser succeeds, otherwise `source_mode='ai_analysis'`. Attach the source and run. Persist the frozen snapshot, raw result, validated proposals, and an initial `submitted` review event. Do not update `ExecutionSchedule`.

- [ ] **Step 6: 添加读取接口**

Add `GET /api/meetings/document-runs/{run_id}` and `GET /api/meetings/{meeting_id}/review-package`; return document metadata, structured draft, project snapshot summary, proposals, validation state, and review events. Draft visibility must follow project access; full review actions remain owner-only.

### Task 4: 扩展执行安排变更提案和事务回写

**Files:**
- Modify: `bowei_ai_dashboard/app/services/meeting_change_set.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_service.py`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`

- [ ] **Step 1: 增加执行安排快照索引**

Build indexes by `execution_schedule_id` and `key_task_id`. Include `plan_type`, `plan_month`, dates, assignee, status, expected output, completion criteria, progress note, risk dependency, actual output, and sort order.

- [ ] **Step 2: 实现确定性提案校验**

Implement `validate_execution_schedule_proposal(raw, snapshot, document_text)` with these rules:

- action must be `update_execution_schedule` or `create_execution_schedule`;
- update target must exist in the frozen snapshot;
- create target must reference an existing non-deleted `key_task_id`;
- proposed fields must match the allowlist and existing `ExecutionSchedulePayload` constraints;
- assignee must be a project member if supplied;
- evidence must be non-empty exact substrings of `document_text`;
- target ID, proposed values, reason, evidence and confidence errors result in `blocked`;
- unknown but plausible people or ambiguous targets result in `needs_review`, never executable.

- [ ] **Step 3: Implement owner-only review endpoints**

Add `PATCH /api/meetings/{meeting_id}/review` with payload:

```json
{"action":"returned","reason":"请补充项目经理流程定稿的验收标准","selected_proposal_ids":[]}
```

Rules:

- only `require_project_owner_or_admin` may call it;
- `returned` requires a non-empty reason and changes status to `returned`;
- `approved` accepts an explicit proposal selection, records a review event, and proceeds to execution;
- review package remains immutable by version; edits create a new draft version rather than overwriting audit history.

- [ ] **Step 4: Implement transactional execution**

Create `execute_execution_schedule_changes(meeting, proposal_ids, actor, db)`:

```python
require_project_owner_or_admin(actor, meeting.project_id, db)
revalidate_selected_proposals_against_live_schedules(proposals, db)
for proposal in proposals:
    if proposal.action == "update_execution_schedule":
        update_execution_schedule_from_proposal(proposal, db)
    else:
        create_execution_schedule_from_proposal(proposal, db)
    mark_executed(proposal, actor, result_target_id)
db.commit()
```

The live revalidation must compare each proposal’s `before_json` against the current row and abort the whole transaction with HTTP 409 on a stale target. It must use the same person validation, project writeability, date, status and completed-output rules as `execution_schedules.py`.

- [ ] **Step 5: Test atomicity and permissions**

Assert owner approval writes exactly the selected schedules; ignored proposals remain pending/ignored and do not write; a stale second proposal rolls back the first; non-owner receives 403; a returned meeting cannot execute; duplicate execution returns 409.

### Task 5: Implement review UI and remove the wrong input path

**Files:**
- Create: `frontend/src/features/meeting/ProjectMeetingReviewWorkspace.tsx`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Test: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: Replace new-meeting input with project-document input**

The modal must require a project context and render only `.docx` upload. Remove the active UI path for `audioFile`, `transcribeAudio`, `audioText`, `supplementalText`, and `preflightMeetingSkill`. Keep legacy API functions only if other routes still use them; do not call them from this workflow.

- [ ] **Step 2: Render the review package**

Use a two-column workspace:

- left: meeting draft sections, source document metadata, download action;
- right: project context, each schedule proposal, before/after values, evidence quote, validation state, accept/ignore selection.

Display “首次会议，无上期追踪” when the snapshot says `is_first_meeting`.

- [ ] **Step 3: Add owner review controls**

Only render approve/return controls when the current user is the project owner according to the existing permission payload. Return opens a required reason field. Approval requires an explicit selection state for proposals; blocked proposals cannot be selected. After successful approval, refresh the plan and meeting detail.

- [ ] **Step 4: Add detail page download and audit tabs**

Add DOCX and PDF download buttons using authenticated API calls, and show source document, review history, selected writes, ignored proposals and returned reasons. Do not use `window.print()` as the primary download implementation.

### Task 6: Generate downloads from the saved meeting version

**Files:**
- Create: `bowei_ai_dashboard/app/services/meeting_minutes_export.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`

- [ ] **Step 1: Implement DOCX export**

Build from saved meeting fields, not transient LLM JSON. Render sections in this order: meeting metadata, agenda, summary/decisions, completed items, next-stage work, risks/open questions, confirmed execution-schedule changes, review metadata. Use the existing document runtime and `python-docx`.

- [ ] **Step 2: Add download endpoint**

Implement `GET /api/meetings/{meeting_id}/download?format=docx|pdf`. Validate project access, use the latest approved/published revision, and return `FileResponse` with a safe filename. Do not expose the storage root or arbitrary paths.

- [ ] **Step 3: Add PDF conversion**

Convert the generated DOCX through the configured LibreOffice/soffice runtime when available. If unavailable, return a clear 503 for PDF only while DOCX remains available; never claim PDF success without a file.

- [ ] **Step 4: Verify download content**

Test that the downloaded DOCX contains the saved title, decision, schedule changes, reviewer and publication data, and that a later edit does not change the previous revision’s downloaded output.

### Task 7: Notifications, audit, and regression coverage

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Modify: `bowei_ai_dashboard/app/services/notify.py` only if an existing helper cannot represent the event
- Modify: `frontend/src/features/meeting/MeetingDetailWorkspace.tsx`
- Test: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`
- Test: `frontend/tests/projectMeetingMinutesWorkflow.test.mjs`

- [ ] **Step 1: Notify project owner of a new review package**

Send one notification when a run becomes `pending_review`, including project, meeting title, and link to the review package. Do not send task notifications before approval.

- [ ] **Step 2: Notify assignees only after execution**

After the write transaction commits, notify affected execution-schedule assignees with the meeting link and changed schedule title. A failed or returned review sends no execution notification.

- [ ] **Step 3: Add audit assertions**

Assert logs/events contain original document hash, snapshot version/hash, reviewer, return reason, selected proposal IDs, result schedule IDs, and timestamps.

- [ ] **Step 4: Run the complete focused suite**

```powershell
cd bowei_ai_dashboard
python -m pytest tests/test_project_meeting_minutes_service.py tests/test_project_meeting_minutes_api.py tests/test_meeting_change_set_service.py tests/test_meeting_change_set_writeback.py -q
cd ..\frontend
node --test tests/projectMeetingMinutesWorkflow.test.mjs tests/meetingChangeSetReviewStructure.test.mjs
```

Expected: PASS, with legacy meeting change-set tests unchanged.

### Task 8: Render and verify generated meeting documents

**Files:**
- Modify: `bowei_ai_dashboard/tests/test_project_meeting_minutes_api.py`
- Test output: task-local QA directory outside tracked source

- [ ] **Step 1: Generate a representative approved meeting DOCX**

Use a fixture with meeting metadata, agenda, decisions, completed work, next-stage plans, one blocked proposal, one accepted schedule update and one accepted schedule creation.

- [ ] **Step 2: Render DOCX to PNG**

Run the bundled `render_docx.py` with the workspace Python runtime and inspect every page. Confirm headings, tables, wrapped evidence, review metadata and page breaks have no clipping or overlap.

- [ ] **Step 3: Add structural assertions for environments without LibreOffice**

If `soffice` is unavailable, assert the DOCX package contains the expected paragraphs, tables, and no internal citation tokens; return PDF as unavailable rather than silently falling back to print output.

### Task 9: Final verification and delivery

**Files:**
- No new production files; inspect all changed files.

- [ ] **Step 1: Run backend lint/compile checks**

```powershell
cd bowei_ai_dashboard
python -m compileall app
python -m pytest tests/test_project_meeting_minutes_service.py tests/test_project_meeting_minutes_api.py -q
```

- [ ] **Step 2: Run frontend checks**

```powershell
cd frontend
node --test tests/projectMeetingMinutesWorkflow.test.mjs
pnpm exec tsc --noEmit
```

- [ ] **Step 3: Inspect git diff and verify no unrelated files changed**

Run `git status --short` and compare the changed paths with this plan. Preserve all pre-existing user changes and do not reset unrelated files.

- [ ] **Step 4: Request code review before integration**

Use the project’s code-review workflow after verification and report any review findings before merging or publishing.

## Self-review against the design

- Project-first input and owner-only review: Tasks 3 and 5.
- Word-only input and no previous-material gate for the first meeting: Tasks 1, 3 and 5.
- Project context as matching context, Word as evidence: Tasks 3 and 4.
- `Task` / `SubTask` / `ExecutionSchedule` mapping: domain mapping and Tasks 3–4.
- Pending-review draft before writes: Tasks 2–3.
- Return reason and immutable audit history: Tasks 2 and 4.
- Transactional schedule writeback: Task 4.
- DOCX/PDF downloads from saved revision: Task 6 and Task 8.
- Notifications and regression safety: Task 7.

No placeholders or unresolved “TBD/TODO” items remain in this plan.
