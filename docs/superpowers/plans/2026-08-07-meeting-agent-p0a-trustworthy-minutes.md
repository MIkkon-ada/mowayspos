# Meeting Agent P0-A Trustworthy Minutes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a resumable, evidence-backed ordinary-meeting analysis flow that processes one complete transcript without silent truncation, produces reviewable structured minutes, and saves only human-reviewed meeting content with immutable provenance.

**Architecture:** Reuse the existing `MeetingTranscriptSource`, `MeetingTranscriptRevision`, `MeetingAnalysisRun`, `MeetingAnalysisCandidate`, and `MeetingRevision` models. Add stable transcript segments and persisted run progress, process every transcript through Segment → Chunk → Atomic Facts → Merge/Conflict → Structured Minutes, then expose a two-column evidence/review workbench. Keep the legacy `/api/meetings/analyze` endpoint temporarily, but route the new UI through persisted analysis runs and never write project tasks in P0-A.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, SQLite/PostgreSQL, OpenAI-compatible/Anthropic providers, React, TypeScript, Vite, pytest, Node test runner.

---

## Scope and locked decisions

- Baseline: `origin/main@fe1b4c9`; create an isolated `codex/` worktree before implementation.
- This plan supersedes `docs/superpowers/plans/2026-08-03-evidence-driven-meeting-agent.md` for P0-A because the older plan assumes the audit models do not yet exist.
- One run uses exactly one complete transcript revision. Audio, realtime transcription, multi-source fusion, task matching, Before/After proposals, and project-task writeback are out of scope.
- Maximum accepted transcript length defaults to 500,000 Unicode characters. Larger input is rejected with HTTP 413; it is never silently truncated.
- Chunk target is 8,000 characters with up to 800 characters of overlap. Every character position belongs to at least one chunk.
- `MeetingSegment` is a table with stable integer IDs. Chunk execution state remains JSON on `MeetingAnalysisRun` in P0-A.
- Background execution uses FastAPI `BackgroundTasks` plus persisted database state. A failed or interrupted run is resumed explicitly through an API; no external queue is introduced in this phase.
- Existing `Meeting` JSON fields remain the compatible latest projection. Rich topics, member reports, issues, decision requests, provenance, and review output live in `MeetingRevision.human_output_json`.
- AI output is untrusted. Only deterministic validation plus explicit human review can feed a saved meeting revision.

## Locked file structure

**Create**

- `bowei_ai_dashboard/app/services/meeting_segmentation.py` — lossless segmentation and chunk manifest construction.
- `bowei_ai_dashboard/app/services/meeting_llm.py` — provider-neutral JSON call and response parsing.
- `bowei_ai_dashboard/app/services/meeting_analysis_agent.py` — prompts and atomic-fact normalization.
- `bowei_ai_dashboard/app/services/meeting_analysis_merge.py` — deduplication, conflict/supersession handling, structured minutes assembly.
- `bowei_ai_dashboard/app/services/meeting_analysis_runner.py` — persisted run state machine, retry, cancellation, usage, and candidate persistence.
- `bowei_ai_dashboard/app/services/meeting_analysis_workbench.py` — source/run creation, candidate review, and reviewed-draft projection.
- `bowei_ai_dashboard/app/routers/meeting_analysis.py` — P0-A run, review, resume, cancel, transcript revision, and save endpoints.
- `bowei_ai_dashboard/migrations/versions/d2e3f4a5b6c7_add_meeting_segments_and_run_progress.py` — additive P0-A schema migration from `c1d2e3f4a5b6`.
- `frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx` — evidence-first two-column workbench.
- `bowei_ai_dashboard/tests/fixtures/meeting_agent_gold.json` — ten deterministic evaluation scenarios.
- Focused backend/frontend tests named in the tasks below.

**Modify**

- `bowei_ai_dashboard/app/models.py`
- `bowei_ai_dashboard/app/schemas.py`
- `bowei_ai_dashboard/app/settings.py`
- `bowei_ai_dashboard/app/services/meeting_validation.py`
- `bowei_ai_dashboard/app/services/meeting_revisions.py`
- `bowei_ai_dashboard/app/routers/meetings.py`
- `bowei_ai_dashboard/app/main.py`
- `frontend/src/api/meetings.ts`
- `frontend/src/features/meeting/NewMeetingModal.tsx`
- `frontend/src/pages/MeetingPage.tsx`

## Canonical state and JSON contracts

Run statuses are exactly:

```python
RUN_STATUSES = {
    "queued", "segmenting", "extracting", "merging", "summarizing",
    "review", "failed", "cancelled", "saved",
}
```

Candidate types are exactly:

```python
CANDIDATE_TYPES = {
    "summary", "topic", "member_report", "progress", "action_item",
    "decision", "decision_request", "issue", "risk",
}
```

`coverage_manifest_json` uses this shape:

```json
{
  "version": "meeting-agent-p0a-v1",
  "transcript_length": 15240,
  "chunks": [
    {
      "chunk_id": "chunk-0001-a81f...",
      "index": 0,
      "char_start": 0,
      "char_end": 7921,
      "segment_ids": [1, 2, 3],
      "text_hash": "<64-character-sha256-hex>",
      "status": "pending",
      "attempts": 0,
      "error_code": ""
    }
  ]
}
```

Every evidence reference uses one canonical field set:

```json
{
  "source_id": 12,
  "transcript_revision_id": 19,
  "segment_id": 88,
  "char_start": 204,
  "char_end": 221,
  "quote": "吴肖下周三前完成测试",
  "source_hash": "<64-character-revision-text-sha256-hex>",
  "start_ms": null,
  "end_ms": null
}
```

### Task 1: Lock the baseline regressions and remove unsafe legacy mapping

**Files:**

