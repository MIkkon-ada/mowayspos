from __future__ import annotations


def test_retired_confidence_setting_is_removed_from_platform_payloads():
    from app.routers.platform_settings import _without_retired_settings

    source = {"platform_name": "测试平台", "confidence": 75}

    assert _without_retired_settings(source) == {"platform_name": "测试平台"}
    assert source["confidence"] == 75
