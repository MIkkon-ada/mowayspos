from urllib.parse import parse_qs, urlparse

from app.services import wecom


def test_wecom_silent_auth_url_preserves_callback_url(monkeypatch):
    callback_url = "https://example.com/api/auth/wecom/callback"
    monkeypatch.setenv("WECOM_CORPID", "corp-id")
    monkeypatch.setenv("WECOM_REDIRECT_URI", callback_url)

    url = wecom.build_silent_auth_url()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert params["redirect_uri"] == [callback_url]
