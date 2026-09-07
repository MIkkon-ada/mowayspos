from app.main import _default_route


def test_project_owner_default_route_is_project_management():
    assert _default_route(None, {"owned_projects": ["Project"], "visible_projects": ["Project"]}) == "/home/projects"
