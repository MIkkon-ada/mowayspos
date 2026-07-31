# Personal Work Report Realtime ASR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade personal work-report recording to use a permission-scoped DashScope Fun-ASR realtime session, 100 ms PCM packets, an explicit start/stop/done protocol, stable transcript merging, safe rollback, and measurable latency.

**Architecture:** Keep the React page and existing AI extraction/submission flow. Split browser protocol/text merging, AudioWorklet packetization, backend context construction, and DashScope session management into focused units; keep the WebSocket router as an authenticated coordinator. Roll out transport fixes separately from the model/context switch so each variable can be measured and reverted.

**Tech Stack:** React 19, TypeScript 5.8, AudioWorklet, WebSocket, FastAPI, SQLAlchemy, DashScope Python SDK, Node test runner, pytest.

---

## File map

### Create

- `bowei_ai_dashboard/app/services/asr_context.py` — validates report scope and builds the bounded task context.
- `bowei_ai_dashboard/app/services/realtime_asr.py` — wraps one DashScope realtime recognition session.
- `bowei_ai_dashboard/tests/test_asr_settings.py` — validates ASR environment parsing and defaults.
- `bowei_ai_dashboard/tests/test_asr_context.py` — validates permissions, field selection, and length limits.
- `bowei_ai_dashboard/tests/test_realtime_asr.py` — validates callback normalization and stop completion.
- `bowei_ai_dashboard/tests/test_transcribe_stream_protocol.py` — validates the WebSocket state machine.
- `frontend/src/features/voice-update/voiceRecorderProtocol.ts` — owns message types and deterministic transcript merging.
- `frontend/tests/voiceRecorderProtocol.test.mjs` — tests parsing, deduplication, and composed text.
- `frontend/tests/pcmAudioProcessor.test.mjs` — executes the worklet in a VM with browser stubs.
- `docs/acceptance/personal-work-report-realtime-asr.md` — fixed-corpus and production acceptance procedure.

### Modify

- `bowei_ai_dashboard/app/settings.py` — adds typed ASR runtime configuration.
- `bowei_ai_dashboard/app/routers/transcribe.py` — replaces the legacy stream loop with the explicit protocol.
- `bowei_ai_dashboard/tests/test_production_runtime_security.py` — updates direct WebSocket security invocation.
- `bowei_ai_dashboard/tests/test_production_runtime_contract.py` — requires documented production ASR variables.
- `.env.production.example` — documents safe ASR settings.
- `bowei_ai_dashboard/.env.example` — documents development ASR settings.
- `frontend/public/worklets/pcm-audio-processor.js` — buffers 1600 samples and flushes the tail.
- `frontend/src/features/voice-update/useVoiceRecorder.ts` — implements the client state machine.
- `frontend/src/pages/VoiceUpdatePage.tsx` — supplies the selected project/task and locks binding during media activity.
- `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx` — presents connecting/stopping states and makes the transcript read-only during media activity.
- `frontend/src/features/voice-update/voiceUpdateFlow.css` — styles partial text and non-recording busy states.
- `frontend/tests/workReportFlowPage.test.mjs` — protects work-report-only scope and UI wiring.

## Task 1: Add typed ASR runtime settings

**Files:**

- Modify: `bowei_ai_dashboard/app/settings.py`
- Create: `bowei_ai_dashboard/tests/test_asr_settings.py`
- Modify: `.env.production.example`
- Modify: `bowei_ai_dashboard/.env.example`
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_contract.py`

- [ ] **Step 1: Write the failing settings tests**

Create `bowei_ai_dashboard/tests/test_asr_settings.py`:

```python
from app.settings import get_asr_settings


