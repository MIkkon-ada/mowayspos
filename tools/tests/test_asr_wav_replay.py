from __future__ import annotations

from pathlib import Path
import sys
import asyncio
import json
import wave

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from asr_wav_replay import (  # noqa: E402
    count_duplicate_finals,
    has_missing_tail,
    classify_tail,
    iter_pcm_frames,
    read_wav_pcm,
    serialize_results,
    write_evidence,
    write_debug_transcripts,
    replay_case,
    normalize_cookie,
)


def test_iter_pcm_frames_uses_100ms_pcm16_frames():
    frames = list(iter_pcm_frames(b"a" * 6500, frame_bytes=3200))

    assert [len(frame) for frame in frames] == [3200, 3200, 100]


def test_read_wav_pcm_rejects_non_pcm16_mono_16khz(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_bytes(b"not a wav")

    with pytest.raises(ValueError, match="16 kHz mono PCM16"):
        read_wav_pcm(path)


def test_count_duplicate_finals_counts_replays_by_fingerprint():
    events = [
        {"type": "transcript", "segment_id": "s1", "text": "a", "final": True},
        {"type": "transcript", "segment_id": "s1", "text": "a", "final": True},
        {"type": "transcript", "segment_id": "s2", "text": "b", "final": True},
    ]

    assert count_duplicate_finals(events) == 1


def test_has_missing_tail_requires_reference_tail_in_hypothesis_end():
    assert has_missing_tail("本周完成验收", "本周完成验收") is False
    assert has_missing_tail("本周完成验收", "本周完成") is True
    assert has_missing_tail("项目名称是 Moways AI 驾驶舱。", "项目名称是 Moways AI 驾驶舱") is False
    assert has_missing_tail("任务预计在八月三日晚上六点完成。", "任务预计在8月3日晚上6点完成。") is False


def test_classify_tail_distinguishes_truncation_from_recognition_mismatch():
    assert classify_tail("当前版本需要重点验证实时出字延迟。", "当前版本需要重点验证实时出自延迟。") == {
        "missing_tail": False,
        "tail_mismatch": True,
    }
    assert classify_tail("本周完成项目验收。", "本周完成项目。") == {
        "missing_tail": True,
        "tail_mismatch": False,
    }


def test_serialize_results_excludes_transcript_text_and_cookie():
    payload = serialize_results(
        [{"case_id": "case-01", "hypothesis": "隐私文本", "status": "done"}]
    )

    assert "隐私文本" not in payload
    assert payload["results"][0] == {"case_id": "case-01", "status": "done"}


def test_write_evidence_writes_json_and_csv_without_transcript_text(tmp_path):
    write_evidence(
        [{"case_id": "case-01", "hypothesis": "不应落盘", "status": "done"}],
        tmp_path / "evidence",
    )

    assert "不应落盘" not in (tmp_path / "evidence" / "results.json").read_text(encoding="utf-8")
    assert "case-01" in (tmp_path / "evidence" / "results.csv").read_text(encoding="utf-8")


def test_write_debug_transcripts_is_explicit_and_case_scoped(tmp_path):
    write_debug_transcripts(
        [{"case_id": "case-09", "_final_text": "调试文本", "status": "done"}],
        tmp_path / "debug",
    )

    assert (tmp_path / "debug" / "transcripts.json").read_text(encoding="utf-8") == (
        '{\n  "transcripts": [\n    {\n      "case_id": "case-09",\n      '
        '"final_text": "调试文本"\n    }\n  ]\n}'
    )


def test_replay_case_follows_explicit_protocol(tmp_path):
    wav_path = tmp_path / "case-01.wav"
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(b"\x00\x00" * 1600)
    wav_path.with_suffix(".txt").write_text("测试尾句", encoding="utf-8")

    class FakeWebSocket:
        def __init__(self):
            self.sent = []
            self.incoming = [
                json.dumps({"type": "ready"}),
                json.dumps({"type": "started", "model": "test", "session_id": "s1"}),
                json.dumps({"type": "transcript", "text": "测试", "final": False}),
                json.dumps({"type": "transcript", "text": "测试尾句", "final": True, "segment_id": "seg-1"}),
                json.dumps({"type": "done"}),
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def recv(self):
            return self.incoming.pop(0)

        async def send(self, value):
            self.sent.append(value)

    socket = FakeWebSocket()

    def connect(_url, **_kwargs):
        return socket

    result = asyncio.run(
        replay_case(
            wav_path,
            url="ws://test",
            project_id=1,
            selected_task_id=2,
            connect=connect,
            pace=False,
        )
    )

    assert result["status"] == "done"
    assert result["packet_count"] == 1
    assert json.loads(socket.sent[0])["type"] == "start"
    assert isinstance(socket.sent[1], bytes)
    assert json.loads(socket.sent[2]) == {"type": "stop"}


def test_normalize_cookie_adds_session_cookie_name_to_raw_value():
    assert normalize_cookie("abc123") == "bowei_session=abc123"
    assert normalize_cookie("bowei_session=abc123; other=x") == "bowei_session=abc123; other=x"
