import asyncio
import json
import sys
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.routers import meetings


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_draft_visibility_allows_creator_owner_and_ceo_but_not_member():
    db = _db()
    db.add_all([
        models.Person(id=1, name="Creator", is_active=True),
        models.Person(id=2, name="Owner", is_active=True),
        models.Person(id=3, name="Member", is_active=True),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=2, role="owner"),
        models.ProjectMember(project_id=1, person_id=3, role="member"),
    ])
    db.add_all([
        models.Account(username="creator", password_hash="x", person_id=1, status="active"),
        models.Account(username="owner", password_hash="x", person_id=2, status="active"),
        models.Account(username="member", password_hash="x", person_id=3, status="active"),
    ])
    db.commit()
    row = models.Meeting(project_id=1, creator_person_id=1, host="Creator", publish_status="draft")
    creator = {"name": "Creator", "is_ceo": False, "is_tech_admin": False}
    owner = {"name": "Owner", "is_ceo": False, "is_tech_admin": False}
    member = {"name": "Member", "is_ceo": False, "is_tech_admin": False}
    ceo = {"name": "CEO", "is_ceo": True, "is_tech_admin": False}

    assert meetings._can_view_meeting_draft(row, "creator", creator, db)
    assert meetings._can_view_meeting_draft(row, "owner", owner, db)
    assert meetings._can_view_meeting_draft(row, "ceo", ceo, db)
    assert not meetings._can_view_meeting_draft(row, "member", member, db)


def test_progress_meeting_analysis_returns_speaker_flag(monkeypatch):
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    ])
    db.commit()
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(meetings, "_do_analyze", lambda *_args: {"title": "Progress review", "participants": "Invented attendee"})

    result = asyncio.run(meetings.analyze_meeting(
        meetings.MeetingAnalyzeRequest(text="1. Owner completed the weekly review", project_id=1, mode="progress"),
        current_user="owner",
        db=db,
    ))

    assert result["title"] == "Progress review"
    assert result["has_speakers"] is True
    assert result["participants"] == ""


def test_meeting_analyzer_uses_first_json_object_when_model_returns_multiple(monkeypatch):
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"title":"First"}\n{"title":"Second"}'))]
    )
    fake_openai = SimpleNamespace(
        OpenAI=lambda **_kwargs: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_request: fake_response))
        )
    )
    monkeypatch.setitem(sys.modules, "openai", fake_openai)
    monkeypatch.setattr(
        meetings,
        "get_provider_config",
        lambda _provider: {
            "api_key": "test-key",
            "base_url": "https://example.invalid/v1",
            "model": "test-model",
        },
    )

    result = meetings._do_analyze("sample", "prompt", "dashscope")

    assert result == {"title": "First"}


def test_progress_meeting_analysis_uses_work_plan_as_non_factual_context(monkeypatch):
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    ])
    db.commit()
    captured: dict[str, str] = {}
    monkeypatch.setattr(meetings, "_build_all_members_context", lambda *_args: "WORK PLAN: Owner is assigned the historical task")
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(meetings, "_do_analyze", lambda _text, prompt, _provider: captured.setdefault("prompt", prompt) and {"title": "Review"})

    asyncio.run(meetings.analyze_meeting(
        meetings.MeetingAnalyzeRequest(text="Owner confirmed the agenda", project_id=1, mode="progress", member_names=["Owner"]),
        current_user="owner",
        db=db,
    ))

    assert "WORK PLAN: Owner is assigned the historical task" in captured["prompt"]
    assert "仅用于理解和核对" in captured["prompt"]


def test_progress_meeting_prompt_forbids_inference_and_status_judgments(monkeypatch):
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
    ])
    db.commit()
    captured: dict[str, str] = {}
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(
        meetings,
        "_do_analyze",
        lambda _text, prompt, _provider: captured.setdefault("prompt", prompt) and {},
    )

    asyncio.run(meetings.analyze_meeting(
        meetings.MeetingAnalyzeRequest(text="Only discuss the delivery plan", project_id=1, mode="progress"),
        current_user="owner",
        db=db,
    ))

    assert "不得推断、评价、补全" in captured["prompt"]
    assert "不能生成进度状态、角色、领导反馈" in captured["prompt"]


def test_meeting_analysis_tags_only_exact_project_member_matches(monkeypatch):
    db = _db()
    db.add_all([
        models.Person(id=1, name="Owner", is_active=True),
        models.Person(id=2, name="Member", is_active=True),
        models.Account(username="owner", password_hash="x", person_id=1, status="active"),
        models.Project(id=1, name="Project", status="active", is_active=True),
        models.ProjectMember(project_id=1, person_id=1, person_name_snapshot="Owner", role="owner"),
        models.ProjectMember(project_id=1, person_id=2, person_name_snapshot="Member", role="member"),
    ])
    db.commit()
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(meetings, "_do_analyze", lambda *_args: {
        "reports": [
            {"member": "Member", "role": "项目经理", "content": "说明当前安排"},
            {"member": "Unknown", "role": "负责人", "content": "提出一个建议"},
            {"member": "Owner", "content": ""},
        ],
        "confirmed_items": ["采用方案 A"],
        "decision_requests": ["请企业教练判断是否追加预算"],
        "action_items": [
            {"member": "Owner", "task": "Confirm scope", "deadline": ""},
            {"member": "Unknown", "task": "Review risks", "deadline": ""},
        ]
    })

    result = asyncio.run(meetings.analyze_meeting(
        meetings.MeetingAnalyzeRequest(text="Owner will confirm scope", project_id=1, mode="progress"),
        current_user="owner",
        db=db,
    ))

    assert json.loads(result["task_list_json"]) == [
        {"member": "Owner", "task": "Confirm scope", "deadline": ""},
        {"member": "待确认", "task": "Review risks", "deadline": ""},
    ]
    assert json.loads(result["reports_json"]) == [
        {"member": "Member", "role": "项目经理", "content": "说明当前安排"},
        {"member": "待确认", "role": "负责人", "content": "提出一个建议"},
    ]
    assert json.loads(result["confirmed_items_json"]) == ["采用方案 A"]
    assert json.loads(result["decision_items_json"]) == ["请企业教练判断是否追加预算"]
