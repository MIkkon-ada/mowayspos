from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.services.meeting_skill_clarification import (
    BlockingClarificationsError,
    append_input_snapshot,
    resume_run,
    start_preflight,
    submit_answers,
)


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_preflight_only_creates_blocking_material_questions_without_minutes_output():
    db = _db()
    run = start_preflight(
        db,
        project_id=1,
        created_by_person_id=None,
        meeting_type="receivables_weekly",
        transcript_text="acceptance and receivables weekly transcript",
        reference_files=[],
    )

    questions = db.query(models.MeetingSkillClarification).filter_by(run_id=run.id).all()
    assert run.status == "waiting_for_answers"
    assert run.output_json == "{}"
    assert len(questions) == 2
    assert all(question.blocking and question.required for question in questions)
    assert all(question.question_kind == "missing_material" for question in questions)


def test_material_snapshot_is_append_only_and_latest_snapshot_can_enter_running():
    db = _db()
    run = start_preflight(
        db,
        project_id=1,
        created_by_person_id=None,
        meeting_type="receivables_weekly",
        transcript_text="acceptance and receivables weekly transcript",
        reference_files=[],
    )
    first_snapshot_id = run.current_input_snapshot_id

    append_input_snapshot(
        db,
        run,
        transcript_text="acceptance and receivables weekly transcript",
        reference_files=[
            {"kind": "acceptance_receivables_ledger", "source_id": "ledger-v1"},
            {"kind": "previous_minutes", "source_id": "minutes-v1"},
        ],
    )

    snapshots = (
        db.query(models.MeetingSkillInputSnapshot)
        .filter_by(run_id=run.id)
        .order_by(models.MeetingSkillInputSnapshot.version)
        .all()
    )
    assert [snapshot.version for snapshot in snapshots] == [1, 2]
    assert snapshots[0].id == first_snapshot_id
    assert run.current_input_snapshot_id == snapshots[1].id
    assert run.status == "running"


def test_resume_requires_blocking_questions_to_be_explicitly_disposed_and_versions_answers():
    db = _db()
    run = start_preflight(
        db,
        project_id=1,
        created_by_person_id=None,
        meeting_type="receivables_weekly",
        transcript_text="acceptance and receivables weekly transcript",
        reference_files=[
            {"kind": "acceptance_receivables_ledger", "source_id": "ledger-v1"},
            {"kind": "previous_minutes", "source_id": "minutes-v1"},
        ],
    )
    question = models.MeetingSkillClarification(
        run_id=run.id,
        input_snapshot_id=run.current_input_snapshot_id,
        code="project_reference_ambiguous",
        question="Which project does reference 422 mean?",
        question_kind="fact_ambiguity",
        blocking=True,
        required=True,
        answer_mode="single_choice",
        allow_omit=True,
        options_json='[{"value":"project-422"}]',
        evidence_json=(
            '[{"source_type":"transcript","source_id":"source-v1",'
            '"locator":"paragraph:3","quote":"project 422"}]'
        ),
    )
    db.add(question)
    db.commit()

    try:
        resume_run(db, run)
        assert False, "expected a blocking clarification error"
    except BlockingClarificationsError:
        pass

    submit_answers(db, run, answers=[{"question_id": question.id, "omit": True}], answered_by_person_id=None)
    submit_answers(db, run, answers=[{"question_id": question.id, "omit": True}], answered_by_person_id=None)
    assert run.status == "running"
    assert run.output_json == "{}"
    result = resume_run(db, run)

    revisions = (
        db.query(models.MeetingSkillClarificationAnswerRevision)
        .filter_by(question_id=question.id)
        .order_by(models.MeetingSkillClarificationAnswerRevision.answer_revision)
        .all()
    )
    facts = db.query(models.MeetingSkillResolvedFact).filter_by(run_id=run.id).all()
    assert [item.answer_revision for item in revisions] == [1, 2]
    assert result.status == "ready_for_review"
    assert len(facts) == 1
    assert facts[0].field_name == "project_reference_ambiguous"
    assert facts[0].value_json == '{"omit": true}'

    submit_answers(db, run, answers=[{"question_id": question.id, "omit": True}], answered_by_person_id=None)
    assert run.status == "running"
    assert run.output_json == "{}"
