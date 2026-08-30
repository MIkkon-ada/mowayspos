"""Truthful routing metadata for project-init document analysis."""

from __future__ import annotations

from typing import Any, Iterable


def select_project_init_analysis_route(
    workbook_profiles: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Choose the current text route and explicitly flag lossy layouts.

    The installed project-init capability is text-only.  A complex workbook is
    still parsed to produce a reviewable draft, but it must never be presented
    as equivalent to native-file understanding.
    """

    profiles = list(workbook_profiles)
    unavailable = any(
        "workbook_structure_unavailable" in profile.get("signals", [])
        for profile in profiles
        if isinstance(profile, dict)
    )
    high_risk = any(
        profile.get("risk_level") == "high"
        for profile in profiles
        if isinstance(profile, dict)
    )
    if unavailable:
        return {
            "mode": "text_with_review",
            "review_required": True,
            "reason_codes": ["workbook_structure_unavailable"],
        }
    if high_risk:
        return {
            "mode": "text_with_review",
            "review_required": True,
            "reason_codes": ["complex_workbook_layout"],
        }
    return {
        "mode": "text_structured",
        "review_required": False,
        "reason_codes": [],
    }
