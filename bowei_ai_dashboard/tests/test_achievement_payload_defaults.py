from app.schemas import AchievementPayload


def test_achievement_payload_defaults_to_draft():
    payload = AchievementPayload(name="示例成果")

    assert payload.status == "草稿"
    assert payload.status != "计划中"
