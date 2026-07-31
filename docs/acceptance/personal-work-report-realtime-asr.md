# Personal Work Report Realtime ASR Acceptance

## Scope

This runbook validates only real-time transcription for a personal work report.
It explicitly excludes meeting transcription, speaker diarization, and local
model hosting. It does not approve meeting-minutes behavior or any
speaker-attribution workflow.

## Test corpus

Create one canonical, immutable release-gate corpus of exactly 20 WAV files.
Store a human-corrected
UTF-8 reference transcript beside each WAV, using the same basename. Record the
WAV checksum and do not rerecord, trim, normalize, denoise, or otherwise change
a file between rollout rows.

The complete corpus must collectively cover all of the following:

- Project names and member names.
- Key-task titles.
- Dates and percentages.
- English brand terms mixed into Chinese speech.
- Natural pauses of 1-3 seconds.
- Representative office noise.
- An immediate stop after the final spoken word, with no trailing silence added.
- `case-20.wav` contains at least 12 seconds of continuous speech/audio so each
  row has a predetermined steady interval of at least 10 seconds for packet-rate
  measurement.

Use the exact same 20 WAV bytes and UTF-8 references for every rollout row. Keep a
manifest containing case ID, WAV SHA-256, reference-transcript SHA-256, covered
features, project ID, task ID, and expected scoped terms. Never put audio bytes
or transcript bodies into application logs. Additional exploratory files may be
reported separately, but they must not replace, enlarge, or selectively filter
the canonical 20-file gate sample.

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

Row 1 cannot be reconstructed with environment variables because its legacy
packet and stop behavior is code-defined. It must use a previously preserved
baseline Git revision and immutable frontend/backend image digests. If that
revision or either image is unavailable, the acceptance run is **BLOCKED**;
never synthesize or label a current build as the legacy baseline.

Row 1 uses its real legacy protocol: after the WebSocket opens, the client sends
small binary PCM frames directly, sends the text message `stop`, receives server
events shaped as `{text, final}`, and treats a normal WebSocket close as the
completion signal. It has no `ready`, `started`, `done`, or `session_id`. The
legacy server's 0.8-second callback wait after `stop` is part of the baseline
behavior and must not be changed or emulated by a current image.
Row 1 CER, terminology recall, missing-tail, duplicate-final, first-partial, and
first-final measurements remain directly comparable with Rows 2-4.

Rows 2-4 use the explicit `ready` -> `start` -> `started` -> binary PCM ->
`stop` -> `done` protocol described by the current implementation.

### Reproducibility record

Before each row, record all of the following in its evidence sheet:

- Git SHA and immutable frontend and backend image digests.
- Effective values, read from the running backend container, for
  `ASR_REALTIME_MODEL`, `ASR_CONTEXT_ENABLED`, `ASR_PACKET_DURATION_MS`,
  `ASR_STOP_TIMEOUT_SECONDS`, and `ASR_HEARTBEAT_ENABLED`. Use `not supported`
  for a legacy setting only when the preserved Row 1 revision truly lacks it.
- Chrome version, operating-system version, and the exact virtual-loopback input
  device name selected as the browser microphone.
- Network path and conditioning: location/VPN, configured latency, jitter,
  loss, and bandwidth. Use one unchanged profile for all rows.
- UTC timestamp and Asia/Shanghai (CST, UTC+08:00) timestamp for row start and
  completion.

Execute rows in fixed order 1, 2, 3, then 4. For every row, recreate only the
backend container, start a fresh Chrome profile/session, run one designated
warm-up WAV that is not part of the 20-file corpus, discard its measurements,
then run cases `01` through `20` exactly once in manifest order. This defines a
cold backend/browser start followed by one consistent warm-up; do not alternate
rows or selectively rerun a measured case. A failed case remains failed, and a
diagnostic retry is recorded separately rather than replacing it.

### Browser loopback replay procedure

Use one dedicated test machine. Configure its fixed virtual-loopback device so
audio played to the paired output appears as Chrome's microphone input. For each
case, confirm Chrome has the recorded loopback microphone selected and open a
new personal work-report WebSocket. Play the immutable WAV through the loopback
output without changing gain or processing settings. For example:

```powershell
ffplay -nodisp -autoexit -loglevel error .\corpus\case-01.wav
```

The command uses the test machine's configured default output; the actual
output/loopback device names and routing must be fixed and recorded for that
machine. Then follow the row-specific sequence:

- **Row 1:** after WebSocket open, begin sending the legacy small binary PCM
  frames. Immediately after playback completes, send text `stop`, retain every
  `{text, final}` event, and wait for a normal WebSocket close. Save monotonic
  timestamps for open, each PCM send, each transcript event, `stop`, and close.
- **Rows 2-4:** wait for `ready`, send `start`, wait for `started`, and only then
  begin PCM. Immediately after playback completes, flush the final short packet,
  send JSON `stop`, retain every transcript event, and wait for `done`. Save
  monotonic timestamps for `ready`, `started`, each PCM send, each transcript
  event, `stop`, and `done`.

Do not start the next file until the applicable completion signal (normal close
for Row 1, `done` for Rows 2-4) has arrived.

This is an operator procedure, not a claim that the repository contains a WAV
replay harness.

## Normalization and scoring

Apply the same deterministic normalization to every reference, hypothesis, and
expected term before CER, term recall, and tail checks:

1. Apply Unicode NFKC normalization.
2. Lowercase English/ASCII letters.
3. Remove every Unicode whitespace code point.
4. Remove only this explicit punctuation set:
   `, . ! ? ; : ' " - _ ( ) [ ] { } / \\ ， 。 ！ ？ ； ： “ ” ‘ ’ 、 （ ） 【 】 《 》 … —`.
5. Preserve all digits, Chinese characters, English letters, and `%` (NFKC
   converts the full-width percent sign to `%`). Preserve any character not in
   the removal set.

Compute **micro CER** as the sum of Levenshtein insertions, deletions, and
substitutions across all 20 files divided by the sum of normalized reference
characters across those files. Do not average 20 per-file CER percentages.

Compute terminology recall as normalized expected-term occurrences matched
exactly in the normalized final transcript divided by total normalized expected
occurrences in the manifest. For each term, count non-overlapping exact matches
in the hypothesis and cap that count at the manifest's expected occurrence
count; sum these capped counts for the numerator. Count repeated expected
occurrences separately and award no fuzzy matches.

## Metrics

Capture per-file values for all 20 files and calculate aggregate median and P95
where applicable. P95 uses nearest rank: sort the `N` values ascending and take
rank `ceil(0.95 * N)`, using one-based ranks. For `N=20`, P95 is rank 19.
Represent a required latency event that never arrives as positive infinity so
it fails the gate; never omit it from `N`.

- Character error rate (CER) against the human-corrected UTF-8 reference.
- Scoped project/task terminology recall.
- First partial latency: client monotonic time when the first partial transcript
  is parsed minus the time immediately after the first successful nonempty PCM
  `WebSocket.send` call.
- First final latency: client monotonic time when the first `final=true`
  transcript is parsed minus that same first-PCM timestamp.
- Stop latency uses a protocol-specific endpoint. For Row 1, record
  stop-to-close from immediately after text `stop` is sent until the normal
  WebSocket close is observed. For Rows 2-4, record stop-to-`done` from
  immediately after JSON `stop` is successfully sent, after the worklet's final
  short-packet flush acknowledgement, until `done` is parsed.
- Audio packets per second: packet count divided by elapsed time over one
  continuous steady window of at least 10 seconds, excluding the final short
  packet and connection/start/stop intervals.
- Backend audio-queue peak: maximum queue depth observed at the coordinator's
  bounded audio-queue enqueue point for that session, sourced from the backend
  queue high-water metric rather than client inference.
- Missing-tail count: after normalization, take the final 5 reference characters
  (or the entire reference when shorter than 5) and require that exact sequence
  to occur within the final 20 normalized hypothesis characters. Count the file
  as one missing tail otherwise.
- Duplicate-final count: for Rows 2-4, count every final after the first with the
  same `segment_id`, and every exact replay of the same final-event fingerprint
  (`segment_id`, normalized text, begin time, and end time). For Row 1, which has
  no `segment_id`, count every second receipt of the same serialized
  `{text, final: true}` payload within a session as a replay. Count duplicates
  even if UI deduplication hides them.

Record provider request IDs beside failed cases so they can be investigated
without storing audio or transcript content in logs.

## Acceptance gates

A rollout row is acceptable only when all applicable gates pass.

### Gates for every row

- Missing-tail count is 0/20.
- Duplicate-final count is 0.
- First-partial P95 is at most 1.5 seconds.
- Row 1 must end every one of its 20 sessions with a normal WebSocket close after
  all final events have been received. The lack of `done` is expected and must
  not fail Row 1.
