import asyncio

import pytest
from fastapi import HTTPException, UploadFile

from app.routers import updates


class NoWriteDB:
    def add(self, *_args, **_kwargs):
        raise AssertionError("document parsing must not create database rows")

    def commit(self):
        raise AssertionError("document parsing must not commit database rows")


def test_document_text_endpoint_requires_login(monkeypatch):
    def reject(*_args, **_kwargs):
        raise HTTPException(status_code=401, detail="unauthorized")

    monkeypatch.setattr(updates, "require_login", reject)
    file = UploadFile(filename="weekly.docx", file=__import__("io").BytesIO(b"document"))

    with pytest.raises(HTTPException) as error:
        asyncio.run(updates.extract_document_text(file=file, current_user="", db=NoWriteDB()))

    assert error.value.status_code == 401


def test_document_text_endpoint_returns_text_without_creating_submission(monkeypatch):
    monkeypatch.setattr(updates, "require_login", lambda *_args, **_kwargs: "alice")
    monkeypatch.setattr(
        updates,
        "extract_work_report_document_text",
        lambda filename, content: "完成接口联调",
    )
    file = UploadFile(filename="weekly.docx", file=__import__("io").BytesIO(b"document"))

    result = asyncio.run(updates.extract_document_text(file=file, current_user="alice", db=NoWriteDB()))

    assert result == {
        "filename": "weekly.docx",
        "text": "完成接口联调",
        "char_count": 6,
        "source_type": "document",
    }
