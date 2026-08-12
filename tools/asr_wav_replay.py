from __future__ import annotations

import hashlib
import argparse
import asyncio
import csv
import json
import os
import time
import unicodedata
import wave
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable, Mapping

import websockets


def read_wav_pcm(path: str | Path) -> tuple[bytes, int]:
    """Read one 16 kHz mono PCM16 WAV and return bytes plus sample rate."""
    try:
        with wave.open(str(path), "rb") as wav:
            valid = (
                wav.getframerate() == 16_000
                and wav.getnchannels() == 1
                and wav.getsampwidth() == 2
                and wav.getcomptype() == "NONE"
            )
            if not valid:
                raise ValueError("WAV must be 16 kHz mono PCM16")
            return wav.readframes(wav.getnframes()), wav.getframerate()
    except (wave.Error, EOFError) as exc:
        raise ValueError("WAV must be 16 kHz mono PCM16") from exc


def iter_pcm_frames(data: bytes, *, frame_bytes: int = 3_200) -> Iterable[bytes]:
    if frame_bytes <= 0:
        raise ValueError("frame_bytes must be positive")
    for offset in range(0, len(data), frame_bytes):
        yield data[offset : offset + frame_bytes]


def count_duplicate_finals(events: Iterable[Mapping[str, object]]) -> int:
    seen: set[tuple[object, object, object, object]] = set()
    duplicates = 0
    for event in events:
        if event.get("type") != "transcript" or event.get("final") is not True:
            continue
        fingerprint = (
            event.get("segment_id"),
            event.get("text"),
            event.get("begin_time"),
            event.get("end_time"),
        )
        if fingerprint in seen:
            duplicates += 1
        else:
            seen.add(fingerprint)
    return duplicates


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.replace("\ufeff", "")
    chinese_digits = str.maketrans(
        "\u96f6\u3007\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d",
        "00123456789",
    )
    return "".join(
        char.translate(chinese_digits)
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def classify_tail(reference: str, hypothesis: str) -> dict[str, bool]:
    normalized_reference = _normalized_text(reference)
    normalized_hypothesis = _normalized_text(hypothesis)
    if not normalized_reference:
        return {"missing_tail": False, "tail_mismatch": False}
    tail = normalized_reference[-5:]
    if tail in normalized_hypothesis[-20:]:
        return {"missing_tail": False, "tail_mismatch": False}
    return {
        "missing_tail": len(normalized_hypothesis) < len(normalized_reference),
        "tail_mismatch": len(normalized_hypothesis) >= len(normalized_reference),
    }


def has_missing_tail(reference: str, hypothesis: str) -> bool:
    return classify_tail(reference, hypothesis)["missing_tail"]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def serialize_results(results: Iterable[Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    allowed = {
        "case_id",
        "wav_sha256",
        "model",
        "session_id",
        "packet_count",
        "audio_duration_ms",
        "first_partial_ms",
        "first_final_ms",
        "stop_done_ms",
        "duplicate_final_count",
        "missing_tail",
        "tail_mismatch",
        "status",
        "error_code",
    }
    return {"results": [{key: value for key, value in row.items() if key in allowed} for row in results]}


def normalize_cookie(cookie: str | None) -> str | None:
    if not cookie:
        return None
    value = cookie.strip()
    if "=" not in value:
        return f"bowei_session={value}"
    return value


async def replay_case(
    path: str | Path,
    *,
    url: str,
    project_id: int,
    selected_task_id: int,
    cookie: str | None = None,
    connect: Callable[..., Any] = websockets.connect,
    pace: bool = True,
    timeout_seconds: float = 20.0,
) -> dict[str, object]:
    wav_path = Path(path)
    pcm, sample_rate = read_wav_pcm(wav_path)
    case_id = wav_path.stem
    result: dict[str, object] = {
        "case_id": case_id,
        "wav_sha256": sha256_file(wav_path),
        "packet_count": 0,
        "audio_duration_ms": len(pcm) * 1000 // (sample_rate * 2),
        "duplicate_final_count": 0,
        "missing_tail": True,
        "status": "failed",
    }
    headers = {"Cookie": normalize_cookie(cookie)} if normalize_cookie(cookie) else None
    connect_kwargs = {"additional_headers": headers} if headers else {}
    events: list[dict[str, object]] = []
    hypothesis_parts: list[str] = []
    opened_at = time.monotonic()
    first_audio_at: float | None = None
    first_partial_at: float | None = None
    first_final_at: float | None = None
    stop_at: float | None = None
    try:
        async with connect(url, **connect_kwargs) as ws:
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout_seconds))
            if message.get("type") != "ready":
                result["error_code"] = message.get("code", "READY_NOT_RECEIVED")
                return result
            await ws.send(json.dumps({
                "type": "start",
                "scene": "work_report",
                "project_id": project_id,
                "selected_task_id": selected_task_id,
                "sample_rate": sample_rate,
                "format": "pcm",
            }))
            message = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout_seconds))
            if message.get("type") != "started":
                result["error_code"] = message.get("code", "STARTED_NOT_RECEIVED")
                return result
            result["model"] = message.get("model")
            result["session_id"] = message.get("session_id")

            async def receive_events() -> None:
                nonlocal first_partial_at, first_final_at
                while True:
                    incoming = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
                    if isinstance(incoming, bytes):
                        continue
                    event = json.loads(incoming)
                    events.append(event)
                    if event.get("type") != "transcript":
                        if event.get("type") in {"done", "error"}:
                            return
                        continue
                    text = event.get("text")
                    if isinstance(text, str):
                        if event.get("final") is True:
                            hypothesis_parts.append(text)
                            if first_final_at is None:
                                first_final_at = time.monotonic()
                        elif first_partial_at is None:
                            first_partial_at = time.monotonic()

            receiver = asyncio.create_task(receive_events())
            frame_count = 0
            for frame in iter_pcm_frames(pcm):
                if first_audio_at is None:
                    first_audio_at = time.monotonic()
                await ws.send(frame)
                frame_count += 1
                if pace:
                    await asyncio.sleep(len(frame) / (sample_rate * 2))
            result["packet_count"] = frame_count
            stop_at = time.monotonic()
            await ws.send(json.dumps({"type": "stop"}))
            await receiver
            done = next((event for event in events if event.get("type") == "done"), None)
            error = next((event for event in events if event.get("type") == "error"), None)
            result["status"] = "done" if done else "error"
            if error:
                result["error_code"] = error.get("code")
            if stop_at is not None and done:
                result["stop_done_ms"] = round((time.monotonic() - stop_at) * 1000)
            if first_audio_at is not None and first_partial_at is not None:
                result["first_partial_ms"] = round((first_partial_at - first_audio_at) * 1000)
            if first_audio_at is not None and first_final_at is not None:
                result["first_final_ms"] = round((first_final_at - first_audio_at) * 1000)
            result["duplicate_final_count"] = count_duplicate_finals(events)
            result["_final_text"] = "".join(hypothesis_parts)
            result.update(classify_tail(_reference_for(wav_path), result["_final_text"]))
            return result
    except Exception as exc:
        result["error_code"] = type(exc).__name__
        return result