def test_asr_settings_have_safe_defaults(monkeypatch):
    for key in (
        "ASR_REALTIME_MODEL",
        "ASR_CONTEXT_ENABLED",
        "ASR_PACKET_DURATION_MS",
        "ASR_STOP_TIMEOUT_SECONDS",
        "ASR_HEARTBEAT_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = get_asr_settings()

    assert settings.realtime_model == "fun-asr-realtime"
    assert settings.context_enabled is True
    assert settings.packet_duration_ms == 100
    assert settings.stop_timeout_seconds == 8.0
    assert settings.heartbeat_enabled is True


def test_asr_settings_clamp_invalid_numeric_values(monkeypatch):
    monkeypatch.setenv("ASR_PACKET_DURATION_MS", "3")
    monkeypatch.setenv("ASR_STOP_TIMEOUT_SECONDS", "invalid")
    monkeypatch.setenv("ASR_CONTEXT_ENABLED", "false")
    monkeypatch.setenv("ASR_HEARTBEAT_ENABLED", "0")

    settings = get_asr_settings()

    assert settings.packet_duration_ms == 100
    assert settings.stop_timeout_seconds == 8.0
    assert settings.context_enabled is False
    assert settings.heartbeat_enabled is False
```

- [ ] **Step 2: Run the settings tests and verify they fail**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_asr_settings.py -v
```

Expected: FAIL because `get_asr_settings` does not exist.

- [ ] **Step 3: Implement the typed configuration**

Add to `bowei_ai_dashboard/app/settings.py`:

```python
@dataclass(frozen=True)
class AsrSettings:
    realtime_model: str
    context_enabled: bool
    packet_duration_ms: int
    stop_timeout_seconds: float
    heartbeat_enabled: bool


def _bounded_int(raw: str | None, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw or "")
    except ValueError:
        return default
    return value if minimum <= value <= maximum else default


def _bounded_float(raw: str | None, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(raw or "")
    except ValueError:
        return default
    return value if minimum <= value <= maximum else default


def get_asr_settings() -> AsrSettings:
    return AsrSettings(
        realtime_model=os.getenv("ASR_REALTIME_MODEL", "fun-asr-realtime").strip()
        or "fun-asr-realtime",
        context_enabled=parse_bool(
            os.getenv("ASR_CONTEXT_ENABLED"), default=True
        ),
        packet_duration_ms=_bounded_int(
            os.getenv("ASR_PACKET_DURATION_MS"), 100, 40, 250
        ),
        stop_timeout_seconds=_bounded_float(
            os.getenv("ASR_STOP_TIMEOUT_SECONDS"), 8.0, 2.0, 30.0
        ),
        heartbeat_enabled=parse_bool(
            os.getenv("ASR_HEARTBEAT_ENABLED"), default=True
        ),
    )
```

Document these exact non-secret values in `.env.production.example` and
`bowei_ai_dashboard/.env.example`:

```dotenv
ASR_REALTIME_MODEL=fun-asr-realtime
ASR_CONTEXT_ENABLED=true
ASR_PACKET_DURATION_MS=100
ASR_STOP_TIMEOUT_SECONDS=8
ASR_HEARTBEAT_ENABLED=true
```

Extend `test_production_environment_example_is_secret_free_and_complete` in
`bowei_ai_dashboard/tests/test_production_runtime_contract.py` with the same five
expected strings. Do not add an ASR API key; the service continues to use
`DASHSCOPE_API_KEY`.

- [ ] **Step 4: Run settings and runtime-contract tests**

Run from `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_asr_settings.py tests/test_production_runtime_contract.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the configuration slice**

```powershell
git add app/settings.py tests/test_asr_settings.py tests/test_production_runtime_contract.py .env.example ..\.env.production.example
git commit -m "feat: add realtime asr runtime settings"
```

## Task 2: Build permission-scoped work-report context

**Files:**

- Create: `bowei_ai_dashboard/app/services/asr_context.py`
- Create: `bowei_ai_dashboard/tests/test_asr_context.py`

- [ ] **Step 1: Write failing context unit tests**

Create `bowei_ai_dashboard/tests/test_asr_context.py`. Use a temporary SQLite
engine and the real ORM models so the test does not touch the configured
application database:

```python
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app import models
from app.services.asr_context import build_work_report_asr_context


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def seed_reportable_task(db):
    person = models.Person(name="张三", system_role="normal_member")
    db.add(person)
    db.flush()
    db.add(models.Account(username="zhangsan", password_hash="x", person_id=person.id))
    project = models.Project(name="博维 AI 驾驶舱", status="active", is_active=True)
    db.add(project)
    db.flush()
    db.add(models.ProjectMember(
        project_id=project.id,
        person_id=person.id,
        person_name_snapshot="张三",
        role="member",
    ))
    task = models.Task(
        project_id=project.id,
        key_task="成果库与工作推进页面升级",
        owner="李明",
        coordinator="王晓燕",
        collaborators="赵六、钱七",
    )
    db.add(task)
    db.flush()
    subtask = models.SubTask(
        task_id=task.id,
        title="完成项目驾驶舱二期验收",
        assignee="张三",
        status="进行中",
    )
    db.add(subtask)
    db.commit()
    return project, task, subtask


def test_context_contains_only_approved_structured_fields(db):
    project, task, subtask = seed_reportable_task(db)

    context = build_work_report_asr_context(
        "zhangsan", project.id, subtask.id, db
    )

    assert "博维 AI 驾驶舱" in context
    assert "成果库与工作推进页面升级" in context
    assert "完成项目驾驶舱二期验收" in context
    for name in ("张三", "李明", "王晓燕", "赵六", "钱七"):
        assert name in context
    assert len(context) <= 400


def test_context_rejects_task_from_another_project(db):
    project, task, subtask = seed_reportable_task(db)
    other = models.Project(name="其他项目", status="active", is_active=True)
    db.add(other)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        build_work_report_asr_context("zhangsan", other.id, subtask.id, db)

    assert exc.value.status_code in {403, 404}


def test_context_rejects_member_who_cannot_report_task(db):
    project, task, subtask = seed_reportable_task(db)
    other_person = models.Person(name="无关成员", system_role="normal_member")
    db.add(other_person)
    db.flush()
    db.add(models.Account(username="other", password_hash="x", person_id=other_person.id))
    db.add(models.ProjectMember(
        project_id=project.id,
        person_id=other_person.id,
        person_name_snapshot="无关成员",
        role="member",
    ))
    db.commit()

    with pytest.raises(HTTPException) as exc:
        build_work_report_asr_context("other", project.id, subtask.id, db)

    assert exc.value.status_code == 403
```

- [ ] **Step 2: Run the context tests and verify they fail**

```powershell
python -m pytest tests/test_asr_context.py -v
```

Expected: FAIL because `app.services.asr_context` does not exist.

- [ ] **Step 3: Implement the context service**

Create `bowei_ai_dashboard/app/services/asr_context.py`:

```python
from __future__ import annotations

import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..permissions import (
    get_all_project_roles,
    get_user_context_from_db,
    require_login,
    require_project_access,
)

_FIXED_TERMS = (
    "Moways",
    "关键任务",
    "重点工作",
    "成果入库",
    "企业教练",
    "项目统筹人",
)
_MANAGER_ROLES = {"owner", "coordinator"}


def _names(*raw_values: str) -> list[str]:
    result: list[str] = []
    for raw in raw_values:
        for value in re.split(r"[,，、/]", raw or ""):
            name = value.strip()
            if name and name not in result:
                result.append(name)
    return result


def _bounded_lines(lines: list[str], limit: int = 400) -> str:
    accepted: list[str] = []
    for line in lines:
        candidate = "\n".join([*accepted, line])
        if len(candidate) <= limit:
            accepted.append(line)
    return "\n".join(accepted)


def build_work_report_asr_context(
    current_user: str,
    project_id: int,
    selected_task_id: int,
    db: Session,
) -> str:
    username = require_login(current_user, db)
    require_project_access(username, project_id, db)
    identity = get_user_context_from_db(username, db)
    display_name = str(identity.get("name") or username)

    project = db.get(models.Project, project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    if (project.status or "").strip() != "active":
        raise HTTPException(409, "project is not active")

    row = (
        db.query(models.SubTask, models.Task)
        .join(models.Task, models.SubTask.task_id == models.Task.id)
        .filter(
            models.SubTask.id == selected_task_id,
            models.SubTask.is_deleted.is_(False),
            models.Task.is_deleted.is_(False),
        )
        .first()
    )
    if row is None:
        raise HTTPException(404, "task not found")
    subtask, task = row
    if task.project_id != project_id:
        raise HTTPException(403, "task is outside project")

    person_id = identity.get("person_id")
    roles = get_all_project_roles(person_id, project_id, db) if person_id else []
    manager = bool(identity.get("can_view_all")) or bool(_MANAGER_ROLES.intersection(roles))
    if not manager and display_name not in {task.owner, subtask.assignee}:
        raise HTTPException(403, "task report permission denied")

    related_names = _names(
        subtask.assignee,
        task.owner,
        task.coordinator,
        task.collaborators,
    )
    lines = [
        f"当前关键任务：{subtask.title}。",
        f"当前重点工作：{task.key_task}。",
        f"当前项目：{project.name}。",
        f"相关人员：{'、'.join(related_names)}。" if related_names else "",
        f"常用术语：{'、'.join(_FIXED_TERMS)}。",
    ]
    lines = [line for line in lines if line]
    return _bounded_lines(lines)
```

- [ ] **Step 4: Run the context tests**

```powershell
python -m pytest tests/test_asr_context.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the existing voice-context regression test set**

```powershell
python -m pytest tests -k "voice_context or work_report" -v
```

Expected: PASS, apart from any already documented repository baseline unrelated
to these files. Investigate any new failure before proceeding.

- [ ] **Step 6: Commit the context slice**

```powershell
git add app/services/asr_context.py tests/test_asr_context.py
git commit -m "feat: build scoped work report asr context"
```

## Task 3: Wrap DashScope realtime recognition

**Files:**

- Create: `bowei_ai_dashboard/app/services/realtime_asr.py`
- Create: `bowei_ai_dashboard/tests/test_realtime_asr.py`

- [ ] **Step 1: Write failing adapter tests with a fake Recognition**

Create `bowei_ai_dashboard/tests/test_realtime_asr.py`:

```python
import asyncio
from types import SimpleNamespace

from app.settings import AsrSettings
from app.services.realtime_asr import DashScopeRealtimeAsr


class FakeRecognition:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.callback = kwargs["callback"]
        self.frames = []
        self.start_kwargs = None
        self.stopped = False
        self.__class__.instances.append(self)

    def start(self, **kwargs):
        self.start_kwargs = kwargs

    def send_audio_frame(self, data):
        self.frames.append(data)

    def stop(self):
        self.stopped = True
        self.callback.on_complete()


def settings(model="fun-asr-realtime"):
    return AsrSettings(
        realtime_model=model,
        context_enabled=True,
        packet_duration_ms=100,
        stop_timeout_seconds=8.0,
        heartbeat_enabled=True,
    )


def test_fun_asr_start_receives_bounded_context():
    async def scenario():
        adapter = DashScopeRealtimeAsr(
            api_key="test",
            settings=settings(),
            context="当前关键任务：完成验收。",
            recognition_factory=FakeRecognition,
        )
        await adapter.start()
        instance = FakeRecognition.instances[-1]
        context = instance.start_kwargs["raw_input"]["context"]
        assert context[0]["role"] == "user"
        assert context[0]["content"][0]["type"] == "input_text"
        assert "完成验收" in context[0]["content"][0]["text"]

    asyncio.run(scenario())


def test_callback_normalizes_partial_and_final_with_stable_segment_id():
    async def scenario():
        adapter = DashScopeRealtimeAsr(
            api_key="test",
            settings=settings(),
            context="",
            recognition_factory=FakeRecognition,
        )
        await adapter.start()
        callback = FakeRecognition.instances[-1].callback
        callback.on_event(SimpleNamespace(
            status_code=200,
            output={"sentence": {
                "text": "本周完成",
                "sentence_end": False,
                "begin_time": 0,
                "end_time": 500,
            }},
        ))
        callback.on_event(SimpleNamespace(
            status_code=200,
            output={"sentence": {
                "text": "本周完成联调。",
                "sentence_end": True,
                "begin_time": 0,
                "end_time": 900,
            }},
        ))
        first = await adapter.next_event()
        second = await adapter.next_event()
        assert first["segment_id"] == second["segment_id"] == "seg-0"
        assert first["final"] is False
        assert second["final"] is True

    asyncio.run(scenario())


def test_stop_waits_for_completion():
    async def scenario():
        adapter = DashScopeRealtimeAsr(
            api_key="test",
            settings=settings(),
            context="",
            recognition_factory=FakeRecognition,
        )
        await adapter.start()
        await adapter.send_audio(b"\x00\x00")
        await adapter.stop()
        instance = FakeRecognition.instances[-1]
        assert instance.frames == [b"\x00\x00"]
        assert instance.stopped is True

    asyncio.run(scenario())
```

- [ ] **Step 2: Run the adapter tests and verify they fail**

```powershell
python -m pytest tests/test_realtime_asr.py -v
```

Expected: FAIL because `DashScopeRealtimeAsr` does not exist.

- [ ] **Step 3: Implement the adapter**

Create `bowei_ai_dashboard/app/services/realtime_asr.py` with:

```python
from __future__ import annotations

import asyncio
from collections.abc import Callable
from http import HTTPStatus
from typing import Any

from ..settings import AsrSettings


class DashScopeRealtimeAsr:
    def __init__(
        self,
        *,
        api_key: str,
        settings: AsrSettings,
        context: str,
        recognition_factory: Callable[..., Any] | None = None,
    ):
        self.api_key = api_key
        self.settings = settings
        self.context = context[:400]
        self._factory = recognition_factory
        self._recognition = None
        self._events: asyncio.Queue[dict] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._completed = asyncio.Event()
        self._segment_index = 0

    def _callback(self):
        owner = self

        class Callback:
            def on_open(self):
                return None

            def on_close(self):
                return None

            def on_complete(self):
                if owner._loop:
                    owner._loop.call_soon_threadsafe(owner._completed.set)

            def on_error(self, result):
                message = str(getattr(result, "message", "recognition failed"))
                request_id = str(getattr(result, "request_id", ""))
                if owner._loop:
                    asyncio.run_coroutine_threadsafe(
                        owner._events.put({
                            "type": "error",
                            "code": "ASR_PROVIDER_ERROR",
                            "message": message,
                            "request_id": request_id,
                            "retryable": True,
                        }),
                        owner._loop,
                    )
                    owner._loop.call_soon_threadsafe(owner._completed.set)

            def on_event(self, result):
                if getattr(result, "status_code", None) != HTTPStatus.OK:
                    self.on_error(result)
                    return
                sentence = (getattr(result, "output", None) or {}).get("sentence") or {}
                text = str(sentence.get("text") or "").strip()
                if not text or owner._loop is None:
                    return
                final = bool(sentence.get("sentence_end", False))
                event = {
                    "type": "transcript",
                    "segment_id": f"seg-{owner._segment_index}",
                    "text": text,
                    "final": final,
                    "begin_time": sentence.get("begin_time"),
                    "end_time": sentence.get("end_time"),
                }
                asyncio.run_coroutine_threadsafe(owner._events.put(event), owner._loop)
                if final:
                    owner._segment_index += 1

        return Callback()

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._factory is None:
            import dashscope
            from dashscope.audio.asr import Recognition

            dashscope.api_key = self.api_key
            factory = Recognition
        else:
            factory = self._factory
        self._recognition = factory(
            model=self.settings.realtime_model,
            format="pcm",
            sample_rate=16000,
            language_hints=["zh"],
            heartbeat=self.settings.heartbeat_enabled,
            callback=self._callback(),
            api_key=self.api_key,
        )
        start_kwargs = {}
        if (
            self.settings.context_enabled
            and self.context
            and self.settings.realtime_model == "fun-asr-realtime"
        ):
            start_kwargs["raw_input"] = {
                "context": [{
                    "role": "user",
                    "content": [{"type": "input_text", "text": self.context}],
                }]
            }
        await asyncio.to_thread(self._recognition.start, **start_kwargs)

    async def send_audio(self, data: bytes) -> None:
        if self._recognition is None:
            raise RuntimeError("ASR session is not started")
        await asyncio.to_thread(self._recognition.send_audio_frame, data)

    async def next_event(self) -> dict | None:
        return await self._events.get()

    async def stop(self) -> None:
        if self._recognition is None:
            await self._events.put(None)
            return
        try:
            await asyncio.to_thread(self._recognition.stop)
            if not self._completed.is_set():
                await asyncio.wait_for(
                    self._completed.wait(),
                    timeout=self.settings.stop_timeout_seconds,
                )
        finally:
            await self._events.put(None)
```

Do not log callback text or `self.context`.

- [ ] **Step 4: Run adapter tests**

```powershell
python -m pytest tests/test_realtime_asr.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the adapter**

```powershell
git add app/services/realtime_asr.py tests/test_realtime_asr.py
git commit -m "feat: wrap dashscope realtime asr session"
```

## Task 4: Replace the legacy WebSocket stream with the explicit protocol

**Files:**

- Modify: `bowei_ai_dashboard/app/routers/transcribe.py`
- Create: `bowei_ai_dashboard/tests/test_transcribe_stream_protocol.py`
- Modify: `bowei_ai_dashboard/tests/test_production_runtime_security.py`

- [ ] **Step 1: Write failing protocol tests**

Create a `FakeWebSocket` that returns a `start`, binary audio, and `stop`; inject
a fake DB and fake ASR factory into an internal coordinator:

```python
import asyncio

from app.routers.transcribe import run_transcribe_stream


class FakeWebSocket:
    def __init__(self, incoming):
        self.incoming = list(incoming)
        self.sent = []

    async def receive(self):
        return self.incoming.pop(0)

    async def send_json(self, item):
        self.sent.append(item)


class FakeAsr:
    def __init__(self):
        self.frames = []
        self.events = asyncio.Queue()
        self.stopped = False

    async def start(self):
        return None

    async def send_audio(self, data):
        self.frames.append(data)

    async def next_event(self):
        return await self.events.get()

    async def stop(self):
        self.stopped = True
        await self.events.put(None)


def test_stream_requires_start_before_binary():
    async def scenario():
        ws = FakeWebSocket([
            {"type": "websocket.receive", "bytes": b"\x00\x00"},
        ])
        await run_transcribe_stream(
            ws,
            current_user="member",
            db=object(),
            context_builder=lambda *args: "context",
            asr_factory=lambda **kwargs: FakeAsr(),
            api_key="key",
        )
        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"

    asyncio.run(scenario())


def test_stream_sends_started_transcript_and_done():
    async def scenario():
        ws = FakeWebSocket([
            {"type": "websocket.receive", "text": (
                '{"type":"start","scene":"work_report","project_id":12,'
                '"selected_task_id":86,"sample_rate":16000,"format":"pcm"}'
            )},
            {"type": "websocket.receive", "bytes": b"\x01\x02"},
            {"type": "websocket.receive", "text": '{"type":"stop"}'},
        ])
        asr = FakeAsr()
        await run_transcribe_stream(
            ws,
            current_user="member",
            db=object(),
            context_builder=lambda *args: "context",
            asr_factory=lambda **kwargs: asr,
            api_key="key",
        )
        assert ws.sent[0]["type"] == "ready"
        assert ws.sent[1]["type"] == "started"
        assert ws.sent[-1]["type"] == "done"
        assert asr.frames == [b"\x01\x02"]
        assert asr.stopped is True

    asyncio.run(scenario())
```

Add this test to protect the approved work-report-only boundary:

```python
def test_stream_rejects_meeting_scene():
    async def scenario():
        ws = FakeWebSocket([{
            "type": "websocket.receive",
            "text": (
                '{"type":"start","scene":"meeting_minutes","project_id":12,'
                '"selected_task_id":86,"sample_rate":16000,"format":"pcm"}'
            ),
        }])
        await run_transcribe_stream(
            ws,
            current_user="member",
            db=object(),
            context_builder=lambda *args: "context",
            asr_factory=lambda **kwargs: FakeAsr(),
            api_key="key",
        )
        assert ws.sent[-1]["type"] == "error"
        assert ws.sent[-1]["code"] == "PROTOCOL_ERROR"

    asyncio.run(scenario())
```

- [ ] **Step 2: Run protocol tests and verify they fail**

```powershell
python -m pytest tests/test_transcribe_stream_protocol.py -v
```

Expected: FAIL because `run_transcribe_stream` does not exist.

- [ ] **Step 3: Implement a testable coordinator**

In `bowei_ai_dashboard/app/routers/transcribe.py`:

1. Add a Pydantic model for the start message.
2. Add `run_transcribe_stream(...)` with injected context/ASR factories.
3. Keep the route responsible for accept, cookie authentication, API-key lookup,
   DB dependency, and final close.

Use these exact validation fields:

```python
class StreamStart(BaseModel):
    type: Literal["start"]
    scene: Literal["work_report"]
    project_id: int = Field(gt=0)
    selected_task_id: int = Field(gt=0)
    sample_rate: Literal[16000]
    format: Literal["pcm"]
```

Implement the coordinator with one result-sender task so every final transcript
is delivered before `done`:

```python
async def run_transcribe_stream(
    websocket,
    *,
    current_user: str,
    db: Session,
    context_builder=build_work_report_asr_context,
    asr_factory=DashScopeRealtimeAsr,
    api_key: str,
) -> None:
    settings = get_asr_settings()
    await websocket.send_json({"type": "ready"})
    first = await websocket.receive()
    try:
        start = StreamStart.model_validate_json(first.get("text") or "")
    except ValidationError:
        await websocket.send_json({
            "type": "error",
            "code": "PROTOCOL_ERROR",
            "message": "录音启动参数无效，请重新开始",
            "retryable": True,
        })
        return

    try:
        context = (
            context_builder(
                current_user,
                start.project_id,
                start.selected_task_id,
                db,
            )
            if settings.context_enabled
            else ""
        )
    except HTTPException as exc:
        await websocket.send_json({
            "type": "error",
            "code": (
                "CONTEXT_FORBIDDEN"
                if exc.status_code == 403
                else "CONTEXT_INVALID"
            ),
            "message": "当前项目或关键任务不可用于录音汇报",
            "retryable": False,
        })
        return

    session = asr_factory(
        api_key=api_key,
        settings=settings,
        context=context,
    )
    try:
        await session.start()
    except Exception:
        logger.exception("ASR session start failed")
        await websocket.send_json({
            "type": "error",
            "code": "ASR_START_FAILED",
            "message": "语音识别服务启动失败，请重试",
            "retryable": True,
        })
        return

    session_id = secrets.token_urlsafe(18)
    await websocket.send_json({
        "type": "started",
        "model": settings.realtime_model,
        "session_id": session_id,
    })

    packet_count = 0
    audio_bytes = 0
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
    queue_peak = 0
    started_at = time.monotonic()
    first_result_at: float | None = None

    async def send_results() -> None:
        nonlocal first_result_at
        while True:
            event = await session.next_event()
            if event is None:
                return
            if first_result_at is None and event.get("type") == "transcript":
                first_result_at = time.monotonic()
            safe_event = {
                key: value
                for key, value in event.items()
                if key != "request_id"
            }
            await websocket.send_json(safe_event)

    async def send_audio() -> None:
        while True:
            data = await audio_queue.get()
            if data is None:
                return
            await session.send_audio(data)

    result_task = asyncio.create_task(send_results())
    audio_task = asyncio.create_task(send_audio())
    try:
        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                data = message["bytes"]
                packet_count += 1
                audio_bytes += len(data)
                try:
                    audio_queue.put_nowait(data)
                except asyncio.QueueFull:
                    await websocket.send_json({
                        "type": "error",
                        "code": "AUDIO_BACKPRESSURE",
                        "message": "网络或语音服务积压过高，请检查已有文字后重试",
                        "retryable": True,
                    })
                    return
                queue_peak = max(queue_peak, audio_queue.qsize())
                continue
            raw = message.get("text") or ""
            try:
                control = json.loads(raw)
            except json.JSONDecodeError:
                control = {}
            if control.get("type") == "stop" or raw == "stop":
                break
            await websocket.send_json({
                "type": "error",
                "code": "PROTOCOL_ERROR",
                "message": "录音消息顺序无效",
                "retryable": False,
            })
            return
    finally:
        stop_started_at = time.monotonic()
        await audio_queue.put(None)
        await audio_task
        try:
            await session.stop()
        finally:
            await result_task

    await websocket.send_json({
        "type": "done",
        "session_id": session_id,
        "duration_ms": audio_bytes * 1000 // (16000 * 2),
    })
    logger.info(
        "ASR session complete session_id=%s model=%s packets=%d "
        "audio_ms=%d queue_peak=%d first_result_ms=%s stop_done_ms=%d",
        session_id,
        settings.realtime_model,
        packet_count,
        audio_bytes * 1000 // (16000 * 2),
        queue_peak,
        (
            round((first_result_at - started_at) * 1000)
            if first_result_at is not None
            else None
        ),
        round((time.monotonic() - stop_started_at) * 1000),
    )
```

Import `json`, `secrets`, `time`, `HTTPException`, `ValidationError`, `Session`,
`BaseModel`, `Field`, and `Literal` explicitly. The logged fields are IDs,
counts, and durations only; do not add text or context to the log call.

- [ ] **Step 4: Update the route wrapper and security test**

Use FastAPI dependency injection for the database:

```python
@router.websocket("/stream")
async def transcribe_stream(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    await websocket.accept()
    session_id = websocket.cookies.get(get_settings().session_cookie_name)
    username = get_session_user(session_id) if session_id else None
    if not username:
        await websocket.send_json({
            "type": "error",
            "code": "UNAUTHENTICATED",
            "message": "未登录，请重新登录后重试",
            "retryable": False,
        })
        await websocket.close(code=4001)
        return
    api_key = get_provider_config("dashscope").get("api_key", "")
    if not api_key:
        await websocket.send_json({
            "type": "error",
            "code": "ASR_NOT_CONFIGURED",
            "message": "未配置语音识别服务，请联系管理员",
            "retryable": False,
        })
        await websocket.close(code=4002)
        return
    try:
        await run_transcribe_stream(
            websocket,
            current_user=username,
            db=db,
            api_key=api_key,
        )
    finally:
        await websocket.close()
```

Update `test_production_runtime_security.py` to pass its test DB/fake DB explicitly
when directly invoking `transcribe_stream`.

- [ ] **Step 5: Run backend stream tests**

```powershell
python -m pytest tests/test_transcribe_stream_protocol.py tests/test_production_runtime_security.py -v
```

Expected: PASS.

- [ ] **Step 6: Run Python compile verification**

```powershell
python -m compileall app
```

Expected: exit code 0.

- [ ] **Step 7: Commit the protocol slice**

```powershell
git add app/routers/transcribe.py tests/test_transcribe_stream_protocol.py tests/test_production_runtime_security.py
git commit -m "feat: add explicit realtime transcription protocol"
```

## Task 5: Add deterministic frontend protocol and transcript merging

**Files:**

- Create: `frontend/src/features/voice-update/voiceRecorderProtocol.ts`
- Create: `frontend/tests/voiceRecorderProtocol.test.mjs`

- [ ] **Step 1: Write failing protocol tests**

Create `frontend/tests/voiceRecorderProtocol.test.mjs` using the existing
TypeScript transpilation pattern:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import ts from 'typescript'

const root = path.resolve(import.meta.dirname, '..')

async function loadModule() {
  const source = fs.readFileSync(
    path.join(root, 'src/features/voice-update/voiceRecorderProtocol.ts'),
    'utf8',
  )
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText
  return import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`)
}

test('partial result replaces the current segment', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  let state = emptyTranscript('已有文字')
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成', final: false,
  })
  state = mergeTranscript(state, {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成联调', final: false,
  })
  assert.equal(composeTranscript(state), '已有文字\n本周完成联调')
})