- Modify: `bowei_ai_dashboard/tests/test_meeting_draft_review.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_legacy_safety.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:330-465`
- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx:114-160`
- Modify: `frontend/tests/meetingDraftReviewStructure.test.mjs`

- [ ] **Step 1: Add failing tests for the two known production defects.**

```python
def test_legacy_analysis_does_not_map_confirmed_items_to_risks(monkeypatch):
    db = seeded_meeting_db()
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(meetings, "_do_analyze", lambda *_: {
        "confirmed_items": ["采用方案 A"],
        "risks": ["企业微盘连接不稳定"],
    })
    result = asyncio.run(meetings.analyze_meeting(
        meetings.MeetingAnalyzeRequest(text="采用方案 A；企业微盘连接不稳定", project_id=1),
        current_user="owner", db=db,
    ))
    assert json.loads(result["confirmed_items_json"]) == ["采用方案 A"]
    assert json.loads(result["risk_items_json"]) == ["企业微盘连接不稳定"]


def test_legacy_analysis_never_silently_slices_long_input(monkeypatch):
    db = seeded_meeting_db()
    captured = {}
    monkeypatch.setattr(meetings, "_pick_provider", lambda: "deepseek")
    monkeypatch.setattr(meetings, "_do_analyze", lambda text, prompt, provider: captured.update(text=text, prompt=prompt) or {})
    text = "甲" * 10001
    with pytest.raises(HTTPException) as exc:
        asyncio.run(meetings.analyze_meeting(
            meetings.MeetingAnalyzeRequest(text=text, project_id=1),
            current_user="owner", db=db,
        ))
    assert exc.value.status_code == 409
    assert "analysis-runs" in str(exc.value.detail)
    assert captured == {}
```

- [ ] **Step 2: Run the tests and confirm the current code fails.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_legacy_safety.py tests/test_meeting_draft_review.py -q`

Expected: the risk assertion fails because `risk_items_json` contains `confirmed_items`, and the long-input test fails because the endpoint slices the prompt.

- [ ] **Step 3: Make the legacy endpoint explicit and non-lossy.**

```python
LEGACY_ANALYSIS_MAX_CHARS = 10_000

if len(payload.text) > LEGACY_ANALYSIS_MAX_CHARS:
    raise HTTPException(
        409,
        "完整会议请使用 /api/meetings/analysis-runs；旧分析接口不会截断输入",
    )

prompt = template.format(context=context_text, text=payload.text)
risks = result.get("risks") or result.get("risk_items") or []
```

Return `risk_items_json=json.dumps(risks, ensure_ascii=False)` and remove every `payload.text[:8000]` / `payload.text[:10000]` expression.

- [ ] **Step 4: Stop the frontend from replacing risks with confirmed items.**

```ts
const payload = {
  project_id: projectId,
  ...meetingForm,
  risk_items_json: form.risk_items_json,
}
```

Keep `confirmed_items_json` only in local legacy review state; never project it into `risk_items_json`.

- [ ] **Step 5: Run backend and frontend regression tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_legacy_safety.py tests/test_meeting_draft_review.py tests/test_meeting_extraction_traceability.py -q; cd ..\frontend; node --test tests/meetingDraftReviewStructure.test.mjs`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the safety baseline.**

```powershell
git add bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_meeting_legacy_safety.py bowei_ai_dashboard/tests/test_meeting_draft_review.py frontend/src/features/meeting/NewMeetingModal.tsx frontend/tests/meetingDraftReviewStructure.test.mjs
git commit -m "fix: prevent lossy legacy meeting analysis"
```

### Task 2: Add segments, persisted run progress, and bounded settings

**Files:**

- Modify: `bowei_ai_dashboard/app/models.py:113-187`
- Modify: `bowei_ai_dashboard/app/schemas.py:430-540`
- Modify: `bowei_ai_dashboard/app/settings.py`
- Create: `bowei_ai_dashboard/migrations/versions/d2e3f4a5b6c7_add_meeting_segments_and_run_progress.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_analysis_models.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_agent_settings.py`

- [ ] **Step 1: Write failing ORM and settings tests.**

```python
def test_segment_binds_exact_revision_and_offsets():
    segment = models.MeetingSegment(
        source_id=3, transcript_revision_id=7, segment_no=1,
        speaker_label="发言人1", char_start=0, char_end=8,
        text="发言人1：开始", text_hash="a" * 64,
    )
    assert segment.speaker_person_id is None
    assert segment.speaker_mapping_json == "{}"


def test_meeting_agent_settings_are_bounded(monkeypatch):
    monkeypatch.setenv("MEETING_AGENT_MAX_TRANSCRIPT_CHARS", "500000")
    monkeypatch.setenv("MEETING_AGENT_CHUNK_TARGET_CHARS", "8000")
    settings = get_meeting_agent_settings()
    assert settings.max_transcript_chars == 500_000
    assert settings.chunk_overlap_chars == 800
```

- [ ] **Step 2: Run tests and verify they fail before the model/settings exist.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_models.py tests/test_meeting_agent_settings.py -q`

Expected: failures for missing `MeetingSegment` and `get_meeting_agent_settings`.

- [ ] **Step 3: Add the segment model and run-state fields.**

```python
class MeetingSegment(Base, TimestampMixin):
    __tablename__ = "meeting_segments"
    __table_args__ = (
        UniqueConstraint("transcript_revision_id", "segment_no", name="uq_meeting_segment_revision_no"),
    )
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("meeting_transcript_sources.id"), nullable=False, index=True)
    transcript_revision_id = Column(Integer, ForeignKey("meeting_transcript_revisions.id"), nullable=False, index=True)
    segment_no = Column(Integer, nullable=False)
    speaker_label = Column(String(120), nullable=False, default="")
    speaker_person_id = Column(Integer, ForeignKey("people.id"), nullable=True, index=True)
    speaker_mapping_json = Column(Text, nullable=False, default="{}")
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    start_ms = Column(Integer, nullable=True)
    end_ms = Column(Integer, nullable=True)
    text = Column(Text, nullable=False)
    text_hash = Column(String(64), nullable=False)
```

Add to `MeetingAnalysisRun`: `coverage_manifest_json`, `progress_json`, `error_json`, `usage_json` as non-null `Text` defaults; `cancel_requested` as non-null Boolean; nullable `started_at` and `completed_at`.

- [ ] **Step 4: Add typed settings with fixed safe defaults.**

