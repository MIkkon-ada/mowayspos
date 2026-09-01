from app.settings import _parse_allowed_origins


def test_default_allowed_origins_include_the_local_frontend_port():
    assert "http://127.0.0.1:6004" in _parse_allowed_origins(None)
