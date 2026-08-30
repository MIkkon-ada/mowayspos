from app.services.project_init_analysis_routing import select_project_init_analysis_route


def test_simple_sources_use_structured_text_route():
    route = select_project_init_analysis_route([
        {"risk_level": "low", "signals": [], "summary": {}},
        {"risk_level": "medium", "signals": ["formulas"], "summary": {}},
    ])

    assert route == {
        "mode": "text_structured",
        "review_required": False,
        "reason_codes": [],
    }


def test_complex_workbook_requires_review_when_only_text_model_is_available():
    route = select_project_init_analysis_route([
        {
            "risk_level": "high",
            "signals": ["hidden_sheets", "merged_cells"],
            "summary": {},
        },
    ])

    assert route == {
        "mode": "text_with_review",
        "review_required": True,
        "reason_codes": ["complex_workbook_layout"],
    }


def test_uninspectable_workbook_requires_review():
    route = select_project_init_analysis_route([
        {
            "risk_level": "high",
            "signals": ["workbook_structure_unavailable"],
            "summary": {},
        },
    ])

    assert route["mode"] == "text_with_review"
    assert route["review_required"] is True
    assert route["reason_codes"] == ["workbook_structure_unavailable"]
