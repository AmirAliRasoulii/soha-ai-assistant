"""Tests for the AI Core query analysis contract, schema version 1.0.0."""

import json
import unittest
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.query_analysis import (
    QueryAnalysis,
    QueryEntity,
    QueryTimeExpression,
)

ANALYSIS_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
MESSAGE_ID = "33333333-3333-4333-8333-333333333333"
RUNTIME_SNAPSHOT_ID = "44444444-4444-4444-8444-444444444444"
UUID1_VALUE = "55555555-5555-1555-8555-555555555555"
ANALYZED_AT = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC_HOUR = 8
PERSIAN_QUERY = (
    "\u0648\u0636\u0639\u06cc\u062a \u062f\u0631\u062e\u0648\u0627\u0633\u062a "
    "\u0645\u0646 \u0686\u06cc\u0633\u062a\u061f"
)

INTENTS: tuple[str, ...] = (
    "greeting",
    "capability_help",
    "factual",
    "procedural",
    "status",
    "eligibility",
    "comparison",
    "analytics",
    "unknown",
)
EVIDENCE_NEEDS: tuple[str, ...] = (
    "none",
    "document",
    "analytics",
    "personal",
    "rule",
    "official_source",
)
AMBIGUITY_LEVELS: tuple[str, ...] = ("none", "non_blocking", "blocking")
RISK_LEVELS: tuple[str, ...] = ("normal", "elevated", "high", "unknown")
RESOLUTION_STATUSES: tuple[str, ...] = ("resolved", "unresolved", "ambiguous")
TIME_TYPES: tuple[str, ...] = (
    "date",
    "date_range",
    "relative",
    "academic_term",
    "unknown",
)

FORBIDDEN_FIELDS: tuple[str, ...] = (
    "lane",
    "route",
    "suggested_route",
    "capability",
    "capabilities",
    "allowed_capabilities",
    "suggested_capability",
    "planner_required",
    "execution_plan",
    "plan",
    "budget",
    "authorization",
    "authorization_decision",
    "permission",
    "roles",
    "groups",
    "policy",
    "policy_decision",
    "sql",
    "query_plan",
    "tool",
    "tool_name",
    "endpoint",
    "url",
    "api_key",
    "token",
    "secret",
    "credentials",
    "prompt",
    "system_prompt",
    "model_response",
    "provider_response",
    "rationale",
    "reasoning",
    "chain_of_thought",
    "clarification_message",
    "answer",
    "raw_message",
    "raw_query",
    "standalone_query",
    "metadata",
    "attributes",
)
IDENTITY_FIELDS: tuple[str, ...] = (
    "principal_id",
    "security_context_id",
    "email",
    "display_name",
    "session_id",
    "role",
    "group",
)

SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "query-analysis" / "1.0.0.schema.json"
)


def entity_payload(status: str = "resolved", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "entity_type": "course",
        "mention": "compiler design",
        "resolution_status": status,
    }
    if status == "resolved":
        payload["canonical_id"] = "course:cs-431"
    elif status == "ambiguous":
        payload["candidate_ids"] = ["course:cs-431", "course:cs-432"]
    payload.update(overrides)
    return payload


def time_payload(status: str = "resolved", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "expression": "this term",
        "time_type": "academic_term",
        "resolution_status": status,
    }
    if status == "resolved":
        payload["canonical_value"] = "term:1404-1"
    elif status == "ambiguous":
        payload["candidate_values"] = ["term:1404-1", "term:1404-2"]
    payload.update(overrides)
    return payload


def analysis_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "analysis_id": ANALYSIS_ID,
        "request_id": REQUEST_ID,
        "message_id": MESSAGE_ID,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "analyzed_at": ANALYZED_AT,
        "normalized_query": "what is the exam schedule",
        "intent": "factual",
        "ambiguity_level": "none",
        "is_personal": False,
        "is_multi_part": False,
        "risk_level": "normal",
        "evidence_needs": ["document"],
        "confidence": 0.75,
        "analyzer_version": "1.0.0",
    }
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    def test_default_schema_version_is_exact(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload())
        self.assertEqual(analysis.schema_version, "1.0.0")

    def test_other_schema_version_is_rejected(self) -> None:
        for value in ("1.0.1", "1.1.0", "2.0.0", "1.0"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(schema_version=value))


