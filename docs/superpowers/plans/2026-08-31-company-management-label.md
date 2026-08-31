# Company Management Label Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Replace every user-facing company-CEO label with “公司管理” while preserving role keys, API contracts, stored status values, and project-coach terminology.

**Architecture:** Keep company_ceo, project_ceo, is_ceo, API endpoints, and canonical submission-status values as compatibility-only identifiers. Change display-label maps and user-facing copy at the frontend/backend boundary, while retaining historical Chinese role/status aliases for existing records.

**Tech Stack:** React + TypeScript + Node tests; FastAPI + Python + pytest.

---

## File structure

- bowei_ai_dashboard/app/permissions.py: global role display label and legacy normalization aliases.
- frontend/src/domain/roles.ts: frontend system-role display label and legacy normalization aliases.
- frontend/src/domain/submissionStatus.ts: UI-only labels for persisted ceo status keys.
- frontend/src/pages/ProjectAdminPage.tsx, ProjectMembersPage.tsx, IssuesPage.tsx, IssueDetailPage.tsx: direct end-user role, action, and operation-log copy.
- bowei_ai_dashboard/app/routers/projects.py: end-user authorization error text.
- bowei_ai_dashboard/README.md and bowei_ai_dashboard/docs/: business-facing documentation.
- bowei_ai_dashboard/tests/test_company_management_label_contract.py: regression coverage.

### Task 1: Protect display-name and compatibility boundaries

**Files:**
- Create: bowei_ai_dashboard/tests/test_company_management_label_contract.py
- Modify: bowei_ai_dashboard/app/permissions.py:21-32
- Modify: frontend/src/domain/roles.ts:23-40
- Modify: frontend/src/domain/submissionStatus.ts:1-52

- [ ] **Step 1: Write the failing contract test**

~~~python
from pathlib import Path

from app.permissions import ROLE_CEO, SYSTEM_ROLE_LABELS, normalize_system_role


def test_company_management_is_the_current_company_role_label():
    assert SYSTEM_ROLE_LABELS[ROLE_CEO] == "公司管理"
    assert normalize_system_role("公司管理") == ROLE_CEO
    assert normalize_system_role("公司CEO") == ROLE_CEO


def test_frontend_preserves_technical_keys_and_changes_only_labels():
    root = Path(__file__).resolve().parents[2]
    roles = (root / "frontend/src/domain/roles.ts").read_text(encoding="utf-8")
    statuses = (root / "frontend/src/domain/submissionStatus.ts").read_text(encoding="utf-8")
    assert "[SYSTEM_ROLE_CEO]: '公司管理'" in roles
    assert "'公司CEO': SYSTEM_ROLE_CEO" in roles
    assert "export const SYSTEM_ROLE_CEO = 'company_ceo'" in roles
    assert "[S_WAITING_CEO]:          '待企业教练决策'" in statuses
    assert "[S_CEO_DECIDED]:          '企业教练已批示'" in statuses
    assert "export const S_WAITING_CEO          = '待CEO决策'" in statuses
    assert "export const S_CEO_DECIDED          = 'CEO已批示'" in statuses
~~~

- [ ] **Step 2: Run test to verify it fails**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py -v

Expected: FAIL because current labels are 公司CEO and 企业教练.

- [ ] **Step 3: Implement the display-only mapping**

~~~python
# bowei_ai_dashboard/app/permissions.py
SYSTEM_ROLE_LABELS = {
    ROLE_CEO: "公司管理",
    # Existing labels unchanged.
}
_LEGACY_SYSTEM_ROLE_VALUES = {
    "公司管理": ROLE_CEO,
    "公司CEO": ROLE_CEO,
    "公司 CEO": ROLE_CEO,
    # Existing historical values unchanged.
}
~~~

~~~ts
// frontend/src/domain/roles.ts
[SYSTEM_ROLE_CEO]: '公司管理',

const LEGACY_ROLE_MAP: Record<string, string> = {
  '公司管理': SYSTEM_ROLE_CEO,
  '公司CEO': SYSTEM_ROLE_CEO,
  '公司 CEO': SYSTEM_ROLE_CEO,
  // Keep existing historical aliases.
}

// frontend/src/domain/submissionStatus.ts
[S_WAITING_CEO]: '待企业教练决策',
[S_CEO_DECIDED]: '企业教练已批示',
~~~