```python
@dataclass(frozen=True)
class MeetingAgentSettings:
    max_transcript_chars: int
    chunk_target_chars: int
    chunk_overlap_chars: int
    max_chunk_attempts: int


def get_meeting_agent_settings() -> MeetingAgentSettings:
    return MeetingAgentSettings(
        max_transcript_chars=_bounded_int(os.getenv("MEETING_AGENT_MAX_TRANSCRIPT_CHARS"), minimum=10_000, maximum=2_000_000, default=500_000),
        chunk_target_chars=_bounded_int(os.getenv("MEETING_AGENT_CHUNK_TARGET_CHARS"), minimum=2_000, maximum=20_000, default=8_000),
        chunk_overlap_chars=_bounded_int(os.getenv("MEETING_AGENT_CHUNK_OVERLAP_CHARS"), minimum=0, maximum=2_000, default=800),
        max_chunk_attempts=_bounded_int(os.getenv("MEETING_AGENT_MAX_CHUNK_ATTEMPTS"), minimum=1, maximum=5, default=3),
    )
```

- [ ] **Step 5: Create the additive migration.**

Set `revision = "d2e3f4a5b6c7"` and `down_revision = "c1d2e3f4a5b6"`. Create `meeting_segments`, indexes for source/revision/speaker, and the seven run columns with server defaults so existing rows remain valid. Downgrade drops only the new columns and table.

- [ ] **Step 6: Extend Pydantic responses.**

Add `MeetingSegmentResponse`, include the new parsed JSON fields in `MeetingAnalysisRunResponse`, and change `EvidenceRef.segment_id` to `int | None`. Keep `source_hash` for wire compatibility, with the documented meaning “hash of the exact transcript revision used by the run.”

- [ ] **Step 7: Run model tests and migration checks.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_models.py tests/test_meeting_agent_settings.py -q; .\.venv\Scripts\python.exe -m alembic heads`

Expected: tests pass and the only head is `d2e3f4a5b6c7`.

- [ ] **Step 8: Commit schema and settings.**

```powershell
git add bowei_ai_dashboard/app/models.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/settings.py bowei_ai_dashboard/migrations/versions/d2e3f4a5b6c7_add_meeting_segments_and_run_progress.py bowei_ai_dashboard/tests/test_meeting_analysis_models.py bowei_ai_dashboard/tests/test_meeting_agent_settings.py
git commit -m "feat: add meeting segments and run progress"
```

### Task 3: Implement lossless segmentation and full-coverage chunking

**Files:**

- Create: `bowei_ai_dashboard/app/services/meeting_segmentation.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_segmentation.py`

- [ ] **Step 1: Write failing coverage, speaker, overlap, and determinism tests.**

```python
def test_chunks_cover_every_character_without_truncation():
    text = "张总：开始\n" + ("甲" * 19_000) + "\n吴肖：结束"
    segments = segment_transcript(text)
    chunks = build_chunks(text, segments, target_chars=8_000, overlap_chars=800)
    covered = set()
    for chunk in chunks:
        covered.update(range(chunk.char_start, chunk.char_end))
    assert covered == set(range(len(text)))
    assert "".join(text[c.char_start:c.char_end] for c in chunks)
    assert chunks == build_chunks(text, segments, 8_000, 800)


def test_speaker_labels_are_unconfirmed_strings():
    rows = segment_transcript("发言人1：完成联调\n张总：改为周五")
    assert [row.speaker_label for row in rows] == ["发言人1", "张总"]
    assert all(row.speaker_person_id is None for row in rows)
```

- [ ] **Step 2: Run tests and verify the module is missing.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_segmentation.py -q`

Expected: import failure for `app.services.meeting_segmentation`.

- [ ] **Step 3: Implement immutable value objects and stable hashes.**

```python
@dataclass(frozen=True)
class SegmentDraft:
    segment_no: int
    speaker_label: str
    speaker_person_id: None
    char_start: int
    char_end: int
    text: str
    text_hash: str


@dataclass(frozen=True)
class AnalysisChunk:
    chunk_id: str
    index: int
    char_start: int
    char_end: int
    segment_numbers: tuple[int, ...]
    text_hash: str
```

`segment_transcript()` must preserve original character offsets, including CR/LF and blank separators. Split first on speaker-prefixed lines (`^[^\n：:]{1,40}[：:]`), then split any segment larger than the chunk target at punctuation/newline boundaries. Do not normalize or rewrite source text.

`build_chunks()` advances by `target_chars - overlap_chars`, snaps boundaries to segment edges where possible, sets the first start to 0 and final end to `len(text)`, and hashes `text[start:end]`. Build `chunk_id` from zero-padded index plus the first 12 hex characters of the hash.

- [ ] **Step 4: Add edge-case tests.**

Cover empty text rejection, CRLF, no speaker labels, one paragraph over 20,000 characters, repeated quotes, emoji, Chinese punctuation, and an overlap of zero.

- [ ] **Step 5: Run segmentation tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_segmentation.py -q`

Expected: all tests pass and the coverage assertion includes every source character.

- [ ] **Step 6: Commit segmentation.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_segmentation.py bowei_ai_dashboard/tests/test_meeting_segmentation.py
git commit -m "feat: segment complete meeting transcripts"
```

### Task 4: Canonicalize evidence and expand deterministic validation

**Files:**

- Modify: `bowei_ai_dashboard/app/services/meeting_validation.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_evidence_contract.py`
- Modify: `bowei_ai_dashboard/tests/test_meeting_validation.py`

- [ ] **Step 1: Write failing tests for revision-bound evidence and unique quote fallback.**

```python
def test_local_evidence_is_converted_to_global_revision_offsets():
    chunk = SimpleNamespace(char_start=100, char_end=110, text="吴肖下周三前完成测试")
    ref = normalize_chunk_evidence(
        {"char_start": 0, "char_end": 10, "quote": "吴肖下周三前完成测试"},
        chunk=chunk, source_id=4, revision_id=9,
        revision_text="甲" * 100 + chunk.text, revision_hash="abc",
        segments=[SimpleNamespace(id=22, char_start=100, char_end=110)],
    )
    assert ref["char_start"] == 100
    assert ref["segment_id"] == 22
    assert ref["transcript_revision_id"] == 9


def test_duplicate_quote_without_valid_offsets_is_blocked():
    issues = normalize_chunk_evidence(
        {"quote": "下周完成"}, chunk=duplicate_quote_chunk(),
        source_id=1, revision_id=2, revision_text=duplicate_quote_text(),
        revision_hash="b" * 64, segments=[],
    )
    assert issues["status"] == "blocked"
    assert issues["code"] == "ambiguous_quote"
```