class ValidAnalysisTests(unittest.TestCase):
    def test_valid_minimal_analysis(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload())
        self.assertEqual(analysis.entities, ())
        self.assertEqual(analysis.time_expressions, ())
        self.assertEqual(analysis.ambiguity_codes, ())
        self.assertEqual(analysis.risk_signals, ())

    def test_valid_fully_populated_analysis(self) -> None:
        payload = analysis_payload(
            entities=[entity_payload("resolved"), entity_payload("ambiguous", mention="algebra")],
            time_expressions=[
                time_payload("resolved"),
                time_payload("unresolved", expression="soon"),
            ],
            ambiguity_level="non_blocking",
            ambiguity_codes=["ambiguity.entity", "ambiguity.time"],
            is_personal=True,
            is_multi_part=True,
            risk_level="elevated",
            risk_signals=["risk.personal_data"],
            evidence_needs=["personal", "document"],
            confidence=1.0,
        )
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(len(analysis.entities), 2)
        self.assertEqual(len(analysis.time_expressions), 2)
        self.assertEqual(analysis.evidence_needs, ("personal", "document"))


class IdentifierAndTimestampTests(unittest.TestCase):
    def test_uuid4_enforced_for_every_identifier(self) -> None:
        for field in ("analysis_id", "request_id", "message_id", "runtime_snapshot_id"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(**{field: UUID1_VALUE}))

    def test_naive_analyzed_at_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(analyzed_at="2026-01-01T12:00:00"))

    def test_non_utc_timestamp_is_normalized(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload())
        self.assertEqual(analysis.analyzed_at.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(analysis.analyzed_at.utcoffset().total_seconds(), 0)


class NormalizedQueryTests(unittest.TestCase):
    def test_persian_query_is_accepted_and_preserved(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(normalized_query=PERSIAN_QUERY))
        self.assertEqual(analysis.normalized_query, PERSIAN_QUERY)

    def test_blank_query_is_rejected(self) -> None:
        for value in ("", "   ", "\t\n"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(normalized_query=value))

    def test_padded_query_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(normalized_query=" padded "))

    def test_nul_query_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(normalized_query="bad\x00value"))

    def test_oversized_query_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(normalized_query="a" * 32001))

    def test_maximum_length_query_is_accepted(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(normalized_query="a" * 32000))
        self.assertEqual(len(analysis.normalized_query), 32000)


class IntentTests(unittest.TestCase):
    def test_every_approved_intent_is_accepted(self) -> None:
        for intent in INTENTS:
            with self.subTest(intent=intent):
                analysis = QueryAnalysis.model_validate(analysis_payload(intent=intent))
                self.assertEqual(analysis.intent, intent)

    def test_unsupported_intent_is_rejected(self) -> None:
        for intent in ("routing", "FACTUAL", "chit_chat", ""):
            with self.subTest(intent=intent):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(intent=intent))