test('final result is idempotent by segment id', async () => {
  const { emptyTranscript, mergeTranscript, composeTranscript } = await loadModule()
  const event = {
    type: 'transcript', segment_id: 'seg-0', text: '本周完成联调。', final: true,
  }
  let state = mergeTranscript(emptyTranscript(''), event)
  state = mergeTranscript(state, event)
  assert.equal(composeTranscript(state), '本周完成联调。')
})

test('parser rejects unknown messages', async () => {
  const { parseServerMessage } = await loadModule()
  assert.equal(parseServerMessage('{"type":"unknown"}'), null)
  assert.equal(parseServerMessage('not json'), null)
})
```

- [ ] **Step 2: Run the protocol tests and verify they fail**

Run from `frontend`:

```powershell
node --test tests/voiceRecorderProtocol.test.mjs
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement message types and the pure merger**

Create `frontend/src/features/voice-update/voiceRecorderProtocol.ts`:

```typescript
export type RecorderState =
  | 'idle'
  | 'connecting'
  | 'starting'
  | 'recording'
  | 'stopping'
  | 'completed'
  | 'failed'

export type ServerMessage =
  | { type: 'ready' }
  | { type: 'started'; model: string; session_id: string }
  | {
      type: 'transcript'
      segment_id: string
      text: string
      final: boolean
      begin_time?: number | null
      end_time?: number | null
    }
  | { type: 'done'; session_id: string; duration_ms: number }
  | { type: 'error'; code: string; message: string; retryable: boolean }

export type TranscriptState = {
  baseText: string
  order: string[]
  confirmed: Record<string, string>
  partial: { segmentId: string; text: string } | null
}

export function emptyTranscript(baseText: string): TranscriptState {
  return {
    baseText: baseText.trim(),
    order: [],
    confirmed: {},
    partial: null,
  }
}

export function mergeTranscript(
  state: TranscriptState,
  event: Extract<ServerMessage, { type: 'transcript' }>,
): TranscriptState {
  if (!event.final) {
    return {
      ...state,
      partial: { segmentId: event.segment_id, text: event.text },
    }
  }
  const exists = Object.hasOwn(state.confirmed, event.segment_id)
  return {
    ...state,
    order: exists ? state.order : [...state.order, event.segment_id],
    confirmed: { ...state.confirmed, [event.segment_id]: event.text },
    partial: state.partial?.segmentId === event.segment_id ? null : state.partial,
  }
}

export function composeTranscript(state: TranscriptState): string {
  const recognized = [
    ...state.order.map((id) => state.confirmed[id]),
    state.partial?.text ?? '',
  ].filter(Boolean).join('')
  return [state.baseText, recognized].filter(Boolean).join('\n')
}

export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const value = JSON.parse(raw) as Record<string, unknown>
    if (value.type === 'ready') return { type: 'ready' }
    if (
      value.type === 'started'
      && typeof value.model === 'string'
      && typeof value.session_id === 'string'
    ) return value as ServerMessage
    if (
      value.type === 'transcript'
      && typeof value.segment_id === 'string'
      && typeof value.text === 'string'
      && typeof value.final === 'boolean'
    ) return value as ServerMessage
    if (
      value.type === 'done'
      && typeof value.session_id === 'string'
      && typeof value.duration_ms === 'number'
    ) return value as ServerMessage
    if (
      value.type === 'error'
      && typeof value.code === 'string'
      && typeof value.message === 'string'
      && typeof value.retryable === 'boolean'
    ) return value as ServerMessage
  } catch {
    return null
  }
  return null
}
```

