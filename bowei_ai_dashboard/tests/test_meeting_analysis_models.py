from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app import models
from app import schemas
from app.database import Base


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_transcript_source_revision_run_and_candidate_can_be_persisted():
    db = make_session()
    project = models.Project(name="Audit project")
    meeting = models.Meeting(project_id=1, transcript_text="latest projection")
    db.add_all([project, meeting])
    db.flush()

    source = models.MeetingTranscriptSource(
        meeting_id=meeting.id,
        raw_text="immutable source",
        source_hash="a" * 64,
    )
    db.add(source)
    db.flush()
    transcript_revision = models.MeetingTranscriptRevision(
        source_id=source.id,
        revision_no=1,
        text="corrected immutable source",
        text_hash="b" * 64,
    )
    db.add(transcript_revision)
    db.flush()
    run = models.MeetingAnalysisRun(
        project_id=project.id,
        meeting_id=meeting.id,
        source_id=source.id,
        transcript_revision_id=transcript_revision.id,
        reference_at=datetime(2026, 8, 3, 9, 0, 0),
    )
    db.add(run)
    db.flush()
    candidate = models.MeetingAnalysisCandidate(
        run_id=run.id,
        candidate_type="decision",
    )
    db.add(candidate)
    db.commit()

    assert source.source_type == "manual"
    assert transcript_revision.text == "corrected immutable source"
    assert run.status == "review"
    assert candidate.review_status == "pending"


def test_transcript_revision_number_is_unique_within_source():
    db = make_session()
    source = models.MeetingTranscriptSource(raw_text="source", source_hash="a" * 64)
    db.add(source)
    db.flush()
    db.add_all(
        [
            models.MeetingTranscriptRevision(
                source_id=source.id,
                revision_no=1,
                text="first",
                text_hash="b" * 64,
            ),
            models.MeetingTranscriptRevision(
                source_id=source.id,
                revision_no=1,
                text="duplicate",
                text_hash="c" * 64,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        db.commit()


def test_meeting_revision_can_link_transcript_and_analysis_provenance():
    db = make_session()
    project = models.Project(name="Provenance project")
    meeting = models.Meeting(project_id=1, transcript_text="latest projection")
    db.add_all([project, meeting])
    db.flush()
    source = models.MeetingTranscriptSource(
        meeting_id=meeting.id,
        raw_text="source",
        source_hash="a" * 64,
    )
    db.add(source)
    db.flush()
    transcript_revision = models.MeetingTranscriptRevision(
        source_id=source.id,
        revision_no=1,
        text="revision",
        text_hash="b" * 64,
    )
    db.add(transcript_revision)
    db.flush()
    run = models.MeetingAnalysisRun(
        project_id=project.id,
        meeting_id=meeting.id,
        source_id=source.id,
        transcript_revision_id=transcript_revision.id,
        reference_at=datetime(2026, 8, 3, 9, 0, 0),
    )
    db.add(run)
    db.flush()
    parent = models.MeetingRevision(meeting_id=meeting.id, version_no=1)
    db.add(parent)
    db.flush()
    revision = models.MeetingRevision(
        meeting_id=meeting.id,
        version_no=2,
        transcript_source_id=source.id,
        transcript_revision_id=transcript_revision.id,
        analysis_run_id=run.id,
        parent_revision_id=parent.id,
        revision_kind="agent_review",
        agent_output_json='{"summary": "agent"}',
        validation_output_json='{"valid": true}',
        human_output_json='{"summary": "human"}',
        human_diff_json='{"summary": "edited"}',
    )
    db.add(revision)
    db.commit()

    assert revision.transcript_source_id == source.id
    assert revision.transcript_revision_id == transcript_revision.id
    assert revision.analysis_run_id == run.id
    assert revision.parent_revision_id == parent.id
    assert revision.revision_kind == "agent_review"
    assert revision.human_diff_json == '{"summary": "edited"}'


def test_analysis_response_contracts_parse_orm_json_into_typed_values():
    db = make_session()
    project = models.Project(name="Schema project")
    source = models.MeetingTranscriptSource(raw_text="source", source_hash="a" * 64)
    db.add_all([project, source])
    db.flush()
    transcript_revision = models.MeetingTranscriptRevision(
        source_id=source.id,
        revision_no=1,
        text="revision",
        text_hash="b" * 64,
    )
    db.add(transcript_revision)
    db.flush()
    run = models.MeetingAnalysisRun(
        project_id=project.id,
        source_id=source.id,
        transcript_revision_id=transcript_revision.id,
        member_snapshot_json='{"member_ids": [1]}',
        reference_at=datetime(2026, 8, 3, 9, 0, 0),
    )
    db.add(run)
    db.flush()
    candidate = models.MeetingAnalysisCandidate(
        run_id=run.id,
        candidate_type="decision",
        evidence_json=(
            '[{"source_id": 1, "transcript_revision_id": 1, "char_start": 0, '
            '"char_end": 6, "quote": "source", "source_hash": "' + "a" * 64 + '"}]'
        ),
    )
    db.add(candidate)
    db.commit()

    run_response = schemas.MeetingAnalysisRunResponse.model_validate(run)
    candidate_response = schemas.MeetingAnalysisCandidateResponse.model_validate(candidate)
    revision_response = schemas.MeetingTranscriptRevisionResponse.model_validate(transcript_revision)
    review_payload = schemas.CandidateReviewPayload(review_status="accepted")

    assert run_response.member_snapshot_json == {"member_ids": [1]}
    assert candidate_response.evidence_json[0].quote == "source"
    assert revision_response.text_hash == "b" * 64
    assert review_payload.final_value == {}
