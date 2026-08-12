from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.routers import meetings
from app.services import extractor
from app.services.project_init_ai_agent import SourceChunk, generate_project_init_draft


class FakeAIService:
    def __init__(self, captured: dict):
        self.captured = captured

    def invoke_chat(self, capability_key, prompt, context):
        self.captured["capability_key"] = capability_key
        self.captured["prompt"] = prompt
        self.captured["resource_id"] = context.resource_id
        return SimpleNamespace(text='{"title":"例会"}')


def test_meeting_analysis_uses_meeting_capability(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    captured: dict = {}
    monkeypatch.setattr(meetings, "AIService", lambda _db: FakeAIService(captured))

    result = meetings._do_analyze(db, "transcript", "prompt", resource_id=4)

    assert result == {"title": "例会"}
    assert captured["capability_key"] == "meeting.analysis"
    assert captured["resource_id"] == 4


def test_task_extractor_uses_task_extraction_capability():
    captured: dict = {}

    class FakeTaskAIService:
        def invoke_chat(self, capability_key, _prompt, context):
            captured["capability_key"] = capability_key
            captured["resource_type"] = context.resource_type
            return SimpleNamespace(text='{"tasks": [{"key_task": "上线验收"}]}')

    result = extractor.extract_tasks(
        "完成上线验收", ai_service=FakeTaskAIService(), project_names=[]
    )

    assert result["tasks"][0]["key_task"] == "上线验收"
    assert captured["capability_key"] == "task.extraction"


def test_project_init_preserves_injected_test_caller_without_selecting_a_provider():
    result = generate_project_init_draft(
        [SourceChunk(file_name="source.txt", text="实施交付", location="1")],
        [],
        [],
        llm_call=lambda _prompt: '{"tasks": [{"title":"实施交付","evidence":[{"file_name":"source.txt","location":"1","excerpt":"实施交付"}],"subtasks":[{"title":"准备方案","evidence":[{"file_name":"source.txt","location":"1","excerpt":"实施交付"}]}]}]}',
    )

    assert result.tasks[0].title == "实施交付"