- [ ] **Step 4: Run protocol tests**

```powershell
node --test tests/voiceRecorderProtocol.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit the frontend protocol**

```powershell
git add src/features/voice-update/voiceRecorderProtocol.ts tests/voiceRecorderProtocol.test.mjs
git commit -m "feat: add voice recorder protocol model"
```

## Task 6: Packetize PCM into 100 ms worklet messages

**Files:**

- Modify: `frontend/public/worklets/pcm-audio-processor.js`
- Create: `frontend/tests/pcmAudioProcessor.test.mjs`

- [ ] **Step 1: Write a failing executable worklet test**

Create `frontend/tests/pcmAudioProcessor.test.mjs`:

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'

function loadProcessor() {
  const file = path.resolve(
    import.meta.dirname,
    '../public/worklets/pcm-audio-processor.js',
  )
  const source = fs.readFileSync(file, 'utf8')
  let Registered
  class AudioWorkletProcessor {
    constructor() {
      this.port = {
        messages: [],
        postMessage: (message) => this.port.messages.push(message),
        onmessage: null,
      }
    }
  }
  const context = {
    AudioWorkletProcessor,
    registerProcessor: (_name, ctor) => { Registered = ctor },
    Int16Array,
    Float32Array,
    ArrayBuffer,
    Math,
  }
  vm.runInNewContext(source, context)
  return new Registered()
}

test('worklet emits one packet per 1600 samples', () => {
  const processor = loadProcessor()
  for (let index = 0; index < 12; index += 1) {
    processor.process([[new Float32Array(128).fill(0.25)]])
  }
  assert.equal(
    processor.port.messages.filter((item) => item.type === 'pcm').length,
    0,
  )
  processor.process([[new Float32Array(64).fill(0.25)]])
  const packets = processor.port.messages.filter((item) => item.type === 'pcm')
  assert.equal(packets.length, 1)
  assert.equal(packets[0].buffer.byteLength, 3200)
})

test('stop flushes the remaining samples once', () => {
  const processor = loadProcessor()
  processor.process([[new Float32Array(128).fill(0.25)]])
  processor.port.onmessage({ data: { type: 'stop' } })
  processor.port.onmessage({ data: { type: 'stop' } })
  const packets = processor.port.messages.filter((item) => item.type === 'pcm')
  assert.equal(packets.length, 1)
  assert.equal(packets[0].buffer.byteLength, 256)
  assert.equal(
    processor.port.messages.filter((item) => item.type === 'flushed').length,
    1,
  )
})
```

