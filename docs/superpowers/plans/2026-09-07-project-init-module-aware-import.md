# Project Init Module-Aware Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split AI-imported project-init files into verified project-profile suggestions and work-progress task suggestions, then let users apply each module safely.

**Architecture:** Extend the existing project-init analysis-run draft with a backwards-compatible `project_profile` object. The existing AI agent remains the sole semantic reader, but it will route source regions into profile fields or tasks and validate evidence for both. The client decodes missing profile data as an empty object, previews both modules, and passes profile choices back to the project creation/edit workflow without allowing the owner-submit page to overwrite core project fields.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, React, TypeScript, Vitest, pytest.

---

## File structure

- `bowei_ai_dashboard/app/services/project_init_ai_agent.py`: strict profile draft models, semantic prompt, source-evidence validation, multi-file merge.
- `bowei_ai_dashboard/app/services/project_init_analysis.py`: persist profile-plus-task analysis results without changing run lifecycle behavior.
- `bowei_ai_dashboard/app/schemas.py`: type the extended draft response while accepting historical task-only JSON.
- `bowei_ai_dashboard/app/routers/project_init_ai.py`: return the compatible run result and preserve apply auditing.
- `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`: backend module-routing and evidence regressions.
- `bowei_ai_dashboard/tests/test_project_init_analysis.py`: persisted run regression, including task-only historical drafts.
- `frontend/src/api/projectInitAi.ts`: decode and expose the profile module and field decisions.
- `frontend/src/features/settings/projectInitProfileDraft.ts`: pure profile merge and decision functions.
- `frontend/src/features/settings/projectInitProfileDraft.test.ts`: client merge rules.
- `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`: module summary, profile preview, and separate apply callback.
- `frontend/src/features/settings/OwnerSubmitModal.tsx`: read-only profile suggestions and request-modification affordance for project owners.
- `frontend/src/features/settings/ProjectInitModal.tsx`: accept an approved profile draft when creating or editing a draft project.
- `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`: preview compatibility and module controls.

### Task 1: Define the profile draft contract and prove semantic routing

**Files:**
- Modify: `bowei_ai_dashboard/app/services/project_init_ai_agent.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_ai_agent.py`

- [ ] **Step 1: Write a failing routing test with profile and task regions**

```python
def test_build_draft_routes_project_profile_and_work_progress_by_semantics():
    result = build_project_init_ai_draft(
        chunks=[
            source("方案.xlsx", "概况!A1:B7", "项目名称：岗位 AI 应用优化\n建设背景：岗位知识分散\n项目目标：提升复用率\n预期成果：形成案例库\n项目周期：2026-07-01 至 2026-09-30"),
            source("方案.xlsx", "推进表!A1:H5", "工作模块：岗位优化\n关键任务：建立应用记录表\n负责人：张三\n计划时间：2026-07-01 至 2026-07-15"),
        ],
        people=[],
        existing_tasks=[],
        complete_text=fake_completion,
    )

    assert result.project_profile.name == "岗位 AI 应用优化"
    assert result.project_profile.background == "岗位知识分散"
    assert result.project_profile.objectives == "提升复用率"
    assert result.project_profile.expected_outcomes == "形成案例库"
    assert result.project_profile.start_date == "2026-07-01"
    assert result.project_profile.end_date == "2026-09-30"
    assert [task.title for task in result.tasks] == ["岗位优化"]
    assert result.project_profile.evidence
```

- [ ] **Step 2: Run the test and confirm it fails because `project_profile` does not exist**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py::test_build_draft_routes_project_profile_and_work_progress_by_semantics -q`

Expected: FAIL with an attribute or validation error referring to `project_profile`.

- [ ] **Step 3: Add strict profile models and extend the AI envelope**

```python
class ProjectProfileDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(default="", max_length=100)
    background: str = Field(default="", max_length=10_000)
    objectives: str = Field(default="", max_length=10_000)
    expected_outcomes: str = Field(default="", max_length=10_000)
    start_date: str = Field(default="", max_length=20)
    end_date: str = Field(default="", max_length=20)
    description: str = Field(default="", max_length=10_000)
    confidence: float = Field(default=0.0, ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list, max_length=20)
    warnings: list[AgentWarning] = Field(default_factory=list, max_length=20)

class ProjectInitAiResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_profile: ProjectProfileDraft = Field(default_factory=ProjectProfileDraft)
    tasks: list[AgentTask] = Field(min_length=1, max_length=100)
    provider: str = ""
    model_name: str = ""
```

Update `_RawEnvelope`, the extraction prompt, normalisation, evidence verification and cross-file merging so profile fields use only supplied source locations. Convert valid date ranges to `YYYY-MM-DD` values and append a warning rather than inventing a missing date.

- [ ] **Step 4: Re-run the routing test**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py::test_build_draft_routes_project_profile_and_work_progress_by_semantics -q`

