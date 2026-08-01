"""Tests for the AI Core error envelope contract, schema version 1.0.0."""

import json
import unittest
from pathlib import Path
from typing import get_args
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.errors import DomainError, ErrorCode, ErrorEnvelope

ERROR_ID = "11111111-1111-4111-8111-111111111111"
CORRELATION_ID = "22222222-2222-4222-8222-222222222222"
DETAIL_REF = "33333333-3333-4333-8333-333333333333"
UUID1_VALUE = "44444444-4444-1444-8444-444444444444"

ERROR_CODES: tuple[str, ...] = get_args(ErrorCode)
RETRYABLE_CODES: tuple[str, ...] = (
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
)
NON_RETRYABLE_CODES: tuple[str, ...] = tuple(
    code for code in ERROR_CODES if code not in RETRYABLE_CODES
)

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "message",
    "safe_message",
    "exception",
    "exception_type",
    "stack_trace",
    "traceback",
    "cause",
    "debug",
    "raw_error",
    "raw_response",
    "provider_response",
    "provider_error",
    "sql",
    "query",
    "system_prompt",
    "prompt",
    "api_key",
    "access_token",
    "token",
    "secret",
    "password",
    "credentials",
    "http_status",
    "headers",
    "type",
    "title",
    "detail",
    "instance",
    "endpoint",
    "url",
    "filesystem_path",
    "email",
    "user_name",
)
HTTP_FIELDS: tuple[str, ...] = (
    "http_status",
    "status",
    "title",
    "detail",
    "instance",
    "headers",
    "retry_after",
)
FORBIDDEN_ENVELOPE_FIELDS: tuple[str, ...] = (
    "occurred_at",
    "request_id",
    "run_id",
    "trace_id",
    "metadata",
    "context",
    "attributes",
)

SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "error-envelope" / "1.0.0.schema.json"
)
# Names that never occur as JSON Schema keywords, so a raw text scan is safe.
SCANNABLE_FORBIDDEN_NAMES: tuple[str, ...] = (
    "stack_trace",
    "traceback",
    "raw_error",
    "raw_response",
    "provider_response",
    "provider_error",
    "system_prompt",
    "api_key",
    "access_token",
    "credentials",
    "http_status",
    "instance",
    "filesystem_path",
    "user_name",
    "occurred_at",
    "request_id",
    "run_id",
    "trace_id",
    "retry_after",
)


def error_payload(code: str = "INVALID_INPUT") -> dict[str, object]:
    return {
        "code": code,
        "safe_message_key": f"error.{code.lower()}",
        "retryable": code in RETRYABLE_CODES,
        "internal_detail_ref": DETAIL_REF,
    }


def envelope_payload(code: str = "INVALID_INPUT") -> dict[str, object]:
    return {
        "error_id": ERROR_ID,
        "correlation_id": CORRELATION_ID,
        "error": error_payload(code),
    }


class SchemaVersionTests(unittest.TestCase):
    def test_default_schema_version_is_exact(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload())
        self.assertEqual(envelope.schema_version, "1.0.0")

    def test_other_schema_version_is_rejected(self) -> None:
        for value in ("1.0.1", "1.1.0", "2.0.0", "1.0"):
            with self.subTest(value=value):
                payload = envelope_payload()
                payload["schema_version"] = value
                with self.assertRaises(ValidationError):
                    ErrorEnvelope.model_validate(payload)


