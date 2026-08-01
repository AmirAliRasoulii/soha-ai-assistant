"""Tests for the AI Core audit event contract, schema version 1.0.0."""

import json
import unittest
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.audit import AuditActorRef, AuditEvent, AuditResourceRef

TEHRAN = "+03:30"
EVENT_ID = "11111111-1111-4111-8111-111111111111"
CORRELATION_ID = "22222222-2222-4222-8222-222222222222"
REQUEST_ID = "33333333-3333-4333-8333-333333333333"
PRINCIPAL_ID = "44444444-4444-4444-8444-444444444444"
SECURITY_CONTEXT_ID = "55555555-5555-4555-8555-555555555555"
RUNTIME_SNAPSHOT_ID = "66666666-6666-4666-8666-666666666666"
AUTHZ_DECISION_ID = "77777777-7777-4777-8777-777777777777"
ERROR_ID = "88888888-8888-4888-8888-888888888888"
DETAIL_REF = "99999999-9999-4999-8999-999999999999"
UUID1_VALUE = "aaaaaaaa-aaaa-1aaa-8aaa-aaaaaaaaaaaa"
OCCURRED_AT = "2026-01-01T12:00:00" + TEHRAN
EXPECTED_UTC_HOUR = 8

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "message",
    "raw_message",
    "normalized_query",
    "prompt",
    "system_prompt",
    "completion",
    "response",
    "answer",
    "citation_text",
    "exception",
    "stack_trace",
    "traceback",
    "raw_error",
    "provider_response",
    "provider_request",
    "model_input",
    "model_output",
    "token",
    "access_token",
    "api_key",
    "secret",
    "password",
    "credentials",
    "email",
    "display_name",
    "roles",
    "groups",
    "session",
    "cookie",
    "headers",
    "http_status",
    "sql",
    "query",
    "url",
    "endpoint",
    "filesystem_path",
    "trace_id",
    "span_id",
    "cloud_event",
    "specversion",
    "source",
    "datacontenttype",
    "dataschema",
    "data",
    "metadata",
    "attributes",
)
# Names that are also legitimate JSON Schema keywords are checked only as
# declared model properties, never by scanning raw schema text.
SCHEMA_KEYWORD_OVERLAP: frozenset[str] = frozenset({"data", "source"})
SCANNABLE_FORBIDDEN_NAMES = tuple(
    name for name in FORBIDDEN_FIELDS if name not in SCHEMA_KEYWORD_OVERLAP
)

SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "audit-event" / "1.0.0.schema.json"
)


def actor_payload(actor_type: str = "user") -> dict[str, object]:
    if actor_type == "system":
        return {"actor_type": "system"}
    return {
        "actor_type": actor_type,
        "principal_id": PRINCIPAL_ID,
        "security_context_id": SECURITY_CONTEXT_ID,
    }


def resource_payload() -> dict[str, object]:
    return {
        "resource_type": "document",
        "resource_id": "doc-123",
        "classification": "confidential",
    }


def event_payload(outcome: str = "success", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "event_id": EVENT_ID,
        "event_type": "runtime.completed",
        "occurred_at": OCCURRED_AT,
        "producer": "runtime",
        "correlation_id": CORRELATION_ID,
        "request_id": REQUEST_ID,
        "actor": actor_payload(),
        "action": "runtime.request",
        "outcome": outcome,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "retention_class": "standard",
        "sensitivity": "internal",
    }
    if outcome == "denied":
        payload["authorization_decision_id"] = AUTHZ_DECISION_ID
        payload["reason_codes"] = ["policy.denied"]
    elif outcome == "failed":
        payload["error_id"] = ERROR_ID
        payload["reason_codes"] = ["dependency.timeout"]
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    def test_default_schema_version_is_exact(self) -> None:
        event = AuditEvent.model_validate(event_payload())
        self.assertEqual(event.schema_version, "1.0.0")

    def test_other_schema_version_is_rejected(self) -> None:
        for value in ("1.0.1", "1.1.0", "2.0.0", "1.0"):
            with self.subTest(value=value):
                payload = event_payload(**{"schema_version": value})
                with self.assertRaises(ValidationError):
                    AuditEvent.model_validate(payload)