- [ ] **Step 2: Run tests and confirm the old validator uses incompatible `start`/`end` fields.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_evidence_contract.py tests/test_meeting_validation.py -q`

Expected: new tests fail before canonical evidence support is implemented.

- [ ] **Step 3: Implement the canonical evidence path.**

Use only `char_start` and `char_end` internally. Accept legacy `start`/`end` only in one adapter, then emit canonical fields. Validate revision ID, SHA-256 hash, range, exact quote, and containing segment. If supplied offsets fail, use the quote only when it appears exactly once inside the chunk; otherwise block it.

```python
def validate_evidence(ref: Any, transcript: Any, expected_hash: Any) -> list[dict[str, str]]:
    if not isinstance(ref, dict) or not isinstance(transcript, str):
        return [{"code": "invalid_ref", "status": "blocked"}]
    start, end = ref.get("char_start"), ref.get("char_end")
    if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start or end > len(transcript):
        return [{"code": "invalid_span", "status": "blocked"}]
    issues = []
    if transcript[start:end] != ref.get("quote"):
        issues.append({"code": "quote_mismatch", "status": "blocked"})
    if ref.get("source_hash", "").removeprefix("sha256:") != expected_hash.removeprefix("sha256:"):
        issues.append({"code": "revision_hash_mismatch", "status": "blocked"})
    return issues
```

- [ ] **Step 4: Expand candidate validation without inference.**

Add all canonical candidate types. Require evidence for summary/topic/member report/progress/action/decision/decision request/issue/risk. Require explicit evidence for owner, deadline, acceptance criteria, risk impact, probability, and mitigation when those fields are non-empty. A project-member snapshot may validate identity but cannot supply a missing claim.

- [ ] **Step 5: Run validator and date regression tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_evidence_contract.py tests/test_meeting_validation.py tests/test_meeting_date_traceability.py tests/test_meeting_extraction_traceability.py -q`

Expected: all selected tests pass.

- [ ] **Step 6: Commit the evidence contract.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_validation.py bowei_ai_dashboard/tests/test_meeting_evidence_contract.py bowei_ai_dashboard/tests/test_meeting_validation.py
git commit -m "feat: bind meeting evidence to transcript revisions"
```

### Task 5: Extract atomic facts from every chunk through a provider-neutral gateway

**Files:**

- Create: `bowei_ai_dashboard/app/services/meeting_llm.py`
- Create: `bowei_ai_dashboard/app/services/meeting_analysis_agent.py`
- Modify: `bowei_ai_dashboard/app/routers/meetings.py:1045-1088`
- Create: `bowei_ai_dashboard/tests/test_meeting_llm.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_agent.py`

- [ ] **Step 1: Write failing parser and prompt-contract tests.**

```python
def test_parse_first_json_object_ignores_trailing_object():
    assert parse_first_json_object('{"facts": []}\n{"ignored": true}') == {"facts": []}


def test_atomic_prompt_forbids_project_context_as_evidence():
    prompt = build_atomic_fact_prompt(chunk_text="吴肖完成测试", member_snapshot={"members": []})
    assert "项目上下文不能作为会议证据" in prompt
    assert "char_start" in prompt and "char_end" in prompt
    assert "不明确则使用 null" in prompt
```

- [ ] **Step 2: Run tests and verify both modules are missing.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_llm.py tests/test_meeting_analysis_agent.py -q`

Expected: import failures.

- [ ] **Step 3: Extract the existing provider calls into `meeting_llm.py`.**

```python
@dataclass(frozen=True)
class MeetingModelResult:
    payload: dict[str, Any]
    provider: str
    model_name: str
    raw_text: str
    usage: dict[str, int]


def call_meeting_json(prompt: str, provider: str) -> MeetingModelResult:
    config = get_provider_config(provider)
    if not config.get("api_key"):
        raise RuntimeError(f"未配置 {provider} API Key")
    if provider == "anthropic":
        import anthropic
        response = anthropic.Anthropic(api_key=config["api_key"], timeout=90).messages.create(
            model=config["model"], max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = response.content[0].text
        usage = {
            "input_tokens": int(getattr(response.usage, "input_tokens", 0)),
            "output_tokens": int(getattr(response.usage, "output_tokens", 0)),
        }
    else:
        from openai import OpenAI
        response = OpenAI(api_key=config["api_key"], base_url=config.get("base_url"), timeout=90).chat.completions.create(
            model=config["model"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        raw_text = response.choices[0].message.content or ""
        usage = {
            "input_tokens": int(getattr(response.usage, "prompt_tokens", 0) or 0),
            "output_tokens": int(getattr(response.usage, "completion_tokens", 0) or 0),
        }
    return MeetingModelResult(
        payload=parse_first_json_object(raw_text), provider=provider,
        model_name=str(config["model"]), raw_text=raw_text, usage=usage,
    )
```

Retain `meetings._do_analyze(text, prompt, provider)` as a compatibility wrapper returning `call_meeting_json(prompt, provider).payload`, so kickoff and legacy tests do not break.

- [ ] **Step 4: Define the atomic-fact output contract.**

```json
{
  "facts": [
    {
      "fact_type": "action_item",
      "content": "完成测试",
      "speaker_label": "吴肖",
      "owner_name": "吴肖",
      "deadline_expression": "下周三前",
      "acceptance_criteria": null,
      "subject_key": "完成测试",
      "evidence": [{"char_start": 0, "char_end": 11, "quote": "吴肖下周三前完成测试"}]
    }
  ]
}
```

The prompt allows only canonical types, requires local chunk offsets and exact quotes, and requires `null` instead of inferred people/dates/criteria.

- [ ] **Step 5: Implement normalization.**

`extract_atomic_facts()` calls the injected provider, rejects non-list facts, canonicalizes types, resolves evidence to global revision offsets through Task 4, validates each field, and returns both raw payload and normalized facts. Facts with no valid evidence remain in the audit output with `validation_status="blocked"` and cannot become review candidates.

