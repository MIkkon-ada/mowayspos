from app.services.meeting_traceability import normalize_action_items


def test_relative_month_day_deadline_does_not_gain_an_invented_year():
    items = normalize_action_items(
        [{"member": "Owner", "task": "8月3日前完成流程定稿", "deadline": "2024-08-03"}],
        "会议讨论：Owner 8月3日前完成流程定稿。",
    )

    assert items[0]["deadline"] == "8月3日前"


def test_explicit_transcript_year_is_preserved():
    items = normalize_action_items(
        [{"member": "Owner", "task": "2026年8月3日前完成流程定稿", "deadline": "2026-08-03"}],
        "会议讨论：Owner 2026年8月3日前完成流程定稿。",
    )

    assert items[0]["deadline"] == "2026-08-03"


def test_missing_deadline_is_not_inferred_from_current_date():
    items = normalize_action_items(
        [{"member": "Owner", "task": "下周完成流程定稿", "deadline": "2024-08-03"}],
        "会议讨论：Owner 下周完成流程定稿。",
    )

    assert items[0]["deadline"] == "待确认"