class ValidEventTests(unittest.TestCase):
    def test_valid_success_event(self) -> None:
        event = AuditEvent.model_validate(event_payload("success"))
        self.assertEqual(event.outcome, "success")
        self.assertIsNone(event.error_id)

    def test_valid_denied_event(self) -> None:
        event = AuditEvent.model_validate(event_payload("denied"))
        self.assertEqual(event.outcome, "denied")
        self.assertEqual(event.authorization_decision_id, UUID(AUTHZ_DECISION_ID))
        self.assertEqual(event.reason_codes, ("policy.denied",))

    def test_valid_failed_event(self) -> None:
        event = AuditEvent.model_validate(event_payload("failed"))
        self.assertEqual(event.outcome, "failed")
        self.assertEqual(event.error_id, UUID(ERROR_ID))
        self.assertEqual(event.reason_codes, ("dependency.timeout",))


class IdentifierTests(unittest.TestCase):
    def test_uuid4_enforced_for_every_identifier_field(self) -> None:
        fields = (
            "event_id",
            "correlation_id",
            "request_id",
            "runtime_snapshot_id",
        )
        for field in fields:
            with self.subTest(field=field):
                payload = event_payload()
                payload[field] = UUID1_VALUE
                with self.assertRaises(ValidationError):
                    AuditEvent.model_validate(payload)

    def test_uuid4_enforced_for_optional_identifiers(self) -> None:
        payload = event_payload("denied")
        payload["authorization_decision_id"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)
        payload = event_payload("failed")
        payload["error_id"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)
        payload = event_payload()
        payload["internal_detail_ref"] = UUID1_VALUE
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_naive_occurred_at_is_rejected(self) -> None:
        payload = event_payload()
        payload["occurred_at"] = "2026-01-01T12:00:00"
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_non_utc_timestamp_is_normalized(self) -> None:
        event = AuditEvent.model_validate(event_payload())
        self.assertEqual(event.occurred_at.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(event.occurred_at.utcoffset().total_seconds(), 0)


class ActorTests(unittest.TestCase):
    def test_valid_user_actor(self) -> None:
        actor = AuditActorRef.model_validate(actor_payload("user"))
        self.assertEqual(actor.actor_type, "user")
        self.assertEqual(actor.principal_id, UUID(PRINCIPAL_ID))

    def test_valid_service_actor(self) -> None:
        actor = AuditActorRef.model_validate(actor_payload("service"))
        self.assertEqual(actor.actor_type, "service")

    def test_valid_system_actor(self) -> None:
        actor = AuditActorRef.model_validate(actor_payload("system"))
        self.assertIsNone(actor.principal_id)
        self.assertIsNone(actor.security_context_id)

    def test_user_actor_missing_principal_is_rejected(self) -> None:
        payload = actor_payload("user")
        del payload["principal_id"]
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_user_actor_missing_security_context_is_rejected(self) -> None:
        payload = actor_payload("user")
        del payload["security_context_id"]
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_service_actor_missing_identity_is_rejected(self) -> None:
        payload = {"actor_type": "service"}
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_system_actor_with_principal_is_rejected(self) -> None:
        payload = {"actor_type": "system", "principal_id": PRINCIPAL_ID}
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_system_actor_with_security_context_is_rejected(self) -> None:
        payload = {"actor_type": "system", "security_context_id": SECURITY_CONTEXT_ID}
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_partial_identity_is_rejected(self) -> None:
        payload = {
            "actor_type": "user",
            "principal_id": PRINCIPAL_ID,
            "security_context_id": None,
        }
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)


class ResourceTests(unittest.TestCase):
    def test_valid_resource(self) -> None:
        resource = AuditResourceRef.model_validate(resource_payload())
        self.assertEqual(resource.resource_id, "doc-123")

    def test_absent_resource_is_accepted(self) -> None:
        event = AuditEvent.model_validate(event_payload())
        self.assertIsNone(event.resource)

    def test_blank_resource_id_is_rejected(self) -> None:
        payload = resource_payload()
        payload["resource_id"] = "   "
        with self.assertRaises(ValidationError):
            AuditResourceRef.model_validate(payload)

    def test_padded_resource_id_is_rejected(self) -> None:
        payload = resource_payload()
        payload["resource_id"] = " doc-123 "
        with self.assertRaises(ValidationError):
            AuditResourceRef.model_validate(payload)

    def test_nul_resource_id_is_rejected(self) -> None:
        payload = resource_payload()
        payload["resource_id"] = "doc-123\x00"
        with self.assertRaises(ValidationError):
            AuditResourceRef.model_validate(payload)

    def test_resource_id_is_preserved_exactly(self) -> None:
        payload = resource_payload()
        payload["resource_id"] = "Doc_ID-With.Mixed:Case"
        resource = AuditResourceRef.model_validate(payload)
        self.assertEqual(resource.resource_id, "Doc_ID-With.Mixed:Case")


