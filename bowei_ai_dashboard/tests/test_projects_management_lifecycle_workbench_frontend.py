from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = (ROOT / "pages" / "ProjectManagementPage.tsx").read_text(encoding="utf-8")
SECTION = (ROOT / "features" / "settings" / "ProjectsMgmtSection.tsx").read_text(encoding="utf-8")


def test_project_management_page_owns_the_management_surface():
    assert "ProjectsMgmtSection" in PAGE
    assert "项目管理" in PAGE


def test_project_management_section_preserves_lifecycle_and_write_entries():
    for symbol in ["filteredProjects", "setShowNew", "setImportOpen", "handleDispatch", "handleReturn", "openProjectEditor"]:
        assert symbol in SECTION
    for status in ["draft", "dispatched", "pending_review", "returned", "active", "archived"]:
        assert status in SECTION


def test_project_management_keeps_approval_materials_workbench():
    for symbol in ["approvalMaterialsProject", "ApprovalMaterialsWorkbenchModal", "navigate(`/work/tasks?projectId=${project.id}`)"]:
        assert symbol in SECTION