- [ ] **Step 2: Run the worklet tests and verify they fail**

```powershell
node --test tests/pcmAudioProcessor.test.mjs
```

Expected: FAIL because the current worklet emits one packet for each 128-sample
quantum.

- [ ] **Step 3: Implement the 1600-sample accumulator**

In `frontend/public/worklets/pcm-audio-processor.js`, add:

```javascript
const PACKET_SAMPLES = 1600;
```

Initialize:

```javascript
this._pending = new Float32Array(PACKET_SAMPLES);
this._pendingLength = 0;
this._flushed = false;
```

Replace direct `_toPcm(channelData)` posting with:

```javascript
_postPcm(samples) {
  if (samples.length === 0) return;
  const pcmBuffer = this._toPcm(samples);
  this.port.postMessage({ type: "pcm", buffer: pcmBuffer }, [pcmBuffer]);
}

_append(samples) {
  let offset = 0;
  while (offset < samples.length) {
    const writable = Math.min(
      PACKET_SAMPLES - this._pendingLength,
      samples.length - offset,
    );
    this._pending.set(
      samples.subarray(offset, offset + writable),
      this._pendingLength,
    );
    this._pendingLength += writable;
    offset += writable;
    if (this._pendingLength === PACKET_SAMPLES) {
      this._postPcm(this._pending);
      this._pending = new Float32Array(PACKET_SAMPLES);
      this._pendingLength = 0;
    }
  }
}

_flush() {
  if (this._flushed) return;
  this._flushed = true;
  if (this._pendingLength > 0) {
    this._postPcm(this._pending.slice(0, this._pendingLength));
    this._pendingLength = 0;
  }
  this.port.postMessage({ type: "flushed" });
}
```

