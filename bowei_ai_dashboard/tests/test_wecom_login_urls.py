from urllib.parse import parse_qs, urlparse

from app.services import wecom


def test_wecom_qrcode_url_uses_web_authorization_qrconnect(monkeypatch):
    monkeypatch.setenv("WECOM_CORPID", "corp-id")
    monkeypatch.setenv("WECOM_AGENT_ID", "100001")
    monkeypatch.setenv("WECOM_SECRET", "secret")
    monkeypatch.setenv("WECOM_REDIRECT_URI", "https://example.com/api/auth/wecom/callback")

    url = wecom.build_qrcode_url(state="state-123")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "open.work.weixin.qq.com"
    assert parsed.path == "/wwopen/sso/qrConnect"
    assert params["appid"] == ["corp-id"]
    assert params["agentid"] == ["100001"]
    assert params["redirect_uri"] == ["https://example.com/api/auth/wecom/callback"]
    assert params["state"] == ["state-123"]
