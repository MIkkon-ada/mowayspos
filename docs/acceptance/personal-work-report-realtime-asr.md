# Personal Work Report Realtime ASR Acceptance

## Scope

This runbook validates only real-time transcription for a personal work report.
It explicitly excludes meeting transcription, speaker diarization, and local
model hosting. It does not approve meeting-minutes behavior or any
speaker-attribution workflow.

## Test corpus

Create an immutable corpus of at least 20 WAV files. Store a human-corrected
UTF-8 reference transcript beside each WAV, using the same basename. Record the
WAV checksum and do not rerecord, trim, normalize, denoise, or otherwise change
a file between rollout rows.

The complete corpus must collectively cover all of the following:

- Project names and member names.
- Key-task titles.
- Dates and percentages.
- English brand terms mixed into Chinese speech.
- Natural pauses of 1-2 seconds.
- Representative office noise.
- An immediate stop after the final spoken word, with no trailing silence added.

Use the exact same WAV bytes and UTF-8 references for every rollout row. Keep a
manifest containing case ID, WAV SHA-256, reference-transcript SHA-256, covered
features, project ID, task ID, and expected scoped terms. Never put audio bytes
or transcript bodies into application logs.

## Rollout matrix

| Row | Model | Transport and stop behavior | Context |
| --- | --- | --- | --- |
| 1 | Paraformer (`paraformer-realtime-v2`) | Legacy packet/stop behavior; baseline only | Disabled |
| 2 | Paraformer (`paraformer-realtime-v2`) | 100 ms packets plus explicit `done` | Disabled |
| 3 | Fun-ASR (`fun-asr-realtime`) | 100 ms packets plus explicit `done` | Disabled |
| 4 | Fun-ASR (`fun-asr-realtime`) | 100 ms packets plus explicit `done` | Permission-scoped project/task context enabled |

Run all corpus files through each row under comparable network and host load.
Do not use Row 1 as a deployment target; it exists only to preserve the legacy
baseline.

## Metrics

Capture per-file values and calculate aggregate median and P95 where applicable:

- Character error rate (CER) against the human-corrected UTF-8 reference.
- Scoped project/task terminology recall.
- First partial latency, from first audio packet sent to first partial received.
- First final latency, from first audio packet sent to first final received.
- Stop-to-`done` latency.
- Audio packets per second.
- Backend audio-queue peak.
- Missing-tail count, checked against the final reference words.
- Duplicate-final count, keyed by final `segment_id` and composed output.

Record provider request IDs beside failed cases so they can be investigated
without storing audio or transcript content in logs.

## Acceptance gates

A rollout row is acceptable only when all applicable gates pass:

- Audio packet rate is approximately 10 packets/second during sustained speech.
- Missing-tail count is 0/20 (and remains zero if the corpus has more than 20 files).
- Duplicate-final count is 0.
- First-partial P95 is at most 1.5 seconds.
- Stop-to-`done` P95 is at most 3 seconds.
- Row 4 permission-scoped terminology recall exceeds the Row 1 Paraformer baseline.
- Forged or inaccessible `project_id` and `selected_task_id` values return a
  stable permission error and leak no project, task, member, or context content.

Treat timeout, provider error, malformed event sequence, or absence of `done` as
a failed case, even when the visible transcript appears complete.

## Permission and leakage checks

For a user without access, separately attempt: a valid project with a foreign
task, a foreign project with a valid-looking task, and nonexistent project/task
IDs. Confirm each request is rejected before the ASR session starts. The client
must receive only a stable error code and safe user-facing message; it must not
receive the context string or any protected names.

## Privacy and logging check

Inspect production-format application, proxy, worker, and exception logs for a
successful run and for each failure path. Logs must not contain:

- Raw PCM bytes or encoded audio.
- Transcript text or transcript fragments.
- DashScope or other provider API keys.
- The full ASR context string.

Logs may contain only operational metadata required for diagnosis: user,
project, task and session IDs; packet, context-term and character counts;
durations and latency measurements; queue peak; model name; provider request
ID; and stable error code. Verify exception formatting and debug logging follow
the same restriction.

## Evidence record

For each dated run, archive the corpus manifest and a result table with one row
per corpus case and rollout row. Include configuration values, deployment
version, timestamps, metric values, gate result, provider request ID when
available, and reviewer. Keep WAV files and reference transcripts in the
approved test-data store, not in production application logs.

## Rollback

Restore the backend environment to:

```dotenv
ASR_REALTIME_MODEL=paraformer-realtime-v2
ASR_CONTEXT_ENABLED=false
```

Recreate only the backend container so the process reloads both values. Open a
new personal work-report transcription session and verify its `started` event
reports `model: "paraformer-realtime-v2"`. Confirm context remains disabled and
that an existing in-flight session was not used as rollback evidence. If the
new session reports another model, keep rollout stopped and investigate the
container environment/configuration source before retrying.
