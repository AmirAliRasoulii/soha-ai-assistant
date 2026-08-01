"""Contract tests for the capability step result envelope."""

import json
import unittest
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.step_result import (
    StepEvidenceRef,
    StepProvenance,
    StepResult,
    StepRetryMetadata,
    StepTypedOutputRef,
)

RESULT_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
PLAN_ID = "33333333-3333-4333-8333-333333333333"
RUNTIME_SNAPSHOT_ID = "44444444-4444-4444-8444-444444444444"
CORRELATION_ID = "55555555-5555-4555-8555-555555555555"
EVIDENCE_ID = "66666666-6666-4666-8666-666666666666"
PREVIOUS_RESULT_ID = "77777777-7777-4777-8777-777777777777"
INTERNAL_DETAIL_REF = "88888888-8888-4888-8888-888888888888"
UUID1_VALUE = "99999999-9999-1999-8999-999999999999"
COMPLETED_AT = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC_HOUR = 8
OUTPUT_DIGEST = "0123456789abcdef" * 4
INPUT_DIGEST = "fedcba9876543210" * 4
MAX_LATENCY_MS = 2147483647

STATUSES = ("success", "partial", "failed")
CAPABILITIES = (
    "document_retrieval",
    "semantic_analytics",
    "personal_selector",
    "rule_evaluator",
    "official_search",
)
FACT_SCOPES = ("general", "personal")
ERROR_CODES = (
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
)
RETRYABLE_ERROR_CODES = (
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
)
FORBIDDEN_FIELDS = (
    "raw_message",
    "raw_query",
    "normalized_query",
    "standalone_query",
    "query_text",
    "prompt",
    "system_prompt",
    "model",
    "model_name",
    "model_output",
    "provider",
    "provider_response",
    "raw_response",
    "raw_output",
    "typed_output",
    "output_value",
    "value",
    "data",
    "payload",
    "content",
    "json",
    "rows",
    "documents",
    "chunks",
    "snippets",
    "html",
    "sql",
    "statement",
    "query",
    "where",
    "predicate",
    "tool",
    "tool_name",
    "tool_arguments",
    "function_call",
    "endpoint",
    "url",
    "path",
    "bucket",
    "api_key",
    "token",
    "access_token",
    "secret",
    "password",
    "credentials",
    "exception",
    "exception_type",
    "exception_message",
    "stack_trace",
    "traceback",
    "safe_error",
    "error_message",
    "rationale",
    "reasoning",
    "chain_of_thought",
    "answer",
    "clarification_message",
    "denial_message",
    "roles",
    "groups",
    "principal_id",
    "security_context_id",
    "email",
    "display_name",
    "session_id",
    "headers",
    "http_status",
    "metadata",
    "attributes",
    "deadline_ms",
    "timeout_ms",
    "token_budget",
    "cost_budget",
    "provider_latency",
    "traceparent",
    "span_id",
    "vendor_trace_id",
)
SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "step-result" / "1.0.0.schema.json"
)


def output_payload(
    fact_id: str = "fact.document",
    value_type: str = "type.document",
    data_scope: str = "general",
) -> dict[str, object]:
    return {
        "fact_id": fact_id,
        "value_type": value_type,
        "data_scope": data_scope,
        "schema_ref": "schema:type.document:1.0.0",
        "value_ref": "artifact:0f2c1b",
        "sha256": OUTPUT_DIGEST,
    }


def evidence_payload(
    evidence_id: str = EVIDENCE_ID,
    supports_fact_ids: list[str] | None = None,
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "supports_fact_ids": (
            list(supports_fact_ids) if supports_fact_ids is not None else ["fact.document"]
        ),
    }


def retry_payload(
    attempt: object = 1,
    max_attempts: object = 2,
    retryable: object = False,
    previous_result_id: str | None = None,
) -> dict[str, object]:
    return {
        "attempt": attempt,
        "max_attempts": max_attempts,
        "retryable": retryable,
        "previous_result_id": previous_result_id,
    }


def provenance_payload(
    capability: str = "document_retrieval",
    operation: str = "document.retrieve",
    implementation_version: str = "1.0.0",
    input_digest: str = INPUT_DIGEST,
) -> dict[str, object]:
    return {
        "capability": capability,
        "operation": operation,
        "implementation_version": implementation_version,
        "input_digest": input_digest,
    }