class CanonicalCodeTests(unittest.TestCase):
    def test_valid_canonical_codes_are_accepted(self) -> None:
        for value in (
            "runtime",
            "runtime.completed",
            "runtime.authorization.denied",
            "capability:document-retrieval",
            "policy.denied",
            "confidential",
            "standard",
        ):
            with self.subTest(value=value):
                payload = event_payload()
                payload["event_type"] = value
                event = AuditEvent.model_validate(payload)
                self.assertEqual(event.event_type, value)

    def test_invalid_canonical_codes_are_rejected(self) -> None:
        for value in ("Runtime.Completed", " leading", "contains/slash", "contains@sign", ""):
            with self.subTest(value=value):
                payload = event_payload()
                payload["event_type"] = value
                with self.assertRaises(ValidationError):
                    AuditEvent.model_validate(payload)


class ReasonCodeTests(unittest.TestCase):
    def test_missing_reason_codes_becomes_empty_tuple(self) -> None:
        event = AuditEvent.model_validate(event_payload("success"))
        self.assertEqual(event.reason_codes, ())

    def test_explicit_null_reason_codes_is_rejected(self) -> None:
        payload = event_payload("success")
        payload["reason_codes"] = None
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_duplicate_reason_codes_are_rejected(self) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = ["policy.denied", "policy.denied"]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_sixteen_reason_codes_are_accepted(self) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = [f"reason.{i}" for i in range(16)]
        event = AuditEvent.model_validate(payload)
        self.assertEqual(len(event.reason_codes), 16)

    def test_seventeen_reason_codes_are_rejected(self) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = [f"reason.{i}" for i in range(17)]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_reason_code_order_is_preserved(self) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = ["reason.c", "reason.a", "reason.b"]
        event = AuditEvent.model_validate(payload)
        self.assertEqual(event.reason_codes, ("reason.c", "reason.a", "reason.b"))


class OutcomeInvariantTests(unittest.TestCase):
    def test_success_with_error_id_is_rejected(self) -> None:
        payload = event_payload("success")
        payload["error_id"] = ERROR_ID
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_success_with_no_reason_is_accepted(self) -> None:
        event = AuditEvent.model_validate(event_payload("success"))
        self.assertEqual(event.reason_codes, ())

    def test_denied_without_authorization_decision_is_rejected(self) -> None:
        payload = event_payload("denied")
        del payload["authorization_decision_id"]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_denied_without_reason_is_rejected(self) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = []
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_denied_with_error_id_is_rejected(self) -> None:
        payload = event_payload("denied")
        payload["error_id"] = ERROR_ID
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_failed_without_error_id_is_rejected(self) -> None:
        payload = event_payload("failed")
        del payload["error_id"]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_failed_without_reason_is_rejected(self) -> None:
        payload = event_payload("failed")
        payload["reason_codes"] = []
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_failed_with_error_and_reason_is_accepted(self) -> None:
        event = AuditEvent.model_validate(event_payload("failed"))
        self.assertEqual(event.error_id, UUID(ERROR_ID))
        self.assertEqual(event.reason_codes, ("dependency.timeout",))

    def test_missing_runtime_snapshot_is_rejected(self) -> None:
        payload = event_payload("success")
        del payload["runtime_snapshot_id"]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)