class EntityResolutionTests(unittest.TestCase):
    def test_valid_resolved_entity(self) -> None:
        entity = QueryEntity.model_validate(entity_payload("resolved"))
        self.assertEqual(entity.canonical_id, "course:cs-431")
        self.assertEqual(entity.candidate_ids, ())

    def test_valid_unresolved_entity(self) -> None:
        entity = QueryEntity.model_validate(entity_payload("unresolved"))
        self.assertIsNone(entity.canonical_id)
        self.assertEqual(entity.candidate_ids, ())

    def test_valid_ambiguous_entity(self) -> None:
        entity = QueryEntity.model_validate(entity_payload("ambiguous"))
        self.assertIsNone(entity.canonical_id)
        self.assertEqual(entity.candidate_ids, ("course:cs-431", "course:cs-432"))

    def test_resolved_entity_without_canonical_id_is_rejected(self) -> None:
        payload = entity_payload("resolved")
        del payload["canonical_id"]
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_resolved_entity_with_candidates_is_rejected(self) -> None:
        payload = entity_payload("resolved", candidate_ids=["course:cs-431", "course:cs-432"])
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_unresolved_entity_with_canonical_id_is_rejected(self) -> None:
        payload = entity_payload("unresolved", canonical_id="course:cs-431")
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_unresolved_entity_with_candidates_is_rejected(self) -> None:
        payload = entity_payload("unresolved", candidate_ids=["course:cs-431", "course:cs-432"])
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_ambiguous_entity_with_canonical_id_is_rejected(self) -> None:
        payload = entity_payload("ambiguous", canonical_id="course:cs-431")
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_ambiguous_entity_with_fewer_than_two_candidates_is_rejected(self) -> None:
        for candidates in ([], ["course:cs-431"]):
            with self.subTest(candidates=candidates):
                payload = entity_payload("ambiguous", candidate_ids=candidates)
                with self.assertRaises(ValidationError):
                    QueryEntity.model_validate(payload)

    def test_ambiguous_entity_with_eight_candidates_is_accepted(self) -> None:
        candidates = [f"course:cs-{index}" for index in range(8)]
        entity = QueryEntity.model_validate(entity_payload("ambiguous", candidate_ids=candidates))
        self.assertEqual(len(entity.candidate_ids), 8)

    def test_ambiguous_entity_with_nine_candidates_is_rejected(self) -> None:
        candidates = [f"course:cs-{index}" for index in range(9)]
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(entity_payload("ambiguous", candidate_ids=candidates))

    def test_duplicate_entity_candidates_are_rejected(self) -> None:
        payload = entity_payload("ambiguous", candidate_ids=["course:cs-431", "course:cs-431"])
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(payload)

    def test_entity_candidate_order_is_preserved(self) -> None:
        candidates = ["course:cs-9", "course:cs-1", "course:cs-5"]
        entity = QueryEntity.model_validate(entity_payload("ambiguous", candidate_ids=candidates))
        self.assertEqual(entity.candidate_ids, tuple(candidates))

    def test_entity_mention_boundaries(self) -> None:
        for value in ("", "   ", " padded ", "bad\x00value", "a" * 513):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    QueryEntity.model_validate(entity_payload("unresolved", mention=value))

    def test_duplicate_entities_are_rejected(self) -> None:
        payload = analysis_payload(
            entities=[entity_payload("resolved"), entity_payload("resolved")],
        )
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_thirty_two_entities_are_accepted(self) -> None:
        entities = [entity_payload("unresolved", mention=f"mention {index}") for index in range(32)]
        analysis = QueryAnalysis.model_validate(analysis_payload(entities=entities))
        self.assertEqual(len(analysis.entities), 32)

    def test_thirty_three_entities_are_rejected(self) -> None:
        entities = [entity_payload("unresolved", mention=f"mention {index}") for index in range(33)]
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(entities=entities))


class TimeExpressionTests(unittest.TestCase):
    def test_valid_resolved_time_expression(self) -> None:
        expression = QueryTimeExpression.model_validate(time_payload("resolved"))
        self.assertEqual(expression.canonical_value, "term:1404-1")

    def test_valid_unresolved_time_expression(self) -> None:
        expression = QueryTimeExpression.model_validate(time_payload("unresolved"))
        self.assertIsNone(expression.canonical_value)

    def test_valid_ambiguous_time_expression(self) -> None:
        expression = QueryTimeExpression.model_validate(time_payload("ambiguous"))
        self.assertEqual(expression.candidate_values, ("term:1404-1", "term:1404-2"))

    def test_every_time_type_is_accepted(self) -> None:
        for time_type in TIME_TYPES:
            with self.subTest(time_type=time_type):
                expression = QueryTimeExpression.model_validate(
                    time_payload("unresolved", time_type=time_type)
                )
                self.assertEqual(expression.time_type, time_type)

    def test_unsupported_time_type_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryTimeExpression.model_validate(time_payload("unresolved", time_type="weekday"))

    def test_all_time_resolution_cross_field_failures_are_rejected(self) -> None:
        invalid_payloads = (
            time_payload("resolved", canonical_value=None),
            time_payload("resolved", candidate_values=["term:1404-1", "term:1404-2"]),
            time_payload("unresolved", canonical_value="term:1404-1"),
            time_payload("unresolved", candidate_values=["term:1404-1", "term:1404-2"]),
            time_payload("ambiguous", canonical_value="term:1404-1"),
            time_payload("ambiguous", candidate_values=[]),
            time_payload("ambiguous", candidate_values=["term:1404-1"]),
            time_payload("ambiguous", candidate_values=[f"term:{index}" for index in range(9)]),
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    QueryTimeExpression.model_validate(payload)

    def test_duplicate_time_candidates_are_rejected(self) -> None:
        payload = time_payload("ambiguous", candidate_values=["term:1404-1", "term:1404-1"])
        with self.assertRaises(ValidationError):
            QueryTimeExpression.model_validate(payload)

    def test_time_candidate_order_is_preserved(self) -> None:
        candidates = ["term:1404-3", "term:1404-1", "term:1404-2"]
        expression = QueryTimeExpression.model_validate(
            time_payload("ambiguous", candidate_values=candidates)
        )
        self.assertEqual(expression.candidate_values, tuple(candidates))

    def test_duplicate_time_expressions_are_rejected(self) -> None:
        payload = analysis_payload(
            time_expressions=[time_payload("resolved"), time_payload("resolved")],
        )
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_sixteen_time_expressions_are_accepted(self) -> None:
        expressions = [
            time_payload("unresolved", expression=f"window {index}") for index in range(16)
        ]
        analysis = QueryAnalysis.model_validate(analysis_payload(time_expressions=expressions))
        self.assertEqual(len(analysis.time_expressions), 16)

    def test_seventeen_time_expressions_are_rejected(self) -> None:
        expressions = [
            time_payload("unresolved", expression=f"window {index}") for index in range(17)
        ]
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(time_expressions=expressions))


