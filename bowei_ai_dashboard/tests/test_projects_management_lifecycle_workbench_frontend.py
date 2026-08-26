from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "frontend" / "src"
PAGE = (ROOT / "pages" / "ProjectManagementPage.tsx").read_text(encoding="utf-8")
SECTION = (ROOT / "features" / "settings" / "ProjectsMgmtSection.tsx").read_text(encoding="utf-8")


def test_project_management_page_owns_the_management_surface():
    assert "ProjectsMgmtSection" in PAGE
    assert "项目管理" in PAGE


def test_project_management_section_preserves_lifecycle_and_write_entries():
    for symbol in ["filteredProjects", "setShowNew", "setImportOpen", "handleReturn", "openProjectEditor", "handleDispatch", "dispatchProject"]:
        assert symbol in SECTION
    for status in ["draft", "dispatched", "pending_kickoff", "pending_review", "returned", "active", "archived"]:
        assert status in SECTION


def test_project_team_configuration_requires_explicit_dispatch_gate():
    assert "async function handleDispatch" in SECTION
    assert "await dispatchProject(project.id)" in SECTION
    assert "await notifyProjectOwner(project.id)" not in SECTION
    assert "await notifyProjectOwner(editProjectId)" not in SECTION


def test_project_return_and_approval_reload_the_lifecycle_workbench():
    approve_block = SECTION[SECTION.index("async function handleApprove"):SECTION.index("function openCloseFlow")]
    assert "approveProject(project.id, {})" in approve_block
    assert "returnProject(pid, reason || undefined)" in approve_block
    assert approve_block.count("reloadProjects()") >= 2


def test_project_management_keeps_approval_materials_workbench():
    for symbol in ["approvalMaterialsProject", "ApprovalMaterialsWorkbenchModal", "navigate(`/work/tasks?projectId=${project.id}`)"]:
        assert symbol in SECTION
