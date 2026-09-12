from __future__ import annotations

import warnings

from sqlalchemy.exc import SAWarning

from app import models  # noqa: F401
from app.database import Base


def test_metadata_has_no_meeting_document_source_foreign_key_cycle():
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", SAWarning)
        Base.metadata.sorted_tables

    assert not any(
        "meeting_document_sources" in str(warning.message)
        and "meetings" in str(warning.message)
        for warning in captured
    )
