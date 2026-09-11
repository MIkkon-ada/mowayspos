# Trusted Delivery Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Do not dispatch subagents for this repository. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让当前仓库恢复为“后端、前端、构建、迁移、CI 全部可重复通过”的可信基线，并消除测试白名单对真实失败的掩盖。

**Architecture:** 保持现有 FastAPI + SQLAlchemy/Alembic 后端、React + TypeScript + Vite 前端以及 PostgreSQL 16 生产门禁不变。修复唯一真实数据库模型漂移；依据已批准设计校准过期的前端契约；删除负责人提交页中已被替代的注释版 JSX；用一个跨平台脚本统一前端两套测试；最后把 CI 改为任何失败都直接阻断。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, pytest, React 18, TypeScript, Vite, Vitest, Node.js test runner, GitHub Actions, Docker Compose, PostgreSQL 16

---

## Scope and constraints

- 设计依据：`docs/superpowers/specs/2026-09-11-system-stabilization-and-architecture-governance-design.md`。
- 本计划只实施第一阶段“可信交付基线”。项目与权限治理、确认与会议治理、项目初始化 AI/前端性能/仓库治理将在本计划全绿后分别出具并执行后续计划。
- 当前工作树已有用户修改。每次提交只暂存本任务明确列出的文件，不使用 `git add .`，不清理、不覆盖任何无关改动。
- `Meeting.document_source_id` 与 `MeetingDocumentSource.meeting_id` 当前都被业务代码使用；本阶段不删除任一外键，也不隐藏 SQLAlchemy 循环外键警告。其生命周期与级联策略留到“确认与会议治理”阶段设计。
- ExcelJS 大包警告当前不影响构建通过；代码分包留到“前端性能与仓库治理”阶段。

## Acceptance gates

完成本计划时必须同时满足：

- `python -m pytest tests -q` 退出码为 0，不存在已知失败白名单。
- `npm run test:all` 同时运行 Vitest 与全部 `frontend/tests/*.test.mjs`，退出码为 0。
- `npm run build` 退出码为 0。
- Alembic 单一 head、SQLite bootstrap schema 与 ORM 一致。
- GitHub Actions 中后端测试、前端测试、PostgreSQL 16 迁移门禁任一失败都会使工作流失败。
- `git diff --check` 退出码为 0。