class CanonicalCodeTests(unittest.TestCase):
    def test_valid_canonical_codes_are_accepted(self) -> None:
        codes = [
            "ambiguity",
            "ambiguity.entity",
            "ambiguity.time.range",
            "signal:personal-data",
            "risk.elevated",
        ]
        payload = analysis_payload(
            ambiguity_level="non_blocking",
            ambiguity_codes=codes,
            risk_signals=codes,
        )
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(analysis.ambiguity_codes, tuple(codes))
        self.assertEqual(analysis.risk_signals, tuple(codes))

    def test_invalid_canonical_codes_are_rejected(self) -> None:
        for value in ("Ambiguity.Entity", " leading", "contains/slash", "contains@sign", ""):
            with self.subTest(value=value):
                payload = analysis_payload(
                    ambiguity_level="blocking",
                    ambiguity_codes=[value],
                )
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(payload)


class AmbiguityTests(unittest.TestCase):
    def test_ambiguity_none_with_empty_codes_is_accepted(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(ambiguity_level="none"))
        self.assertEqual(analysis.ambiguity_codes, ())

    def test_ambiguity_none_with_code_is_rejected(self) -> None:
        payload = analysis_payload(ambiguity_level="none", ambiguity_codes=["ambiguity.entity"])
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_blocking_ambiguity_without_code_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(ambiguity_level="blocking"))

    def test_non_blocking_ambiguity_without_code_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(ambiguity_level="non_blocking"))

    def test_blocking_ambiguity_with_code_is_accepted(self) -> None:
        payload = analysis_payload(
            ambiguity_level="blocking",
            ambiguity_codes=["ambiguity.entity"],
        )
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(analysis.ambiguity_level, "blocking")

    def test_duplicate_ambiguity_codes_are_rejected(self) -> None:
        payload = analysis_payload(
            ambiguity_level="blocking",
            ambiguity_codes=["ambiguity.entity", "ambiguity.entity"],
        )
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_ambiguity_code_order_is_preserved(self) -> None:
        codes = ["ambiguity.time", "ambiguity.entity", "ambiguity.scope"]
        payload = analysis_payload(ambiguity_level="blocking", ambiguity_codes=codes)
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(analysis.ambiguity_codes, tuple(codes))

    def test_sixteen_ambiguity_codes_accepted_and_seventeen_rejected(self) -> None:
        codes = [f"ambiguity.{index}" for index in range(16)]
        payload = analysis_payload(ambiguity_level="blocking", ambiguity_codes=codes)
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(len(analysis.ambiguity_codes), 16)
        oversized = analysis_payload(
            ambiguity_level="blocking",
            ambiguity_codes=[f"ambiguity.{index}" for index in range(17)],
        )
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(oversized)


