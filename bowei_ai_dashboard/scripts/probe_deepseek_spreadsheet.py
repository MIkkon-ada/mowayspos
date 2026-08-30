"""Run a standalone DeepSeek spreadsheet-understanding diagnostic."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import load_local_env

load_local_env()

from app import models
from app.ai.adapters import DefaultAIAdapters
from app.ai.service import AIService
from app.database import SessionLocal
from app.services.deepseek_spreadsheet_probe import (
    ProbeRunner,
    build_text_completion,
    build_workbook_evidence,
)


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DeepSeek spreadsheet diagnostic")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--mode", choices=("a", "b", "all"), default="all")
    parser.add_argument("--output-dir", type=Path, default=Path("tmp/deepseek-probe"))
    parser.add_argument("--max-sheets", type=int, default=12)
    parser.add_argument("--max-cells", type=int, default=5_000)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _result_payload(result) -> dict:
    payload = asdict(result)
    if result.output is not None:
        payload["output"] = result.output.model_dump(mode="json")
    return payload


def _configured_deepseek_model(db):
    return (
        db.query(models.AIModel)
        .join(models.AIModelCredential, models.AIModelCredential.model_id == models.AIModel.id)
        .filter(
            models.AIModel.provider == "deepseek",
            models.AIModel.model_type == "chat",
            models.AIModel.enabled.is_(True),
            models.AIModelCredential.encrypted_api_key != "",
        )
        .order_by(models.AIModel.id)
        .first()
    )


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    if not args.input.is_file():
        print("输入工作簿不可读取。")
        return 2
    try:
        evidence = build_workbook_evidence(
            args.input,
            args.input.name,
            max_sheets=args.max_sheets,
            max_cells=args.max_cells,
        )
    except Exception:
        print("工作簿解析失败，未发送任何外部请求。")
        return 2

    planned = ["deepseek-v4-flash", "deepseek-v4-pro"] if args.mode in {"a", "all"} else []
    if args.mode in {"b", "all"}:
        planned.append("deepseek-v4-flash-vision-exp")
    if args.dry_run:
        print("计划模型：" + " -> ".join(planned))
        print("干跑完成；未发送外部请求。")
        return 0
    if args.mode not in {"a", "all"}:
        print("视觉探针尚未启用；未发送外部请求。")
        return 0

    with SessionLocal() as db:
        model = _configured_deepseek_model(db)
        if model is None:
            print("未找到可用的 DeepSeek 聊天模型凭据。")
            return 3
        try:
            service = AIService(db)
            completion = build_text_completion(
                model,
                credential_reader=service._credential,
                adapter=lambda target, key, prompt: DefaultAIAdapters().complete_chat(
                    target, key, prompt, timeout_seconds=60
                ),
            )
        except Exception:
            print("无法读取受控 DeepSeek 凭据。")
            return 3
        results = ProbeRunner(complete_text=completion).run_text(evidence)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "input_sha256": evidence.input_sha256,
                "results": [_result_payload(result) for result in results],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("结果已写入：" + str(summary_path))
    print("状态：" + ", ".join(f"{item.model_name}={item.status}" for item in results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