The port handler becomes:

```javascript
this.port.onmessage = (event) => {
  if (event.data?.type === "stop") {
    this._flush();
    this._stopped = true;
  }
};
```

`process()` calls `this._append(channelData)` and no longer posts each quantum.
Keep RMS calculation for diagnostics, but do not auto-stop or drop silence.

- [ ] **Step 4: Run worklet tests and JavaScript syntax verification**

```powershell
node --test tests/pcmAudioProcessor.test.mjs
node --check public/worklets/pcm-audio-processor.js
```

Expected: PASS and exit code 0.

- [ ] **Step 5: Commit the worklet packetizer**

```powershell
git add public/worklets/pcm-audio-processor.js tests/pcmAudioProcessor.test.mjs
git commit -m "fix: packetize realtime pcm into 100ms frames"
```

## Task 7: Integrate the protocol into the React recording flow

**Files:**

- Modify: `frontend/src/features/voice-update/useVoiceRecorder.ts`
- Modify: `frontend/src/pages/VoiceUpdatePage.tsx`
- Modify: `frontend/src/features/voice-update/VoiceUpdateInputPanel.tsx`
- Modify: `frontend/src/features/voice-update/voiceUpdateFlow.css`
- Modify: `frontend/tests/workReportFlowPage.test.mjs`

- [ ] **Step 1: Add failing structural integration tests**

Extend `frontend/tests/workReportFlowPage.test.mjs` with constants for
`useVoiceRecorder.ts` and `voiceRecorderProtocol.ts`, then add:

```javascript
test('voice recording requires one selected project task', () => {
  const page = read(PAGE)
  assert.match(page, /projectId:\s*selectedProjectId/)
  assert.match(page, /selectedTaskId:\s*taskBinding\.selectedSubtaskId/)
  assert.match(page, /canRecord:\s*reportScope === 'task'/)
})

test('binding and transcript editing lock throughout media activity', () => {
  const page = read(PAGE)
  const input = read(INPUT)
  assert.match(page, /mediaActive/)
  assert.match(page, /controlsLocked[\s\S]*mediaActive/)
  assert.match(input, /readOnly=\{mediaActive\}/)
})

test('recorder waits for started and done protocol events', () => {
  const recorder = read('src/features/voice-update/useVoiceRecorder.ts')
  assert.match(recorder, /message\.type === 'started'/)
  assert.match(recorder, /message\.type === 'done'/)
  assert.doesNotMatch(recorder, /setTimeout\(resolve,\s*1500\)/)
  assert.match(recorder, /JSON\.stringify\(\{\s*type:\s*'stop'/)
})

test('meeting transcription remains outside the work report recorder', () => {
  const recorder = read('src/features/voice-update/useVoiceRecorder.ts')
  assert.match(recorder, /scene:\s*'work_report'/)
  assert.doesNotMatch(recorder, /meeting_minutes|meeting_id/)
})
```

- [ ] **Step 2: Run the integration tests and verify they fail**

```powershell
node --test tests/workReportFlowPage.test.mjs
```

Expected: FAIL on the new assertions.

- [ ] **Step 3: Rewrite the hook around the explicit state machine**

Change the hook arguments to:

```typescript
type UseVoiceRecorderArgs = {
  projectId: number | null
  selectedTaskId: number | null
  canRecord: boolean
  initialText: string
  setText: (updater: string | ((prev: string) => string)) => void
  setError: (value: string | null) => void
}
```

Use `RecorderState`, `parseServerMessage`, `emptyTranscript`,
`mergeTranscript`, and `composeTranscript` from
`voiceRecorderProtocol.ts`.

Add one permanent message dispatcher instead of replacing `ws.onmessage` for
each handshake phase:

```typescript
type MessageWaiter = {
  predicate: (message: ServerMessage) => boolean
  resolve: (message: ServerMessage | null) => void
  timeoutId: ReturnType<typeof setTimeout>
}

const waitersRef = useRef<MessageWaiter[]>([])

function dispatchServerMessage(message: ServerMessage) {
  const matched = waitersRef.current.filter((item) => item.predicate(message))
  waitersRef.current = waitersRef.current.filter((item) => !matched.includes(item))
  for (const item of matched) {
    clearTimeout(item.timeoutId)
    item.resolve(message)
  }
}

function waitForServerMessage(
  predicate: (message: ServerMessage) => boolean,
  timeoutMs: number,
): Promise<ServerMessage | null> {
  return new Promise((resolve) => {
    const waiter: MessageWaiter = {
      predicate,
      resolve,
      timeoutId: setTimeout(() => {
        waitersRef.current = waitersRef.current.filter((item) => item !== waiter)
        resolve(null)
      }, timeoutMs),
    }
    waitersRef.current.push(waiter)
  })
}

function waitForOpen(ws: WebSocket, timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeoutId = setTimeout(
      () => reject(new Error('语音服务连接超时，请重试')),
      timeoutMs,
    )
    ws.addEventListener('open', () => {
      clearTimeout(timeoutId)
      resolve()
    }, { once: true })
    ws.addEventListener('error', () => {
      clearTimeout(timeoutId)
      reject(new Error('语音服务连接失败，请重试'))
    }, { once: true })
  })
}
```

The permanent handler parses, dispatches, and then applies state:

```typescript
function handleServerMessage(event: MessageEvent) {
  if (typeof event.data !== 'string') return
  const message = parseServerMessage(event.data)
  if (!message) return
  dispatchServerMessage(message)
  if (message.type === 'transcript') {
    transcriptRef.current = mergeTranscript(transcriptRef.current, message)
    setText(composeTranscript(transcriptRef.current))
  } else if (message.type === 'error') {
    setText(composeTranscript(transcriptRef.current))
    setError(message.message)
    setState('failed')
  } else if (message.type === 'done') {
    setText(composeTranscript(transcriptRef.current))
    setState('completed')
  }
}
```

Move the existing microphone/worklet construction into a concrete helper. It
must attach all refs before returning:

```typescript
async function startMicrophoneAndWorklet(ws: WebSocket): Promise<void> {
  const audioContext = new AudioContext({ sampleRate: 16000 })
  await audioContext.audioWorklet.addModule('/worklets/pcm-audio-processor.js')
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: 16000,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  })
  const node = new AudioWorkletNode(audioContext, 'pcm-audio-processor')
  node.port.onmessage = (event: MessageEvent<WorkletMessage>) => {
    if (event.data.type !== 'pcm') return
    if (ws.readyState !== WebSocket.OPEN) return
    if (ws.bufferedAmount > 512 * 1024) {
      setError('网络积压过高，已停止本次录音，请检查已有文字')
      void stopRecording()
      return
    }
    ws.send(event.data.buffer)
  }
  audioContext.createMediaStreamSource(stream).connect(node)
  audioCtxRef.current = audioContext
  streamRef.current = stream
  workletRef.current = node
}
```

Add `workletRef` and keep the existing `audioCtxRef`, `streamRef`, and `wsRef`.
Add `stoppingRef = useRef(false)` and reset it at the beginning of each new
recording.
The high-water mark is a fail-safe, not permission to discard PCM frames.

The required sequence inside `startRecording` is:

```typescript
if (!canRecord || !projectId || !selectedTaskId) {
  setError('请先选择本次汇报对应的项目和关键任务。')
  return
}
stoppingRef.current = false
transcriptRef.current = emptyTranscript(initialText)
setError(null)
setState('connecting')
const ws = new WebSocket(url)
wsRef.current = ws
ws.onmessage = handleServerMessage
const readyPromise = waitForServerMessage(
  (message) => message.type === 'ready',
  6000,
)
await waitForOpen(ws, 6000)
setState('starting')
const ready = await readyPromise
if (!ready) throw new Error('语音服务未就绪，请重试')
const startedPromise = waitForServerMessage(
  (message) => message.type === 'started',
  8000,
)
ws.send(JSON.stringify({
  type: 'start',
  scene: 'work_report',
  project_id: projectId,
  selected_task_id: selectedTaskId,
  sample_rate: 16000,
  format: 'pcm',
}))
const started = await startedPromise
if (!started) throw new Error('语音识别启动超时，请重试')
await startMicrophoneAndWorklet()
setState('recording')
```

Register the permanent `onmessage` handler before sending `start`. It must:

- parse every string message;
- update and render transcript messages;
- resolve the `started` waiter;
- on `done`, flush text, close media resources, and set `completed`;
- on `error`, retain composed stable text and enter `failed`.

`stopRecording` must:

```typescript
if (stoppingRef.current) return
stoppingRef.current = true
setState('stopping')
await new Promise<void>((resolve) => {
  const timeoutId = setTimeout(resolve, 1000)
  flushedResolverRef.current = () => {
    clearTimeout(timeoutId)
    resolve()
  }
  workletNode.port.postMessage({ type: 'stop' })
})
workletNode.disconnect()
await audioContext.close()
stream.getTracks().forEach((track) => track.stop())
const donePromise = waitForServerMessage(
  (message) => message.type === 'done',
  8000,
)
ws.send(JSON.stringify({ type: 'stop' }))
const done = await donePromise
if (!done) {
  setText(composeTranscript(transcriptRef.current))
  setError('最后一句可能不完整，请检查后再提交')
  setState('failed')
}
stoppingRef.current = false
```

Do not close the WebSocket before `done`, except on timeout or error. Remove the
fixed 1.5-second wait. Add component-unmount cleanup with `useEffect`.

Extend `WorkletMessage` with `{ type: 'flushed' }`, add
`flushedResolverRef`, and handle the acknowledgement in the existing worklet
port callback:

```typescript
if (event.data.type === 'flushed') {
  flushedResolverRef.current?.()
  flushedResolverRef.current = null
  return
}
```

This acknowledgement guarantees the final short PCM packet reaches
`WebSocket.send()` before the JSON `stop` control message.

The unified cleanup must be idempotent:

```typescript
function cleanupResources(closeSocket: boolean) {
  workletRef.current?.disconnect()
  workletRef.current = null
  void audioCtxRef.current?.close()
  audioCtxRef.current = null
  streamRef.current?.getTracks().forEach((track) => track.stop())
  streamRef.current = null
  if (closeSocket) wsRef.current?.close(1000)
  if (closeSocket) wsRef.current = null
  for (const waiter of waitersRef.current) {
    clearTimeout(waiter.timeoutId)
    waiter.resolve(null)
  }
  waitersRef.current = []
}

useEffect(() => () => cleanupResources(true), [])
```

