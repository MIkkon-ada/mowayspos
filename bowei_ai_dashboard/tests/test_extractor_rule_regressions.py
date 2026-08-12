from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.services.extractor import extract_update


def test_rule_extractor_splits_completed_issue_and_next_step_fragments():
    text = (
        "\u672c\u5468\u5b8c\u6210\u4e86\u6570\u636e\u6e05\u6d17\uff0c"
        "\u4f46\u540e\u7eed\u63a5\u53e3\u8054\u8c03\u56e0\u6743\u9650\u95ee\u9898\u53d7\u963b\uff0c"
        "\u4e0b\u5468\u7ee7\u7eed\u3002"
    )

    result = extract_update("text_update", text, submitter="\u6d4b\u8bd5", provider="rules")

    assert any("\u6570\u636e\u6e05\u6d17" in item for item in result["completed_items"])
    assert any("\u63a5\u53e3\u8054\u8c03" in item["description"] for item in result["issues"])
    assert result["next_steps"] == ["\u4e0b\u5468\u7ee7\u7eed"]


def test_rule_extractor_does_not_turn_plain_progress_into_issue():
    result = extract_update(
        "text_update",
        "\u76ee\u524d\u6b63\u5728\u63a8\u8fdb\u6743\u9650\u89c4\u5219\u548c\u6807\u7b7e\u4f53\u7cfb\u3002",
        submitter="\u6d4b\u8bd5",
        provider="rules",
    )

    assert result["issues"] == []
