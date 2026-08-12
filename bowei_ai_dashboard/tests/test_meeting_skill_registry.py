from app.services.meeting_skill_registry import SkillPreflightInput, preflight_skill, route_meeting_skill


def test_weekly_receivables_skill_requires_its_source_materials():
    skill = route_meeting_skill("receivables_weekly")

    result = preflight_skill(
        skill,
        SkillPreflightInput(
            transcript_text="本周验收与回款进展会议转写",
            reference_files=[],
        ),
    )

    assert skill is not None
    assert skill.name == "weekly-meeting-minutes"
    assert result.can_run is False
    assert {question.code for question in result.questions} == {
        "acceptance_receivables_ledger_missing",
        "previous_minutes_missing",
    }
    assert all(question.question_kind == "missing_material" for question in result.questions)
    assert all(question.blocking and question.required for question in result.questions)
    assert all(question.action == "material_upload" for question in result.questions)


def test_weekly_receivables_skill_runs_without_questions_when_materials_are_present():
    skill = route_meeting_skill("receivables_weekly")
    result = preflight_skill(
        skill,
        SkillPreflightInput(
            transcript_text="本周验收与回款进展会议转写",
            reference_files=[
                {"kind": "acceptance_receivables_ledger", "source_id": "ledger-v1"},
                {"kind": "previous_minutes", "source_id": "minutes-v5"},
            ],
        ),
    )

    assert result.can_run is True
    assert result.questions == []


def test_project_weekly_meeting_routes_to_weekly_minutes_skill():
    skill = route_meeting_skill("regular")

    assert skill is not None
    assert skill.name == "weekly-meeting-minutes"


def test_receivables_signals_route_to_weekly_skill_without_adding_a_seventh_meeting_type():
    skill = route_meeting_skill("regular", "acceptance and receivables status update")

    assert skill is not None
    assert skill.name == "weekly-meeting-minutes"