def _reference_for(wav_path: Path) -> str:
    reference = wav_path.with_suffix(".txt")
    return reference.read_text(encoding="utf-8") if reference.exists() else ""


async def replay_corpus(
    corpus: str | Path,
    *,
    url: str,
    project_id: int,
    selected_task_id: int,
    cookie: str | None = None,
    pace: bool = True,
) -> list[dict[str, object]]:
    paths = sorted(Path(corpus).glob("*.wav"))
    if not paths:
        raise ValueError(f"no WAV files found in {corpus}")
    return [
        await replay_case(
            path,
            url=url,
            project_id=project_id,
            selected_task_id=selected_task_id,
            cookie=cookie,
            pace=pace,
        )
        for path in paths
    ]


def write_evidence(results: Iterable[Mapping[str, object]], output: str | Path) -> None:
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    sanitized = serialize_results(results)["results"]
    (output_path / "results.json").write_text(
        json.dumps({"results": sanitized}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    fields = sorted({key for row in sanitized for key in row})
    with (output_path / "results.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sanitized)


def write_debug_transcripts(results: Iterable[Mapping[str, object]], output: str | Path) -> None:
    """Write opt-in local diagnostics; never called by the default CLI path."""
    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)
    payload = {
        "transcripts": [
            {"case_id": row.get("case_id"), "final_text": row.get("_final_text", "")}
            for row in results
        ]
    }
    (output_path / "transcripts.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay local work-report ASR WAV corpus")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--url", default="ws://127.0.0.1:8008/api/transcribe/stream")
    parser.add_argument("--project-id", type=int, required=True)
    parser.add_argument("--task-id", type=int, required=True)
    parser.add_argument("--cookie", default=os.environ.get("MOWAYS_ASR_SESSION_COOKIE"))
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-pace", action="store_true")
    parser.add_argument(
        "--debug-transcripts",
        action="store_true",
        help="explicitly write local final transcript diagnostics",
    )
    args = parser.parse_args()
    results = asyncio.run(
        replay_corpus(
            args.corpus,
            url=args.url,
            project_id=args.project_id,
            selected_task_id=args.task_id,
            cookie=args.cookie,
            pace=not args.no_pace,
        )
    )
    write_evidence(results, args.output)
    if args.debug_transcripts:
        write_debug_transcripts(results, args.output)
    print(json.dumps(serialize_results(results), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
