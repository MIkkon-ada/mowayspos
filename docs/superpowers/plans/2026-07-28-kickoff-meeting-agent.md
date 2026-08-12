# 启动会确认 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将项目启动会实现为 PM 发起、企业教练审核、审核通过后原子写入执行版并启动项目的可审计 Agent 工作流。

**Architecture:** 项目生命周期增加 `pending_kickoff`；启动会 Agent 的运行、会前快照和变更提案存入独立模型，不直接修改 `Task`/`SubTask`。企业教练确认启动时，服务端在单一事务中应用已批准提案、发布启动会纪要并将项目转为 `active`。

**Tech Stack:** FastAPI、SQLAlchemy、React/TypeScript、现有 LLM provider、pytest、Node 结构测试。

---

### Task 1: 生命周期与数据模型

**Files:**
- Modify: `bowei_ai_dashboard/app/domain/project_lifecycle.py`
- Modify: `bowei_ai_dashboard/app/models.py`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Test: `bowei_ai_dashboard/tests/test_kickoff_agent_model.py`

- [ ] **Step 1: 写失败测试**

```python
from app.domain import project_lifecycle as PL
from app import models

def test_pending_kickoff_has_a_canonical_lifecycle_and_audit_models():
    assert PL.normalize("pending_kickoff") == "pending_kickoff"
    assert "pending_kickoff" in PL.ALL_STATUSES
    assert models.KickoffAgentRun.__tablename__ == "kickoff_agent_runs"
    assert models.KickoffChangeProposal.__tablename__ == "kickoff_change_proposals"
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_model.py -q`  
Expected: FAIL because the state and models do not exist.

- [ ] **Step 3: 实现最小模型**

Add `S_PENDING_KICKOFF = "pending_kickoff"` to lifecycle constants and `ALL_STATUSES`. Add models `KickoffAgentRun(project_id, meeting_id, snapshot_json, result_json, status, created_by_person_id)` and `KickoffChangeProposal(run_id, proposal_type, target_type, target_id, before_json, proposed_json, evidence_json, validation_json, review_status, reviewer_person_id, review_comment)`. Add Pydantic payloads for run creation, PM submission, proposal review and start confirmation.

- [ ] **Step 4: 运行通过测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_model.py -q`  
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add bowei_ai_dashboard/app/domain/project_lifecycle.py bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/tests/test_kickoff_agent_model.py
git commit -m "feat: add kickoff agent lifecycle models"
```

### Task 2: 审核通过进入待启动会

**Files:**
- Modify: `bowei_ai_dashboard/app/routers/projects.py`
- Modify: `bowei_ai_dashboard/app/routers/updates.py`
- Modify: `bowei_ai_dashboard/app/routers/subtasks.py`
- Test: `bowei_ai_dashboard/tests/test_kickoff_agent_flow.py`

- [ ] **Step 1: 写失败测试**

```python
def test_approval_requires_kickoff_before_active(client, coach_headers, pending_review_project):
    response = client.post(f"/api/projects/{pending_review_project.id}/approve", headers=coach_headers)
    assert response.json()["lifecycle_status"] == "pending_kickoff"
    assert response.json()["kickoff_date"] == ""

def test_pending_kickoff_rejects_formal_update(client, member_headers, pending_kickoff_project):
    response = client.post("/api/updates", headers=member_headers, json={"project_id": pending_kickoff_project.id, "source_type": "文字", "transcript_text": "进展"})
    assert response.status_code == 409
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_flow.py -q`  
Expected: FAIL because approval currently returns `active`.

- [ ] **Step 3: 实现状态转换**

Change `approve_project()` to write `pending_kickoff` without kickoff fields. Keep formal reports and execution-period task structure writes guarded by `S_ACTIVE`; return 409 with “项目待启动会确认” for `pending_kickoff`.

- [ ] **Step 4: 运行通过测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_flow.py -q`  
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/app/routers/updates.py bowei_ai_dashboard/app/routers/subtasks.py bowei_ai_dashboard/tests/test_kickoff_agent_flow.py
git commit -m "feat: require kickoff confirmation before activation"
```

### Task 3: 分阶段启动会 Agent 服务

**Files:**
- Create: `bowei_ai_dashboard/app/services/kickoff_agent.py`
- Test: `bowei_ai_dashboard/tests/test_kickoff_agent_service.py`

- [ ] **Step 1: 写失败测试**

```python
from app.services.kickoff_agent import normalize_agent_result

def test_no_change_result_still_creates_a_reviewable_conclusion():
    result = normalize_agent_result({"summary": "按原计划执行", "proposals": []}, {"tasks": []})
    assert result["start_conclusion"] == "no_change"
    assert result["proposals"] == [{"proposal_type": "no_change", "evidence": []}]
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_service.py -q`  
Expected: FAIL because the service does not exist.

- [ ] **Step 3: 实现 Agent 编排**

Implement `build_kickoff_snapshot(project_id, db)`, `run_kickoff_agent(transcript, snapshot, provider)`, `normalize_agent_result(result, snapshot)`, and `validate_proposal(proposal, snapshot)`. The LLM performs meeting understanding and proposes differences; code performs snapshotting, member/role/task hierarchy/date validation, and emits `before`, `proposed`, evidence, and validation errors.

