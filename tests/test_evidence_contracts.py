"""Tests for the evidence and evidence bundle contracts."""

import importlib.util
import json
import unittest
import warnings
from collections.abc import Sequence
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.evidence import (
    EVIDENCE_SCHEMA_ID,
    EVIDENCE_SCHEMA_VERSION,
    AllowedEvidenceClaim,
    DocumentEvidence,
    Evidence,
    EvidenceBundle,
    EvidenceConflict,
    EvidenceProvenance,
    EvidenceSecurityScope,
    EvidenceSourceRef,
    EvidenceSourceTime,
    EvidenceSubjectRef,
    EvidenceValidityWindow,
    FactEvidenceMapEntry,
    ProhibitedEvidenceClaim,
    RejectedEvidenceRef,
    RuleEvidence,
    SelectorEvidence,
    SqlEvidence,
    WebEvidence,
)

BUNDLE_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
ROUTE_DECISION_ID = "33333333-3333-4333-8333-333333333333"
PLAN_ID = "44444444-4444-4444-8444-444444444444"
AUTHORIZATION_DECISION_ID = "55555555-5555-4555-8555-555555555555"
RUNTIME_SNAPSHOT_ID = "66666666-6666-4666-8666-666666666666"
CORRELATION_ID = "77777777-7777-4777-8777-777777777777"
STEP_RESULT_ID = "88888888-8888-4888-8888-888888888888"
CONFLICT_ID = "99999999-9999-4999-8999-999999999999"
OTHER_CONFLICT_ID = "9a999999-9999-4999-8999-999999999999"
UUID1_VALUE = "aaaaaaaa-aaaa-1aaa-8aaa-aaaaaaaaaaaa"

DOCUMENT_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000001"
SQL_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000002"
SELECTOR_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000003"
RULE_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000004"
WEB_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000005"
SECOND_DOCUMENT_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000006"
UNKNOWN_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000099"

DIGEST_A = "0123456789abcdef" * 4
DIGEST_B = "fedcba9876543210" * 4

OBSERVED_AT = "2026-01-01T12:00:00+00:00"
PUBLISHED_AT = "2025-12-31T12:00:00+00:00"
AS_OF = "2026-01-01T12:00:00+00:00"
VALID_FROM = "2025-12-01T00:00:00+00:00"
VALID_TO = "2026-02-01T00:00:00+00:00"
BUILT_AT = "2026-01-01T12:00:00+00:00"
OFFSET_TIMESTAMP = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC_HOUR = 8
NAIVE_TIMESTAMP = "2026-01-01T12:00:00"

FACT_ALPHA = "fact.alpha"
FACT_BETA = "fact.beta"
FACT_GAMMA = "fact.gamma"

SCHEMA_ARTIFACT = Path(__file__).resolve().parents[1] / "schemas" / "evidence" / "1.0.0.schema.json"
MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "contracts" / "evidence.py"
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
    "text",
    "excerpt",
    "body",
    "json",
    "rows",
    "row",
    "documents",
    "document_text",
    "chunks",
    "snippet",
    "snippets",
    "html",
    "sql",
    "statement",
    "query",
    "where",
    "predicate",
    "table",
    "column",
    "join",
    "tool",
    "tool_name",
    "tool_arguments",
    "function_call",
    "endpoint",
    "url",
    "uri",
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
    "rationale_text",
    "reasoning",
    "chain_of_thought",
    "answer",
    "answer_text",
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
    "traceparent",
    "span_id",
    "vendor_trace_id",
)

EVIDENCE_ADAPTER: TypeAdapter[Evidence] = TypeAdapter(Evidence)


def subject_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_type": "subject.employee",
        "subject_ref": "subject:7c1f",
    }
    payload.update(overrides)
    return payload


def validity_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"as_of": AS_OF}
    payload.update(overrides)
    return payload


def source_time_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"observed_at": OBSERVED_AT}
    payload.update(overrides)
    return payload


def source_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_type": "source.policy-library",
        "source_ref": "source:2b9d",
        "source_version": "source-version:5",
    }
    payload.update(overrides)
    return payload


def scope_payload(data_scope: str = "general", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "scope_ref": "scope:general",
        "data_scope": data_scope,
        "classification": "classification.internal",
    }
    payload.update(overrides)
    return payload


def provenance_payload(
    capability: str = "document_retrieval", **overrides: object
) -> dict[str, object]:
    payload: dict[str, object] = {
        "step_result_id": STEP_RESULT_ID,
        "plan_id": PLAN_ID,
        "step_id": "step.retrieve",
        "capability": capability,
        "operation": "document.retrieve",
        "materializer_version": "1.0.0",
        "input_digest": DIGEST_B,
    }
    payload.update(overrides)
    return payload


def common_payload(
    evidence_id: str,
    capability: str,
    data_scope: str,
    supports: Sequence[str] = (FACT_ALPHA,),
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": evidence_id,
        "subject": subject_payload(),
        "valid_time": validity_payload(),
        "source_time": source_time_payload(),
        "source": source_payload(),
        "authority": "authority.official",
        "security_scope": scope_payload(data_scope),
        "validation_status": "validated",
        "freshness": "current",
        "provenance": provenance_payload(capability),
        "allowed_uses": ["claim_support"],
        "retention_class": "retention.standard",
        "supports_fact_ids": list(supports),
    }
    payload.update(overrides)
    return payload


def document_payload(
    evidence_id: str = DOCUMENT_EVIDENCE_ID,
    supports: Sequence[str] = (FACT_ALPHA,),
    **overrides: object,
) -> dict[str, object]:
    payload = common_payload(evidence_id, "document_retrieval", "general", supports)
    payload.update(
        {
            "evidence_type": "document",
            "document_ref": "document:41ab",
            "document_version": "document-version:3",
            "chunk_ref": "chunk:9",
            "locator_ref": "locator:page-4",
            "content_ref": "content:8f21",
            "content_sha256": DIGEST_A,
        }
    )
    payload.update(overrides)
    return payload


def sql_payload(
    evidence_id: str = SQL_EVIDENCE_ID,
    supports: Sequence[str] = (FACT_ALPHA,),
    **overrides: object,
) -> dict[str, object]:
    payload = common_payload(evidence_id, "semantic_analytics", "general", supports)
    payload.update(
        {
            "evidence_type": "sql",
            "semantic_query_ref": "semantic-query:22",
            "semantic_catalog_version": "2.1.0",
            "result_ref": "result:77",
            "result_sha256": DIGEST_A,
            "metric_codes": ["metric.headcount"],
            "result_shape": "shape.scalar",
            "suppression_applied": False,
        }
    )
    payload.update(overrides)
    return payload


def selector_payload(
    evidence_id: str = SELECTOR_EVIDENCE_ID,
    supports: Sequence[str] = (FACT_ALPHA,),
    **overrides: object,
) -> dict[str, object]:
    payload = common_payload(evidence_id, "personal_selector", "personal", supports)
    payload.update(
        {
            "evidence_type": "selector",
            "selector_ref": "selector:leave-balance",
            "result_ref": "result:13",
            "result_sha256": DIGEST_A,
            "field_codes": ["field.balance"],
        }
    )
    payload.update(overrides)
    return payload


def rule_payload(
    evidence_id: str = RULE_EVIDENCE_ID,
    supports: Sequence[str] = (FACT_ALPHA,),
    inputs: Sequence[str] = (DOCUMENT_EVIDENCE_ID,),
    **overrides: object,
) -> dict[str, object]:
    payload = common_payload(evidence_id, "rule_evaluator", "general", supports)
    payload.update(
        {
            "evidence_type": "rule",
            "rule_bundle_ref": "rule-bundle:leave",
            "rule_code": "rule.leave-eligibility",
            "rule_version": "1.2.0",
            "outcome_ref": "outcome:5",
            "outcome_sha256": DIGEST_A,
            "input_evidence_ids": list(inputs),
        }
    )
    payload.update(overrides)
    return payload


