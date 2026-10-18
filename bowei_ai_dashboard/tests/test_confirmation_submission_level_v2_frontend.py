from pathlib import Path


PAGE = (
    Path(__file__).resolve().parents[2]
    / "frontend-v2"
    / "src"
    / "pages"
    / "ConfirmPage.tsx"
)


def test_structured_submission_exposes_safe_whole_report_return():
    source = PAGE.read_text(encoding="utf-8")

    assert "退回整条汇报" in source
    assert "handleDecision('return', submissionReturnNote)" in source
    assert "hasConfirmedTaskCards" in source
    assert "hasAnyPersistedTaskCard" in source
