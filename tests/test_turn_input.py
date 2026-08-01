"""Tests for the TurnInput 1.0.0 contract."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import ai_assistant.contracts as contracts
from ai_assistant.contracts import AttachmentRef, TurnInput

TEHRAN = timezone(timedelta(hours=3, minutes=30))
RECEIVED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN)
REQUEST_ID = "11111111-1111-4111-8111-111111111111"
MESSAGE_ID = "22222222-2222-4222-8222-222222222222"
CONVERSATION_ID = "33333333-3333-4333-8333-333333333333"
IDEMPOTENCY_KEY = "44444444-4444-4444-8444-444444444444"
UUID1_VALUE = "11111111-1111-1111-8111-111111111111"
IDENTIFIER_FIELDS = ("request_id", "message_id", "conversation_id", "idempotency_key")
PERSIAN_MESSAGE = "\u06af\u0632\u0627\u0631\u0634 \u0641\u0646\u06cc \u06f1\u06f2\u06f3"
FORBIDDEN_FIELDS = (
    "role",
    "roles",
    "permission",
    "permissions",
    "scope",
    "scopes",
    "token",
    "secret",
    "security_context",
    "normalized_query",
    "attachment_url",
    "filesystem_path",
)
SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "turn-input" / "1.0.0.schema.json"
)


def payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "request_id": REQUEST_ID,
        "message_id": MESSAGE_ID,
        "conversation_id": CONVERSATION_ID,
        "raw_message": PERSIAN_MESSAGE,
        "received_at": "2026-01-01T12:00:00+03:30",
        "idempotency_key": IDEMPOTENCY_KEY,
    }
    values.update(overrides)
    return values


def attachment(index: int, version: int = 1) -> dict[str, object]:
    return {
        "attachment_id": f"{index:08x}-0000-4000-8000-000000000000",
        "version": version,
    }


def test_schema_version_defaults_to_the_approved_value() -> None:
    assert TurnInput(**payload()).schema_version == "1.0.0"


def test_other_schema_versions_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(schema_version="1.1.0"))


def test_valid_turn_input_is_constructed() -> None:
    turn = TurnInput(**payload(attachments=[attachment(1)]))
    assert turn.request_id == UUID(REQUEST_ID)
    assert turn.locale == "fa-IR"
    assert turn.channel == "web"
    assert turn.received_at == datetime(2026, 1, 1, 8, 30, tzinfo=UTC)
    assert turn.attachments[0].version == 1


@pytest.mark.parametrize("field", IDENTIFIER_FIELDS)
def test_identifier_fields_require_uuid_version_4(field: str) -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(**{field: UUID1_VALUE}))


def test_empty_raw_message_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(raw_message=""))


def test_whitespace_only_raw_message_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(raw_message="   \t\n "))


def test_raw_message_with_nul_character_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(raw_message="salam\x00"))


def test_surrounding_whitespace_is_preserved() -> None:
    message = "  hello  "
    assert TurnInput(**payload(raw_message=message)).raw_message == message


def test_newlines_and_tabs_are_preserved() -> None:
    message = "line one\n\tline two\n"
    assert TurnInput(**payload(raw_message=message)).raw_message == message


def test_persian_text_is_preserved_exactly() -> None:
    assert TurnInput(**payload()).raw_message == PERSIAN_MESSAGE


def test_maximum_length_raw_message_is_accepted() -> None:
    message = "a" * 32000
    assert TurnInput(**payload(raw_message=message)).raw_message == message


def test_oversized_raw_message_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(raw_message="a" * 32001))


def test_missing_attachments_becomes_an_empty_tuple() -> None:
    assert TurnInput(**payload()).attachments == ()


def test_null_attachments_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(attachments=None))


def test_single_attachment_is_accepted() -> None:
    assert len(TurnInput(**payload(attachments=[attachment(1)])).attachments) == 1


def test_ten_attachments_are_accepted() -> None:
    items = [attachment(index) for index in range(10)]
    assert len(TurnInput(**payload(attachments=items)).attachments) == 10


def test_eleven_attachments_are_rejected() -> None:
    items = [attachment(index) for index in range(11)]
    with pytest.raises(ValidationError):
        TurnInput(**payload(attachments=items))


def test_duplicate_attachment_identifiers_are_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(attachments=[attachment(1), attachment(1, version=2)]))


def test_attachment_order_is_preserved() -> None:
    items = [attachment(index) for index in (3, 1, 2)]
    turn = TurnInput(**payload(attachments=items))
    assert [str(item.attachment_id) for item in turn.attachments] == [
        item["attachment_id"] for item in items
    ]


@pytest.mark.parametrize("version", [0, -1])
def test_attachment_version_must_be_positive(version: int) -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(attachments=[attachment(1, version=version)]))


@pytest.mark.parametrize("field", ["attachment_url", "filesystem_path", "token", "filename"])
def test_attachment_ref_rejects_location_and_credential_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        AttachmentRef(**{**attachment(1), field: "value"})


@pytest.mark.parametrize("field", FORBIDDEN_FIELDS)
def test_security_related_field_injection_is_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(**{field: "injected"}))


def test_unsupported_locale_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(locale="en-US"))


def test_unsupported_channel_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(channel="sms"))


def test_naive_received_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(received_at=datetime(2026, 1, 1, 12, 0, 0)))


def test_non_utc_received_at_is_normalized() -> None:
    turn = TurnInput(**payload(received_at=RECEIVED_AT))
    assert turn.received_at.utcoffset() == timedelta(0)
    assert turn.received_at == RECEIVED_AT


def test_json_round_trip_preserves_the_payload() -> None:
    turn = TurnInput(**payload(attachments=[attachment(1), attachment(2)]))
    assert TurnInput.model_validate_json(turn.model_dump_json()) == turn


def test_attachments_are_an_immutable_tuple() -> None:
    turn = TurnInput(**payload(attachments=[attachment(1)]))
    assert isinstance(turn.attachments, tuple)
    with pytest.raises(ValidationError):
        turn.raw_message = "changed"


def test_root_schema_rejects_additional_properties() -> None:
    assert TurnInput.model_json_schema()["additionalProperties"] is False


def test_attachment_ref_schema_rejects_additional_properties() -> None:
    assert AttachmentRef.model_json_schema()["additionalProperties"] is False


def test_schema_declares_the_approved_dialect() -> None:
    schema = TurnInput.model_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_declares_the_approved_identifier() -> None:
    schema = TurnInput.model_json_schema()
    assert schema["$id"] == "urn:ai-assistant:contracts:turn-input:1.0.0"


def test_committed_schema_artifact_matches_the_model() -> None:
    committed = json.loads(SCHEMA_ARTIFACT.read_text(encoding="utf-8"))
    assert committed == TurnInput.model_json_schema()


def test_turn_input_public_exports_are_available() -> None:
    assert {"AttachmentRef", "TurnInput"} <= set(contracts.__all__)


def test_no_forbidden_field_appears_in_the_schema() -> None:
    schema = json.dumps(TurnInput.model_json_schema())
    assert all(f'"{field}"' not in schema for field in FORBIDDEN_FIELDS)


@given(
    st.text(
        alphabet=st.characters(exclude_characters="\x00", exclude_categories=("Cs",)),
        max_size=32,
    )
)
def test_property_nonblank_messages_round_trip_unchanged(suffix: str) -> None:
    message = f"\u0645{suffix}"
    turn = TurnInput(**payload(raw_message=message))
    assert turn.raw_message == message
    assert TurnInput.model_validate_json(turn.model_dump_json()).raw_message == message


@given(st.lists(st.uuids(version=4), min_size=0, max_size=10, unique=True))
def test_property_attachment_order_is_preserved(identifiers: list[UUID]) -> None:
    items = [{"attachment_id": str(value), "version": 1} for value in identifiers]
    turn = TurnInput(**payload(attachments=items))
    assert [item.attachment_id for item in turn.attachments] == identifiers


@given(st.sampled_from(FORBIDDEN_FIELDS))
def test_property_unknown_security_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        TurnInput(**payload(**{field: "injected"}))