class ErrorCodeTests(unittest.TestCase):
    def test_catalog_contains_exactly_the_approved_codes(self) -> None:
        self.assertEqual(
            set(ERROR_CODES),
            {
                "INVALID_INPUT",
                "UNAUTHENTICATED",
                "UNAUTHORIZED",
                "AMBIGUOUS_REQUEST",
                "POLICY_REJECTED",
                "NO_EVIDENCE",
                "CONFLICTING_EVIDENCE",
                "SCHEMA_INVALID",
                "DEPENDENCY_TIMEOUT",
                "TRANSIENT_DEPENDENCY",
                "BUDGET_EXCEEDED",
                "RATE_LIMITED",
                "CAPACITY_REJECTED",
                "INTERNAL_ERROR",
            },
        )

    def test_every_approved_code_is_accepted(self) -> None:
        for code in ERROR_CODES:
            with self.subTest(code=code):
                envelope = ErrorEnvelope.model_validate(envelope_payload(code))
                self.assertEqual(envelope.error.code, code)

    def test_unknown_code_is_rejected(self) -> None:
        for value in ("CUSTOM_ERROR", "invalid_input", "PROVIDER_ERROR", "", "INTERNAL"):
            with self.subTest(value=value):
                payload = error_payload()
                payload["code"] = value
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)


