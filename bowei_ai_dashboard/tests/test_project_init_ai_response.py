import json

import pytest

from app.services.project_init_ai_response import (
    classify_project_init_response,
    normalize_project_init_response,
)


def test_normalize_wrapped_json_aliases_and_defaults():
    raw = """```json
{
  "project_profile": {
    "name": "示例",
    "startDate": "2026-09-01",
    "endDate": "2026-09-30",
    "evidence": [{"file_name": "a.xlsx", "location": "Sheet1!A1"}]
  },
  "tasks": [{
    "title": "任务一",
    "deadline": "2026-09-30",
    "evidence": [{"file_name": "a.xlsx", "location": "Sheet1!A2"}],
    "subtasks": [{"title": "子任务一"}]
  }]
}
```"""

    payload, diagnostics = normalize_project_init_response(raw)

    assert diagnostics == []
    assert payload["project_profile"]["name"] == "示例"
    assert payload["project_profile"]["start_date"] == "2026-09-01"
    assert payload["project_profile"]["end_date"] == "2026-09-30"
    assert payload["tasks"][0]["plan_end"] == "2026-09-30"
    assert payload["tasks"][0]["plan_start"] == ""
    assert payload["tasks"][0]["subtasks"][0]["assignee_name"] == ""


def test_classify_invalid_response_returns_bounded_diagnostics_without_raw_text():
    secret_like = "PRIVATE_MODEL_SOURCE"
    raw = json.dumps({
        "tasks": [{"title": secret_like, "private_field": "should-not-leak"}],
    })

    diagnostics = classify_project_init_response(raw)

    assert diagnostics.code == "schema_invalid"
    assert diagnostics.paths
    assert secret_like not in json.dumps(diagnostics.to_dict(), ensure_ascii=False)
    assert "should-not-leak" not in json.dumps(diagnostics.to_dict(), ensure_ascii=False)
