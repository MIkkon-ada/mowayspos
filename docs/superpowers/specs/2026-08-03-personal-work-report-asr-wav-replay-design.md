# Personal Work Report ASR WAV Replay Design

## Scope

Build a local-only command-line replay tool for the personal work-report
realtime transcription WebSocket. It replays immutable 16 kHz mono PCM16 WAV
files and validates transport behavior; it does not test meeting transcription,
speaker diarization, or production deployment.

## Interface

The tool accepts a corpus directory, WebSocket URL, project ID, task ID, and an
optional session cookie. It sends the explicit protocol in this order:

```text
ready -> start -> started -> binary PCM frames -> stop -> done
```

Audio is sent in 100 ms frames (3200 bytes at 16 kHz PCM16). A final short frame
is sent before `stop`. The tool never logs audio bytes, transcript bodies, API
keys, or cookies.

## Evidence

For every case it records only sanitized metadata: case ID, WAV SHA-256, model,
session ID, packet count, audio duration, first partial/final latency,
stop-to-done latency, duplicate-final count, missing-tail result, queue/error
signals, and terminal status. It writes JSON and CSV summaries under an
explicit output directory.

## Authentication and safety

The default endpoint is local (`ws://127.0.0.1:8008/api/transcribe/stream`). A
session cookie may be supplied through an environment variable or command-line
option, but the value is never printed or persisted. The tool refuses meeting
scenes and does not modify application or database state.

## Testing

Unit tests cover corpus discovery, 100 ms frame slicing, protocol ordering,
metadata-only result serialization, duplicate-final detection, and missing-tail
calculation. A live run against the local backend is a separate integration
step and may fail safely when login, project/task scope, or provider credentials
are unavailable.