## Task 1: Repair the ORM/database default drift

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py:34`
- Test: `bowei_ai_dashboard/tests/test_migration_bootstrap.py`

- [ ] **Step 1: Reproduce the focused failure**

  Run from `bowei_ai_dashboard`:

  ```powershell
  python -m pytest tests/test_migration_bootstrap.py::test_t3_head_schema_matches_current_orm -q
  ```

  Expected before the fix: FAIL, identifying `tasks.plan_process` default drift.

- [ ] **Step 2: Make the ORM declare the same server default as the migration**

  Change only the `Task.plan_process` declaration:

  ```python
  plan_process = Column(Text, default="", server_default="")
  ```

  Do not create a new migration: `k2l3m4n5o6p7_add_task_plan_process.py` already establishes the intended database default.

- [ ] **Step 3: Verify schema bootstrap and migration graph**

  ```powershell
  python -m pytest tests/test_migration_bootstrap.py -q
  python -m alembic heads
  python -m alembic upgrade head
  ```

  Expected: migration bootstrap tests pass; `alembic heads` prints exactly one head; upgrade exits 0.

- [ ] **Step 4: Commit only the model fix**

  ```powershell
  git add bowei_ai_dashboard/app/models.py
  git commit -m "fix: align task plan process database default"
  ```

## Task 2: Align shared document-format contracts with the approved behavior

**Files:**

- Modify: `frontend/tests/newMeetingMultiSource.test.mjs`
- Modify: `frontend/tests/workReportDocumentInput.test.mjs`
- Verify: `frontend/src/config/aiDocumentFormats.ts`
- Verify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Verify: `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx`

- [ ] **Step 1: Run the two stale contracts and confirm they fail**

  Run from `frontend`:

  ```powershell
  node --test tests/newMeetingMultiSource.test.mjs tests/workReportDocumentInput.test.mjs
  ```

  Expected before test correction: both document-acceptance assertions fail because components now use the shared format configuration.

- [ ] **Step 2: Replace the meeting upload test with a shared-config contract**

  Add this source read next to the existing `modal` and `api` constants:

  ```javascript
  const formats = readFileSync(new URL('../src/config/aiDocumentFormats.ts', import.meta.url), 'utf8')
  ```

  Replace the obsolete “Word only” test with:

  ```javascript
  test('new project meeting uses the shared Word, text, and spreadsheet format policy', () => {
    assert.match(modal, /acceptedDocumentTypes\('meeting'\)/)
    assert.match(formats, /meeting:\s*\['\.docx', '\.txt', '\.xlsx'\]/)
    assert.doesNotMatch(formats, /meeting:\s*\[[^\]]*'\.pdf'/)
  })
  ```

- [ ] **Step 3: Replace the work-report literal-string assertion with a shared-config contract**

  In `workReportDocumentInput.test.mjs`, use the existing `read()` helper and assert:

  ```javascript
  test('work-report document input uses the shared supported-format policy', () => {
    const source = read('src/features/voice-update/VoiceUpdateInputPanel.tsx')
    const formats = read('src/config/aiDocumentFormats.ts')
    assert.match(source, /acceptedDocumentTypes\('workReport'\)/)
    assert.match(formats, /workReport:\s*\['\.docx', '\.pdf', '\.xlsx', '\.pptx'\]/)
  })
  ```

  Preserve the file-size, upload-progress, cancellation, and parsing-flow assertions already present in that file.

- [ ] **Step 4: Run both corrected contracts**

  ```powershell
  node --test tests/newMeetingMultiSource.test.mjs tests/workReportDocumentInput.test.mjs
  ```

  Expected: PASS.

- [ ] **Step 5: Commit the contract corrections**

  ```powershell
  git add frontend/tests/newMeetingMultiSource.test.mjs frontend/tests/workReportDocumentInput.test.mjs
  git commit -m "test: align document upload contracts"
  ```

## Task 3: Remove the false-positive login CSS assertion

**Files:**

- Modify: `frontend/tests/loginPageVisualStructure.test.mjs`
- Verify: `frontend/src/styles.css`

- [ ] **Step 1: Reproduce the single login contract failure**

  ```powershell
  node --test tests/loginPageVisualStructure.test.mjs
  ```

  Expected before the fix: the desktop-composition test fails even though the `.login-card` rule itself has no `min-height`; the broad regular expression crosses into later CSS rules.

- [ ] **Step 2: Add a rule-scoped CSS helper**

  Add after the `css` constant:

  ```javascript
  function cssRule(selector) {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const match = css.match(new RegExp(`${escaped}\\s*\\{([^}]*)\\}`))
    assert.ok(match, `missing CSS rule: ${selector}`)
    return match[1]
  }
  ```

- [ ] **Step 3: Scope the negative assertion to `.login-card`**

  Replace:

  ```javascript
  assert.doesNotMatch(css, /\.login-card \{[\s\S]*?min-height:/)
  ```

  with:

  ```javascript
  assert.doesNotMatch(cssRule('.login-card'), /min-height:/)
  ```

- [ ] **Step 4: Verify the focused contract**

  ```powershell
  node --test tests/loginPageVisualStructure.test.mjs
  ```

  Expected: all tests in the file pass.

- [ ] **Step 5: Commit the test repair**

  ```powershell
  git add frontend/tests/loginPageVisualStructure.test.mjs
  git commit -m "test: scope login css assertions"
  ```

## Task 4: Align AI preview, project-init decoder, and work-progress layout contracts

**Files:**

- Modify: `frontend/tests/ownerSubmitAiPanelPresentation.test.mjs`
- Modify: `frontend/tests/projectInitAiClient.test.mjs`
- Modify: `frontend/tests/workProgressExcelView.test.mjs`
- Verify: `frontend/src/features/settings/OwnerSubmitAiPanel.tsx`
- Verify: `frontend/src/api/projectInitAi.ts`
- Verify: `frontend/src/components/task-management/PlanTableViewV2.tsx`
- Verify: `frontend/src/components/task-management/planTableExcelV2.css`

- [ ] **Step 1: Reproduce the three stale contracts**

  ```powershell
  node --test tests/ownerSubmitAiPanelPresentation.test.mjs tests/projectInitAiClient.test.mjs tests/workProgressExcelView.test.mjs
  ```

  Expected before correction: one failure in each file.

- [ ] **Step 2: Update the AI preview summary assertion**

  Replace the old `已生成` assertion with:

  ```javascript
  assert.match(source, /识别到 \{suggestedProfileFieldCount\} 项项目基本信息、\{draft\.tasks\.length\} 项候选重点工作/)
  assert.match(source, /项目基本信息/)
  assert.match(source, /工作推进方案/)
  ```

  Preserve assertions for completion status, pending count, technical details, evidence, task cards, and apply action.

- [ ] **Step 3: Update the failed-analysis decoder expectation**

  In the test named `failed analysis runs accept an empty draft and preserve status and error message`, replace the obsolete whole-object equality with:

  ```javascript
  assert.deepEqual(run.draft.tasks, [])
  assert.deepEqual(run.draft.project_profile, api.EMPTY_PROJECT_INIT_AI_PROFILE)
  assert.deepEqual(run.draft.warnings, [])
  ```

  This verifies the current invariant that every decoded draft has a module-aware `project_profile` shape.

- [ ] **Step 4: Update work-progress width assertions to the approved proportional layout**

  Replace fixed pixel-column assertions with:

  ```javascript
  assert.match(source, /<col style=\{\{ width: '14%' \}\}/)
  assert.match(source, /<col style=\{\{ width: '23%' \}\}/)
  assert.match(source, /<col style=\{\{ width: '6%' \}\}/)
  assert.match(source, /<col style=\{\{ width: '9%' \}\}/)
  assert.match(source, /<col style=\{\{ width: '11%' \}\}/)
  assert.equal((source.match(/<col style=\{\{ width: '18\.5%' \}\}/g) ?? []).length, 2)
  assert.match(css, /min-width:\s*1120px/)
  assert.doesNotMatch(css, /min-width:\s*1305px/)
  ```

- [ ] **Step 5: Verify all three corrected contracts**

  ```powershell
  node --test tests/ownerSubmitAiPanelPresentation.test.mjs tests/projectInitAiClient.test.mjs tests/workProgressExcelView.test.mjs
  ```

  Expected: PASS.

- [ ] **Step 6: Commit these contract corrections**

  ```powershell
  git add frontend/tests/ownerSubmitAiPanelPresentation.test.mjs frontend/tests/projectInitAiClient.test.mjs frontend/tests/workProgressExcelView.test.mjs
  git commit -m "test: align ai and work progress contracts"
  ```

## Task 5: Delete the superseded OwnerSubmit layout and test the approved B layout

**Files:**

- Modify: `frontend/src/features/settings/OwnerSubmitModal.tsx:897-1212`
- Modify: `frontend/tests/ownerSubmitModalLayout.test.mjs`
- Modify: `frontend/src/features/settings/OwnerSubmitModal.layout.test.tsx`
- Reference: `docs/superpowers/specs/2026-09-04-owner-submit-layout-design.md`

- [ ] **Step 1: Add a failing behavior test for add/select/delete**

  Append to `OwnerSubmitModal.layout.test.tsx`:

  ```tsx
  it('selects a newly added workstream and returns to a valid selection after deletion', async () => {
    render(<OwnerSubmitWorkbench project={project} onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: '+ 新增重点工作' }))
    expect(screen.getByText('02')).toBeTruthy()

    fireEvent.click(screen.getByLabelText('重点工作 2 更多操作'))
    fireEvent.click(screen.getByRole('button', { name: '删除重点工作' }))

    await waitFor(() => expect(screen.queryByText('02')).toBeNull())
    expect(screen.getByText('01')).toBeTruthy()
  })
  ```

  Ensure `waitFor` is imported from `@testing-library/react`.

- [ ] **Step 2: Replace obsolete source-shape tests with approved-layout invariants**

  In `ownerSubmitModalLayout.test.mjs`, preserve the four picker behavior tests and the AI upload-recovery test. Remove the obsolete tests from `picker triggers use a stable SVG chevron` through `AI merge identifies one genuinely new task`. Add these tests:

  ```javascript
  test('picker triggers use stable SVG chevrons instead of a font glyph', () => {
    assert.equal((source.match(/className=\{`owner-submit-picker-chevron shrink-0 h-4 w-4/g) ?? []).length, 2)
    assert.doesNotMatch(source, />⌄</)
  })

  test('approved B layout shows project overview beside one selected workstream editor', () => {
    assert.match(source, /function renderApprovedLayout\(\)/)
    assert.match(source, /aria-label="重点工作列表"/)
    assert.match(source, /draftTasks\[selectedTaskIndex\] \?\? draftTasks\[0\]/)
    assert.match(source, /owner-submit-b-split/)
    assert.match(source, /验收标准 \/ 关键成果/)
    assert.match(source, /推进流程/)
  })

  test('approved layout has one add action and no legacy expansion UI', () => {
    assert.equal((source.match(/onClick=\{addTaskDraft\}/g) ?? []).length, 1)
    assert.doesNotMatch(source, /owner-submit-continue-add/)
    assert.doesNotMatch(source, /expandedTaskIndexes/)
    assert.doesNotMatch(source, /collapseTask\(/)
    assert.doesNotMatch(source, /expandTask\(/)
  })

  test('AI merge preserves selection by stable identity and selects a genuinely new task as fallback', () => {
    assert.match(source, /function taskStableIdentity\(/)
    assert.match(source, /existingTaskIdentities/)
    assert.match(source, /firstNewTaskIndex/)
    assert.match(source, /setSelectedTaskIndex\(nextSelectedIndex >= 0 \? nextSelectedIndex : \(firstNewTaskIndex >= 0 \? firstNewTaskIndex : 0\)\)/)
  })
  ```

- [ ] **Step 3: Confirm tests fail while the commented legacy JSX remains**

  ```powershell
  npm run test:unit -- src/features/settings/OwnerSubmitModal.layout.test.tsx
  node --test tests/ownerSubmitModalLayout.test.mjs
  ```

  Expected: at least the “one add action and no legacy expansion UI” contract fails because the dead commented block is still present.

- [ ] **Step 4: Delete the entire superseded commented JSX block**

  In `OwnerSubmitModal.tsx`, keep:

  ```tsx
  return renderApprovedLayout()
  ```

  Delete everything from the following `/*` through its matching closing `*/`. Do not change the active `renderApprovedLayout()` implementation in this step.

- [ ] **Step 5: Verify active B-layout behavior and source contracts**

  ```powershell
  npm run test:unit -- src/features/settings/OwnerSubmitModal.layout.test.tsx
  node --test tests/ownerSubmitModalLayout.test.mjs
  npm run build
  ```

  Expected: all focused tests and the TypeScript production build pass.

- [ ] **Step 6: Commit the dead-code removal and replacement tests**

  ```powershell
  git add frontend/src/features/settings/OwnerSubmitModal.tsx frontend/src/features/settings/OwnerSubmitModal.layout.test.tsx frontend/tests/ownerSubmitModalLayout.test.mjs
  git commit -m "refactor: remove superseded owner submit layout"
  ```

## Task 6: Create one cross-platform frontend test entry point

**Files:**

- Create: `frontend/scripts/run-contract-tests.mjs`
- Modify: `frontend/package.json`

- [ ] **Step 1: Demonstrate that the unified command does not exist**

  ```powershell
  npm run test:all
  ```

  Expected before implementation: npm reports a missing `test:all` script.

- [ ] **Step 2: Add the deterministic Node contract-test runner**

  Create `frontend/scripts/run-contract-tests.mjs`:

  ```javascript
  import { spawnSync } from 'node:child_process'
  import { readdirSync } from 'node:fs'
  import { resolve } from 'node:path'

  const testsDir = resolve('tests')
  const testFiles = readdirSync(testsDir)
    .filter((name) => name.endsWith('.test.mjs'))
    .sort()
    .map((name) => resolve(testsDir, name))

  if (testFiles.length === 0) {
    console.error('No frontend contract tests found in frontend/tests')
    process.exit(1)
  }

  const result = spawnSync(process.execPath, ['--test', ...testFiles], {
    stdio: 'inherit',
  })

  process.exit(result.status ?? 1)
  ```

- [ ] **Step 3: Add package scripts without changing existing commands**

  Extend `frontend/package.json` scripts to:

  ```json
  {
    "dev": "vite --host 0.0.0.0",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test:unit": "vitest run",
    "test:contracts": "node scripts/run-contract-tests.mjs",
    "test:all": "npm run test:unit && npm run test:contracts"
  }
  ```

- [ ] **Step 4: Verify both suites are reached through one command**

  ```powershell
  npm run test:all
  ```

  Expected: Vitest summary appears first, Node test-runner summary appears second, and the command exits 0.

- [ ] **Step 5: Commit the unified frontend test entry point**

  ```powershell
  git add frontend/package.json frontend/scripts/run-contract-tests.mjs
  git commit -m "test: unify frontend quality command"
  ```

## Task 7: Make CI fail closed and run on application changes

**Files:**

- Modify: `.github/workflows/cloud-p1b2a-gate.yml`

- [ ] **Step 1: Expand the pull-request path filter**

  Preserve `workflow_dispatch` and the existing production-runtime push branch. Replace the narrow `pull_request.paths` list with:

  ```yaml
  pull_request:
    paths:
      - '.github/workflows/cloud-p1b2a-gate.yml'
      - 'bowei_ai_dashboard/**'
      - 'frontend/**'
      - '.env.production.example'
      - 'Dockerfile.backend'
      - 'Dockerfile.frontend'
      - 'docker-compose.prod.yml'
      - 'nginx.conf'
      - 'docs/production-runtime-contract.md'
      - 'docs/ghcr-private-image-publish.md'
  ```

- [ ] **Step 2: Delete the backend known-failure whitelist**

  Replace the entire `Backend full pytest with known structural baseline` step, including its generated `allowed` set, with:

  ```yaml
      - name: Backend full pytest
        working-directory: bowei_ai_dashboard
        run: python -m pytest tests -q
  ```

  No `continue-on-error`, exit-code capture, or failure allowlist may remain.

- [ ] **Step 3: Route CI frontend tests through the unified command**

  Replace the Bash `find tests ... node --test` step with:

  ```yaml
      - name: Frontend tests
        working-directory: frontend
        run: npm run test:all
  ```

  Keep the subsequent `npm run build`, Compose configuration, image builds, PostgreSQL 16 migration gate, health smoke, port-isolation check, whitespace check, and guarded cleanup unchanged.

- [ ] **Step 4: Verify the workflow no longer contains bypasses**

  Run from the repository root:

  ```powershell
  rg -n "known structural baseline|allowed = \{|continue-on-error|mapfile|node --test" .github/workflows/cloud-p1b2a-gate.yml
  ```

  Expected: no matches.

  Then verify required gates remain:

  ```powershell
  rg -n "python -m pytest tests -q|npm run test:all|npm run build|PostgreSQL 16 migration gate|alembic upgrade head|Final repository whitespace check" .github/workflows/cloud-p1b2a-gate.yml
  ```

  Expected: all six gate patterns match.

- [ ] **Step 5: Commit the fail-closed CI gate**

  ```powershell
  git add .github/workflows/cloud-p1b2a-gate.yml
  git commit -m "ci: enforce fail closed quality gates"
  ```

## Task 8: Run the complete trusted-delivery verification

**Files:**

- Verify only; do not modify unrelated files to make commands pass.

- [ ] **Step 1: Run the complete backend suite**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m pytest tests -q
  Set-Location ..
  ```

  Expected: exit 0, no failed tests. Existing deprecation and circular-FK warnings may remain visible; they must not be converted into ignored failures.

- [ ] **Step 2: Run the complete frontend suite and production build**

  ```powershell
  Set-Location frontend
  npm run test:all
  npm run build
  Set-Location ..
  ```

  Expected: both commands exit 0. The current ExcelJS chunk-size warning is allowed as a visible optimization warning, not as a test failure.

- [ ] **Step 3: Recheck migration integrity**

  ```powershell
  Set-Location bowei_ai_dashboard
  python -m alembic heads
  python -m pytest tests/test_migration_bootstrap.py -q
  Set-Location ..
  ```

  Expected: one Alembic head and all migration-bootstrap tests pass.

- [ ] **Step 4: Check patch hygiene and scope**

  ```powershell
  git diff --check
  git status --short
  git diff --stat HEAD~7..HEAD
  ```

  Expected: no whitespace errors; only files listed by this plan appear in the seven implementation commits. Pre-existing user changes remain unstaged and untouched.

- [ ] **Step 5: Validate the PostgreSQL 16 gate in GitHub Actions**

  Push or open the normal review flow for the implementation branch and confirm `CLOUD P1B2A production runtime gate` passes. The decisive evidence is the workflow log showing:

  ```text
  Backend full pytest: success
  Frontend tests: success
  Frontend build: success
  PostgreSQL 16 migration gate: success
  Complete Compose smoke and port isolation: success
  Final repository whitespace check: success
  ```

  If CI fails, stop at the first failing gate, reproduce it locally where possible, and use `systematic-debugging` before changing code.

## Deferred follow-up plans

After all acceptance gates above are green, create and execute these plans in order:

1. Project and permission governance: centralize authorization, resolve scope consistency, and add backend/frontend permission matrices.
2. Confirmation and meeting governance: formalize state transitions, idempotency, dual document-source lifecycle, and audit behavior.
3. Project-init AI, frontend performance, and repository governance: modularize AI import, split heavy bundles, reduce source-shape tests, and define generated-data retention rules.

Do not begin a deferred plan while this baseline has a failing gate.