Return:

```typescript
const recording = state === 'recording'
const transcribing = ['connecting', 'starting', 'stopping'].includes(state)
const mediaActive = recording || transcribing
return {
  state,
  recording,
  transcribing,
  mediaActive,
  timer,
  startRecording,
  stopRecording,
}
```

- [ ] **Step 4: Wire project/task context and UI locks**

In `VoiceUpdatePage.tsx`:

```typescript
const recorder = useVoiceRecorder({
  projectId: selectedProjectId,
  selectedTaskId: taskBinding.selectedSubtaskId,
  canRecord: reportScope === 'task'
    && selectedProjectIsActive
    && selectedProjectId !== null
    && taskBinding.selectedSubtaskId !== null,
  initialText: text,
  setText,
  setError: setExtractionError,
})
const {
  recording,
  transcribing,
  mediaActive,
  timer,
  startRecording,
  stopRecording,
} = recorder
const controlsLocked =
  phase === 'extracting' || phase === 'submitting' || mediaActive
```

Pass `mediaActive`, `recorder.state`, and `canRecord` to
`VoiceUpdateInputPanel`.

In `VoiceUpdateInputPanel.tsx`:

- disable mode changes and start recording while `mediaActive`;
- keep the stop button enabled only in `recording`;
- show “正在连接语音服务” for `connecting/starting`;
- show “正在完成最后一句” for `stopping`;
- set the voice textarea to `readOnly={mediaActive}`;
- show a task-selection hint when `canRecord` is false;
- do not disable text/upload input modes merely because voice recording is
  unavailable.

Add CSS classes for the busy label and read-only textarea. Preserve the existing
layout dimensions.

- [ ] **Step 5: Run frontend unit and structure tests**

```powershell
node --test tests/voiceRecorderProtocol.test.mjs tests/pcmAudioProcessor.test.mjs tests/workReportFlowPage.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Run the frontend build**

```powershell
npm run build
```

Expected: TypeScript and Vite build succeed.

- [ ] **Step 7: Commit the React integration**

```powershell
git add src/features/voice-update/useVoiceRecorder.ts src/pages/VoiceUpdatePage.tsx src/features/voice-update/VoiceUpdateInputPanel.tsx src/features/voice-update/voiceUpdateFlow.css tests/workReportFlowPage.test.mjs
git commit -m "feat: integrate scoped realtime work report recording"
```

## Task 8: Add acceptance evidence and execute the staged verification

**Files:**

- Create: `docs/acceptance/personal-work-report-realtime-asr.md`

- [ ] **Step 1: Write the acceptance runbook**

Create `docs/acceptance/personal-work-report-realtime-asr.md` with:

```markdown
# Personal Work Report Realtime ASR Acceptance

## Scope

This run validates only personal work-report recording. Meeting transcription,
speaker diarization, and local model hosting are excluded.

## Test corpus

Record one immutable WAV file for each of at least 20 scripts. Include project
names, member names, key-task titles, dates, percentages, English brand terms,
1–3 second pauses, office noise, and immediate stop after the final word.
Keep a human-corrected UTF-8 reference transcript beside each WAV.

## Rollout matrix

1. Paraformer, legacy packet/stop behavior — baseline only.
2. Paraformer, 100 ms packets and done protocol.
3. Fun-ASR, context disabled.
4. Fun-ASR, permission-scoped context enabled.

Use the same WAV bytes for all four rows.

## Metrics

- Character error rate.
- Project-term recall.
- First partial latency.
- First final latency.
- Stop-to-done latency.
- Audio packets per second.
- Backend queue peak.
- Missing-tail count.
- Duplicate-final count.

## Gates

- About 10 audio packets/second.
- 0/20 missing tails.
- 0 duplicate final segments.
- First partial P95 <= 1.5 seconds.
- Stop-to-done P95 <= 3 seconds.
- Context-enabled term recall exceeds the Paraformer baseline.
- Forged project/task IDs return a permission error without context leakage.

## Privacy check

Confirm production logs contain no PCM bytes, transcript body, API key, or full
context string. Logs may contain IDs, counts, durations, provider request IDs,
and stable error codes.

## Rollback

Set `ASR_REALTIME_MODEL=paraformer-realtime-v2` and
`ASR_CONTEXT_ENABLED=false`, recreate only the backend container, and verify
new sessions report the fallback model in the `started` event.
```

- [ ] **Step 2: Run the targeted backend suite**

From `bowei_ai_dashboard`:

```powershell
python -m pytest tests/test_asr_settings.py tests/test_asr_context.py tests/test_realtime_asr.py tests/test_transcribe_stream_protocol.py tests/test_production_runtime_security.py tests/test_production_runtime_contract.py -v
```

Expected: PASS.

- [ ] **Step 3: Run the complete frontend test suite**

From `frontend`:

```powershell
$tests = @(Get-ChildItem tests -Filter '*.test.mjs' | Sort-Object FullName | ForEach-Object FullName)
node --test $tests
```

Expected: PASS.

- [ ] **Step 4: Run build and syntax checks**

```powershell
node --check public/worklets/pcm-audio-processor.js
npm run build
```

From `bowei_ai_dashboard`:

```powershell
python -m compileall app
```

Expected: all commands exit 0.

- [ ] **Step 5: Run repository diff checks**

From the repository root:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors. Confirm every modified file is in the approved
scope and preserve all unrelated pre-existing user changes.

- [ ] **Step 6: Commit the acceptance runbook**

```powershell
git add docs/acceptance/personal-work-report-realtime-asr.md
git commit -m "docs: add realtime asr acceptance runbook"
```

## Task 9: Manual production canary

**Files:**

- No code changes.

- [ ] **Step 1: Capture the current baseline**

Run the fixed 20-file corpus against the existing Paraformer implementation and
record all metrics in a dated copy of the acceptance table. Do not enable
Fun-ASR or context yet.

- [ ] **Step 2: Deploy transport-only canary**

Deploy with:

```dotenv
ASR_REALTIME_MODEL=paraformer-realtime-v2
ASR_CONTEXT_ENABLED=false
```

Verify the server reports about 10 packets/second, no missing tails, and a
`done` event for every test.

- [ ] **Step 3: Enable Fun-ASR without context for test users**

Set:

```dotenv
ASR_REALTIME_MODEL=fun-asr-realtime
ASR_CONTEXT_ENABLED=false
```

Run the same corpus and compare model-only differences.

- [ ] **Step 4: Enable context for test users**

Set:

```dotenv
ASR_REALTIME_MODEL=fun-asr-realtime
ASR_CONTEXT_ENABLED=true
```

Run the same corpus and compare professional-term recall. Verify logs contain
only context length/count, not context content.

- [ ] **Step 5: Decide rollout or rollback**

Roll out only if all acceptance gates pass. Otherwise restore:

```dotenv
ASR_REALTIME_MODEL=paraformer-realtime-v2
ASR_CONTEXT_ENABLED=false
```

Record the failed gate and the provider request IDs needed for diagnosis before
attempting another change.
