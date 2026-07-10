from app.schemas import ProjectCreatePayload


def test_project_create_payload_defaults_to_draft():
    payload = ProjectCreatePayload(name="示例项目")

    assert payload.status == "draft"
    assert getattr(payload, "is_active", False) is False
