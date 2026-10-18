from app.services.policy import can_view_batch


def test_confirmation_batch_does_not_expose_same_name_submission_by_name_alone():
    context = {
        "can_view_all": False,
        "is_ceo": False,
        "person_id": 2,
        "name": "同名人员",
        "legacy_identity_values": set(),
    }

    assert not can_view_batch(context, "同名人员", 4, {}, submitter_id=1)


def test_confirmation_batch_allows_current_person_id_submission():
    context = {
        "can_view_all": False,
        "is_ceo": False,
        "person_id": 2,
        "name": "同名人员",
        "legacy_identity_values": set(),
    }

    assert can_view_batch(context, "同名人员", 4, {}, submitter_id=2)


def test_confirmation_batch_keeps_unique_legacy_submitter_compatibility():
    context = {
        "can_view_all": False,
        "is_ceo": False,
        "person_id": 2,
        "name": "唯一人员",
        "legacy_identity_values": {"唯一人员"},
    }

    assert can_view_batch(context, "唯一人员", 4, {}, submitter_id=None)