- Rows 2-4 must emit `done` for every one of their 20 sessions.

Row 1 stop-to-close latency and its legacy packet rate are recorded as baseline
observations only. The current stop-to-`done`, 10-packets/second, and new-queue
gates do not apply to Row 1.

### Candidate gates for Rows 2-4

- Each row's micro CER is less than or equal to the Row 1 Paraformer baseline
  micro CER; no accuracy-regression tolerance is allowed. If Row 2, Row 3, or
  Row 4 is worse during its actual canary, do not advance that candidate and
  roll it back.
- Stop-to-`done` P95 is at most 3 seconds.
- Audio packet rate is 9-11 packets/second over the predetermined continuous
  steady window of at least 10 seconds. If `case-20.wav` does not produce a
  qualifying window, the row fails acceptance rather than skipping this gate.
- The backend `audio_queue` capacity is 50. Sanitized logs for every successful
  session must report `queue_peak <= 40` (80%), and the complete 20-file row must
  contain zero terminal `AUDIO_BACKPRESSURE` events. Any
  `AUDIO_BACKPRESSURE` event fails that session, fails the row, and requires
  rollback.
- Telemetry limitation: the coordinator enqueues audio with `put_nowait`; it
  does not wait on a full queue and therefore produces no producer-blocking
  duration or count. Current telemetry also has no independent dropped-packet
  counter. Do not claim either uncollected value is zero: the auditable overflow
  evidence is the terminal `AUDIO_BACKPRESSURE` event, together with
  `queue_peak` for successful sessions.
- Every session follows the explicit protocol without timeout, provider error,
  malformed event order, or missing `done`, even when visible text appears
  complete.

Row 1's legacy queue capacity is 200. Record its queue peak only when observable
in the preserved build; do not compare it with the capacity-50/peak-40 gate.

### Context gate for Row 4

- Row 4 permission-scoped terminology recall strictly exceeds the Row 1
  Paraformer baseline.
- Forged or inaccessible `project_id` and `selected_task_id` values return a
  stable permission error and leak no project, task, member, or context content.

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

Logs may contain only operational metadata required for diagnosis: opaque
internal user, project, task and session IDs (never member or project names);
packet, context-term and character counts; durations and latency measurements;
queue peak; model name; provider request ID; and stable error code. Verify
exception formatting and debug logging follow the same restriction.

## Evidence record

For each dated run, archive the corpus manifest and a result table with one row
per corpus case and rollout row. Include configuration values, deployment
version, timestamps, metric values, gate result, provider request ID when
available, and reviewer. Keep WAV files and reference transcripts in the
approved test-data store, not in production application logs. Limit access to
named test personnel. Retain raw WAV files, UTF-8 references, and detailed metric
exports for no more than 30 days, or the organization's shorter policy if one
applies, then securely delete them and record deletion time, scope, method, and
operator in the evidence register.

## Verification status

The Task 8 code-level verification was run successfully on 2026-07-31:

- Targeted backend suite: 93 passed.
- All frontend `tests/*.test.mjs`: 309 passed, 0 failed.
- Worklet `node --check`, frontend production build, backend `compileall`, and
  repository diff checks exited successfully.

These results validate the implementation and build only. The four-row
production canary, fixed 20-WAV replay, metric collection, privacy inspection,
and rollback exercise described in this runbook have **not been executed** and
must not be reported as passed until dated evidence exists.

## Rollback

Restore the backend environment to:

```dotenv
ASR_REALTIME_MODEL=paraformer-realtime-v2
ASR_CONTEXT_ENABLED=false
```

Recreate only the backend container so the process reloads both values. Open a
new personal work-report transcription session. Without printing or querying
the provider API key, record the recreated container's effective
`ASR_REALTIME_MODEL=paraformer-realtime-v2` and `ASR_CONTEXT_ENABLED=false`.
Verify the new session's `started` event reports
`model: "paraformer-realtime-v2"`, then complete one full
`ready` -> `started` -> `transcript` -> `done` flow.

Evidence that context is disabled is the effective container environment value
`ASR_CONTEXT_ENABLED=false`, plus a context count of zero if that sanitized
metric is available in logs. Do not depend on a nonexistent context field in
the `started` event. Confirm an existing in-flight session was not used as
rollback evidence. If the new session reports another model or cannot complete
the full flow, keep rollout stopped and investigate the backend container's
effective configuration before retrying.