Expected: PASS.

- [ ] **Step 5: Add negative tests for unsupported evidence and historical task-only output**

```python
def test_profile_value_without_valid_evidence_is_not_applied():
    with pytest.raises(ProjectInitAiError, match="无法追溯"):
        build_project_init_ai_draft(chunks=[source("方案.xlsx", "概况!A1", "项目名称：A")], people=[], existing_tasks=[], complete_text=invalid_profile_evidence)

def test_historical_task_only_envelope_uses_empty_profile():
    result = parse_project_init_ai_result({"tasks": [valid_task_payload()]})
    assert result.project_profile.model_dump() == ProjectProfileDraft().model_dump()
```

- [ ] **Step 6: Run the focused agent suite**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py -q`

Expected: PASS.

### Task 2: Preserve the extended draft through analysis-run APIs

**Files:**
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/services/project_init_analysis.py`
- Modify: `bowei_ai_dashboard/app/routers/project_init_ai.py`
- Modify: `bowei_ai_dashboard/tests/test_project_init_analysis.py`

- [ ] **Step 1: Write a failing persisted-run regression**

```python
def test_completed_analysis_run_returns_profile_and_tasks(client, seeded_project, analysis_ready):
    run = create_and_complete_run(client, seeded_project.id, analysis_ready)
    body = client.get(f"/api/projects/{seeded_project.id}/init-analysis/{run.id}").json()

    assert body["draft"]["project_profile"]["objectives"] == "提升复用率"
    assert body["draft"]["tasks"][0]["title"] == "岗位优化"
```

- [ ] **Step 2: Run the regression and verify the response lacks `project_profile`**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_analysis.py::test_completed_analysis_run_returns_profile_and_tasks -q`

Expected: FAIL with `KeyError: 'project_profile'`.

- [ ] **Step 3: Add response schema defaults and JSON serialization**

```python
class ProjectInitAnalysisDraft(BaseModel):
    project_profile: ProjectProfileDraft = Field(default_factory=ProjectProfileDraft)
    tasks: list[ProjectInitAiTaskDraft] = Field(default_factory=list)
    warnings: list[ProjectInitAgentWarning] = Field(default_factory=list)
    provider: str = ""
    model_name: str = ""
```

Ensure run serialization uses this default when existing `draft_json` contains a task array or a `tasks` object without `project_profile`. Do not mark a run applied merely because the user applies a client-side profile draft.

- [ ] **Step 4: Run the persisted-run regression and historical fixture**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_analysis.py -q`

Expected: PASS.

### Task 3: Add pure client-side profile merge decisions

**Files:**
- Create: `frontend/src/features/settings/projectInitProfileDraft.ts`
- Create: `frontend/src/features/settings/projectInitProfileDraft.test.ts`
- Modify: `frontend/src/api/projectInitAi.ts`

- [ ] **Step 1: Write failing merge tests**

```ts
it('marks an empty current field as a supplement', () => {
  expect(buildProjectProfileMergePreview({ objectives: '' }, { objectives: '提升复用率' }).fields.objectives.status).toBe('supplement')
})

it('requires a decision before a different non-empty value is applied', () => {
  const preview = buildProjectProfileMergePreview({ objectives: '旧目标' }, { objectives: '新目标' })
  expect(preview.fields.objectives.status).toBe('change')
  expect(applyProjectProfileDecisions(preview, {})).toEqual({})
})
```

- [ ] **Step 2: Run the test and confirm the module is missing**

Run: `npm --prefix frontend run test -- projectInitProfileDraft.test.ts --run`

Expected: FAIL because `projectInitProfileDraft.ts` does not exist.

- [ ] **Step 3: Implement the pure profile merge API**

```ts
export type ProjectProfileField = 'name' | 'background' | 'objectives' | 'expected_outcomes' | 'start_date' | 'end_date' | 'description'
export type ProjectProfileFieldStatus = 'empty' | 'same' | 'supplement' | 'change' | 'unverified'
export type ProjectProfileDecision = 'apply' | 'keep'

export function buildProjectProfileMergePreview(current: ProjectProfileValues, suggestion: ProjectInitAiProjectProfile): ProjectProfileMergePreview { /* compare values and evidence */ }
export function applyProjectProfileDecisions(preview: ProjectProfileMergePreview, decisions: Partial<Record<ProjectProfileField, ProjectProfileDecision>>): Partial<ProjectProfileValues> { /* only supplements or explicit apply */ }
```

Extend `ProjectInitAiDraft` in `projectInitAi.ts` with a defaulted `project_profile` decoder, preserving compatibility for saved `tasks`-only runs.

- [ ] **Step 4: Re-run the merge tests**

Run: `npm --prefix frontend run test -- projectInitProfileDraft.test.ts --run`

Expected: PASS.

