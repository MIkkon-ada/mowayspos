from app.schemas import AchievementPayload, IssuePayload


def test_source_type_normalize_and_labels():
    from app.domain import source_type as ST

    assert ST.normalize("人工录入") == "manual"
    assert ST.normalize("人工补录") == "manual"
    assert ST.normalize("manual") == "manual"
    assert ST.normalize("text") == "manual"
    assert ST.normalize("语音提交") == "voice"
    assert ST.normalize("voice") == "voice"
    assert ST.normalize("会议纪要") == "meeting"
    assert ST.normalize("meeting") == "meeting"
    assert ST.normalize("AI提取") == "ai_extract"
    assert ST.normalize("ai_extract") == "ai_extract"
    assert ST.normalize("批量导入") == "import"
    assert ST.normalize("excel") == "import"
    assert ST.normalize(None) == "unknown"
    assert ST.normalize("") == "unknown"
    assert ST.label("manual") == "人工录入"
    assert ST.label("人工录入") == "人工录入"


def test_issue_and_achievement_payload_source_type_defaults_can_be_normalized():
    from app.domain import source_type as ST

    issue_payload = IssuePayload(project_id=1, description="示例问题")
    achievement_payload = AchievementPayload(name="示例成果")

    assert ST.normalize(issue_payload.source_type) == "manual"
    assert ST.normalize(achievement_payload.source_type) == "manual"