class UnknownAndForbiddenFieldTests(unittest.TestCase):
    def test_root_unknown_fields_are_rejected(self) -> None:
        payload = event_payload()
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_actor_unknown_fields_are_rejected(self) -> None:
        payload = actor_payload("system")
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            AuditActorRef.model_validate(payload)

    def test_resource_unknown_fields_are_rejected(self) -> None:
        payload = resource_payload()
        payload["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            AuditResourceRef.model_validate(payload)

    def test_forbidden_fields_are_rejected_at_root(self) -> None:
        for name in FORBIDDEN_FIELDS:
            with self.subTest(name=name):
                payload = event_payload()
                payload[name] = "value"
                with self.assertRaises(ValidationError):
                    AuditEvent.model_validate(payload)


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    def test_root_model_is_immutable(self) -> None:
        event = AuditEvent.model_validate(event_payload())
        with self.assertRaises(ValidationError):
            event.event_id = UUID(CORRELATION_ID)

    def test_nested_model_is_immutable(self) -> None:
        event = AuditEvent.model_validate(event_payload())
        with self.assertRaises(ValidationError):
            event.actor.actor_type = "system"

    def test_json_round_trip(self) -> None:
        original = AuditEvent.model_validate(event_payload("denied"))
        restored = AuditEvent.model_validate_json(original.model_dump_json())
        self.assertEqual(restored, original)


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = AuditEvent.model_json_schema()

    def schema_property_names(self) -> set[str]:
        names = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            names.update(definition["properties"])
        return names

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:audit-event:1.0.0")

    def test_root_schema_is_closed(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])

    def test_nested_schemas_are_closed(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertFalse(definition["additionalProperties"])

    def test_committed_artifact_matches_generated_schema(self) -> None:
        committed = json.loads(SCHEMA_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        self.assertTrue(SCHEMA_ARTIFACT.read_text(encoding="utf-8").endswith("}\n"))

    def test_forbidden_property_names_absent_from_schema(self) -> None:
        declared = self.schema_property_names()
        for name in FORBIDDEN_FIELDS:
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_no_cloudevents_transport_property_declared(self) -> None:
        declared = self.schema_property_names()
        for name in (
            "specversion",
            "cloud_event",
            "datacontenttype",
            "dataschema",
            "source",
            "data",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_no_sensitive_or_transport_fields_declared(self) -> None:
        declared = self.schema_property_names()
        for name in (
            "prompt",
            "response",
            "exception",
            "token",
            "email",
            "sql",
            "url",
            "filesystem_path",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_forbidden_names_absent_from_serialized_schema(self) -> None:
        serialized = json.dumps(self.schema)
        for name in SCANNABLE_FORBIDDEN_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, serialized)


class ExportTests(unittest.TestCase):
    def test_public_exports_are_available(self) -> None:
        expected = {"AuditActorRef", "AuditResourceRef", "AuditEvent"}
        self.assertTrue(expected <= set(contracts.__all__))
        self.assertIs(contracts.AuditEvent, AuditEvent)
        self.assertIs(contracts.AuditActorRef, AuditActorRef)
        self.assertIs(contracts.AuditResourceRef, AuditResourceRef)
        self.assertIn("ErrorEnvelope", contracts.__all__)


reason_code_strategy = st.from_regex(r"\Areason\.[a-z0-9]{1,6}\Z", fullmatch=True)
unknown_field_names = st.sampled_from(FORBIDDEN_FIELDS)


class AuditEventPropertyTests(unittest.TestCase):
    @given(codes=st.lists(reason_code_strategy, min_size=1, max_size=6, unique=True))
    def test_unique_reason_codes_preserve_order(self, codes: list[str]) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = codes
        event = AuditEvent.model_validate(payload)
        self.assertEqual(event.reason_codes, tuple(codes))

    @given(code=reason_code_strategy)
    def test_duplicate_reason_code_is_rejected(self, code: str) -> None:
        payload = event_payload("denied")
        payload["reason_codes"] = [code, code]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    def test_valid_success_events_round_trip_unchanged(self) -> None:
        original = AuditEvent.model_validate(event_payload("success"))
        restored = AuditEvent.model_validate_json(original.model_dump_json())
        self.assertEqual(restored, original)

    @given(outcome=st.sampled_from(["denied", "failed"]))
    def test_missing_required_reference_is_rejected(self, outcome: str) -> None:
        payload = event_payload(outcome)
        if outcome == "denied":
            del payload["authorization_decision_id"]
        else:
            del payload["error_id"]
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)

    @given(name=unknown_field_names, value=st.text(min_size=0, max_size=8))
    def test_unknown_sensitive_fields_are_rejected(self, name: str, value: str) -> None:
        payload = event_payload()
        payload[name] = value
        with self.assertRaises(ValidationError):
            AuditEvent.model_validate(payload)


if __name__ == "__main__":
    unittest.main()