- [ ] **Step 6: Add tests for unknown types, invented owners, invalid evidence, and provider metadata.**

Use fake provider functions only; unit tests must not call external models.

- [ ] **Step 7: Run tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_llm.py tests/test_meeting_analysis_agent.py tests/test_meeting_draft_review.py -q`

Expected: all selected tests pass, including compatibility tests for `_do_analyze`.

- [ ] **Step 8: Commit extraction.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_llm.py bowei_ai_dashboard/app/services/meeting_analysis_agent.py bowei_ai_dashboard/app/routers/meetings.py bowei_ai_dashboard/tests/test_meeting_llm.py bowei_ai_dashboard/tests/test_meeting_analysis_agent.py
git commit -m "feat: extract evidence-backed meeting facts"
```

### Task 6: Merge facts, detect conflicts, and assemble grounded minutes

**Files:**

- Create: `bowei_ai_dashboard/app/services/meeting_analysis_merge.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_merge.py`

- [ ] **Step 1: Write failing merge and conflict tests.**

```python
def test_duplicate_fact_keeps_all_evidence():
    merged = merge_atomic_facts([fact("完成联调", "q1"), fact("完成联调", "q2")])
    assert len(merged.candidates) == 1
    assert {ref["quote"] for ref in merged.candidates[0]["evidence_refs"]} == {"q1", "q2"}


def test_later_explicit_replacement_is_superseded_not_silently_resolved():
    result = merge_atomic_facts([
        action("周三交付", deadline="周三", offset=10),
        action("改为周五交付，以周五为准", deadline="周五", offset=80),
    ])
    assert result.relations == [{"kind": "superseded", "old_fact_id": result.fact_ids[0], "new_fact_id": result.fact_ids[1]}]


def test_unresolved_dates_create_conflict():
    result = merge_atomic_facts([action("交付", deadline="周三"), action("交付", deadline="周五")])
    assert result.candidates[0]["validation_status"] == "needs_confirmation"
    assert result.conflicts[0]["field"] == "deadline_expression"
```

- [ ] **Step 2: Run tests and verify the merge module is missing.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_merge.py -q`

Expected: import failure.

- [ ] **Step 3: Implement deterministic merge rules.**

Create stable `fact_id` from type, normalized subject, content, owner, deadline, and evidence hashes. Deduplicate exact normalized facts, preserving all evidence. Group possible conflicts only when type and normalized `subject_key` match. Recognize supersession only when the later evidence contains an explicit marker such as `改为`, `更正为`, `取消刚才`, or `以…为准`; otherwise preserve both values and mark `needs_confirmation`.

- [ ] **Step 4: Assemble the structured minutes package.**

```python
def assemble_minutes(candidates: list[dict], conflicts: list[dict]) -> dict[str, Any]:
    return {
        "executive_summary": [],
        "topics": by_type(candidates, "topic"),
        "member_reports": by_type(candidates, "member_report"),
        "progress_items": by_type(candidates, "progress"),
        "decisions": by_type(candidates, "decision"),
        "decision_requests": by_type(candidates, "decision_request"),
        "action_items": by_type(candidates, "action_item"),
        "issues": by_type(candidates, "issue"),
        "risks": by_type(candidates, "risk"),
        "conflicts": conflicts,
    }
```

Generate executive-summary bullets only from validated fact IDs. Each bullet stores `fact_ids` and inherits their evidence; reject unknown IDs. The summary model may choose and paraphrase validated facts, but cannot introduce an owner, date, criterion, decision, issue, or risk absent from referenced facts.

- [ ] **Step 5: Add classification regressions.**

Verify completed progress is not a risk, questions are not decisions, issues are distinct from future risks, and an unresolved conflict is visible instead of auto-resolved.

- [ ] **Step 6: Run merge tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_merge.py tests/test_meeting_validation.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit merge and grounded assembly.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_analysis_merge.py bowei_ai_dashboard/tests/test_meeting_analysis_merge.py
git commit -m "feat: merge meeting facts with conflict tracking"
```

### Task 7: Persist and resume the complete analysis run

**Files:**

- Create: `bowei_ai_dashboard/app/services/meeting_analysis_runner.py`
- Create: `bowei_ai_dashboard/app/services/meeting_analysis_workbench.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_runner.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_workbench.py`

- [ ] **Step 1: Write failing run-state and resume tests.**

```python
def test_run_cannot_reach_review_with_failed_chunk(db, fake_provider):
    run = create_run_fixture(db, chunk_count=3)
    fake_provider.fail_on_chunk(1)
    process_analysis_run(run.id, session_factory(db), fake_provider)
    db.refresh(run)
    assert run.status == "failed"
    manifest = json.loads(run.coverage_manifest_json)
    assert [c["status"] for c in manifest["chunks"]] == ["completed", "failed", "pending"]


def test_resume_reuses_completed_chunks_without_duplicate_candidates(db, fake_provider):
    run = failed_run_with_first_chunk_complete(db)
    process_analysis_run(run.id, session_factory(db), fake_provider)
    assert fake_provider.calls_for("chunk-0000") == 0
    assert db.query(models.MeetingAnalysisCandidate).filter_by(run_id=run.id).count() == 2
```

- [ ] **Step 2: Run tests and verify runner/workbench modules are missing.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_runner.py tests/test_meeting_analysis_workbench.py -q`

Expected: import failures.

- [ ] **Step 3: Implement transactional run creation.**

```python
def create_analysis_run(payload: MeetingAnalysisRunCreate, actor_person_id: int, db: Session) -> MeetingAnalysisRun:
    settings = get_meeting_agent_settings()
    text = payload.transcript_text
    if not text.strip():
        raise AnalysisInputError("transcript_empty")
    if len(text) > settings.max_transcript_chars:
        raise AnalysisInputError("transcript_too_large")
    revision_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source = MeetingTranscriptSource(raw_text=text, source_hash=revision_hash, source_type="manual", created_by_person_id=actor_person_id)
    db.add(source); db.flush()
    revision = MeetingTranscriptRevision(source_id=source.id, revision_no=1, text=text, text_hash=revision_hash, created_by_person_id=actor_person_id)
    db.add(revision); db.flush()
    # Persist segment rows, construct chunk manifest, freeze member snapshot, create queued run.
