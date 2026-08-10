from app.services import wecom


def test_send_text_message_ignores_empty_recipients(monkeypatch):
    monkeypatch.setattr(wecom, "get_access_token", lambda: "token")
    assert wecom.send_text_message([], "提醒") is False