def result_payload(status: str = "success", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "result_id": RESULT_ID,
        "request_id": REQUEST_ID,
        "plan_id": PLAN_ID,
        "step_id": "step.retrieve",
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "correlation_id": CORRELATION_ID,
        "completed_at": COMPLETED_AT,
        "status": status,
        "typed_outputs": [output_payload()],
        "missing_fact_ids": [],
        "evidence_refs": [evidence_payload()],
        "latency_ms": 120,
        "retry": retry_payload(),
        "failure_code": None,
        "internal_detail_ref": None,
        "provenance": provenance_payload(),
    }
    if status == "partial":
        payload["missing_fact_ids"] = ["fact.summary"]
        payload["failure_code"] = "DEPENDENCY_TIMEOUT"
        payload["internal_detail_ref"] = INTERNAL_DETAIL_REF
    elif status == "failed":
        payload["typed_outputs"] = []
        payload["evidence_refs"] = []
        payload["missing_fact_ids"] = ["fact.document"]
        payload["failure_code"] = "DEPENDENCY_TIMEOUT"
        payload["internal_detail_ref"] = INTERNAL_DETAIL_REF
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    """Schema version behavior."""

    def test_default_schema_version(self) -> None:
        result = StepResult.model_validate(result_payload())
        self.assertEqual(result.schema_version, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(schema_version="1.1.0"))


class ValidResultTests(unittest.TestCase):
    """Valid results for each status."""

    def test_valid_success_result(self) -> None:
        result = StepResult.model_validate(result_payload())
        self.assertEqual(result.status, "success")
        self.assertEqual(result.typed_outputs[0].fact_id, "fact.document")
        self.assertIsNone(result.failure_code)

    def test_valid_partial_result(self) -> None:
        result = StepResult.model_validate(result_payload("partial"))
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.missing_fact_ids, ("fact.summary",))
        self.assertEqual(result.failure_code, "DEPENDENCY_TIMEOUT")

    def test_valid_failed_result(self) -> None:
        result = StepResult.model_validate(result_payload("failed"))
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.typed_outputs, ())
        self.assertEqual(result.evidence_refs, ())

    def test_every_status_accepted_with_matching_payload(self) -> None:
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertEqual(StepResult.model_validate(result_payload(status)).status, status)

    def test_unsupported_status_rejected(self) -> None:
        for status in ("succeeded", "Success", "error", ""):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(status=status))


