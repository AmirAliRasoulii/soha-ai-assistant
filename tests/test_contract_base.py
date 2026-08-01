from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ai_assistant.contracts import ContractModel, SchemaVersion, UtcDateTime

TEHRAN = timezone(timedelta(hours=3, minutes=30))


class SampleContract(ContractModel):
    label: str
    version: SchemaVersion = "1.0.0"


class SampleEvent(ContractModel):
    occurred_at: UtcDateTime


class BrokenDefaultContract(ContractModel):
    version: SchemaVersion = "1.0"


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SampleContract(label="a", unexpected="b")


def test_model_is_immutable() -> None:
    contract = SampleContract(label="a")
    with pytest.raises(ValidationError):
        contract.label = "b"


def test_default_values_are_validated() -> None:
    with pytest.raises(ValidationError):
        BrokenDefaultContract()


def test_strings_are_not_trimmed() -> None:
    contract = SampleContract(label="  spaced value \t")
    assert contract.label == "  spaced value \t"


def test_persian_text_is_preserved() -> None:
    persian = "\u06af\u0632\u0627\u0631\u0634 \u0641\u0646\u06cc \u06f1\u06f2\u06f3"
    contract = SampleContract(label=persian)
    assert contract.label == persian
    assert contract.model_dump()["label"] == persian


@pytest.mark.parametrize("version", ["0.1.0", "1.0.0", "12.4.37"])
def test_valid_schema_versions_are_accepted(version: str) -> None:
    assert SampleContract(label="a", version=version).version == version


@pytest.mark.parametrize(
    "version",
    ["1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0", "1.0.0+build", "1.0.0.0", ""],
)
def test_invalid_schema_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValidationError):
        SampleContract(label="a", version=version)


def test_schema_version_rejects_oversized_value() -> None:
    with pytest.raises(ValidationError):
        SampleContract(label="a", version="1." + "0" * 40 + ".0")


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SampleEvent(occurred_at=datetime(2026, 1, 1, 12, 0, 0))


def test_naive_datetime_string_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SampleEvent.model_validate({"occurred_at": "2026-01-01T12:00:00"})


def test_utc_datetime_remains_utc() -> None:
    moment = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    event = SampleEvent(occurred_at=moment)
    assert event.occurred_at.utcoffset() == timedelta(0)
    assert event.occurred_at == moment


def test_non_utc_datetime_is_converted_to_utc() -> None:
    event = SampleEvent(occurred_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN))
    assert event.occurred_at.utcoffset() == timedelta(0)
    assert event.occurred_at.hour == 8
    assert event.occurred_at.minute == 30


def test_conversion_preserves_the_same_instant() -> None:
    original = datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN)
    event = SampleEvent(occurred_at=original)
    assert event.occurred_at == original
    assert event.occurred_at.timestamp() == original.timestamp()


def test_json_datetime_string_is_parsed() -> None:
    event = SampleEvent.model_validate_json('{"occurred_at": "2026-01-01T12:00:00+03:30"}')
    assert event.occurred_at == datetime(2026, 1, 1, 8, 30, 0, tzinfo=UTC)


def test_serialized_datetime_includes_timezone() -> None:
    event = SampleEvent(occurred_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN))
    serialized = event.model_dump(mode="json")["occurred_at"]
    parsed = datetime.fromisoformat(serialized)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timedelta(0)
    assert parsed == event.occurred_at


def test_json_schema_rejects_additional_properties() -> None:
    assert SampleContract.model_json_schema()["additionalProperties"] is False


def test_base_model_declares_no_business_fields() -> None:
    assert ContractModel.model_fields == {}