Do not change ROLE_CEO, SYSTEM_ROLE_CEO, S_WAITING_CEO, S_CEO_DECIDED, API names, or database values.

- [ ] **Step 4: Run test to verify it passes**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~powershell
git add bowei_ai_dashboard/app/permissions.py frontend/src/domain/roles.ts frontend/src/domain/submissionStatus.ts bowei_ai_dashboard/tests/test_company_management_label_contract.py
git commit -m "feat: rename company CEO display role"
~~~

### Task 2: Replace direct product copy and authorization messages

**Files:**
- Modify: frontend/src/pages/ProjectAdminPage.tsx:116
- Modify: frontend/src/pages/ProjectMembersPage.tsx:79
- Modify: frontend/src/pages/IssuesPage.tsx:96-106
- Modify: frontend/src/pages/IssueDetailPage.tsx:49-59,509-516
- Modify: bowei_ai_dashboard/app/permissions.py:614
- Modify: bowei_ai_dashboard/app/routers/projects.py:357-399
- Modify: bowei_ai_dashboard/tests/test_company_management_label_contract.py

- [ ] **Step 1: Add failing assertions for visible copy**

~~~python
def test_product_copy_uses_company_management_without_renaming_apis():
    root = Path(__file__).resolve().parents[2]
    project_admin = (root / "frontend/src/pages/ProjectAdminPage.tsx").read_text(encoding="utf-8")
    members = (root / "frontend/src/pages/ProjectMembersPage.tsx").read_text(encoding="utf-8")
    issues = (root / "frontend/src/pages/IssuesPage.tsx").read_text(encoding="utf-8")
    detail = (root / "frontend/src/pages/IssueDetailPage.tsx").read_text(encoding="utf-8")
    permissions = (root / "bowei_ai_dashboard/app/permissions.py").read_text(encoding="utf-8")
    projects = (root / "bowei_ai_dashboard/app/routers/projects.py").read_text(encoding="utf-8")
    assert "项目管理对公司管理 / 超级管理员开放。" in project_admin
    assert "成员管理仅对超级管理员或公司管理开放。" in members
    assert "请求公司管理决策" in issues
    assert "⚡ 请求公司管理决策" in detail
    assert "仅超级管理员、公司管理、企业教练、负责人或创建人可执行此操作" in permissions
    assert "项目归档需提交公司管理审核。" in projects
    assert "requestIssueCeo" in detail
~~~

- [ ] **Step 2: Run test to verify it fails**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py::test_product_copy_uses_company_management_without_renaming_apis -v

Expected: FAIL on the old visible copy.

- [ ] **Step 3: Replace direct copy, not identifiers**

~~~tsx
// ProjectAdminPage.tsx
<Hint title="无权限访问" subtitle="项目管理对公司管理 / 超级管理员开放。" />

// ProjectMembersPage.tsx
<Hint title="无权限访问" subtitle="成员管理仅对超级管理员或公司管理开放。" />

// IssuesPage.tsx and IssueDetailPage.tsx
issue_request_ceo: '请求公司管理决策',
// visible button
⚡ 请求公司管理决策
~~~

~~~python
# permissions.py and routers/projects.py
detail = "仅超级管理员、公司管理、企业教练、负责人或创建人可执行此操作"
raise HTTPException(403, "项目归档需提交公司管理审核。")
~~~

Keep requestIssueCeo, doRequestCeo, company_ceo, project_ceo, is_ceo, and every endpoint unchanged. Keep 企业教练 for the project-level role.

- [ ] **Step 4: Run test to verify it passes**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~powershell
git add frontend/src/pages/ProjectAdminPage.tsx frontend/src/pages/ProjectMembersPage.tsx frontend/src/pages/IssuesPage.tsx frontend/src/pages/IssueDetailPage.tsx bowei_ai_dashboard/app/permissions.py bowei_ai_dashboard/app/routers/projects.py bowei_ai_dashboard/tests/test_company_management_label_contract.py
git commit -m "feat: update company management copy"
~~~

### Task 3: Update business documentation

**Files:**
- Modify: bowei_ai_dashboard/README.md:26
- Modify: bowei_ai_dashboard/PROJECT_STATE.md
- Modify: bowei_ai_dashboard/docs/UAT_TEST_PLAN.md:14-35
- Modify: bowei_ai_dashboard/docs/LAUNCH_ACCEPTANCE_CHECKLIST.md:31-63
- Modify: bowei_ai_dashboard/AGENTS.md
- Modify: bowei_ai_dashboard/BACKEND_API_REGISTRY.md:146-155
- Modify: bowei_ai_dashboard/tests/test_company_management_label_contract.py