class IdentifierAndTimestampTests(unittest.TestCase):
    """Identifier and timestamp validation."""

    def test_uuid4_enforced_for_root_identifiers(self) -> None:
        for field in (
            "result_id",
            "request_id",
            "plan_id",
            "runtime_snapshot_id",
            "correlation_id",
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(**{field: UUID1_VALUE}))

    def test_uuid4_enforced_for_internal_detail_ref(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", internal_detail_ref=UUID1_VALUE))

    def test_uuid4_enforced_for_previous_result_id(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=2, previous_result_id=UUID1_VALUE)
            )

    def test_uuid4_enforced_for_evidence_id(self) -> None:
        with self.assertRaises(ValidationError):
            StepEvidenceRef.model_validate(evidence_payload(evidence_id=UUID1_VALUE))

    def test_naive_timestamp_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(completed_at="2026-01-01T12:00:00"))

    def test_non_utc_timestamp_normalized(self) -> None:
        result = StepResult.model_validate(result_payload())
        self.assertEqual(result.completed_at.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(result.completed_at.utcoffset().total_seconds(), 0)

    def test_identifiers_parsed(self) -> None:
        result = StepResult.model_validate(result_payload())
        self.assertEqual(result.result_id, UUID(RESULT_ID))
        self.assertEqual(result.correlation_id, UUID(CORRELATION_ID))


class TypedOutputRefTests(unittest.TestCase):
    """Typed output reference validation."""

    def test_valid_typed_output_reference(self) -> None:
        output = StepTypedOutputRef.model_validate(output_payload())
        self.assertEqual(output.fact_id, "fact.document")
        self.assertEqual(output.value_type, "type.document")
        self.assertEqual(output.sha256, OUTPUT_DIGEST)

    def test_invalid_fact_code_rejected(self) -> None:
        for fact_id in ("Fact.document", "1fact", "fact document", "", "f" * 129):
            with self.subTest(fact_id=fact_id), self.assertRaises(ValidationError):
                StepTypedOutputRef.model_validate(output_payload(fact_id=fact_id))

    def test_valid_canonical_codes_accepted(self) -> None:
        for fact_id in ("a", "fact.one", "fact:one-two", "f" * 128):
            with self.subTest(fact_id=fact_id):
                output = StepTypedOutputRef.model_validate(output_payload(fact_id=fact_id))
                self.assertEqual(output.fact_id, fact_id)

    def test_invalid_value_type_rejected(self) -> None:
        for value_type in ("Type", "_type", "type value", ""):
            with self.subTest(value_type=value_type), self.assertRaises(ValidationError):
                StepTypedOutputRef.model_validate(output_payload(value_type=value_type))

    def test_both_data_scopes_accepted(self) -> None:
        for scope in FACT_SCOPES:
            with self.subTest(scope=scope):
                output = StepTypedOutputRef.model_validate(output_payload(data_scope=scope))
                self.assertEqual(output.data_scope, scope)

    def test_unsupported_data_scope_rejected(self) -> None:
        for scope in ("internal", "General", ""):
            with self.subTest(scope=scope), self.assertRaises(ValidationError):
                StepTypedOutputRef.model_validate(output_payload(data_scope=scope))

    def test_blank_schema_reference_rejected(self) -> None:
        payload = output_payload()
        payload["schema_ref"] = "   "
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_padded_schema_reference_rejected(self) -> None:
        payload = output_payload()
        payload["schema_ref"] = " schema:type.document:1.0.0 "
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_nul_schema_reference_rejected(self) -> None:
        payload = output_payload()
        payload["schema_ref"] = "schema\x00document"
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_oversized_schema_reference_rejected(self) -> None:
        payload = output_payload()
        payload["schema_ref"] = "s" * 257
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_value_reference_preserved_exactly(self) -> None:
        payload = output_payload()
        payload["value_ref"] = "Artifact:AB_12/xy"
        output = StepTypedOutputRef.model_validate(payload)
        self.assertEqual(output.value_ref, "Artifact:AB_12/xy")

    def test_uppercase_digest_rejected(self) -> None:
        payload = output_payload()
        payload["sha256"] = OUTPUT_DIGEST.upper()
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_short_digest_rejected(self) -> None:
        payload = output_payload()
        payload["sha256"] = OUTPUT_DIGEST[:63]
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_non_hex_digest_rejected(self) -> None:
        payload = output_payload()
        payload["sha256"] = "z" + OUTPUT_DIGEST[1:]
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)

    def test_valid_lowercase_digest_accepted(self) -> None:
        payload = output_payload()
        payload["sha256"] = "a" * 64
        self.assertEqual(StepTypedOutputRef.model_validate(payload).sha256, "a" * 64)

    def test_output_unknown_field_rejected(self) -> None:
        payload = output_payload()
        payload["value"] = "forbidden"
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(payload)


class TypedOutputCollectionTests(unittest.TestCase):
    """Typed output collection rules."""

    def test_duplicate_output_fact_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(
                    typed_outputs=[output_payload(), output_payload()],
                    evidence_refs=[],
                )
            )

    def test_output_order_preserved(self) -> None:
        outputs = [output_payload(fact_id=f"fact.item{index}") for index in range(4)]
        result = StepResult.model_validate(result_payload(typed_outputs=outputs, evidence_refs=[]))
        self.assertEqual(
            [output.fact_id for output in result.typed_outputs],
            ["fact.item0", "fact.item1", "fact.item2", "fact.item3"],
        )

    def test_sixteen_outputs_accepted(self) -> None:
        outputs = [output_payload(fact_id=f"fact.item{index}") for index in range(16)]
        result = StepResult.model_validate(result_payload(typed_outputs=outputs, evidence_refs=[]))
        self.assertEqual(len(result.typed_outputs), 16)

    def test_seventeen_outputs_rejected(self) -> None:
        outputs = [output_payload(fact_id=f"fact.item{index}") for index in range(17)]
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(typed_outputs=outputs, evidence_refs=[]))