class IdentifierTests(unittest.TestCase):
    def test_error_id_requires_uuid4(self) -> None:
        payload = envelope_payload()
        payload["error_id"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            ErrorEnvelope.model_validate(payload)

    def test_correlation_id_requires_uuid4(self) -> None:
        payload = envelope_payload()
        payload["correlation_id"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            ErrorEnvelope.model_validate(payload)

    def test_internal_detail_ref_requires_uuid4(self) -> None:
        payload = error_payload()
        payload["internal_detail_ref"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_malformed_identifiers_are_rejected(self) -> None:
        for value in ("not-a-uuid", "", "33333333333333333333333333333333333"):
            with self.subTest(value=value):
                payload = envelope_payload()
                payload["error_id"] = value
                with self.assertRaises(ValidationError):
                    ErrorEnvelope.model_validate(payload)

    def test_missing_internal_detail_ref_is_rejected(self) -> None:
        payload = error_payload()
        del payload["internal_detail_ref"]
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_null_internal_detail_ref_is_rejected(self) -> None:
        payload = error_payload()
        payload["internal_detail_ref"] = None
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_identifiers_are_preserved(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload())
        self.assertEqual(envelope.error_id, UUID(ERROR_ID))
        self.assertEqual(envelope.correlation_id, UUID(CORRELATION_ID))
        self.assertEqual(envelope.error.internal_detail_ref, UUID(DETAIL_REF))


class SafeMessageKeyTests(unittest.TestCase):
    def test_exact_key_accepted_for_every_code(self) -> None:
        for code in ERROR_CODES:
            with self.subTest(code=code):
                error = DomainError.model_validate(error_payload(code))
                self.assertEqual(error.safe_message_key, f"error.{code.lower()}")

    def test_mismatched_key_is_rejected(self) -> None:
        payload = error_payload("INVALID_INPUT")
        payload["safe_message_key"] = "error.no_evidence"
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_uppercase_key_is_rejected(self) -> None:
        for value in ("error.INVALID_INPUT", "ERROR.invalid_input", "Error.invalid_input"):
            with self.subTest(value=value):
                payload = error_payload()
                payload["safe_message_key"] = value
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_whitespace_padded_key_is_rejected(self) -> None:
        for value in (" error.invalid_input", "error.invalid_input ", "error.invalid input"):
            with self.subTest(value=value):
                payload = error_payload()
                payload["safe_message_key"] = value
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_nul_containing_key_is_rejected(self) -> None:
        payload = error_payload()
        payload["safe_message_key"] = "error.invalid_input\x00"
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_oversized_key_is_rejected(self) -> None:
        payload = error_payload()
        payload["safe_message_key"] = "error." + ("a" * 200)
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_empty_or_unprefixed_key_is_rejected(self) -> None:
        for value in ("", "invalid_input", "errors.invalid_input", "error:invalid_input"):
            with self.subTest(value=value):
                payload = error_payload()
                payload["safe_message_key"] = value
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_missing_key_is_rejected(self) -> None:
        payload = error_payload()
        del payload["safe_message_key"]
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)


class RetryabilityTests(unittest.TestCase):
    def test_retryable_true_accepted_for_retryable_codes(self) -> None:
        for code in RETRYABLE_CODES:
            with self.subTest(code=code):
                error = DomainError.model_validate(error_payload(code))
                self.assertTrue(error.retryable)

    def test_retryable_false_rejected_for_retryable_codes(self) -> None:
        for code in RETRYABLE_CODES:
            with self.subTest(code=code):
                payload = error_payload(code)
                payload["retryable"] = False
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_retryable_false_accepted_for_non_retryable_codes(self) -> None:
        for code in NON_RETRYABLE_CODES:
            with self.subTest(code=code):
                error = DomainError.model_validate(error_payload(code))
                self.assertFalse(error.retryable)

    def test_retryable_true_rejected_for_non_retryable_codes(self) -> None:
        for code in NON_RETRYABLE_CODES:
            with self.subTest(code=code):
                payload = error_payload(code)
                payload["retryable"] = True
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_missing_retryable_is_rejected(self) -> None:
        payload = error_payload()
        del payload["retryable"]
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)


class EnvelopeTests(unittest.TestCase):
    def test_valid_envelope(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload("DEPENDENCY_TIMEOUT"))
        self.assertEqual(envelope.schema_version, "1.0.0")
        self.assertEqual(envelope.error.code, "DEPENDENCY_TIMEOUT")
        self.assertEqual(envelope.error.safe_message_key, "error.dependency_timeout")
        self.assertTrue(envelope.error.retryable)

    def test_missing_error_is_rejected(self) -> None:
        payload = envelope_payload()
        del payload["error"]
        with self.assertRaises(ValidationError):
            ErrorEnvelope.model_validate(payload)

    def test_root_unknown_fields_are_rejected(self) -> None:
        payload = envelope_payload()
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            ErrorEnvelope.model_validate(payload)

    def test_nested_unknown_fields_are_rejected(self) -> None:
        payload = error_payload()
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    def test_forbidden_fields_are_rejected_at_root(self) -> None:
        for name in FORBIDDEN_FIELDS + FORBIDDEN_ENVELOPE_FIELDS:
            with self.subTest(name=name):
                payload = envelope_payload()
                payload[name] = "value"
                with self.assertRaises(ValidationError):
                    ErrorEnvelope.model_validate(payload)

    def test_forbidden_fields_are_rejected_in_domain_error(self) -> None:
        for name in FORBIDDEN_FIELDS:
            with self.subTest(name=name):
                payload = error_payload()
                payload[name] = "value"
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_user_text_cannot_be_injected_as_a_message_field(self) -> None:
        for name in ("message", "safe_message", "detail"):
            with self.subTest(name=name):
                payload = error_payload()
                payload[name] = "\u062e\u0637\u0627\u06cc \u062f\u0627\u062e\u0644\u06cc"
                with self.assertRaises(ValidationError):
                    DomainError.model_validate(payload)

    def test_root_model_is_immutable(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload())
        with self.assertRaises(ValidationError):
            envelope.error_id = UUID(CORRELATION_ID)

    def test_nested_model_is_immutable(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload())
        with self.assertRaises(ValidationError):
            envelope.error.retryable = True

    def test_json_round_trip(self) -> None:
        original = ErrorEnvelope.model_validate(envelope_payload("RATE_LIMITED"))
        restored = ErrorEnvelope.model_validate_json(original.model_dump_json())
        self.assertEqual(restored, original)

    def test_json_dump_shape(self) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload())
        dumped = envelope.model_dump(mode="json")
        self.assertEqual(set(dumped), {"schema_version", "error_id", "correlation_id", "error"})
        self.assertEqual(
            set(dumped["error"]),
            {"code", "safe_message_key", "retryable", "internal_detail_ref"},
        )


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = ErrorEnvelope.model_json_schema()

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:error-envelope:1.0.0")

    def test_root_schema_is_closed(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])

    def test_nested_schema_is_closed(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertFalse(definition["additionalProperties"])

    def test_nested_domain_error_has_no_schema_version(self) -> None:
        self.assertNotIn("schema_version", self.schema["$defs"]["DomainError"]["properties"])

    def test_schema_contains_exact_code_catalog(self) -> None:
        code_schema = self.schema["$defs"]["DomainError"]["properties"]["code"]
        self.assertEqual(tuple(code_schema["enum"]), ERROR_CODES)

    def test_committed_artifact_matches_generated_schema(self) -> None:
        committed = json.loads(SCHEMA_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        self.assertTrue(SCHEMA_ARTIFACT.read_text(encoding="utf-8").endswith("}\n"))

    def schema_property_names(self) -> set[str]:
        names = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            names.update(definition["properties"])
        return names

    def test_forbidden_field_names_absent_from_schema(self) -> None:
        declared = self.schema_property_names()
        for name in FORBIDDEN_FIELDS + FORBIDDEN_ENVELOPE_FIELDS:
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_http_specific_fields_absent_from_schema(self) -> None:
        declared = self.schema_property_names()
        for name in HTTP_FIELDS:
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_forbidden_names_absent_from_serialized_schema(self) -> None:
        serialized = json.dumps(self.schema)
        for name in SCANNABLE_FORBIDDEN_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, serialized)

    def test_declared_property_names_are_exact(self) -> None:
        self.assertEqual(
            self.schema_property_names(),
            {
                "schema_version",
                "error_id",
                "correlation_id",
                "error",
                "code",
                "safe_message_key",
                "retryable",
                "internal_detail_ref",
            },
        )


class ExportTests(unittest.TestCase):
    def test_public_exports_are_available(self) -> None:
        expected = {"ErrorCode", "DomainError", "ErrorEnvelope"}
        self.assertTrue(expected <= set(contracts.__all__))
        self.assertIs(contracts.DomainError, DomainError)
        self.assertIs(contracts.ErrorEnvelope, ErrorEnvelope)


uuid4_values = st.uuids(version=4).map(str)
approved_codes = st.sampled_from(ERROR_CODES)
unknown_field_names = st.sampled_from(FORBIDDEN_FIELDS + FORBIDDEN_ENVELOPE_FIELDS + HTTP_FIELDS)


class ErrorEnvelopePropertyTests(unittest.TestCase):
    @given(code=approved_codes)
    def test_approved_combinations_round_trip(self, code: str) -> None:
        envelope = ErrorEnvelope.model_validate(envelope_payload(code))
        restored = ErrorEnvelope.model_validate_json(envelope.model_dump_json())
        self.assertEqual(restored.error.code, code)
        self.assertEqual(restored.error.safe_message_key, f"error.{code.lower()}")
        self.assertEqual(restored.error.retryable, code in RETRYABLE_CODES)

    @given(code=approved_codes, other=approved_codes)
    def test_mismatched_message_key_is_rejected(self, code: str, other: str) -> None:
        if code == other:
            return
        payload = error_payload(code)
        payload["safe_message_key"] = f"error.{other.lower()}"
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    @given(code=approved_codes)
    def test_inverted_retryability_is_rejected(self, code: str) -> None:
        payload = error_payload(code)
        payload["retryable"] = code not in RETRYABLE_CODES
        with self.assertRaises(ValidationError):
            DomainError.model_validate(payload)

    @given(name=unknown_field_names, value=st.text(min_size=0, max_size=8))
    def test_unknown_diagnostic_fields_are_rejected(self, name: str, value: str) -> None:
        payload = envelope_payload()
        payload[name] = value
        with self.assertRaises(ValidationError):
            ErrorEnvelope.model_validate(payload)

    @given(error_id=uuid4_values, correlation_id=uuid4_values)
    def test_uuid4_identifiers_are_unchanged(self, error_id: str, correlation_id: str) -> None:
        payload = envelope_payload()
        payload["error_id"] = error_id
        payload["correlation_id"] = correlation_id
        envelope = ErrorEnvelope.model_validate(payload)
        self.assertEqual(envelope.error_id, UUID(error_id))
        self.assertEqual(envelope.correlation_id, UUID(correlation_id))


if __name__ == "__main__":
    unittest.main()