### Task 4: Build the modular preview and enforce role-safe application

**Files:**
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx`
- Modify: `frontend/src/features/settings/ProjectInitModal.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitAiPanel.retry.test.tsx`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.layout.test.tsx`

- [ ] **Step 1: Write failing UI tests for a two-module preview**

```tsx
it('shows a project-profile summary and leaves profile application disabled for the owner flow', async () => {
  render(<OwnerSubmitAiPanel projectId={1} currentDraft={[]} currentProject={project} onApplyDraft={vi.fn()} />)
  await completeAnalysisWithProfileAndTask()

  expect(screen.getByText('项目基本信息')).toBeInTheDocument()
  expect(screen.getByText('工作推进方案')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '申请修改项目基本信息' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: '应用基本信息' })).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the UI test and confirm it fails**

Run: `npm --prefix frontend run test -- OwnerSubmitAiPanel.retry.test.tsx --run`

Expected: FAIL because the module summary and owner-safe profile action are absent.

- [ ] **Step 3: Implement preview tabs and callbacks**

```tsx
type Props = {
  currentProject: Project
  onApplyDraft: (draft: ProjectInitAiDraft, decisions: ProjectInitAiDecision[], runId: number) => Promise<void>
  onRequestProfileChange?: (preview: ProjectProfileMergePreview) => void
}

const [previewModule, setPreviewModule] = useState<'profile' | 'work_progress'>('profile')
```

Render the field-by-field profile comparison with evidence and `补充` / `保留当前值` controls. In `OwnerSubmitModal`, invoke `onRequestProfileChange` only to show a read-only change request payload; do not call `ownerSubmitProfile` with profile fields. In `ProjectInitModal`, allow the draft creator/editor to apply accepted profile decisions to the local `NewProjectForm` before that form is saved.

- [ ] **Step 4: Re-run focused UI tests**

Run: `npm --prefix frontend run test -- OwnerSubmitAiPanel.retry.test.tsx OwnerSubmitModal.layout.test.tsx --run`

Expected: PASS.

### Task 5: End-to-end verification and documentation

**Files:**
- Modify: `docs/superpowers/plans/2026-09-07-project-init-module-aware-import.md`

- [ ] **Step 1: Run backend module and owner-submit regression suites**

Run: `pytest bowei_ai_dashboard/tests/test_project_init_ai_agent.py bowei_ai_dashboard/tests/test_project_init_analysis.py bowei_ai_dashboard/tests/test_project_init_work_progress_draft.py -q`

Expected: PASS.

- [ ] **Step 2: Run frontend unit tests and production build**

Run: `npm --prefix frontend run test -- --run`

Expected: PASS.

Run: `npm --prefix frontend run build`

Expected: exit code 0.

- [ ] **Step 3: Inspect the complete diff and type-check changed files**

Run: `git diff --check && git status --short`

Expected: no whitespace errors; only intended files added or modified, plus the pre-existing runtime files already present before this feature.

- [ ] **Step 4: Mark completed checklist items with evidence references**

```markdown
- [x] Task 1 focused agent tests: `pytest ... -q` passed on YYYY-MM-DD.
- [x] Task 2 persisted run tests: `pytest ... -q` passed on YYYY-MM-DD.
- [x] Task 3 frontend merge tests: `npm ...` passed on YYYY-MM-DD.
- [x] Task 4 preview tests: `npm ...` passed on YYYY-MM-DD.
- [x] Task 5 complete verification: backend tests, frontend tests, build and diff check passed on YYYY-MM-DD.
```

## Execution record — 2026-09-07

- [x] Task 1: Added the evidence-bound `project_profile` contract, semantic routing prompt, cross-file merge, historical task-only compatibility, and profile-only source support. `py -m pytest tests/test_project_init_ai_agent.py -q` passed: 68 tests.
- [x] Task 2: Analysis-run JSON already transports the typed agent `model_dump`; added profile-field metadata while retaining task-only JSON compatibility. `py -m pytest tests/test_project_init_analysis.py -q` passed as part of the 129-test backend regression.
- [x] Task 3: Added client decoding defaults plus pure, evidence-gated profile merge decisions. `npm run test:unit -- projectInitProfileDraft.test.ts` passed: 3 tests.
- [x] Task 4: Added separate project-information and work-progress preview tabs; owner flow is read-only for core fields, while draft-stage project editors can review and return accepted values to the form before saving. `npm run test:unit -- OwnerSubmitAiPanel.retry.test.tsx projectInitProfileDraft.test.ts` passed: 7 tests.
- [x] Task 5: `py -m pytest tests/test_project_init_ai_agent.py tests/test_project_init_analysis.py tests/test_project_init_work_progress_draft.py -q` passed: 129 tests; `npm run test:unit` passed: 70 tests; `npm run build` passed; `git diff --check` reported no whitespace errors.