class EvidenceRefTests(unittest.TestCase):
    """Evidence reference validation."""

    def test_valid_evidence_reference(self) -> None:
        reference = StepEvidenceRef.model_validate(evidence_payload())
        self.assertEqual(reference.evidence_id, UUID(EVIDENCE_ID))
        self.assertEqual(reference.supports_fact_ids, ("fact.document",))

    def test_evidence_support_list_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            StepEvidenceRef.model_validate(evidence_payload(supports_fact_ids=[]))

    def test_duplicate_supported_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepEvidenceRef.model_validate(
                evidence_payload(supports_fact_ids=["fact.document", "fact.document"])
            )

    def test_sixteen_supported_facts_accepted(self) -> None:
        facts = [f"fact.item{index}" for index in range(16)]
        reference = StepEvidenceRef.model_validate(evidence_payload(supports_fact_ids=facts))
        self.assertEqual(len(reference.supports_fact_ids), 16)

    def test_seventeen_supported_facts_rejected(self) -> None:
        facts = [f"fact.item{index}" for index in range(17)]
        with self.assertRaises(ValidationError):
            StepEvidenceRef.model_validate(evidence_payload(supports_fact_ids=facts))

    def test_evidence_support_order_preserved(self) -> None:
        facts = ["fact.item2", "fact.item0", "fact.item1"]
        reference = StepEvidenceRef.model_validate(evidence_payload(supports_fact_ids=facts))
        self.assertEqual(list(reference.supports_fact_ids), facts)

    def test_evidence_unknown_field_rejected(self) -> None:
        payload = evidence_payload()
        payload["snippets"] = ["forbidden"]
        with self.assertRaises(ValidationError):
            StepEvidenceRef.model_validate(payload)

    def test_duplicate_evidence_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(evidence_refs=[evidence_payload(), evidence_payload()])
            )

    def test_evidence_order_preserved(self) -> None:
        outputs = [output_payload(fact_id=f"fact.item{index}") for index in range(2)]
        first_id = "a1111111-1111-4111-8111-111111111111"
        second_id = "b1111111-1111-4111-8111-111111111111"
        first = evidence_payload(evidence_id=first_id, supports_fact_ids=["fact.item1"])
        second = evidence_payload(evidence_id=second_id, supports_fact_ids=["fact.item0"])
        result = StepResult.model_validate(
            result_payload(typed_outputs=outputs, evidence_refs=[first, second])
        )
        self.assertEqual(
            [reference.evidence_id for reference in result.evidence_refs],
            [UUID(first_id), UUID(second_id)],
        )

    def test_evidence_cannot_support_unknown_output_fact(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(evidence_refs=[evidence_payload(supports_fact_ids=["fact.unknown"])])
            )


class RetryMetadataTests(unittest.TestCase):
    """Bounded retry metadata validation."""

    def test_valid_first_attempt_metadata(self) -> None:
        retry = StepRetryMetadata.model_validate(retry_payload())
        self.assertEqual(retry.attempt, 1)
        self.assertIsNone(retry.previous_result_id)

    def test_valid_second_attempt_metadata(self) -> None:
        retry = StepRetryMetadata.model_validate(
            retry_payload(attempt=2, max_attempts=2, previous_result_id=PREVIOUS_RESULT_ID)
        )
        self.assertEqual(retry.attempt, 2)
        self.assertEqual(retry.previous_result_id, UUID(PREVIOUS_RESULT_ID))

    def test_first_attempt_rejects_previous_result_reference(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=1, previous_result_id=PREVIOUS_RESULT_ID)
            )

    def test_second_attempt_requires_previous_result_reference(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(retry_payload(attempt=2, max_attempts=2))

    def test_second_attempt_requires_max_attempts_two(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=2, max_attempts=1, previous_result_id=PREVIOUS_RESULT_ID)
            )

    def test_attempt_greater_than_maximum_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=2, max_attempts=1, previous_result_id=PREVIOUS_RESULT_ID)
            )

    def test_attempt_above_two_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=3, max_attempts=2, previous_result_id=PREVIOUS_RESULT_ID)
            )

    def test_attempt_below_one_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(retry_payload(attempt=0, max_attempts=2))

    def test_max_attempts_above_two_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(retry_payload(attempt=1, max_attempts=3))

    def test_attempt_booleans_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(retry_payload(attempt=True))
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(retry_payload(max_attempts=True))

    def test_final_attempt_cannot_be_retryable(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(
                    attempt=2,
                    max_attempts=2,
                    retryable=True,
                    previous_result_id=PREVIOUS_RESULT_ID,
                )
            )

    def test_max_attempts_one_cannot_be_retryable(self) -> None:
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(
                retry_payload(attempt=1, max_attempts=1, retryable=True)
            )

    def test_retry_unknown_field_rejected(self) -> None:
        payload = retry_payload()
        payload["deadline_ms"] = 10
        with self.assertRaises(ValidationError):
            StepRetryMetadata.model_validate(payload)

    def test_self_previous_result_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(
                    "failed",
                    retry=retry_payload(attempt=2, max_attempts=2, previous_result_id=RESULT_ID),
                )
            )