class CollectionDefaultTests(unittest.TestCase):
    def test_missing_collections_become_empty_tuples(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload())
        self.assertEqual(analysis.entities, ())
        self.assertEqual(analysis.time_expressions, ())
        self.assertEqual(analysis.ambiguity_codes, ())
        self.assertEqual(analysis.risk_signals, ())

    def test_explicit_null_collections_are_rejected(self) -> None:
        for field in ("entities", "time_expressions", "ambiguity_codes", "risk_signals"):
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(**{field: None}))


class RiskTests(unittest.TestCase):
    def test_every_approved_risk_level_is_accepted(self) -> None:
        for level in RISK_LEVELS:
            with self.subTest(level=level):
                analysis = QueryAnalysis.model_validate(analysis_payload(risk_level=level))
                self.assertEqual(analysis.risk_level, level)

    def test_unsupported_risk_level_is_rejected(self) -> None:
        for level in ("critical", "HIGH", "low", ""):
            with self.subTest(level=level):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(risk_level=level))

    def test_duplicate_risk_signals_are_rejected(self) -> None:
        payload = analysis_payload(risk_signals=["risk.personal", "risk.personal"])
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_risk_signal_order_is_preserved(self) -> None:
        signals = ["risk.c", "risk.a", "risk.b"]
        analysis = QueryAnalysis.model_validate(analysis_payload(risk_signals=signals))
        self.assertEqual(analysis.risk_signals, tuple(signals))


class EvidenceNeedTests(unittest.TestCase):
    def test_every_evidence_need_is_accepted(self) -> None:
        for need in EVIDENCE_NEEDS:
            with self.subTest(need=need):
                payload = analysis_payload(evidence_needs=[need], is_personal=need == "personal")
                analysis = QueryAnalysis.model_validate(payload)
                self.assertEqual(analysis.evidence_needs, (need,))

    def test_empty_evidence_needs_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(evidence_needs=[]))

    def test_duplicate_evidence_needs_are_rejected(self) -> None:
        payload = analysis_payload(evidence_needs=["document", "document"])
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_evidence_need_order_is_preserved(self) -> None:
        needs = ["rule", "document", "official_source"]
        analysis = QueryAnalysis.model_validate(analysis_payload(evidence_needs=needs))
        self.assertEqual(analysis.evidence_needs, tuple(needs))

    def test_none_alone_is_accepted(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(evidence_needs=["none"]))
        self.assertEqual(analysis.evidence_needs, ("none",))

    def test_none_combined_with_another_need_is_rejected(self) -> None:
        for needs in (["none", "document"], ["document", "none"], ["none", "rule", "analytics"]):
            with self.subTest(needs=needs):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(evidence_needs=needs))

    def test_personal_evidence_with_personal_flag_true_is_accepted(self) -> None:
        payload = analysis_payload(evidence_needs=["personal"], is_personal=True)
        analysis = QueryAnalysis.model_validate(payload)
        self.assertTrue(analysis.is_personal)

    def test_personal_evidence_with_personal_flag_false_is_rejected(self) -> None:
        payload = analysis_payload(evidence_needs=["personal"], is_personal=False)
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(payload)

    def test_personal_flag_true_without_personal_evidence_is_accepted(self) -> None:
        payload = analysis_payload(evidence_needs=["document"], is_personal=True)
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(analysis.evidence_needs, ("document",))

    def test_unsupported_evidence_need_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(evidence_needs=["retrieval"]))


class ConfidenceTests(unittest.TestCase):
    def test_confidence_zero_is_accepted(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(confidence=0.0))
        self.assertEqual(analysis.confidence, 0.0)

    def test_confidence_one_is_accepted(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload(confidence=1.0))
        self.assertEqual(analysis.confidence, 1.0)

    def test_confidence_below_zero_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(confidence=-0.01))

    def test_confidence_above_one_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(confidence=1.01))

    def test_nan_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(confidence=float("nan")))

    def test_positive_infinity_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(confidence=float("inf")))

    def test_negative_infinity_confidence_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(confidence=float("-inf")))


class AnalyzerVersionTests(unittest.TestCase):
    def test_valid_analyzer_version_is_accepted(self) -> None:
        for value in ("0.1.0", "1.0.0", "12.4.37"):
            with self.subTest(value=value):
                analysis = QueryAnalysis.model_validate(analysis_payload(analyzer_version=value))
                self.assertEqual(analysis.analyzer_version, value)

    def test_invalid_analyzer_version_is_rejected(self) -> None:
        for value in ("1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0", "1.0.0+build"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(analyzer_version=value))


