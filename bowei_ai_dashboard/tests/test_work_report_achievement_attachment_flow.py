"""Contracts for evidence selected on AI work-report achievements."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ATTACHMENTS = ROOT / "bowei_ai_dashboard" / "app" / "routers" / "achievement_attachments.py"
CONFIRMATIONS = ROOT / "bowei_ai_dashboard" / "app" / "routers" / "confirmations.py"


def test_work_report_attachments_can_be_uploaded_unbound_then_transferred_on_confirmation():
    upload_source = ATTACHMENTS.read_text(encoding="utf-8")
    confirmation_source = CONFIRMATIONS.read_text(encoding="utf-8")
    assert "exactly one achievement target is required" not in upload_source
    assert "attachment_ids" in confirmation_source
    assert "attachment.achievement_id = ach.id" in confirmation_source