class ProvenanceTests(unittest.TestCase):
    """Provider-neutral provenance validation."""

    def test_valid_provenance(self) -> None:
        provenance = StepProvenance.model_validate(provenance_payload())
        self.assertEqual(provenance.capability, "document_retrieval")
        self.assertEqual(provenance.operation, "document.retrieve")
        self.assertEqual(provenance.input_digest, INPUT_DIGEST)

    def test_every_capability_accepted(self) -> None:
        for capability in CAPABILITIES:
            with self.subTest(capability=capability):
                provenance = StepProvenance.model_validate(
                    provenance_payload(capability=capability)
                )
                self.assertEqual(provenance.capability, capability)

    def test_unsupported_capability_rejected(self) -> None:
        for capability in ("web_search", "Document_Retrieval", ""):
            with self.subTest(capability=capability), self.assertRaises(ValidationError):
                StepProvenance.model_validate(provenance_payload(capability=capability))

    def test_invalid_operation_rejected(self) -> None:
        for operation in ("Document.Retrieve", "9retrieve", "retrieve now", ""):
            with self.subTest(operation=operation), self.assertRaises(ValidationError):
                StepProvenance.model_validate(provenance_payload(operation=operation))

    def test_valid_implementation_version_accepted(self) -> None:
        provenance = StepProvenance.model_validate(
            provenance_payload(implementation_version="2.14.3")
        )
        self.assertEqual(provenance.implementation_version, "2.14.3")

    def test_invalid_implementation_version_rejected(self) -> None:
        for version in ("1.0", "v1.0.0", "1.0.0-rc1", "01.0.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                StepProvenance.model_validate(provenance_payload(implementation_version=version))

    def test_invalid_input_digest_rejected(self) -> None:
        for digest in (INPUT_DIGEST.upper(), INPUT_DIGEST[:63], "g" + INPUT_DIGEST[1:], ""):
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                StepProvenance.model_validate(provenance_payload(input_digest=digest))

    def test_provenance_unknown_field_rejected(self) -> None:
        payload = provenance_payload()
        payload["model_name"] = "forbidden"
        with self.assertRaises(ValidationError):
            StepProvenance.model_validate(payload)


class LatencyTests(unittest.TestCase):
    """Latency validation."""

    def test_latency_zero_accepted(self) -> None:
        self.assertEqual(StepResult.model_validate(result_payload(latency_ms=0)).latency_ms, 0)

    def test_maximum_latency_accepted(self) -> None:
        result = StepResult.model_validate(result_payload(latency_ms=MAX_LATENCY_MS))
        self.assertEqual(result.latency_ms, MAX_LATENCY_MS)

    def test_negative_latency_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(latency_ms=-1))

    def test_oversized_latency_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(latency_ms=MAX_LATENCY_MS + 1))

    def test_latency_boolean_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(latency_ms=True))

    def test_latency_float_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(latency_ms=1.5))