def web_payload(
    evidence_id: str = WEB_EVIDENCE_ID,
    supports: Sequence[str] = (FACT_ALPHA,),
    **overrides: object,
) -> dict[str, object]:
    payload = common_payload(evidence_id, "official_search", "general", supports)
    payload.update(
        {
            "evidence_type": "web",
            "page_ref": "page:0a3c",
            "allowlist_ref": "allowlist:official",
            "locator_ref": "locator:section-2",
            "content_ref": "content:1d4e",
            "content_sha256": DIGEST_A,
        }
    )
    payload.update(overrides)
    return payload


def claim_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "claim_id": "claim.alpha",
        "claim_code": "claim-code.policy-statement",
        "claim_type": "claim-type.factual",
        "subject": subject_payload(),
        "supporting_fact_ids": [FACT_ALPHA],
        "evidence_ids": [DOCUMENT_EVIDENCE_ID],
    }
    payload.update(overrides)
    return payload


def fact_map_payload(
    fact_id: str = FACT_ALPHA,
    evidence_ids: Sequence[str] = (DOCUMENT_EVIDENCE_ID,),
) -> dict[str, object]:
    return {"fact_id": fact_id, "evidence_ids": list(evidence_ids)}


def bundle_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "bundle_id": BUNDLE_ID,
        "request_id": REQUEST_ID,
        "route_decision_id": ROUTE_DECISION_ID,
        "plan_id": PLAN_ID,
        "authorization_decision_id": AUTHORIZATION_DECISION_ID,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "correlation_id": CORRELATION_ID,
        "built_at": BUILT_AT,
        "required_fact_ids": [FACT_ALPHA],
        "accepted_evidence": [document_payload()],
        "fact_map": [fact_map_payload()],
        "sufficient": True,
        "decision": "answer",
        "allowed_claims": [claim_payload()],
        "decision_reason_codes": ["coverage.complete"],
        "evidence_manager_version": "1.0.0",
    }
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    def test_default_schema_version(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        self.assertEqual(bundle.schema_version, "1.0.0")
        self.assertEqual(EVIDENCE_SCHEMA_VERSION, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(schema_version="1.1.0"))

    def test_schema_version_is_a_model_field(self) -> None:
        self.assertIn("schema_version", EvidenceBundle.model_fields)
        dumped = EvidenceBundle.model_validate(bundle_payload()).model_dump()
        self.assertIn("schema_version", dumped)

    def test_module_definition_emits_no_schema_version_warning(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            spec = importlib.util.spec_from_file_location("evidence_reload", MODULE_PATH)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        messages = [str(item.message) for item in caught]
        self.assertEqual([message for message in messages if "schema_version" in message], [])

    def test_nested_models_have_no_schema_version(self) -> None:
        nested = (
            EvidenceSubjectRef,
            EvidenceValidityWindow,
            EvidenceSourceTime,
            EvidenceSourceRef,
            EvidenceSecurityScope,
            EvidenceProvenance,
            DocumentEvidence,
            SqlEvidence,
            SelectorEvidence,
            RuleEvidence,
            WebEvidence,
            RejectedEvidenceRef,
            FactEvidenceMapEntry,
            EvidenceConflict,
            AllowedEvidenceClaim,
            ProhibitedEvidenceClaim,
        )
        for model in nested:
            with self.subTest(model=model.__name__):
                self.assertNotIn("schema_version", model.model_fields)


class SubjectRefTests(unittest.TestCase):
    def test_valid_subject(self) -> None:
        subject = EvidenceSubjectRef.model_validate(subject_payload())
        self.assertEqual(subject.subject_type, "subject.employee")
        self.assertEqual(subject.subject_ref, "subject:7c1f")

    def test_invalid_subject_type_rejected(self) -> None:
        for value in ("Subject", "1subject", "subject type", ""):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                EvidenceSubjectRef.model_validate(subject_payload(subject_type=value))

    def test_blank_subject_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSubjectRef.model_validate(subject_payload(subject_ref="   "))

    def test_padded_subject_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSubjectRef.model_validate(subject_payload(subject_ref=" subject:7c1f "))

    def test_nul_subject_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSubjectRef.model_validate(subject_payload(subject_ref="subject\x007c1f"))

    def test_oversized_subject_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSubjectRef.model_validate(subject_payload(subject_ref="s" * 257))

    def test_subject_reference_preserved(self) -> None:
        raw = "subject:Mixed_Case/7c1f-2B"
        subject = EvidenceSubjectRef.model_validate(subject_payload(subject_ref=raw))
        self.assertEqual(subject.subject_ref, raw)


class ValidityWindowTests(unittest.TestCase):
    def test_valid_open_window(self) -> None:
        window = EvidenceValidityWindow.model_validate(validity_payload())
        self.assertIsNone(window.valid_from)
        self.assertIsNone(window.valid_to)

    def test_valid_bounded_window(self) -> None:
        window = EvidenceValidityWindow.model_validate(
            validity_payload(valid_from=VALID_FROM, valid_to=VALID_TO)
        )
        self.assertIsNotNone(window.valid_from)
        self.assertIsNotNone(window.valid_to)

    def test_valid_from_after_valid_to_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceValidityWindow.model_validate(
                validity_payload(valid_from=VALID_TO, valid_to=VALID_FROM)
            )

    def test_as_of_before_valid_from_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceValidityWindow.model_validate(
                validity_payload(as_of=VALID_FROM, valid_from=AS_OF, valid_to=VALID_TO)
            )

    def test_as_of_after_valid_to_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceValidityWindow.model_validate(
                validity_payload(as_of=VALID_TO, valid_from=VALID_FROM, valid_to=AS_OF)
            )

    def test_naive_timestamps_rejected(self) -> None:
        for field in ("as_of", "valid_from", "valid_to"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceValidityWindow.model_validate(validity_payload(**{field: NAIVE_TIMESTAMP}))

    def test_non_utc_timestamp_normalized(self) -> None:
        window = EvidenceValidityWindow.model_validate(validity_payload(as_of=OFFSET_TIMESTAMP))
        self.assertEqual(window.as_of.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(window.as_of.utcoffset().total_seconds(), 0.0)


class SourceTests(unittest.TestCase):
    def test_valid_source_time(self) -> None:
        source_time = EvidenceSourceTime.model_validate(
            source_time_payload(published_at=PUBLISHED_AT)
        )
        self.assertIsNotNone(source_time.published_at)

    def test_published_after_observed_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSourceTime.model_validate(
                source_time_payload(observed_at=PUBLISHED_AT, published_at=OBSERVED_AT)
            )

    def test_naive_source_time_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSourceTime.model_validate(source_time_payload(observed_at=NAIVE_TIMESTAMP))

    def test_valid_source_reference(self) -> None:
        source = EvidenceSourceRef.model_validate(source_payload())
        self.assertEqual(source.source_type, "source.policy-library")
        self.assertEqual(source.source_version, "source-version:5")

    def test_invalid_source_reference_rejected(self) -> None:
        for override in ({"source_type": "Source"}, {"source_ref": ""}, {"source_version": " x"}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                EvidenceSourceRef.model_validate(source_payload(**override))


class SecurityScopeTests(unittest.TestCase):
    def test_valid_security_scope(self) -> None:
        scope = EvidenceSecurityScope.model_validate(scope_payload())
        self.assertEqual(scope.data_scope, "general")
        self.assertEqual(scope.classification, "classification.internal")

    def test_both_data_scopes_accepted(self) -> None:
        for value in ("general", "personal"):
            with self.subTest(value=value):
                scope = EvidenceSecurityScope.model_validate(scope_payload(value))
                self.assertEqual(scope.data_scope, value)

    def test_unsupported_data_scope_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceSecurityScope.model_validate(scope_payload("confidential"))


class ProvenanceTests(unittest.TestCase):
    def test_valid_provenance(self) -> None:
        provenance = EvidenceProvenance.model_validate(provenance_payload())
        self.assertEqual(provenance.capability, "document_retrieval")
        self.assertEqual(provenance.materializer_version, "1.0.0")

    def test_unsupported_capability_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceProvenance.model_validate(provenance_payload("vector_search"))

    def test_invalid_operation_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceProvenance.model_validate(provenance_payload(operation="Document.Retrieve"))

    def test_invalid_materializer_version_rejected(self) -> None:
        for value in ("1.0", "v1.0.0", "1.0.0-rc1"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                EvidenceProvenance.model_validate(provenance_payload(materializer_version=value))

    def test_invalid_input_digest_rejected(self) -> None:
        for value in (DIGEST_A.upper(), DIGEST_A[:63], "z" * 64, ""):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                EvidenceProvenance.model_validate(provenance_payload(input_digest=value))

    def test_valid_lowercase_digest_accepted(self) -> None:
        provenance = EvidenceProvenance.model_validate(provenance_payload(input_digest=DIGEST_A))
        self.assertEqual(provenance.input_digest, DIGEST_A)

    def test_uuid4_enforced_for_provenance_identifiers(self) -> None:
        for field in ("step_result_id", "plan_id"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceProvenance.model_validate(provenance_payload(**{field: UUID1_VALUE}))


class DocumentEvidenceTests(unittest.TestCase):
    def test_valid_document_evidence(self) -> None:
        evidence = DocumentEvidence.model_validate(document_payload())
        self.assertEqual(evidence.evidence_type, "document")
        self.assertIsNone(evidence.ranking_score)
        self.assertEqual(evidence.content_sha256, DIGEST_A)

    def test_document_requires_document_retrieval_provenance(self) -> None:
        evidence = DocumentEvidence.model_validate(document_payload())
        self.assertEqual(evidence.provenance.capability, "document_retrieval")

    def test_document_rejects_wrong_capability(self) -> None:
        payload = document_payload(provenance=provenance_payload("semantic_analytics"))
        with self.assertRaises(ValidationError):
            DocumentEvidence.model_validate(payload)

    def test_ranking_score_bounds_accepted(self) -> None:
        for value in (0.0, 0.5, 1.0):
            with self.subTest(value=value):
                evidence = DocumentEvidence.model_validate(document_payload(ranking_score=value))
                self.assertEqual(evidence.ranking_score, value)

    def test_ranking_score_out_of_range_rejected(self) -> None:
        for value in (-0.1, 1.1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DocumentEvidence.model_validate(document_payload(ranking_score=value))

    def test_document_evidence_immutable(self) -> None:
        evidence = DocumentEvidence.model_validate(document_payload())
        with self.assertRaises(ValidationError):
            evidence.document_ref = "document:other"


class SqlEvidenceTests(unittest.TestCase):
    def test_valid_sql_evidence(self) -> None:
        evidence = SqlEvidence.model_validate(sql_payload())
        self.assertEqual(evidence.evidence_type, "sql")
        self.assertEqual(evidence.filter_codes, ())
        self.assertFalse(evidence.suppression_applied)

    def test_sql_requires_semantic_analytics_provenance(self) -> None:
        payload = sql_payload(provenance=provenance_payload("document_retrieval"))
        with self.assertRaises(ValidationError):
            SqlEvidence.model_validate(payload)

    def test_sql_requires_general_scope(self) -> None:
        payload = sql_payload(security_scope=scope_payload("personal"))
        with self.assertRaises(ValidationError):
            SqlEvidence.model_validate(payload)

    def test_metric_codes_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            SqlEvidence.model_validate(sql_payload(metric_codes=[]))

    def test_duplicate_metric_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            SqlEvidence.model_validate(
                sql_payload(metric_codes=["metric.headcount", "metric.headcount"])
            )

    def test_filter_code_order_preserved(self) -> None:
        codes = ["filter.region", "filter.department", "filter.year"]
        evidence = SqlEvidence.model_validate(sql_payload(filter_codes=codes))
        self.assertEqual(list(evidence.filter_codes), codes)


class SelectorEvidenceTests(unittest.TestCase):
    def test_valid_selector_evidence(self) -> None:
        evidence = SelectorEvidence.model_validate(selector_payload())
        self.assertEqual(evidence.evidence_type, "selector")
        self.assertEqual(evidence.security_scope.data_scope, "personal")

    def test_selector_requires_personal_selector_provenance(self) -> None:
        payload = selector_payload(provenance=provenance_payload("official_search"))
        with self.assertRaises(ValidationError):
            SelectorEvidence.model_validate(payload)

    def test_selector_requires_personal_scope(self) -> None:
        payload = selector_payload(security_scope=scope_payload("general"))
        with self.assertRaises(ValidationError):
            SelectorEvidence.model_validate(payload)

    def test_field_codes_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            SelectorEvidence.model_validate(selector_payload(field_codes=[]))


class RuleEvidenceTests(unittest.TestCase):
    def test_valid_rule_evidence(self) -> None:
        evidence = RuleEvidence.model_validate(rule_payload())
        self.assertEqual(evidence.evidence_type, "rule")
        self.assertEqual(evidence.rule_version, "1.2.0")

    def test_rule_requires_rule_evaluator_provenance(self) -> None:
        payload = rule_payload(provenance=provenance_payload("document_retrieval"))
        with self.assertRaises(ValidationError):
            RuleEvidence.model_validate(payload)

    def test_rule_rejects_self_input(self) -> None:
        payload = rule_payload(inputs=[RULE_EVIDENCE_ID])
        with self.assertRaises(ValidationError):
            RuleEvidence.model_validate(payload)

    def test_duplicate_rule_inputs_rejected(self) -> None:
        payload = rule_payload(inputs=[DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID])
        with self.assertRaises(ValidationError):
            RuleEvidence.model_validate(payload)

    def test_rule_inputs_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            RuleEvidence.model_validate(rule_payload(inputs=[]))


class WebEvidenceTests(unittest.TestCase):
    def test_valid_web_evidence(self) -> None:
        evidence = WebEvidence.model_validate(web_payload())
        self.assertEqual(evidence.evidence_type, "web")
        self.assertEqual(evidence.allowlist_ref, "allowlist:official")

    def test_web_requires_official_search_provenance(self) -> None:
        payload = web_payload(provenance=provenance_payload("document_retrieval"))
        with self.assertRaises(ValidationError):
            WebEvidence.model_validate(payload)

    def test_web_requires_general_scope(self) -> None:
        payload = web_payload(security_scope=scope_payload("personal"))
        with self.assertRaises(ValidationError):
            WebEvidence.model_validate(payload)


class VariantCatalogTests(unittest.TestCase):
    def test_every_evidence_type_accepted(self) -> None:
        builders = {
            "document": document_payload(),
            "sql": sql_payload(),
            "selector": selector_payload(),
            "rule": rule_payload(),
            "web": web_payload(),
        }
        for evidence_type, payload in builders.items():
            with self.subTest(evidence_type=evidence_type):
                evidence = EVIDENCE_ADAPTER.validate_python(payload)
                self.assertEqual(evidence.evidence_type, evidence_type)

    def test_unsupported_evidence_type_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EVIDENCE_ADAPTER.validate_python(document_payload(evidence_type="graph"))

    def test_every_validation_status_accepted(self) -> None:
        for value in ("validated", "degraded"):
            with self.subTest(value=value):
                payload = document_payload(validation_status=value)
                evidence = DocumentEvidence.model_validate(payload)
                self.assertEqual(evidence.validation_status, value)

    def test_unsupported_validation_status_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentEvidence.model_validate(document_payload(validation_status="rejected"))

    def test_every_freshness_accepted(self) -> None:
        for value in ("current", "stale", "unknown"):
            with self.subTest(value=value):
                evidence = DocumentEvidence.model_validate(document_payload(freshness=value))
                self.assertEqual(evidence.freshness, value)

    def test_unsupported_freshness_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentEvidence.model_validate(document_payload(freshness="fresh"))

    def test_allowed_uses_rules(self) -> None:
        evidence = DocumentEvidence.model_validate(
            document_payload(allowed_uses=["claim_support", "citation"])
        )
        self.assertEqual(list(evidence.allowed_uses), ["claim_support", "citation"])
        oversized = ["use." + str(index) for index in range(9)]
        for value in ([], ["claim_support", "claim_support"], oversized):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DocumentEvidence.model_validate(document_payload(allowed_uses=value))

    def test_supports_fact_rules(self) -> None:
        for value in ([], [FACT_ALPHA, FACT_ALPHA], [f"fact.item{index}" for index in range(17)]):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                DocumentEvidence.model_validate(document_payload(supports_fact_ids=value))

    def test_every_variant_rejects_raw_and_locator_fields(self) -> None:
        builders = (
            (DocumentEvidence, document_payload),
            (SqlEvidence, sql_payload),
            (SelectorEvidence, selector_payload),
            (RuleEvidence, rule_payload),
            (WebEvidence, web_payload),
        )
        injected = ("content", "text", "rows", "sql", "html", "url", "uri", "path", "bucket")
        for model, builder in builders:
            for field in injected:
                with self.subTest(model=model.__name__, field=field):
                    with self.assertRaises(ValidationError):
                        model.model_validate(builder(**{field: "injected"}))

    def test_variant_uuid4_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            DocumentEvidence.model_validate(document_payload(evidence_id=UUID1_VALUE))


class RejectedEvidenceTests(unittest.TestCase):
    def test_valid_rejected_reference(self) -> None:
        reference = RejectedEvidenceRef.model_validate(
            {
                "evidence_id": UNKNOWN_EVIDENCE_ID,
                "evidence_type": "web",
                "reason_codes": ["reason.not-allowlisted"],
            }
        )
        self.assertEqual(reference.evidence_type, "web")
        self.assertEqual(list(reference.reason_codes), ["reason.not-allowlisted"])

    def test_rejected_reference_requires_reason(self) -> None:
        with self.assertRaises(ValidationError):
            RejectedEvidenceRef.model_validate(
                {
                    "evidence_id": UNKNOWN_EVIDENCE_ID,
                    "evidence_type": "web",
                    "reason_codes": [],
                }
            )

    def test_duplicate_rejection_reasons_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RejectedEvidenceRef.model_validate(
                {
                    "evidence_id": UNKNOWN_EVIDENCE_ID,
                    "evidence_type": "web",
                    "reason_codes": ["reason.stale", "reason.stale"],
                }
            )

    def test_rejected_reference_requires_uuid4(self) -> None:
        with self.assertRaises(ValidationError):
            RejectedEvidenceRef.model_validate(
                {
                    "evidence_id": UUID1_VALUE,
                    "evidence_type": "web",
                    "reason_codes": ["reason.stale"],
                }
            )


class FactMapEntryTests(unittest.TestCase):
    def test_valid_entry(self) -> None:
        entry = FactEvidenceMapEntry.model_validate(fact_map_payload())
        self.assertEqual(entry.fact_id, FACT_ALPHA)
        self.assertEqual(len(entry.evidence_ids), 1)

    def test_entry_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            FactEvidenceMapEntry.model_validate(fact_map_payload(evidence_ids=[]))

    def test_entry_rejects_duplicate_evidence(self) -> None:
        duplicated = [DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID]
        with self.assertRaises(ValidationError):
            FactEvidenceMapEntry.model_validate(fact_map_payload(evidence_ids=duplicated))


def conflict_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "conflict_id": CONFLICT_ID,
        "fact_id": FACT_ALPHA,
        "evidence_ids": [DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID],
        "status": "unresolved",
    }
    payload.update(overrides)
    return payload


def resolved_conflict_payload(**overrides: object) -> dict[str, object]:
    payload = conflict_payload(
        status="resolved",
        resolution_code="resolution.newer-source",
        controlling_evidence_id=DOCUMENT_EVIDENCE_ID,
    )
    payload.update(overrides)
    return payload


class ConflictTests(unittest.TestCase):
    def test_valid_unresolved_conflict(self) -> None:
        conflict = EvidenceConflict.model_validate(conflict_payload())
        self.assertEqual(conflict.status, "unresolved")
        self.assertIsNone(conflict.resolution_code)
        self.assertIsNone(conflict.controlling_evidence_id)

    def test_unresolved_conflict_rejects_resolution_fields(self) -> None:
        overrides = (
            {"resolution_code": "resolution.newer-source"},
            {"controlling_evidence_id": DOCUMENT_EVIDENCE_ID},
        )
        for override in overrides:
            with self.subTest(override=override), self.assertRaises(ValidationError):
                EvidenceConflict.model_validate(conflict_payload(**override))

    def test_valid_resolved_conflict(self) -> None:
        conflict = EvidenceConflict.model_validate(resolved_conflict_payload())
        self.assertEqual(conflict.status, "resolved")
        self.assertEqual(conflict.resolution_code, "resolution.newer-source")

    def test_resolved_conflict_requires_resolution_code(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceConflict.model_validate(resolved_conflict_payload(resolution_code=None))

    def test_resolved_conflict_requires_controlling_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceConflict.model_validate(resolved_conflict_payload(controlling_evidence_id=None))

    def test_controlling_evidence_must_belong_to_conflict(self) -> None:
        payload = resolved_conflict_payload(controlling_evidence_id=UNKNOWN_EVIDENCE_ID)
        with self.assertRaises(ValidationError):
            EvidenceConflict.model_validate(payload)

    def test_conflict_requires_two_evidence_identifiers(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceConflict.model_validate(conflict_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID]))

    def test_duplicate_conflict_evidence_rejected(self) -> None:
        duplicated = [DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID]
        with self.assertRaises(ValidationError):
            EvidenceConflict.model_validate(conflict_payload(evidence_ids=duplicated))


class ClaimTests(unittest.TestCase):
    def test_valid_allowed_claim(self) -> None:
        claim = AllowedEvidenceClaim.model_validate(claim_payload())
        self.assertEqual(claim.claim_id, "claim.alpha")
        self.assertEqual(list(claim.supporting_fact_ids), [FACT_ALPHA])

    def test_allowed_claim_requires_facts(self) -> None:
        with self.assertRaises(ValidationError):
            AllowedEvidenceClaim.model_validate(claim_payload(supporting_fact_ids=[]))

    def test_allowed_claim_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            AllowedEvidenceClaim.model_validate(claim_payload(evidence_ids=[]))

    def test_allowed_claim_rejects_prose(self) -> None:
        for field in ("claim_text", "statement", "explanation", "reasoning"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                AllowedEvidenceClaim.model_validate(claim_payload(**{field: "text"}))

    def test_valid_prohibited_claim(self) -> None:
        claim = ProhibitedEvidenceClaim.model_validate(
            {"claim_code": "claim-code.salary", "reason_codes": ["reason.unauthorized"]}
        )
        self.assertEqual(claim.claim_code, "claim-code.salary")

    def test_prohibited_claim_requires_reason(self) -> None:
        with self.assertRaises(ValidationError):
            ProhibitedEvidenceClaim.model_validate(
                {"claim_code": "claim-code.salary", "reason_codes": []}
            )


def partial_missing_bundle() -> dict[str, object]:
    return bundle_payload(
        required_fact_ids=[FACT_ALPHA, FACT_BETA],
        missing_fact_ids=[FACT_BETA],
        sufficient=False,
        decision="partial_answer",
        decision_reason_codes=["coverage.partial"],
    )


def conflict_bundle(**overrides: object) -> dict[str, object]:
    payload = bundle_payload(
        accepted_evidence=[
            document_payload(),
            document_payload(SECOND_DOCUMENT_EVIDENCE_ID),
        ],
        fact_map=[
            fact_map_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID])
        ],
        conflicts=[conflict_payload()],
        sufficient=False,
        decision="partial_answer",
        decision_reason_codes=["conflict.unresolved"],
    )
    payload.update(overrides)
    return payload


def clarify_bundle(**overrides: object) -> dict[str, object]:
    payload = bundle_payload(
        accepted_evidence=[],
        fact_map=[],
        missing_fact_ids=[FACT_ALPHA],
        sufficient=False,
        decision="clarify",
        allowed_claims=[],
        decision_reason_codes=["clarification.required"],
    )
    payload.update(overrides)
    return payload


class ValidBundleTests(unittest.TestCase):
    def test_valid_answer_bundle(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        self.assertTrue(bundle.sufficient)
        self.assertEqual(bundle.decision, "answer")
        self.assertEqual(len(bundle.allowed_claims), 1)

    def test_valid_partial_bundle_with_missing_fact(self) -> None:
        bundle = EvidenceBundle.model_validate(partial_missing_bundle())
        self.assertFalse(bundle.sufficient)
        self.assertEqual(list(bundle.missing_fact_ids), [FACT_BETA])

    def test_valid_partial_bundle_with_unresolved_conflict(self) -> None:
        bundle = EvidenceBundle.model_validate(conflict_bundle())
        self.assertEqual(bundle.decision, "partial_answer")
        self.assertEqual(bundle.conflicts[0].status, "unresolved")

    def test_valid_partial_bundle_with_degraded_evidence(self) -> None:
        payload = bundle_payload(
            accepted_evidence=[document_payload(validation_status="degraded")],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["evidence.degraded"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(bundle.accepted_evidence[0].validation_status, "degraded")

    def test_valid_partial_bundle_with_stale_evidence(self) -> None:
        payload = bundle_payload(
            accepted_evidence=[document_payload(freshness="stale")],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["evidence.stale"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(bundle.accepted_evidence[0].freshness, "stale")

    def test_valid_clarify_bundle(self) -> None:
        bundle = EvidenceBundle.model_validate(clarify_bundle())
        self.assertEqual(bundle.decision, "clarify")
        self.assertEqual(bundle.allowed_claims, ())

    def test_valid_abstain_bundle_without_evidence(self) -> None:
        payload = clarify_bundle(decision="abstain", decision_reason_codes=["evidence.absent"])
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(bundle.decision, "abstain")
        self.assertEqual(bundle.accepted_evidence, ())

    def test_valid_abstain_bundle_with_unresolved_conflict(self) -> None:
        payload = conflict_bundle(
            decision="abstain",
            allowed_claims=[],
            decision_reason_codes=["conflict.unresolved"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(bundle.decision, "abstain")

    def test_bundle_with_every_variant(self) -> None:
        facts = [FACT_ALPHA, FACT_BETA, FACT_GAMMA, "fact.delta", "fact.epsilon"]
        accepted = [
            document_payload(supports=[FACT_ALPHA]),
            sql_payload(supports=[FACT_BETA]),
            selector_payload(supports=[FACT_GAMMA]),
            rule_payload(supports=["fact.delta"]),
            web_payload(supports=["fact.epsilon"]),
        ]
        identifiers = [
            DOCUMENT_EVIDENCE_ID,
            SQL_EVIDENCE_ID,
            SELECTOR_EVIDENCE_ID,
            RULE_EVIDENCE_ID,
            WEB_EVIDENCE_ID,
        ]
        payload = bundle_payload(
            required_fact_ids=facts,
            accepted_evidence=accepted,
            fact_map=[
                fact_map_payload(fact, [identifier])
                for fact, identifier in zip(facts, identifiers, strict=True)
            ],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.accepted_evidence), 5)
        types = [item.evidence_type for item in bundle.accepted_evidence]
        self.assertEqual(types, ["document", "sql", "selector", "rule", "web"])


class BundleIdentifierTests(unittest.TestCase):
    def test_uuid4_enforced_for_every_identifier(self) -> None:
        fields = (
            "bundle_id",
            "request_id",
            "route_decision_id",
            "plan_id",
            "authorization_decision_id",
            "runtime_snapshot_id",
            "correlation_id",
        )
        for field in fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceBundle.model_validate(bundle_payload(**{field: UUID1_VALUE}))

    def test_naive_built_at_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(built_at=NAIVE_TIMESTAMP))

    def test_non_utc_built_at_normalized(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload(built_at=OFFSET_TIMESTAMP))
        self.assertEqual(bundle.built_at.hour, EXPECTED_UTC_HOUR)

    def test_invalid_evidence_manager_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(evidence_manager_version="1.0"))


class RequiredFactTests(unittest.TestCase):
    def test_duplicate_required_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(
                bundle_payload(required_fact_ids=[FACT_ALPHA, FACT_ALPHA])
            )

    def test_required_fact_order_preserved(self) -> None:
        facts = [FACT_GAMMA, FACT_ALPHA, FACT_BETA]
        payload = bundle_payload(
            required_fact_ids=facts,
            missing_fact_ids=[FACT_GAMMA, FACT_BETA],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(list(bundle.required_fact_ids), facts)
        self.assertEqual(list(bundle.missing_fact_ids), [FACT_GAMMA, FACT_BETA])

    def test_thirty_two_required_facts_accepted(self) -> None:
        facts = [f"fact.item{index}" for index in range(32)]
        payload = clarify_bundle(required_fact_ids=facts, missing_fact_ids=facts)
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.required_fact_ids), 32)

    def test_thirty_three_required_facts_rejected(self) -> None:
        facts = [f"fact.item{index}" for index in range(33)]
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(
                clarify_bundle(required_fact_ids=facts, missing_fact_ids=facts)
            )

    def test_required_facts_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(clarify_bundle(required_fact_ids=[], missing_fact_ids=[]))


class EvidenceIdentityTests(unittest.TestCase):
    def test_duplicate_accepted_evidence_rejected(self) -> None:
        payload = bundle_payload(accepted_evidence=[document_payload(), document_payload()])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_rejected_evidence_rejected(self) -> None:
        rejected = {
            "evidence_id": UNKNOWN_EVIDENCE_ID,
            "evidence_type": "web",
            "reason_codes": ["reason.stale"],
        }
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(rejected_evidence=[rejected, rejected]))

    def test_accepted_and_rejected_overlap_rejected(self) -> None:
        rejected = {
            "evidence_id": DOCUMENT_EVIDENCE_ID,
            "evidence_type": "document",
            "reason_codes": ["reason.stale"],
        }
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(rejected_evidence=[rejected]))

    def test_sixty_four_accepted_items_accepted(self) -> None:
        facts = [f"fact.item{index}" for index in range(32)]
        accepted = []
        identifiers = []
        for index in range(64):
            identifier = f"b0000000-0000-4000-8000-{index:012d}"
            identifiers.append(identifier)
            accepted.append(document_payload(identifier, supports=[facts[index // 2]]))
        fact_map = [
            fact_map_payload(facts[index], [identifiers[index * 2], identifiers[index * 2 + 1]])
            for index in range(32)
        ]
        payload = bundle_payload(
            required_fact_ids=facts,
            accepted_evidence=accepted,
            fact_map=fact_map,
            allowed_claims=[
                claim_payload(supporting_fact_ids=[facts[0]], evidence_ids=[identifiers[0]])
            ],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.accepted_evidence), 64)

    def test_sixty_five_accepted_items_rejected(self) -> None:
        accepted = [
            document_payload(f"b0000000-0000-4000-8000-{index:012d}") for index in range(65)
        ]
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(accepted_evidence=accepted))

    def test_evidence_supporting_unknown_fact_rejected(self) -> None:
        payload = bundle_payload(accepted_evidence=[document_payload(supports=[FACT_BETA])])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_evidence_plan_mismatch_rejected(self) -> None:
        provenance = provenance_payload(plan_id=BUNDLE_ID)
        payload = bundle_payload(accepted_evidence=[document_payload(provenance=provenance)])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_rule_input_must_be_accepted(self) -> None:
        payload = bundle_payload(
            accepted_evidence=[rule_payload(inputs=[UNKNOWN_EVIDENCE_ID])],
            fact_map=[fact_map_payload(evidence_ids=[RULE_EVIDENCE_ID])],
            allowed_claims=[claim_payload(evidence_ids=[RULE_EVIDENCE_ID])],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_rule_input_present_in_bundle_accepted(self) -> None:
        payload = bundle_payload(
            accepted_evidence=[document_payload(), rule_payload(supports=[FACT_BETA])],
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            fact_map=[
                fact_map_payload(),
                fact_map_payload(FACT_BETA, [RULE_EVIDENCE_ID]),
            ],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.accepted_evidence), 2)


class FactPartitionTests(unittest.TestCase):
    def test_exact_partition_accepted(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            missing_fact_ids=[FACT_BETA],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.fact_map), 1)

    def test_missing_required_fact_from_partition_rejected(self) -> None:
        payload = bundle_payload(required_fact_ids=[FACT_ALPHA, FACT_BETA])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_unknown_fact_map_fact_rejected(self) -> None:
        payload = bundle_payload(
            fact_map=[fact_map_payload(), fact_map_payload(FACT_BETA, [DOCUMENT_EVIDENCE_ID])]
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_unknown_missing_fact_rejected(self) -> None:
        payload = bundle_payload(
            missing_fact_ids=[FACT_BETA],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_fact_in_map_and_missing_rejected(self) -> None:
        payload = bundle_payload(
            missing_fact_ids=[FACT_ALPHA],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_fact_map_fact_rejected(self) -> None:
        payload = bundle_payload(fact_map=[fact_map_payload(), fact_map_payload()])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_missing_facts_rejected(self) -> None:
        payload = clarify_bundle(
            required_fact_ids=[FACT_ALPHA],
            missing_fact_ids=[FACT_ALPHA, FACT_ALPHA],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)


class ExactFactMapTests(unittest.TestCase):
    def test_unknown_fact_map_evidence_rejected(self) -> None:
        payload = bundle_payload(
            fact_map=[fact_map_payload(evidence_ids=[UNKNOWN_EVIDENCE_ID])],
            allowed_claims=[],
            sufficient=False,
            decision="abstain",
            decision_reason_codes=["evidence.unusable"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_mapped_relationship_must_be_declared(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            accepted_evidence=[document_payload(), document_payload(SECOND_DOCUMENT_EVIDENCE_ID)],
            fact_map=[
                fact_map_payload(),
                fact_map_payload(FACT_BETA, [SECOND_DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID]),
            ],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_declared_support_must_appear_in_fact_map(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            accepted_evidence=[document_payload(supports=[FACT_ALPHA, FACT_BETA])],
            fact_map=[fact_map_payload()],
            missing_fact_ids=[FACT_BETA],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_multiple_evidence_for_one_fact_accepted(self) -> None:
        payload = bundle_payload(
            accepted_evidence=[document_payload(), document_payload(SECOND_DOCUMENT_EVIDENCE_ID)],
            fact_map=[
                fact_map_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID])
            ],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(len(bundle.fact_map[0].evidence_ids), 2)


class BundleConflictTests(unittest.TestCase):
    def test_conflict_unknown_fact_rejected(self) -> None:
        payload = conflict_bundle(conflicts=[conflict_payload(fact_id=FACT_BETA)])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_conflict_unknown_evidence_rejected(self) -> None:
        conflict = conflict_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, UNKNOWN_EVIDENCE_ID])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(conflict_bundle(conflicts=[conflict]))

    def test_conflict_evidence_must_support_fact(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            accepted_evidence=[
                document_payload(),
                document_payload(SECOND_DOCUMENT_EVIDENCE_ID, supports=[FACT_BETA]),
            ],
            fact_map=[
                fact_map_payload(),
                fact_map_payload(FACT_BETA, [SECOND_DOCUMENT_EVIDENCE_ID]),
            ],
            conflicts=[conflict_payload()],
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["conflict.unresolved"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_semantic_conflict_rejected(self) -> None:
        duplicate = conflict_payload(conflict_id=OTHER_CONFLICT_ID)
        payload = conflict_bundle(conflicts=[conflict_payload(), duplicate])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_conflict_identifier_rejected(self) -> None:
        other = conflict_payload(evidence_ids=[SECOND_DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID])
        payload = conflict_bundle(conflicts=[conflict_payload(), other])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_resolved_conflict_allows_answer(self) -> None:
        payload = conflict_bundle(
            conflicts=[resolved_conflict_payload()],
            sufficient=True,
            decision="answer",
            allowed_claims=[
                claim_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID])
            ],
            decision_reason_codes=["conflict.resolved"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(bundle.conflicts[0].status, "resolved")

    def test_unresolved_conflict_blocks_answer(self) -> None:
        payload = conflict_bundle(
            sufficient=True,
            decision="answer",
            allowed_claims=[
                claim_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID])
            ],
            decision_reason_codes=["coverage.complete"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)


class BundleClaimTests(unittest.TestCase):
    def test_allowed_claim_using_missing_fact_rejected(self) -> None:
        payload = partial_missing_bundle()
        payload["allowed_claims"] = [claim_payload(supporting_fact_ids=[FACT_BETA])]
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_allowed_claim_using_unknown_evidence_rejected(self) -> None:
        payload = bundle_payload(allowed_claims=[claim_payload(evidence_ids=[UNKNOWN_EVIDENCE_ID])])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_claim_evidence_must_support_a_claim_fact(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            accepted_evidence=[
                document_payload(),
                document_payload(SECOND_DOCUMENT_EVIDENCE_ID, supports=[FACT_BETA]),
            ],
            fact_map=[
                fact_map_payload(),
                fact_map_payload(FACT_BETA, [SECOND_DOCUMENT_EVIDENCE_ID]),
            ],
            allowed_claims=[
                claim_payload(
                    supporting_fact_ids=[FACT_ALPHA],
                    evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID],
                )
            ],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_each_claim_fact_requires_listed_evidence(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            accepted_evidence=[
                document_payload(),
                document_payload(SECOND_DOCUMENT_EVIDENCE_ID, supports=[FACT_BETA]),
            ],
            fact_map=[
                fact_map_payload(),
                fact_map_payload(FACT_BETA, [SECOND_DOCUMENT_EVIDENCE_ID]),
            ],
            allowed_claims=[
                claim_payload(
                    supporting_fact_ids=[FACT_ALPHA, FACT_BETA],
                    evidence_ids=[DOCUMENT_EVIDENCE_ID],
                )
            ],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_claim_identifier_rejected(self) -> None:
        payload = bundle_payload(allowed_claims=[claim_payload(), claim_payload()])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_duplicate_prohibited_claim_code_rejected(self) -> None:
        prohibited = {
            "claim_code": "claim-code.salary",
            "reason_codes": ["reason.unauthorized"],
        }
        payload = bundle_payload(prohibited_claims=[prohibited, prohibited])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_allowed_and_prohibited_claim_code_overlap_rejected(self) -> None:
        prohibited = {
            "claim_code": "claim-code.policy-statement",
            "reason_codes": ["reason.unauthorized"],
        }
        payload = bundle_payload(prohibited_claims=[prohibited])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_disjoint_claim_codes_accepted(self) -> None:
        prohibited = {
            "claim_code": "claim-code.salary",
            "reason_codes": ["reason.unauthorized"],
        }
        bundle = EvidenceBundle.model_validate(bundle_payload(prohibited_claims=[prohibited]))
        self.assertEqual(len(bundle.prohibited_claims), 1)


class DecisionTests(unittest.TestCase):
    def test_answer_requires_sufficient_true(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(sufficient=False))

    def test_sufficient_true_requires_answer(self) -> None:
        payload = partial_missing_bundle()
        payload["sufficient"] = True
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_answer_requires_no_missing_fact(self) -> None:
        payload = bundle_payload(
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            missing_fact_ids=[FACT_BETA],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_answer_requires_allowed_claim(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(allowed_claims=[]))

    def test_partial_requires_sufficient_false(self) -> None:
        payload = partial_missing_bundle()
        payload["sufficient"] = True
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_partial_requires_allowed_claim(self) -> None:
        payload = partial_missing_bundle()
        payload["allowed_claims"] = []
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_partial_requires_supporting_condition(self) -> None:
        payload = bundle_payload(
            sufficient=False,
            decision="partial_answer",
            decision_reason_codes=["coverage.partial"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_clarify_requires_missing_fact(self) -> None:
        payload = bundle_payload(
            sufficient=False,
            decision="clarify",
            allowed_claims=[],
            decision_reason_codes=["clarification.required"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_clarify_rejects_allowed_claims(self) -> None:
        payload = clarify_bundle(
            accepted_evidence=[document_payload()],
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            fact_map=[fact_map_payload()],
            missing_fact_ids=[FACT_BETA],
            allowed_claims=[claim_payload()],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_abstain_rejects_allowed_claims(self) -> None:
        payload = clarify_bundle(
            accepted_evidence=[document_payload()],
            required_fact_ids=[FACT_ALPHA, FACT_BETA],
            fact_map=[fact_map_payload()],
            missing_fact_ids=[FACT_BETA],
            decision="abstain",
            allowed_claims=[claim_payload()],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_abstain_requires_missing_conflict_or_empty_basis(self) -> None:
        payload = bundle_payload(
            sufficient=False,
            decision="abstain",
            allowed_claims=[],
            decision_reason_codes=["evidence.unusable"],
        )
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    def test_unsupported_decision_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(decision="refuse"))

    def test_decision_reasons_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(decision_reason_codes=[]))

    def test_duplicate_decision_reasons_rejected(self) -> None:
        payload = bundle_payload(decision_reason_codes=["coverage.complete", "coverage.complete"])
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)


class CollectionTests(unittest.TestCase):
    def test_missing_collections_become_empty_tuples(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        self.assertEqual(bundle.rejected_evidence, ())
        self.assertEqual(bundle.missing_fact_ids, ())
        self.assertEqual(bundle.conflicts, ())
        self.assertEqual(bundle.prohibited_claims, ())

    def test_explicit_null_collections_rejected(self) -> None:
        fields = (
            "accepted_evidence",
            "rejected_evidence",
            "fact_map",
            "missing_fact_ids",
            "conflicts",
            "allowed_claims",
            "prohibited_claims",
        )
        for field in fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceBundle.model_validate(bundle_payload(**{field: None}))

    def test_collection_order_preserved(self) -> None:
        facts = [FACT_GAMMA, FACT_ALPHA]
        identifiers = [SECOND_DOCUMENT_EVIDENCE_ID, DOCUMENT_EVIDENCE_ID]
        payload = bundle_payload(
            required_fact_ids=facts,
            accepted_evidence=[
                document_payload(SECOND_DOCUMENT_EVIDENCE_ID, supports=[FACT_GAMMA]),
                document_payload(),
            ],
            fact_map=[
                fact_map_payload(FACT_GAMMA, [SECOND_DOCUMENT_EVIDENCE_ID]),
                fact_map_payload(),
            ],
            decision_reason_codes=["coverage.complete", "conflict.absent"],
        )
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(list(bundle.required_fact_ids), facts)
        self.assertEqual([str(item.evidence_id) for item in bundle.accepted_evidence], identifiers)
        self.assertEqual([entry.fact_id for entry in bundle.fact_map], facts)
        self.assertEqual(
            list(bundle.decision_reason_codes), ["coverage.complete", "conflict.absent"]
        )

    def test_collections_are_tuples(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        self.assertIsInstance(bundle.required_fact_ids, tuple)
        self.assertIsInstance(bundle.accepted_evidence, tuple)
        self.assertIsInstance(bundle.fact_map, tuple)


class StrictnessTests(unittest.TestCase):
    def test_root_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(extra_field="value"))

    def test_nested_unknown_fields_rejected(self) -> None:
        payloads = (
            bundle_payload(accepted_evidence=[document_payload(extra_field="value")]),
            bundle_payload(fact_map=[{**fact_map_payload(), "extra_field": "value"}]),
            bundle_payload(allowed_claims=[claim_payload(extra_field="value")]),
        )
        for payload in payloads:
            with self.subTest(payload=sorted(payload)), self.assertRaises(ValidationError):
                EvidenceBundle.model_validate(payload)

    def test_forbidden_fields_rejected_at_root(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceBundle.model_validate(bundle_payload(**{field: "value"}))

    def test_forbidden_fields_rejected_in_nested_models(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    EvidenceSubjectRef.model_validate(subject_payload(**{field: "value"}))
                with self.assertRaises(ValidationError):
                    EvidenceProvenance.model_validate(provenance_payload(**{field: "value"}))

    def test_forbidden_provider_and_credential_fields_rejected(self) -> None:
        fields = (
            "provider",
            "provider_response",
            "model",
            "model_name",
            "api_key",
            "token",
            "access_token",
            "secret",
            "password",
            "credentials",
        )
        for field in fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                DocumentEvidence.model_validate(document_payload(**{field: "value"}))

    def test_forbidden_identity_and_vendor_fields_rejected(self) -> None:
        fields = (
            "roles",
            "groups",
            "principal_id",
            "security_context_id",
            "email",
            "display_name",
            "session_id",
            "headers",
            "http_status",
            "traceparent",
            "span_id",
            "vendor_trace_id",
        )
        for field in fields:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                EvidenceBundle.model_validate(bundle_payload(**{field: "value"}))

    def test_models_are_immutable(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        with self.assertRaises(ValidationError):
            bundle.decision = "abstain"
        with self.assertRaises(ValidationError):
            bundle.accepted_evidence[0].authority = "authority.other"


class SerializationTests(unittest.TestCase):
    def test_json_round_trip(self) -> None:
        bundle = EvidenceBundle.model_validate(bundle_payload())
        restored = EvidenceBundle.model_validate_json(bundle.model_dump_json())
        self.assertEqual(restored, bundle)

    def test_discriminated_union_round_trip(self) -> None:
        payloads = (
            document_payload(),
            sql_payload(),
            selector_payload(),
            rule_payload(),
            web_payload(),
        )
        for payload in payloads:
            with self.subTest(evidence_type=payload["evidence_type"]):
                evidence = EVIDENCE_ADAPTER.validate_python(payload)
                encoded = EVIDENCE_ADAPTER.dump_json(evidence)
                restored = EVIDENCE_ADAPTER.validate_json(encoded)
                self.assertEqual(restored, evidence)


class SchemaArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generated = EvidenceBundle.model_json_schema()
        cls.raw = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        cls.committed = json.loads(cls.raw)

    def test_schema_identity(self) -> None:
        self.assertEqual(self.generated["$id"], EVIDENCE_SCHEMA_ID)
        self.assertEqual(self.generated["$id"], "urn:ai-assistant:contracts:evidence:1.0.0")
        self.assertEqual(self.generated["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_root_schema_closed(self) -> None:
        self.assertIs(self.generated["additionalProperties"], False)

    def test_nested_schemas_closed(self) -> None:
        for name, definition in self.generated["$defs"].items():
            with self.subTest(definition=name):
                self.assertIs(definition["additionalProperties"], False)

    def test_discriminator_present(self) -> None:
        accepted = self.generated["properties"]["accepted_evidence"]
        discriminator = accepted["items"]["discriminator"]
        self.assertEqual(discriminator["propertyName"], "evidence_type")
        self.assertEqual(
            sorted(discriminator["mapping"]),
            ["document", "rule", "selector", "sql", "web"],
        )

    def test_literal_catalogs_present(self) -> None:
        decision = self.generated["properties"]["decision"]
        self.assertEqual(decision["enum"], ["answer", "partial_answer", "clarify", "abstain"])
        rejected = self.generated["$defs"]["RejectedEvidenceRef"]["properties"]["evidence_type"]
        self.assertEqual(rejected["enum"], ["document", "sql", "selector", "rule", "web"])
        conflict = self.generated["$defs"]["EvidenceConflict"]["properties"]["status"]
        self.assertEqual(conflict["enum"], ["resolved", "unresolved"])

    def test_committed_schema_matches_generated(self) -> None:
        self.assertEqual(self.committed, self.generated)

    def test_committed_schema_is_sorted_with_trailing_newline(self) -> None:
        expected = json.dumps(self.generated, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        self.assertEqual(self.raw, expected)
        self.assertTrue(self.raw.endswith("\n"))

    def test_schema_version_declared_as_property(self) -> None:
        self.assertIn("schema_version", self.generated["properties"])
        self.assertEqual(self.generated["properties"]["schema_version"]["const"], "1.0.0")

    def test_forbidden_property_names_absent(self) -> None:
        declared: set[str] = set(self.generated["properties"])
        for definition in self.generated["$defs"].values():
            declared.update(definition.get("properties", {}))
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, declared)

    def test_nested_definitions_declare_no_schema_version(self) -> None:
        for name, definition in self.generated["$defs"].items():
            with self.subTest(definition=name):
                self.assertNotIn("schema_version", definition.get("properties", {}))


class ExportTests(unittest.TestCase):
    def test_public_exports_available(self) -> None:
        expected = {
            "AllowedEvidenceClaim",
            "DocumentEvidence",
            "Evidence",
            "EvidenceBundle",
            "EvidenceConflict",
            "EvidenceConflictStatus",
            "EvidenceDecision",
            "EvidenceFreshness",
            "EvidenceProvenance",
            "EvidenceSecurityScope",
            "EvidenceSourceRef",
            "EvidenceSourceTime",
            "EvidenceSubjectRef",
            "EvidenceType",
            "EvidenceValidationStatus",
            "EvidenceValidityWindow",
            "FactEvidenceMapEntry",
            "ProhibitedEvidenceClaim",
            "RejectedEvidenceRef",
            "RuleEvidence",
            "SelectorEvidence",
            "SqlEvidence",
            "WebEvidence",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_private_aliases_not_exported(self) -> None:
        private = (
            "_CanonicalCode",
            "_OpaqueRef",
            "_Sha256Digest",
            "_Uuid4",
            "_Score",
            "_EvidenceBase",
            "_EvidenceItem",
        )
        for name in private:
            with self.subTest(name=name):
                self.assertNotIn(name, contracts.__all__)
                self.assertFalse(hasattr(contracts, name))


EVIDENCE_ID_TEMPLATE = "b0000000-0000-4000-8000-%012d"
CODE_STRATEGY = st.from_regex(r"\A[a-z][a-z0-9._:-]{0,8}\Z")


def build_generated_bundle(
    facts: Sequence[str], supports: Sequence[Sequence[str]]
) -> dict[str, object]:
    identifiers = [EVIDENCE_ID_TEMPLATE % index for index in range(len(supports))]
    accepted = [
        document_payload(identifier, supports=list(declared))
        for identifier, declared in zip(identifiers, supports, strict=True)
    ]
    mapping: dict[str, list[str]] = {}
    for identifier, declared in zip(identifiers, supports, strict=True):
        for fact in declared:
            mapping.setdefault(fact, []).append(identifier)
    fact_map = [fact_map_payload(fact, mapping[fact]) for fact in facts if fact in mapping]
    missing = [fact for fact in facts if fact not in mapping]
    if fact_map:
        first = fact_map[0]
        first_fact = first["fact_id"]
        first_evidence = first["evidence_ids"]
        assert isinstance(first_fact, str)
        assert isinstance(first_evidence, list)
        claims = [
            claim_payload(supporting_fact_ids=[first_fact], evidence_ids=list(first_evidence))
        ]
        decision = "partial_answer" if missing else "answer"
        sufficient = not missing
    else:
        claims = []
        decision = "clarify"
        sufficient = False
    return bundle_payload(
        required_fact_ids=list(facts),
        accepted_evidence=accepted,
        fact_map=fact_map,
        missing_fact_ids=missing,
        allowed_claims=claims,
        sufficient=sufficient,
        decision=decision,
        decision_reason_codes=["coverage.generated"],
    )


@st.composite
def bundle_inputs(draw: st.DrawFn, minimum_evidence: int = 0) -> tuple[list[str], list[list[str]]]:
    facts = draw(st.lists(CODE_STRATEGY, min_size=1, max_size=8, unique=True))
    count = draw(st.integers(min_value=minimum_evidence, max_value=12))
    supports = [
        draw(st.lists(st.sampled_from(facts), min_size=1, max_size=4, unique=True))
        for _ in range(count)
    ]
    return facts, supports


class BundlePropertyTests(unittest.TestCase):
    @given(bundle_inputs())
    def test_collections_preserve_generated_order(
        self, generated: tuple[list[str], list[list[str]]]
    ) -> None:
        facts, supports = generated
        payload = build_generated_bundle(facts, supports)
        bundle = EvidenceBundle.model_validate(payload)
        self.assertEqual(list(bundle.required_fact_ids), facts)
        expected_ids = [EVIDENCE_ID_TEMPLATE % index for index in range(len(supports))]
        self.assertEqual([str(item.evidence_id) for item in bundle.accepted_evidence], expected_ids)

    @given(bundle_inputs())
    def test_fact_map_round_trips_support_declarations(
        self, generated: tuple[list[str], list[list[str]]]
    ) -> None:
        facts, supports = generated
        bundle = EvidenceBundle.model_validate(build_generated_bundle(facts, supports))
        declared: set[tuple[str, str]] = set()
        for item in bundle.accepted_evidence:
            for fact in item.supports_fact_ids:
                declared.add((fact, str(item.evidence_id)))
        mapped: set[tuple[str, str]] = set()
        for entry in bundle.fact_map:
            for identifier in entry.evidence_ids:
                mapped.add((entry.fact_id, str(identifier)))
        self.assertEqual(declared, mapped)
        covered = {entry.fact_id for entry in bundle.fact_map}
        self.assertEqual(covered | set(bundle.missing_fact_ids), set(bundle.required_fact_ids))
        self.assertEqual(covered & set(bundle.missing_fact_ids), set())

    @given(bundle_inputs(minimum_evidence=1))
    def test_duplicate_accepted_evidence_always_rejected(
        self, generated: tuple[list[str], list[list[str]]]
    ) -> None:
        facts, supports = generated
        payload = build_generated_bundle(facts, supports)
        accepted = payload["accepted_evidence"]
        assert isinstance(accepted, list)
        payload["accepted_evidence"] = [*accepted, accepted[0]]
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(payload)

    @given(
        st.booleans(),
        st.integers(min_value=0, max_value=1),
        st.lists(CODE_STRATEGY, min_size=1, max_size=4, unique=True),
    )
    def test_conflict_structures_obey_invariants(
        self, resolved: bool, controlling_index: int, reasons: list[str]
    ) -> None:
        conflict_identifiers = [DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID]
        if resolved:
            conflict = conflict_payload(
                status="resolved",
                resolution_code="resolution.newer-source",
                controlling_evidence_id=conflict_identifiers[controlling_index],
            )
            claims = [
                claim_payload(evidence_ids=[DOCUMENT_EVIDENCE_ID, SECOND_DOCUMENT_EVIDENCE_ID])
            ]
            payload = conflict_bundle(
                conflicts=[conflict],
                sufficient=True,
                decision="answer",
                allowed_claims=claims,
                decision_reason_codes=reasons,
            )
            bundle = EvidenceBundle.model_validate(payload)
            controlling = bundle.conflicts[0].controlling_evidence_id
            self.assertIsNotNone(controlling)
            self.assertIn(controlling, bundle.conflicts[0].evidence_ids)
        else:
            payload = conflict_bundle(decision_reason_codes=reasons)
            bundle = EvidenceBundle.model_validate(payload)
            self.assertIsNone(bundle.conflicts[0].resolution_code)
            self.assertIsNone(bundle.conflicts[0].controlling_evidence_id)
            self.assertFalse(bundle.sufficient)

    @given(st.sampled_from(FORBIDDEN_FIELDS))
    def test_sampled_forbidden_fields_rejected(self, field: str) -> None:
        with self.assertRaises(ValidationError):
            EvidenceBundle.model_validate(bundle_payload(**{field: "value"}))
        with self.assertRaises(ValidationError):
            DocumentEvidence.model_validate(document_payload(**{field: "value"}))
        with self.assertRaises(ValidationError):
            EvidenceSecurityScope.model_validate(scope_payload(**{field: "value"}))


if __name__ == "__main__":
    unittest.main()
