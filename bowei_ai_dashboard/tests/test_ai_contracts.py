import pytest

from app.ai.contracts import Capability, ModelType, classify_retryable_error


def test_capability_registry_requires_chat_for_meeting_and_asr_for_speech():
    assert Capability.required_model_type("meeting.analysis") is ModelType.CHAT
    assert Capability.required_model_type("speech.realtime") is ModelType.ASR
    with pytest.raises(ValueError, match="unsupported AI capability"):
        Capability.required_model_type("unknown.capability")


@pytest.mark.parametrize(
    ("status", "retryable"),
    [(408, True), (429, True), (500, True), (503, True), (400, False), (401, False), (422, False)],
)
def test_retry_classifier_only_retries_transient_upstream_statuses(status, retryable):
    assert classify_retryable_error(status_code=status) is retryable


def test_retry_classifier_treats_network_failures_as_retryable():
    assert classify_retryable_error(status_code=None) is True