class SuccessInvariantTests(unittest.TestCase):
    """Success status invariants."""

    def test_success_requires_at_least_one_output(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(typed_outputs=[], evidence_refs=[]))

    def test_success_rejects_missing_facts(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(missing_fact_ids=["fact.summary"]))

    def test_success_rejects_failure_code(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(failure_code="INTERNAL_ERROR"))

    def test_success_rejects_internal_detail_reference(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(internal_detail_ref=INTERNAL_DETAIL_REF))

    def test_success_rejects_retryable_metadata(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(retry=retry_payload(attempt=1, max_attempts=2, retryable=True))
            )


class PartialInvariantTests(unittest.TestCase):
    """Partial status invariants."""

    def test_partial_requires_at_least_one_output(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("partial", typed_outputs=[], evidence_refs=[]))

    def test_partial_requires_at_least_one_missing_fact(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("partial", missing_fact_ids=[]))

    def test_partial_requires_failure_code(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("partial", failure_code=None))

    def test_partial_may_be_retryable(self) -> None:
        result = StepResult.model_validate(
            result_payload(
                "partial",
                retry=retry_payload(attempt=1, max_attempts=2, retryable=True),
            )
        )
        self.assertTrue(result.retry.retryable)


class FailedInvariantTests(unittest.TestCase):
    """Failed status invariants."""

    def test_failed_rejects_outputs(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", typed_outputs=[output_payload()]))

    def test_failed_requires_missing_facts(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", missing_fact_ids=[]))

    def test_failed_rejects_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(
                    "failed",
                    evidence_refs=[evidence_payload(supports_fact_ids=["fact.document"])],
                )
            )

    def test_failed_requires_failure_code(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", failure_code=None))


class FactCollectionTests(unittest.TestCase):
    """Fact identifier collection rules."""

    def test_output_and_missing_fact_overlap_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("partial", missing_fact_ids=["fact.document"]))

    def test_duplicate_missing_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload("failed", missing_fact_ids=["fact.a", "fact.a"])
            )

    def test_missing_fact_order_preserved(self) -> None:
        facts = ["fact.c", "fact.a", "fact.b"]
        result = StepResult.model_validate(result_payload("failed", missing_fact_ids=facts))
        self.assertEqual(list(result.missing_fact_ids), facts)

    def test_sixteen_missing_facts_accepted(self) -> None:
        facts = [f"fact.miss{index}" for index in range(16)]
        result = StepResult.model_validate(result_payload("failed", missing_fact_ids=facts))
        self.assertEqual(len(result.missing_fact_ids), 16)

    def test_seventeen_missing_facts_rejected(self) -> None:
        facts = [f"fact.miss{index}" for index in range(17)]
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", missing_fact_ids=facts))

    def test_invalid_step_code_rejected(self) -> None:
        for step_id in ("Step.one", "1step", "step one", ""):
            with self.subTest(step_id=step_id), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(step_id=step_id))


class FailureCodeAndRetryTests(unittest.TestCase):
    """Failure-code and retry interaction rules."""

    def test_every_error_code_accepted_where_structurally_valid(self) -> None:
        for code in ERROR_CODES:
            with self.subTest(code=code):
                result = StepResult.model_validate(result_payload("failed", failure_code=code))
                self.assertEqual(result.failure_code, code)

    def test_retryable_accepts_every_retryable_error_code(self) -> None:
        for code in RETRYABLE_ERROR_CODES:
            with self.subTest(code=code):
                result = StepResult.model_validate(
                    result_payload(
                        "failed",
                        failure_code=code,
                        retry=retry_payload(attempt=1, max_attempts=2, retryable=True),
                    )
                )
                self.assertTrue(result.retry.retryable)

    def test_retryable_rejects_non_retryable_error_code(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(
                    "failed",
                    failure_code="POLICY_REJECTED",
                    retry=retry_payload(attempt=1, max_attempts=2, retryable=True),
                )
            )

    def test_retryable_rejects_success_status(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(
                result_payload(retry=retry_payload(attempt=1, max_attempts=2, retryable=True))
            )

    def test_retryable_class_error_may_be_non_retryable_on_final_attempt(self) -> None:
        result = StepResult.model_validate(
            result_payload(
                "failed",
                failure_code="RATE_LIMITED",
                retry=retry_payload(
                    attempt=2,
                    max_attempts=2,
                    retryable=False,
                    previous_result_id=PREVIOUS_RESULT_ID,
                ),
            )
        )
        self.assertFalse(result.retry.retryable)

    def test_unsupported_failure_code_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload("failed", failure_code="BOOM"))