- [ ] **Step 1: Add failing documentation vocabulary test**

~~~python
def test_business_documents_use_company_management_term():
    root = Path(__file__).resolve().parents[2] / "bowei_ai_dashboard"
    documents = [
        root / "README.md",
        root / "PROJECT_STATE.md",
        root / "docs/UAT_TEST_PLAN.md",
        root / "docs/LAUNCH_ACCEPTANCE_CHECKLIST.md",
        root / "BACKEND_API_REGISTRY.md",
    ]
    for path in documents:
        source = path.read_text(encoding="utf-8")
        assert "公司 CEO" not in source
        assert "公司CEO" not in source
        assert "公司管理" in source
~~~

- [ ] **Step 2: Run test to verify it fails**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py::test_business_documents_use_company_management_term -v

Expected: FAIL because current business documents still use 公司 CEO.

- [ ] **Step 3: Update business wording and retain technical-key notes**

~~~markdown
- 公司管理：创建项目入口、配置人员、全局查看
- [ ] 公司管理拥有全局查看和项目入口配置权限
- [ ] 已确认 / 转交 / 公司管理决策流程正常
~~~

In BACKEND_API_REGISTRY.md, retain the explanation that company_ceo and project_ceo are compatibility keys, but change the business label to 公司管理. In AGENTS.md, alter only the role wording and preserve every engineering instruction.

- [ ] **Step 4: Run documentation and contract tests**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py -v

Expected: PASS.

- [ ] **Step 5: Commit**

~~~powershell
git add bowei_ai_dashboard/README.md bowei_ai_dashboard/PROJECT_STATE.md bowei_ai_dashboard/docs/UAT_TEST_PLAN.md bowei_ai_dashboard/docs/LAUNCH_ACCEPTANCE_CHECKLIST.md bowei_ai_dashboard/AGENTS.md bowei_ai_dashboard/BACKEND_API_REGISTRY.md bowei_ai_dashboard/tests/test_company_management_label_contract.py
git commit -m "docs: rename company management role"
~~~

### Task 4: Full verification and compatibility audit

**Files:**
- Verify: all Task 1–3 files

- [ ] **Step 1: Run focused role and dashboard suites**

Run: bowei_ai_dashboard/.venv/Scripts/python.exe -m pytest bowei_ai_dashboard/tests/test_company_management_label_contract.py bowei_ai_dashboard/tests/test_role_boundary.py bowei_ai_dashboard/tests/test_dashboard_project_scope_frontend.py bowei_ai_dashboard/tests/test_project_close_request_permissions.py -v

Expected: PASS, showing no company-management account was promoted into a project-coach role and dashboard scope is unchanged.

- [ ] **Step 2: Run frontend checks**

Run: npm --prefix frontend run test -- --run; npm --prefix frontend run build

Expected: all frontend tests and the production build pass.

- [ ] **Step 3: Audit visible vocabulary and technical compatibility**

~~~powershell
rg -n -i -g '!backups/**' -g '!**/node_modules/**' -g '!**/.venv/**' "公司 ?CEO|请求CEO决策|待CEO决策|CEO已批示" frontend/src bowei_ai_dashboard/app bowei_ai_dashboard/README.md bowei_ai_dashboard/docs
rg -n "company_ceo|project_ceo|is_ceo|S_WAITING_CEO|S_CEO_DECIDED" bowei_ai_dashboard/app/permissions.py frontend/src/domain/roles.ts frontend/src/domain/submissionStatus.ts
~~~

Expected: the first command returns only intentional legacy aliases or non-user-facing compatibility comments; the second confirms all required technical keys remain.

- [ ] **Step 4: Run final repository checks**

Run: git diff --check; git status --short

Expected: no whitespace errors and no unrelated files are staged.

## Plan self-review

- Spec coverage: Task 1 covers display maps and compatibility; Task 2 covers direct UI/action/error text; Task 3 covers all business documentation; Task 4 verifies behavior, build output, terminology, and key preservation.
- Placeholder scan: no deferred implementation work or unspecified checks remain.
- Consistency: global display name is always 公司管理, project project_ceo and its decision statuses remain 企业教练, and stored/API ceo values remain unchanged.