```

Always create revision 1 for the original source so every run binds an exact revision. Populate `plan_snapshot_json` with `{}` in P0-A; project tasks are not read by the analysis agent.

- [ ] **Step 4: Implement the persisted state machine.**

`process_analysis_run(run_id, session_factory=SessionLocal, model_call=call_meeting_json)` reloads the run, marks the active stage, processes only pending/failed chunks below the attempt limit, and commits manifest/raw output/usage after each chunk. It checks `cancel_requested` between chunks. It deletes and recreates final candidates only when every chunk is completed and merge begins inside one transaction.

On exception, store only an error code, stage, and safe message in `error_json`; never log transcript text or raw model output. Set `completed_at` only for `review`, `failed`, `cancelled`, or `saved`.

- [ ] **Step 5: Implement explicit resume and cancellation.**

`prepare_resume()` changes retryable failed chunks to pending, preserves completed chunks, clears safe error state, and returns the run to queued. `request_cancel()` sets `cancel_requested=True`; a queued run becomes cancelled immediately, while an active run stops at the next chunk boundary.

- [ ] **Step 6: Add concurrency and idempotency tests.**

Verify a run already in an active state cannot be started twice; repeated resume after review is rejected; repeated runner invocation after review does not duplicate candidates; cancellation preserves completed chunk audit data.

- [ ] **Step 7: Run runner tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_runner.py tests/test_meeting_analysis_workbench.py -q`

Expected: all tests pass without external API calls.

- [ ] **Step 8: Commit persisted execution.**

```powershell
git add bowei_ai_dashboard/app/services/meeting_analysis_runner.py bowei_ai_dashboard/app/services/meeting_analysis_workbench.py bowei_ai_dashboard/tests/test_meeting_analysis_runner.py bowei_ai_dashboard/tests/test_meeting_analysis_workbench.py
git commit -m "feat: persist and resume meeting analysis runs"
```

### Task 8: Add secured P0-A APIs and immutable reviewed-draft saving

**Files:**

- Create: `bowei_ai_dashboard/app/routers/meeting_analysis.py`
- Modify: `bowei_ai_dashboard/app/main.py:475-496`
- Modify: `bowei_ai_dashboard/app/schemas.py`
- Modify: `bowei_ai_dashboard/app/services/meeting_revisions.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_api.py`
- Create: `bowei_ai_dashboard/tests/test_meeting_analysis_save.py`

- [ ] **Step 1: Add failing API permission and lifecycle tests.**

Test these exact routes:

```text
POST  /api/meetings/analysis-runs
GET   /api/meetings/analysis-runs/{run_id}
POST  /api/meetings/analysis-runs/{run_id}/resume
POST  /api/meetings/analysis-runs/{run_id}/cancel
PATCH /api/meetings/analysis-runs/{run_id}/candidates/{candidate_id}/review
POST  /api/meetings/analysis-runs/{run_id}/save-draft
POST  /api/meetings/{meeting_id}/transcript-revisions
```

Creator, project owner, and CEO may view a draft run; ordinary members may create their own run but cannot view another member's draft run unless existing project rules allow it. Only the creator or project owner may review/save. Tech admin follows existing project access policy and does not gain implicit business-write permission.

- [ ] **Step 2: Run API tests and verify the router is absent.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_api.py tests/test_meeting_analysis_save.py -q`

Expected: route/import failures.

- [ ] **Step 3: Add typed request/response contracts.**

```python
class MeetingAnalysisRunCreate(BaseModel):
    project_id: int
    meeting_id: int | None = None
    transcript_text: str = Field(min_length=1)
    meeting_date: str = ""
    meeting_type: str = ""


class MeetingAnalysisRunDetail(BaseModel):
    run: MeetingAnalysisRunResponse
    segments: list[MeetingSegmentResponse]
    candidates: list[MeetingAnalysisCandidateResponse]
    minutes: dict[str, Any]
```

Return HTTP 202 from run creation and resume, 409 for invalid state transitions, 413 for configured transcript size overflow, and 422 for malformed review values.

- [ ] **Step 4: Schedule work without holding the request open.**

```python
@router.post("/analysis-runs", status_code=202)
def create_run(payload: schemas.MeetingAnalysisRunCreate, background_tasks: BackgroundTasks, ...):
    run = meeting_analysis_workbench.create_analysis_run(payload, account.person_id, db)
    db.commit()
    background_tasks.add_task(process_analysis_run, run.id)
    return {"id": run.id, "status": run.status}
```

- [ ] **Step 5: Implement candidate review rules.**

Candidate review states remain `accepted`, `needs_confirmation`, and `ignored`. Block accepting a candidate whose deterministic validation status is `blocked`. Save reviewer ID, comment, human final value, and a field-level diff from the agent proposal.

- [ ] **Step 6: Extend revision saving with provenance.**

Add optional keyword-only `provenance` to `append_meeting_revision()` and pass only allowlisted fields:

```python
provenance = {
    "transcript_source_id": run.source_id,
    "transcript_revision_id": run.transcript_revision_id,
    "analysis_run_id": run.id,
    "parent_revision_id": latest_revision.id if latest_revision else None,
    "revision_kind": "agent_review_save",
    "agent_output_json": run.normalized_output_json,
    "validation_output_json": run.validation_output_json,
    "human_output_json": json.dumps(reviewed_package, ensure_ascii=False),
    "human_diff_json": json.dumps(review_diff, ensure_ascii=False),
}
```

Saving requires every candidate to be explicitly reviewed. Accepted items populate the rich package; `needs_confirmation` items populate `pending_items`; ignored items remain audit-only. Legacy projection maps only accepted `action_item` → `task_list_json`, `decision` → `decision_items_json`, and `issue`/`risk` → `risk_items_json`. It never maps confirmed items or progress into risks. No task/subtask/issue/achievement write service may be imported.

- [ ] **Step 7: Add transcript-revision behavior.**

Creating a corrected revision appends `revision_no + 1`, computes a new hash, and does not mutate prior revisions or prior runs. A new analysis must be started against that revision; old evidence remains valid against the old revision.

- [ ] **Step 8: Run API, revision, and permission tests.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_analysis_api.py tests/test_meeting_analysis_save.py tests/test_meeting_revision_service.py tests/test_meeting_revision_api.py tests/test_meeting_draft_review.py -q`