class CollectionDefaultTests(unittest.TestCase):
    """Collection default and null rules."""

    def test_missing_collections_become_empty_tuples(self) -> None:
        payload = result_payload("failed")
        del payload["typed_outputs"]
        del payload["evidence_refs"]
        result = StepResult.model_validate(payload)
        self.assertEqual(result.typed_outputs, ())
        self.assertEqual(result.evidence_refs, ())

    def test_explicit_null_collections_rejected(self) -> None:
        for field in ("typed_outputs", "missing_fact_ids", "evidence_refs"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(**{field: None}))


class ForbiddenFieldTests(unittest.TestCase):
    """Unknown and forbidden field rejection."""

    def test_root_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(unexpected_field="value"))

    def test_forbidden_root_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(**{field: "forbidden"}))

    def test_forbidden_nested_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                output = output_payload()
                output[field] = "forbidden"
                with self.assertRaises(ValidationError):
                    StepResult.model_validate(
                        result_payload(typed_outputs=[output], evidence_refs=[])
                    )
                provenance = provenance_payload()
                provenance[field] = "forbidden"
                with self.assertRaises(ValidationError):
                    StepResult.model_validate(result_payload(provenance=provenance))

    def test_raw_exception_fields_rejected(self) -> None:
        raw_error_fields = (
            "exception",
            "exception_type",
            "exception_message",
            "stack_trace",
            "traceback",
        )
        for field in raw_error_fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload("failed", **{field: "boom"}))

    def test_raw_payload_fields_rejected(self) -> None:
        for field in ("value", "data", "payload", "content", "json", "rows", "html"):
            with self.subTest(field=field):
                output = output_payload()
                output[field] = "forbidden"
                with self.assertRaises(ValidationError):
                    StepTypedOutputRef.model_validate(output)

    def test_provider_and_credential_fields_rejected(self) -> None:
        for field in ("provider", "provider_response", "api_key", "token", "credentials", "url"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                StepResult.model_validate(result_payload(**{field: "forbidden"}))


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    """Immutability and serialization behavior."""

    def test_root_model_immutable(self) -> None:
        result = StepResult.model_validate(result_payload())
        with self.assertRaises(ValidationError):
            result.latency_ms = 5

    def test_nested_models_immutable(self) -> None:
        result = StepResult.model_validate(result_payload())
        with self.assertRaises(ValidationError):
            result.typed_outputs[0].fact_id = "fact.other"
        with self.assertRaises(ValidationError):
            result.evidence_refs[0].evidence_id = UUID(EVIDENCE_ID)
        with self.assertRaises(ValidationError):
            result.retry.attempt = 2
        with self.assertRaises(ValidationError):
            result.provenance.operation = "document.other"

    def test_json_round_trip(self) -> None:
        original = StepResult.model_validate(result_payload("partial"))
        restored = StepResult.model_validate(json.loads(original.model_dump_json()))
        self.assertEqual(restored, original)


class SchemaTests(unittest.TestCase):
    """JSON Schema artifact behavior."""

    def setUp(self) -> None:
        self.schema = StepResult.model_json_schema()
        self.raw_text = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.committed = json.loads(self.raw_text)

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:step-result:1.0.0")
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_root_schema_closed(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])

    def test_all_nested_schemas_closed(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(model=name):
                self.assertFalse(definition["additionalProperties"])

    def test_committed_schema_matches_generated_schema(self) -> None:
        self.assertEqual(self.committed, self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        self.assertTrue(self.raw_text.endswith("\n"))

    def test_exact_status_catalog_in_schema(self) -> None:
        self.assertEqual(
            self.schema["properties"]["status"]["enum"],
            ["success", "partial", "failed"],
        )

    def test_error_code_catalog_represented(self) -> None:
        failure = self.schema["properties"]["failure_code"]
        codes = [option["enum"] for option in failure["anyOf"] if "enum" in option]
        self.assertEqual(codes, [list(ERROR_CODES)])

    def test_forbidden_property_names_absent_from_schema(self) -> None:
        declared: set[str] = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            declared.update(definition["properties"])
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, declared)

    def test_nested_models_contain_no_schema_version(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(model=name):
                self.assertNotIn("schema_version", definition["properties"])


class ExportTests(unittest.TestCase):
    """Package export behavior."""

    def test_public_exports_available(self) -> None:
        expected = {
            "StepEvidenceRef",
            "StepProvenance",
            "StepResult",
            "StepRetryMetadata",
            "StepStatus",
            "StepTypedOutputRef",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_private_aliases_not_exported(self) -> None:
        for name in ("_CanonicalCode", "_OpaqueRef", "_Sha256Digest", "_Uuid4", "_AttemptCount"):
            with self.subTest(name=name):
                self.assertNotIn(name, contracts.__all__)
                self.assertFalse(hasattr(contracts, name))


CODE_STRATEGY = st.from_regex(r"\A[a-z][a-z0-9._:-]{0,8}\Z")


class StepResultPropertyTests(unittest.TestCase):
    """Bounded property-based checks."""

    @given(fact_ids=st.lists(CODE_STRATEGY, min_size=1, max_size=16, unique=True))
    def test_unique_output_tuples_preserve_order(self, fact_ids: list[str]) -> None:
        outputs = [output_payload(fact_id=fact_id) for fact_id in fact_ids]
        result = StepResult.model_validate(result_payload(typed_outputs=outputs, evidence_refs=[]))
        self.assertEqual([output.fact_id for output in result.typed_outputs], fact_ids)

    @given(fact_ids=st.lists(CODE_STRATEGY, min_size=1, max_size=8, unique=True))
    def test_duplicate_output_fact_rejected(self, fact_ids: list[str]) -> None:
        outputs = [output_payload(fact_id=fact_id) for fact_id in fact_ids]
        outputs.append(output_payload(fact_id=fact_ids[0]))
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(typed_outputs=outputs, evidence_refs=[]))

    @given(
        fact_ids=st.lists(CODE_STRATEGY, min_size=1, max_size=8, unique=True),
        evidence_count=st.integers(min_value=0, max_value=8),
    )
    def test_evidence_support_round_trip(self, fact_ids: list[str], evidence_count: int) -> None:
        outputs = [output_payload(fact_id=fact_id) for fact_id in fact_ids]
        references = [
            evidence_payload(
                evidence_id=f"{index:08x}-1111-4111-8111-111111111111",
                supports_fact_ids=[fact_ids[index % len(fact_ids)]],
            )
            for index in range(evidence_count)
        ]
        result = StepResult.model_validate(
            result_payload(typed_outputs=outputs, evidence_refs=references)
        )
        self.assertEqual(len(result.evidence_refs), evidence_count)
        produced = {output.fact_id for output in result.typed_outputs}
        for reference in result.evidence_refs:
            self.assertTrue(set(reference.supports_fact_ids).issubset(produced))

    @given(attempt=st.integers(min_value=1, max_value=2))
    def test_bounded_retry_metadata_round_trip(self, attempt: int) -> None:
        previous = PREVIOUS_RESULT_ID if attempt == 2 else None
        payload = retry_payload(
            attempt=attempt, max_attempts=2, retryable=attempt < 2, previous_result_id=previous
        )
        retry = StepRetryMetadata.model_validate(payload)
        restored = StepRetryMetadata.model_validate(json.loads(retry.model_dump_json()))
        self.assertEqual(restored, retry)
        self.assertLessEqual(retry.attempt, retry.max_attempts)

    @given(field=st.sampled_from(FORBIDDEN_FIELDS))
    def test_sampled_forbidden_fields_rejected(self, field: str) -> None:
        with self.assertRaises(ValidationError):
            StepResult.model_validate(result_payload(**{field: "forbidden"}))
        output = output_payload()
        output[field] = "forbidden"
        with self.assertRaises(ValidationError):
            StepTypedOutputRef.model_validate(output)


if __name__ == "__main__":
    unittest.main()