class UnknownAndForbiddenFieldTests(unittest.TestCase):
    def test_root_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(unexpected="value"))

    def test_nested_entity_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(entity_payload("unresolved", unexpected="value"))

    def test_nested_time_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            QueryTimeExpression.model_validate(time_payload("unresolved", unexpected="value"))

    def test_all_forbidden_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELDS + IDENTITY_FIELDS:
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    QueryAnalysis.model_validate(analysis_payload(**{name: "value"}))

    def test_forbidden_fields_are_rejected_on_nested_models(self) -> None:
        for name in ("route", "policy", "prompt", "roles", "provider_response"):
            with self.subTest(name=name):
                with self.assertRaises(ValidationError):
                    QueryEntity.model_validate(entity_payload("unresolved", **{name: "value"}))
                with self.assertRaises(ValidationError):
                    QueryTimeExpression.model_validate(
                        time_payload("unresolved", **{name: "value"})
                    )


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    def test_root_and_nested_models_are_immutable(self) -> None:
        payload = analysis_payload(
            entities=[entity_payload("resolved")],
            time_expressions=[time_payload("resolved")],
        )
        analysis = QueryAnalysis.model_validate(payload)
        with self.assertRaises(ValidationError):
            analysis.intent = "status"
        with self.assertRaises(ValidationError):
            analysis.entities[0].mention = "other"
        with self.assertRaises(ValidationError):
            analysis.time_expressions[0].expression = "other"

    def test_json_round_trip(self) -> None:
        payload = analysis_payload(
            entities=[entity_payload("ambiguous")],
            time_expressions=[time_payload("resolved")],
            ambiguity_level="blocking",
            ambiguity_codes=["ambiguity.entity"],
            is_personal=True,
            evidence_needs=["personal", "rule"],
            risk_signals=["risk.personal"],
        )
        original = QueryAnalysis.model_validate(payload)
        restored = QueryAnalysis.model_validate_json(original.model_dump_json())
        self.assertEqual(restored, original)

    def test_identifiers_round_trip_as_uuid_objects(self) -> None:
        analysis = QueryAnalysis.model_validate(analysis_payload())
        self.assertEqual(analysis.analysis_id, UUID(ANALYSIS_ID))
        self.assertEqual(analysis.request_id, UUID(REQUEST_ID))
        self.assertEqual(analysis.message_id, UUID(MESSAGE_ID))
        self.assertEqual(analysis.runtime_snapshot_id, UUID(RUNTIME_SNAPSHOT_ID))


class SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = QueryAnalysis.model_json_schema()

    def schema_property_names(self) -> set[str]:
        names = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            names.update(definition["properties"])
        return names

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:query-analysis:1.0.0")

    def test_root_schema_is_closed(self) -> None:
        self.assertIs(self.schema["additionalProperties"], False)

    def test_nested_schemas_are_closed(self) -> None:
        self.assertEqual(set(self.schema["$defs"]), {"QueryEntity", "QueryTimeExpression"})
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertIs(definition["additionalProperties"], False)

    def test_committed_schema_artifact_matches_generated_schema(self) -> None:
        committed = json.loads(SCHEMA_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        raw = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.assertTrue(raw.endswith("}\n"))
        self.assertFalse(raw.endswith("\n\n"))

    def test_exact_literal_catalogs_appear_in_schema(self) -> None:
        properties = self.schema["properties"]
        self.assertEqual(tuple(properties["intent"]["enum"]), INTENTS)
        self.assertEqual(tuple(properties["ambiguity_level"]["enum"]), AMBIGUITY_LEVELS)
        self.assertEqual(tuple(properties["risk_level"]["enum"]), RISK_LEVELS)
        self.assertEqual(
            tuple(properties["evidence_needs"]["items"]["enum"]),
            EVIDENCE_NEEDS,
        )
        entity = self.schema["$defs"]["QueryEntity"]
        self.assertEqual(
            tuple(entity["properties"]["resolution_status"]["enum"]),
            RESOLUTION_STATUSES,
        )
        expression = self.schema["$defs"]["QueryTimeExpression"]
        self.assertEqual(tuple(expression["properties"]["time_type"]["enum"]), TIME_TYPES)

    def test_forbidden_property_names_are_absent_from_schema(self) -> None:
        declared = self.schema_property_names()
        for name in FORBIDDEN_FIELDS + IDENTITY_FIELDS:
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_no_route_capability_policy_or_rationale_property_declared(self) -> None:
        declared = self.schema_property_names()
        for name in (
            "route",
            "lane",
            "capability",
            "planner_required",
            "budget",
            "policy",
            "prompt",
            "rationale",
            "chain_of_thought",
        ):
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_nested_models_have_no_schema_version(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertNotIn("schema_version", definition["properties"])

    def test_root_schema_declares_expected_required_fields(self) -> None:
        self.assertEqual(
            set(self.schema["required"]),
            {
                "analysis_id",
                "request_id",
                "message_id",
                "runtime_snapshot_id",
                "analyzed_at",
                "normalized_query",
                "intent",
                "ambiguity_level",
                "is_personal",
                "is_multi_part",
                "risk_level",
                "evidence_needs",
                "confidence",
                "analyzer_version",
            },
        )


class ExportTests(unittest.TestCase):
    def test_public_exports_are_available(self) -> None:
        expected = {
            "AmbiguityLevel",
            "EntityResolutionStatus",
            "EvidenceNeed",
            "QueryAnalysis",
            "QueryEntity",
            "QueryIntent",
            "QueryTimeExpression",
            "RiskLevel",
            "TimeExpressionType",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_private_validation_aliases_are_not_exported(self) -> None:
        for name in ("_CanonicalCode", "_OpaqueId", "_DerivedQueryText", "_MentionText"):
            with self.subTest(name=name):
                self.assertNotIn(name, contracts.__all__)


candidate_strategy = st.lists(
    st.from_regex(r"\Acourse:[a-z0-9]{1,6}\Z", fullmatch=True),
    min_size=2,
    max_size=8,
    unique=True,
)
code_strategy = st.lists(
    st.from_regex(r"\Acode\.[a-z0-9]{1,6}\Z", fullmatch=True),
    min_size=1,
    max_size=8,
    unique=True,
)
confidence_strategy = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)
forbidden_name_strategy = st.sampled_from(FORBIDDEN_FIELDS + IDENTITY_FIELDS)


class QueryAnalysisPropertyTests(unittest.TestCase):
    @given(candidates=candidate_strategy)
    def test_unique_entity_candidates_preserve_order(self, candidates: list[str]) -> None:
        entity = QueryEntity.model_validate(entity_payload("ambiguous", candidate_ids=candidates))
        self.assertEqual(entity.candidate_ids, tuple(candidates))

    @given(candidates=candidate_strategy)
    def test_duplicate_entity_candidate_is_rejected(self, candidates: list[str]) -> None:
        duplicated = [*candidates, candidates[0]]
        with self.assertRaises(ValidationError):
            QueryEntity.model_validate(entity_payload("ambiguous", candidate_ids=duplicated))

    @given(codes=code_strategy)
    def test_code_tuples_preserve_order(self, codes: list[str]) -> None:
        payload = analysis_payload(
            ambiguity_level="blocking",
            ambiguity_codes=codes,
            risk_signals=codes,
        )
        analysis = QueryAnalysis.model_validate(payload)
        self.assertEqual(analysis.ambiguity_codes, tuple(codes))
        self.assertEqual(analysis.risk_signals, tuple(codes))

    @given(confidence=confidence_strategy)
    def test_confidence_round_trips(self, confidence: float) -> None:
        original = QueryAnalysis.model_validate(analysis_payload(confidence=confidence))
        restored = QueryAnalysis.model_validate_json(original.model_dump_json())
        self.assertEqual(restored.confidence, original.confidence)
        self.assertEqual(restored, original)

    @given(name=forbidden_name_strategy)
    def test_forbidden_fields_are_always_rejected(self, name: str) -> None:
        with self.assertRaises(ValidationError):
            QueryAnalysis.model_validate(analysis_payload(**{name: "value"}))


if __name__ == "__main__":
    unittest.main()
