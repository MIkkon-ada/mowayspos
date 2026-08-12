# Personal Work Report ASR WAV Replay Implementation Plan

> **For agentic workers:** Execute this plan task-by-task with test-first checkpoints.

**Goal:** Add a local-only WAV replay CLI that exercises the realtime work-report ASR WebSocket and emits sanitized per-case metrics.

**Architecture:** Keep the replay logic outside production code in `tools/`. A small pure-function layer handles WAV validation, 100ms PCM slicing, duplicate-final detection, and tail checks; an async runner handles one WebSocket session and serializes only metadata. The CLI runs the corpus sequentially and writes JSON/CSV evidence.

**Tech Stack:** Python 3, `wave`, `asyncio`, installed `websockets`, `pytest`, JSON/CSV.

---

### Task 1: Add pure replay helpers and tests

**Files:**
- Create: `tools/asr_wav_replay.py`
- Create: `tools/tests/test_asr_wav_replay.py`

- [ ] Write failing tests for 16kHz mono PCM16 validation, 100ms frame slicing, duplicate-final counting, and missing-tail detection.
- [ ] Run `python -m pytest tools/tests/test_asr_wav_replay.py -q`; confirm failure because helpers do not exist.
- [ ] Implement `read_wav_pcm(path)`, `iter_pcm_frames(data, frame_bytes=3200)`, `count_duplicate_finals(events)`, and `has_missing_tail(reference, hypothesis)` using only the standard library.
- [ ] Run the focused test file and confirm all helper tests pass.

### Task 2: Add one-session WebSocket runner

**Files:**
- Modify: `tools/asr_wav_replay.py`
- Modify: `tools/tests/test_asr_wav_replay.py`

- [ ] Add a fake async WebSocket test that verifies the runner waits for `ready`, sends `start`, waits for `started`, sends binary frames, sends `stop`, and waits for `done`.
- [ ] Run the new test and confirm it fails before the runner exists.
- [ ] Implement `async replay_case(...)` with monotonic timestamps and optional cookie header; never include transcript bodies or cookie values in the result.
- [ ] Record case ID, SHA-256, packet count, audio duration, first partial/final latency, stop-to-done latency, duplicate-final count, and terminal error/status.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Add corpus CLI and evidence output

**Files:**
- Modify: `tools/asr_wav_replay.py`
- Modify: `tools/tests/test_asr_wav_replay.py`

- [ ] Test deterministic corpus ordering, reference-text lookup, and JSON/CSV metadata-only serialization.
- [ ] Implement CLI arguments for `--corpus`, `--url`, `--project-id`, `--task-id`, `--cookie`, and `--output`; default URL must be local.
- [ ] Run cases sequentially, fail a case without replacing it with a retry, and write `results.json` and `results.csv` under the explicit output directory.
- [ ] Add a clear refusal for non-16kHz, non-mono, or non-PCM16 files.
- [ ] Run all helper/CLI tests and confirm they pass.

### Task 4: Execute the generated corpus locally

**Files:**
- No production files modified.
- Output: `tmp/asr-corpus-generated/replay-results/`.

- [ ] Start the local backend with the existing explicit SQLite environment and confirm port 8008 is listening.
- [ ] Run the CLI against the 20 generated WAVs with a valid local session cookie, project ID, and selected task ID.
- [ ] If authentication, scope, or provider credentials prevent the run, record the stable terminal error and do not bypass authorization.
- [ ] Inspect JSON/CSV output for packet count, terminal status, duplicate finals, missing tails, and latency fields without exposing transcript content.

### Task 5: Verification and handoff

- [ ] Run `python -m pytest tools/tests/test_asr_wav_replay.py -q`.
- [ ] Run the existing ASR backend tests.
- [ ] Run `python -m compileall tools/asr_wav_replay.py`.
- [ ] Report whether the run was an actual provider-backed replay or only blocked at authentication/scope, clearly separating code verification from ASR accuracy acceptance.