Expected: all selected tests pass.

- [ ] **Step 9: Commit APIs and reviewed saving.**

```powershell
git add bowei_ai_dashboard/app/routers/meeting_analysis.py bowei_ai_dashboard/app/main.py bowei_ai_dashboard/app/schemas.py bowei_ai_dashboard/app/services/meeting_revisions.py bowei_ai_dashboard/tests/test_meeting_analysis_api.py bowei_ai_dashboard/tests/test_meeting_analysis_save.py
git commit -m "feat: review and save grounded meeting minutes"
```

### Task 9: Add typed frontend run APIs and the evidence review workspace

**Files:**

- Modify: `frontend/src/api/meetings.ts`
- Create: `frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx`
- Create: `frontend/tests/meetingAnalysisApi.test.mjs`
- Create: `frontend/tests/meetingAnalysisWorkspace.test.mjs`

- [ ] **Step 1: Write failing structural tests for API types and the two-column workspace.**

```js
test('meeting analysis API uses persisted runs', () => {
  assert.ok(apiSource.includes('/api/meetings/analysis-runs'))
  assert.ok(apiSource.includes('fetchMeetingAnalysisRun'))
  assert.ok(apiSource.includes('reviewMeetingCandidate'))
  assert.ok(apiSource.includes('saveMeetingAnalysisDraft'))
})

test('workspace exposes evidence and review states', () => {
  assert.ok(workspace.includes('原文证据'))
  assert.ok(workspace.includes('AI 纪要'))
  assert.ok(workspace.includes('待确认'))
  assert.ok(workspace.includes('定位证据'))
})
```

- [ ] **Step 2: Run tests and verify the new files/functions are absent.**

Run: `cd frontend; node --test tests/meetingAnalysisApi.test.mjs tests/meetingAnalysisWorkspace.test.mjs`

Expected: failures for missing source files/functions.

- [ ] **Step 3: Add canonical TypeScript types and API functions.**

Define `EvidenceRef`, `MeetingSegment`, `MeetingAnalysisCandidate`, `MeetingAnalysisRun`, `MeetingAnalysisRunDetail`, and the exact run status union. Add create/fetch/resume/cancel/review/save functions. Keep legacy `analyzeMeeting()` for fallback only.

- [ ] **Step 4: Implement polling with terminal-state handling.**

The workspace polls every two seconds only while status is queued/segmenting/extracting/merging/summarizing. It stops on review/failed/cancelled/saved and on unmount. It displays completed/total chunks, current stage, retryable error code, resume, and cancel controls.

- [ ] **Step 5: Implement two-column review.**

Left column renders the immutable revision text split by segment. Right column groups candidates by type and shows agent value, validator state/messages, evidence quotes, editable final value, and accepted/needs-confirmation/ignored actions. Clicking evidence scrolls to `segment-${segment_id}` and highlights the quote range. No project-change column or writeback button is present in P0-A.

- [ ] **Step 6: Run frontend tests and TypeScript build.**

Run: `cd frontend; node --test tests/meetingAnalysisApi.test.mjs tests/meetingAnalysisWorkspace.test.mjs; npm run build`

Expected: Node tests pass and Vite/TypeScript build exits 0.

- [ ] **Step 7: Commit frontend run/review primitives.**

```powershell
git add frontend/src/api/meetings.ts frontend/src/features/meeting/MeetingAnalysisReviewWorkspace.tsx frontend/tests/meetingAnalysisApi.test.mjs frontend/tests/meetingAnalysisWorkspace.test.mjs
git commit -m "feat: add meeting evidence review workspace"
```

### Task 10: Integrate the new flow and show immutable provenance

**Files:**

- Modify: `frontend/src/features/meeting/NewMeetingModal.tsx`
- Modify: `frontend/src/pages/MeetingPage.tsx`
- Modify: `frontend/src/api/meetings.ts`
- Create: `frontend/tests/meetingAnalysisIntegration.test.mjs`
- Modify: `frontend/tests/meetingRevisionHistory.test.mjs`

- [ ] **Step 1: Write failing integration structure tests.**

Verify `NewMeetingModal` creates a run instead of calling `analyzeMeeting`, renders `MeetingAnalysisReviewWorkspace`, and only closes after `saveMeetingAnalysisDraft` succeeds. Verify `MeetingPage` renders source revision, run ID, validator status, topics, member reports, decisions, decision requests, actions, issues, risks, conflicts, and pending items from `human_output_json`.

- [ ] **Step 2: Run tests and confirm the old modal still uses one-shot analysis.**

Run: `cd frontend; node --test tests/meetingAnalysisIntegration.test.mjs tests/meetingRevisionHistory.test.mjs`

Expected: failures until integration is changed.

- [ ] **Step 3: Replace the modal's ordinary-meeting path.**

Keep kickoff behavior unchanged. For ordinary meetings: input → create run → progress/review workspace → save reviewed draft. Preserve entered meeting type/date as run metadata. On failure, keep the modal open and expose resume; never fall back automatically to a truncated one-shot call.

- [ ] **Step 4: Extend revision response parsing and history UI.**

Parse `human_output_json`, `validation_output_json`, and provenance IDs in `fetchMeetingRevisions`. Legacy revisions with invalid/empty JSON render through existing summary/action/decision/risk fields without crashing.

- [ ] **Step 5: Add accessibility and state tests.**

Ensure controls have text labels, the selected evidence segment receives focus, save is disabled while candidates remain pending, and a failed run cannot be presented as completed.

- [ ] **Step 6: Run all meeting frontend tests and build.**

Run: `cd frontend; node --test tests/kickoffAgentStructure.test.mjs tests/meeting*.test.mjs; npm run build`

Expected: all meeting tests pass and build exits 0.

- [ ] **Step 7: Commit integration.**

```powershell
git add frontend/src/features/meeting/NewMeetingModal.tsx frontend/src/pages/MeetingPage.tsx frontend/src/api/meetings.ts frontend/tests/meetingAnalysisIntegration.test.mjs frontend/tests/meetingRevisionHistory.test.mjs
git commit -m "feat: use persisted meeting analysis runs"
```

