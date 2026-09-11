from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.api_errors import CodedHTTPException, coded_http_exception_handler
from app.database import Base
from app.permissions import require_login


def _make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_coded_http_exception_keeps_detail_and_adds_code():
    app = FastAPI()
    app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)

    @app.get("/denied")
    def denied():
        raise CodedHTTPException(403, "PROJECT_ACTION_DENIED", "仅公司管理或超级管理员可执行此操作")

    response = TestClient(app).get("/denied")

    assert response.status_code == 403
    assert response.json() == {
        "detail": "仅公司管理或超级管理员可执行此操作",
        "code": "PROJECT_ACTION_DENIED",
    }


@pytest.mark.parametrize(
    ("username", "status_code", "code", "detail"),
    [
        ("missing-account", 401, "AUTHENTICATION_REQUIRED", "unauthorized"),
        ("disabled-account", 403, "ACCOUNT_DISABLED", "account_disabled"),
    ],
)
def test_account_identity_errors_use_stable_codes(username, status_code, code, detail):
    db = _make_session()
    if username == "disabled-account":
        db.add(models.Account(username=username, password_hash="x", status="disabled"))
        db.commit()

    with pytest.raises(CodedHTTPException) as exc:
        require_login(username, db)

    assert (exc.value.status_code, exc.value.code, exc.value.detail) == (status_code, code, detail)