- [ ] **Step 4: 运行通过测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_service.py -q`  
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add bowei_ai_dashboard/app/services/kickoff_agent.py bowei_ai_dashboard/tests/test_kickoff_agent_service.py
git commit -m "feat: add staged kickoff meeting agent"
```

### Task 4: 启动会 API、审核和原子写入

**Files:**
- Create: `bowei_ai_dashboard/app/services/kickoff_writeback.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py`
- Test: `bowei_ai_dashboard/tests/test_kickoff_agent_flow.py`

- [ ] **Step 1: 写失败测试**

```python
def test_confirm_start_rejects_pending_proposal(client, coach_headers, kickoff_run):
    assert client.post(f"/api/meetings/kickoff-runs/{kickoff_run.id}/confirm-start", headers=coach_headers).status_code == 409

def test_confirm_start_applies_approved_proposals_and_activates(client, coach_headers, reviewed_kickoff_run):
    response = client.post(f"/api/meetings/kickoff-runs/{reviewed_kickoff_run.id}/confirm-start", headers=coach_headers)
    assert response.json()["project"]["lifecycle_status"] == "active"
    assert response.json()["meeting"]["meeting_type"] == "kickoff"
```

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_flow.py -q`  
Expected: FAIL because kickoff-run routes do not exist.

- [ ] **Step 3: 实现受控接口**

Create routes to create/run/edit/submit a kickoff run, review an individual proposal, and confirm start. `confirm-start` verifies `pending_kickoff`, coach/tech-admin permission, and no pending/blocking proposal, then `apply_kickoff_run()` updates approved tasks, publishes one `meeting_type="kickoff"` meeting, writes kickoff fields, logs, notifies, and switches to `active` in the same database transaction.

- [ ] **Step 4: 运行通过测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_flow.py -q`  
Expected: PASS.

- [ ] **Step 5: 提交**

```bash
git add bowei_ai_dashboard/app/services/kickoff_writeback.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_kickoff_agent_flow.py
git commit -m "feat: add reviewed kickoff writeback"
```

### Task 5: 状态驱动的启动会工作台

**Files:**
- Create: `frontend/src/features/meeting/KickoffAgentWorkspace.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Test: `frontend/tests/kickoffAgentStructure.test.mjs`

- [ ] **Step 1: 写失败结构测试**

```js
assert.match(read("frontend/src/pages/MeetingPage.tsx"), /pending_kickoff/)
assert.match(read("frontend/src/features/meeting/KickoffAgentWorkspace.tsx"), /提交企业教练审核/)
assert.doesNotMatch(read("frontend/src/features/meeting/KickoffAgentWorkspace.tsx"), /<option value="kickoff">/)
```

- [ ] **Step 2: 运行失败测试**

Run: `node --test frontend/tests/kickoffAgentStructure.test.mjs`  
Expected: FAIL because the workspace file is absent.

- [ ] **Step 3: 实现界面**

MeetingPage sends a selected `pending_kickoff` project to `KickoffAgentWorkspace`; `active` projects open normal meetings. The workspace shows transcript, frozen plan, Agent summary, proposal list, validation, PM submit action, and coach item review/confirm-start actions. Remove the manual kickoff option and the mode picker from `NewMeetingModal`.

- [ ] **Step 4: 运行通过测试**

Run: `node --test frontend/tests/kickoffAgentStructure.test.mjs && npm run build`  
Expected: PASS and build completes.

- [ ] **Step 5: 提交**

```bash
git add frontend/src/api/meetings.ts frontend/src/pages/MeetingPage.tsx frontend/src/features/meeting/NewMeetingModal.tsx frontend/src/features/meeting/KickoffAgentWorkspace.tsx frontend/tests/kickoffAgentStructure.test.mjs
git commit -m "feat: add kickoff agent workspace"
```

### Task 6: 回归和流程文档

**Files:**
- Modify: `docs/N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md`
- Modify: `docs/PROJECT_FLOW_BOUNDARY.md`
- Test: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Test: `bowei_ai_dashboard/tests/test_project_close_lifecycle_guards.py`

- [ ] **Step 1: 补充失败回归测试**

Add assertions that a pending-kickoff project cannot create a normal meeting, an active project cannot create another kickoff run, PM cannot review its own run, and an approved no-change run activates the project.

- [ ] **Step 2: 运行失败测试**

Run: `pytest bowei_ai_dashboard/tests/test_kickoff_agent_flow.py -q`  
Expected: FAIL until all lifecycle and permission guards are implemented.

- [ ] **Step 3: 同步文档**

Update the baseline flow to `pending_review → pending_kickoff → active`, document startup meeting as mandatory, and document that pending-kickoff projects cannot report, assign execution work, or create normal meetings.

- [ ] **Step 4: 执行完整验证**

Run: `pytest bowei_ai_dashboard/tests -q && node --test frontend/tests/*.test.mjs && npm run build`  
Expected: all tests pass and the build succeeds.

- [ ] **Step 5: 提交**

```bash
git add docs/N4_P0_BASELINE_MAIN_FLOW_STAGE_MAP.md docs/PROJECT_FLOW_BOUNDARY.md bowei_ai_dashboard/tests/test_kickoff_agent_flow.py
git commit -m "docs: document mandatory kickoff confirmation"
```