### Task 11: Add the ten-case gold evaluation and final release gate

**Files:**

- Create: `bowei_ai_dashboard/tests/fixtures/meeting_agent_gold.json`
- Create: `bowei_ai_dashboard/tests/test_meeting_agent_gold.py`
- Create: `docs/acceptance/meeting-agent-p0a-acceptance.md`

- [ ] **Step 1: Create ten explicit synthetic scenarios.**

The fixture IDs and required focus are fixed:

1. `explicit_action_owner_date` — explicit owner and “8月3日前”.
2. `missing_owner_and_criteria` — both remain null/needs confirmation.
3. `progress_not_risk` — completed platform update is progress.
4. `issue_vs_future_risk` — current connection timeout is issue; possible delay is risk.
5. `question_not_decision` — “是否追加预算” is decision request.
6. `conflicting_deadlines` — Wednesday/Friday conflict remains unresolved.
7. `explicit_supersession` — “改为周五，以周五为准” supersedes Wednesday.
8. `repeated_quote_offsets` — duplicate quote requires valid offsets.
9. `long_transcript_all_chunks` — over 24,000 characters and at least four chunks, all completed.
10. `unknown_speaker_identity` — speaker label retained, person ID remains null.

Each case stores transcript, expected fact types, exact evidence quotes, fields that must remain null, expected conflict/supersession relations, and forbidden classifications.

- [ ] **Step 2: Write the evaluator test.**

```python
def test_gold_cases_have_full_evidence_and_no_forbidden_claims():
    for case in load_gold_cases():
        result = run_pipeline_with_fixture_provider(case)
        assert result.coverage_rate == 1.0
        assert result.evidence_coverage == 1.0
        assert result.unsupported_claims == []
        assert_gold_expectations(case, result)
```

Use recorded fixture-provider responses so CI is deterministic and never calls a paid model. Add a separate opt-in script/marker for live-model evaluation; it is not part of the default test suite.

- [ ] **Step 3: Run the gold and full scoped backend suite.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests/test_meeting_agent_gold.py tests/test_meeting_legacy_safety.py tests/test_meeting_analysis_models.py tests/test_meeting_segmentation.py tests/test_meeting_evidence_contract.py tests/test_meeting_validation.py tests/test_meeting_llm.py tests/test_meeting_analysis_agent.py tests/test_meeting_analysis_merge.py tests/test_meeting_analysis_runner.py tests/test_meeting_analysis_workbench.py tests/test_meeting_analysis_api.py tests/test_meeting_analysis_save.py tests/test_meeting_revision_service.py tests/test_meeting_revision_api.py -q`

Expected: all selected tests pass; gold coverage and evidence coverage are exactly 100%, and unsupported claims are zero for recorded cases.

Release metric gate: `Coverage Rate = 100%`, `Evidence Coverage = 100%`, and `Unsupported Claim Rate = 0` for the recorded deterministic gold set.

- [ ] **Step 4: Verify migration on temporary SQLite and PostgreSQL-compatible SQL generation.**

Run: `cd bowei_ai_dashboard; $env:DATABASE_URL='sqlite:///./meeting_agent_migration_test.db'; .\.venv\Scripts\python.exe -m alembic upgrade head; .\.venv\Scripts\python.exe -m alembic current`

Expected: upgrade exits 0 and current revision is `d2e3f4a5b6c7`. Remove only the explicitly named temporary database after confirming its resolved path is inside `bowei_ai_dashboard`.

- [ ] **Step 5: Run the complete repository verification.**

Run: `cd bowei_ai_dashboard; .\.venv\Scripts\python.exe -m pytest tests -q; cd ..\frontend; node --test tests/*.test.mjs; npm run build`

Expected: backend suite, frontend suite, and production build all exit 0. Any pre-existing unrelated failure must be recorded with the exact command and output; do not claim completion while a P0-A-related failure remains.

- [ ] **Step 6: Write the acceptance record.**

`docs/acceptance/meeting-agent-p0a-acceptance.md` records baseline commit, implementation commit, migration head, test counts, build result, ten-case metric table, maximum transcript setting, chunk settings, known P0 limitation (in-process background scheduling), and confirmation that no project-task write path was added.

- [ ] **Step 7: Commit fixtures and acceptance evidence.**

```powershell
git add bowei_ai_dashboard/tests/fixtures/meeting_agent_gold.json bowei_ai_dashboard/tests/test_meeting_agent_gold.py docs/acceptance/meeting-agent-p0a-acceptance.md
git commit -m "test: verify trustworthy meeting minutes p0a"
```

## Plan self-review

- **P0-A scope:** Tasks 2–8 implement source/revision binding, stable segments, full chunk coverage, atomic extraction, merge/conflict handling, resumable runs, review, and immutable draft saving. Tasks 9–10 implement only the evidence/minutes UI; project-change UI is absent.
- **Existing-code reuse:** Existing transcript source/revision, run, candidate, revision, validation, permission, and provider configuration are extended rather than duplicated.
- **No silent truncation:** Task 1 removes old slicing and Task 3/7 guarantee full coverage in the new flow. Oversized input is rejected explicitly.
- **No hidden writes:** The new Agent path writes transcript/audit/minutes records only. It does not import project task, subtask, issue, achievement, kickoff writeback, or generic workflow mutation services.
- **Traceability:** Every candidate binds exact revision hash, global offsets, quote, and segment; every saved revision binds source/revision/run and preserves agent, validation, human output, and diff.
- **Failure behavior:** A failed chunk prevents review status; completed chunks survive retry; cancellation and resume are explicit; the UI cannot display failed work as completed.
- **Compatibility:** Legacy analyze/create/update/history paths remain available, kickoff behavior remains unchanged, and legacy revisions still render.
- **Deferred work:** P0-B task matching and Before/After proposals, P0-C project-data writeback, audio, realtime, multi-source fusion, and external durable queues remain outside this plan.

## Execution handoff

Implement only after creating an isolated worktree from the latest fetched `origin/main`. Recommended execution is subagent-driven, one task at a time, with requirement review and code-quality review after each task. Do not stage or commit the unrelated local database, login configuration, design files, or older untracked plans in the current backup worktree.
