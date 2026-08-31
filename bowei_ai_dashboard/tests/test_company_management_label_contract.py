from pathlib import Path

from app.permissions import ROLE_CEO, SYSTEM_ROLE_LABELS, normalize_system_role


ROOT = Path(__file__).resolve().parents[2]


def test_company_management_is_the_current_company_role_label():
    assert SYSTEM_ROLE_LABELS[ROLE_CEO] == "公司管理"
    assert normalize_system_role("公司管理") == ROLE_CEO
    assert normalize_system_role("公司CEO") == ROLE_CEO


def test_frontend_preserves_technical_keys_and_changes_only_labels():
    roles = (ROOT / "frontend/src/domain/roles.ts").read_text(encoding="utf-8")
    statuses = (ROOT / "frontend/src/domain/submissionStatus.ts").read_text(encoding="utf-8")

    assert "[SYSTEM_ROLE_CEO]: '公司管理'" in roles
    assert "'公司CEO': SYSTEM_ROLE_CEO" in roles
    assert "export const SYSTEM_ROLE_CEO = 'company_ceo'" in roles
    assert "[S_WAITING_CEO]:          '待企业教练决策'" in statuses
    assert "[S_CEO_DECIDED]:          '企业教练已批示'" in statuses
    assert "export const S_WAITING_CEO          = '待CEO决策'" in statuses
    assert "export const S_CEO_DECIDED          = 'CEO已批示'" in statuses


def test_product_copy_uses_company_management_without_renaming_apis():
    project_admin = (ROOT / "frontend/src/pages/ProjectAdminPage.tsx").read_text(encoding="utf-8")
    members = (ROOT / "frontend/src/pages/ProjectMembersPage.tsx").read_text(encoding="utf-8")
    issues = (ROOT / "frontend/src/pages/IssuesPage.tsx").read_text(encoding="utf-8")
    detail = (ROOT / "frontend/src/pages/IssueDetailPage.tsx").read_text(encoding="utf-8")
    permissions = (ROOT / "bowei_ai_dashboard/app/permissions.py").read_text(encoding="utf-8")
    projects = (ROOT / "bowei_ai_dashboard/app/routers/projects.py").read_text(encoding="utf-8")
    seed = (ROOT / "bowei_ai_dashboard/app/seed.py").read_text(encoding="utf-8")

    assert "项目管理对公司管理 / 超级管理员开放。" in project_admin
    assert "成员管理仅对超级管理员或公司管理开放。" in members
    assert "请求公司管理决策" in issues
    assert "⚡ 请求公司管理决策" in detail
    assert "仅超级管理员、公司管理、企业教练、负责人或创建人可执行此操作" in permissions
    assert "仅公司管理或超级管理员可执行此操作" in projects
    assert "项目归档需提交公司管理审核。" in projects
    assert 'role="公司管理"' in seed
    assert "requestIssueCeo" in detail


def test_business_documents_use_company_management_term():
    root = ROOT / "bowei_ai_dashboard"
    documents = [
        root / "README.md",
        root / "PROJECT_STATE.md",
        root / "docs/UAT_TEST_PLAN.md",
        root / "docs/LAUNCH_ACCEPTANCE_CHECKLIST.md",
        root / "BACKEND_API_REGISTRY.md",
        root / "AGENTS.md",
        ROOT / "docs/semantic-contract.md",
        ROOT / "docs/full-flow-manual-acceptance-runbook.md",
        ROOT / "docs/execution-submission-work-progress-acceptance.md",
        ROOT / "docs/MOWAYS_WAVE_GAP_ANALYSIS.md",
    ]

    for path in documents:
        source = path.read_text(encoding="utf-8")
        assert "公司 CEO" not in source
        assert "公司CEO" not in source
        assert "公司管理" in source
