import json
from pathlib import Path

from app.ai.service import ChatResult
from app.services.project_init_vision_analysis import generate_project_init_vision_draft


class FakeVisionService:
    def __init__(self) -> None:
        self.calls = []

    def invoke_project_init_vision(self, images, prompt, context):
        self.calls.append((list(images), prompt, context))
        return ChatResult(
            text=json.dumps(
                {
                    "tasks": [
                        {
                            "title": "复杂版式任务",
                            "description": "",
                            "owner_name": "",
                            "priority": "",
                            "status": "进行中",
                            "plan_start": "",
                            "plan_end": "",
                            "evidence": [
                                {
                                    "attachment_id": 8,
                                    "file_name": "复杂表.xlsx",
                                    "location": "'推进表'!A1:J30",
                                }
                            ],
                            "subtasks": [
                                {
                                    "title": "确认版式层级",
                                    "description": "",
                                    "assignee_name": "",
                                    "helper_names": [],
                                    "priority": "",
                                    "status": "进行中",
                                    "plan_start": "",
                                    "plan_end": "",
                                    "evaluation_standard": "",
                                    "evidence": [
                                        {
                                            "attachment_id": 8,
                                            "file_name": "复杂表.xlsx",
                                            "location": "'推进表'!A1:J30",
                                        }
                                    ],
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
            model_code="deepseek-vision",
            invocation_log_id=11,
        )


def test_vision_analysis_uses_images_and_existing_evidence_validation(tmp_path):
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"png")
    service = FakeVisionService()

    result = generate_project_init_vision_draft(
        [image_path],
        [
            {
                "attachment_id": 8,
                "file_name": "复杂表.xlsx",
                "location": "'推进表'!A1:J30",
                "text": "合并单元格中的工作安排",
            }
        ],
        [],
        [],
        ai_service=service,
    )

    assert result.model_name == "deepseek-vision"
    assert result.provider == "deepseek-vision"
    assert result.tasks[0].title == "复杂版式任务"
    assert service.calls[0][0] == [image_path]
    assert "合并单元格中的工作安排" in service.calls[0][1]
