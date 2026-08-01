"""Contract tests for the deterministic route decision contract."""

import json
import unittest
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.route_decision import (
    RouteBudget,
    RouteDecision,
    RouteFilterRef,
)

DECISION_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
QUERY_ANALYSIS_ID = "33333333-3333-4333-8333-333333333333"
AUTHORIZATION_DECISION_ID = "44444444-4444-4444-8444-444444444444"
RUNTIME_SNAPSHOT_ID = "55555555-5555-4555-8555-555555555555"
UUID1_VALUE = "66666666-6666-1666-8666-666666666666"
DECIDED_AT = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC_HOUR = 8
APPROVED_FLOW_REF = "flow:loan-eligibility-v4"

UUID_FIELDS: tuple[str, ...] = (
    "decision_id",
    "request_id",
    "query_analysis_id",
    "authorization_decision_id",
    "runtime_snapshot_id",
)
LANES: tuple[str, ...] = (
    "deterministic",
    "fast",
    "composite",
    "clarify",
    "abstain",
    "deny",
)
TERMINAL_LANES: tuple[str, ...] = ("clarify", "abstain", "deny")
CAPABILITIES: tuple[str, ...] = (
    "document_retrieval",
    "semantic_analytics",
    "personal_selector",
    "rule_evaluator",
    "official_search",
)
COUNTER_LIMITS: tuple[tuple[str, int], ...] = (
    ("max_steps", 5),
    ("max_parallel_steps", 3),
    ("max_replans", 1),
    ("max_retrieval_retries", 1),
    ("max_analytics_repairs", 1),
    ("max_answer_repairs", 1),
)
FORBIDDEN_FIELDS: tuple[str, ...] = (
    "raw_message",
    "raw_query",
    "normalized_query",
    "standalone_query",
    "intent",
    "entities",
    "time_expressions",
    "confidence",
    "risk_signals",
    "model",
    "model_name",
    "model_output",
    "provider",
    "provider_response",
    "prompt",
    "system_prompt",
    "rationale",
    "rationale_text",
    "explanation",
    "reasoning",
    "chain_of_thought",
    "clarification_message",
    "denial_message",
    "answer",
    "execution_plan",
    "plan_steps",
    "dependency_graph",
    "capability_request",
    "tool",
    "tool_name",
    "tool_arguments",
    "sql",
    "query",
    "where",
    "predicate",
    "filter_expression",
    "filter_value",
    "operator",
    "endpoint",
    "url",
    "api_key",
    "token",
    "access_token",
    "secret",
    "password",
    "credentials",
    "roles",
    "groups",
    "principal_id",
    "security_context_id",
    "email",
    "display_name",
    "session_id",
    "http_status",
    "headers",
    "metadata",
    "attributes",
    "deadline_ms",
    "token_budget",
    "cost_budget",
)
SCHEMA_ARTIFACT = Path(__file__).resolve().parents[1] / "schemas/route-decision/1.0.0.schema.json"


def budget_payload(**overrides: int) -> dict[str, int]:
    """Build an all-zero budget payload with optional overrides."""
    payload = {name: 0 for name, _ in COUNTER_LIMITS}
    payload.update(overrides)
    return payload


def filter_payload(index: int = 0) -> dict[str, str]:
    """Build a valid approved-filter reference payload."""
    return {
        "filter_type": "authorization.scope",
        "filter_ref": f"scope-set:employee-self-service-v{index}",
    }


def decision_payload(lane: str = "deterministic", **overrides: object) -> dict[str, object]:
    """Build a valid decision payload for the requested lane."""
    payload: dict[str, object] = {
        "decision_id": DECISION_ID,
        "request_id": REQUEST_ID,
        "query_analysis_id": QUERY_ANALYSIS_ID,
        "authorization_decision_id": AUTHORIZATION_DECISION_ID,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "decided_at": DECIDED_AT,
        "effective_risk_level": "normal",
        "lane": lane,
        "route": "fixed.help",
        "planner_required": lane == "composite",
        "budget": budget_payload(),
        "rationale_code": "query.single_document_need",
        "policy_version": "1.0.0",
    }
    if lane == "fast":
        payload["route"] = "fast.document"
        payload["allowed_capabilities"] = ["document_retrieval"]
        payload["required_facts"] = ["fact.document"]
        payload["budget"] = budget_payload(max_steps=1, max_parallel_steps=1)
    elif lane == "composite":
        payload["route"] = "composite.default"
        payload["allowed_capabilities"] = ["document_retrieval", "semantic_analytics"]
        payload["required_facts"] = ["fact.document", "fact.analytics"]
        payload["budget"] = budget_payload(max_steps=3, max_parallel_steps=2)
    elif lane in TERMINAL_LANES:
        payload["route"] = f"terminal.{lane}"
        payload["rationale_code"] = "query.blocking_ambiguity"
    payload.update(overrides)
    return payload


def flow_payload(**overrides: object) -> dict[str, object]:
    """Build a valid deterministic predefined executable flow payload."""
    payload = decision_payload(
        "deterministic",
        route="flow.loan_eligibility",
        allowed_capabilities=["rule_evaluator"],
        required_facts=["fact.eligibility_rule"],
        filters=[filter_payload()],
        budget=budget_payload(max_steps=2, max_parallel_steps=1),
        approved_flow_ref=APPROVED_FLOW_REF,
    )
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    """Schema version literal behavior."""

    def test_default_schema_version(self) -> None:
        decision = RouteDecision.model_validate(decision_payload())
        self.assertEqual(decision.schema_version, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload(schema_version="1.1.0"))


class ValidLaneTests(unittest.TestCase):
    """Valid decisions for every supported lane."""

    def test_valid_deterministic_fixed_response(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("deterministic"))
        self.assertEqual(decision.lane, "deterministic")
        self.assertEqual(decision.allowed_capabilities, ())
        self.assertTrue(decision.budget.is_all_zero())

    def test_valid_deterministic_predefined_flow(self) -> None:
        decision = RouteDecision.model_validate(flow_payload())
        self.assertEqual(decision.allowed_capabilities, ("rule_evaluator",))
        self.assertEqual(decision.approved_flow_ref, APPROVED_FLOW_REF)
        self.assertEqual(decision.budget.max_steps, 2)

    def test_valid_fast_decision(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("fast"))
        self.assertEqual(decision.lane, "fast")
        self.assertFalse(decision.planner_required)
        self.assertEqual(decision.budget.max_steps, 1)

    def test_valid_composite_decision(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("composite"))
        self.assertTrue(decision.planner_required)
        self.assertEqual(len(decision.allowed_capabilities), 2)

    def test_valid_clarify_decision(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("clarify"))
        self.assertEqual(decision.lane, "clarify")
        self.assertTrue(decision.budget.is_all_zero())

    def test_valid_abstain_decision(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("abstain"))
        self.assertEqual(decision.lane, "abstain")
        self.assertEqual(decision.filters, ())

    def test_valid_deny_decision(self) -> None:
        decision = RouteDecision.model_validate(
            decision_payload("deny", rationale_code="authorization.denied")
        )
        self.assertEqual(decision.lane, "deny")
        self.assertIsNone(decision.approved_flow_ref)

    def test_every_lane_accepted(self) -> None:
        for lane in LANES:
            with self.subTest(lane=lane):
                decision = RouteDecision.model_validate(decision_payload(lane))
                self.assertEqual(decision.lane, lane)

    def test_unsupported_lane_rejected(self) -> None:
        for lane in ("planner", "Fast", "retrieval", ""):
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(lane))


class IdentifierAndTimestampTests(unittest.TestCase):
    """Identifier and timestamp validation."""

    def test_uuid4_enforced_for_every_identifier(self) -> None:
        for field in UUID_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(**{field: UUID1_VALUE}))

    def test_identifiers_parsed_as_uuid(self) -> None:
        decision = RouteDecision.model_validate(decision_payload())
        self.assertEqual(decision.decision_id, UUID(DECISION_ID))
        self.assertEqual(decision.authorization_decision_id, UUID(AUTHORIZATION_DECISION_ID))

    def test_naive_decided_timestamp_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload(decided_at="2026-01-01T12:00:00"))

    def test_non_utc_timestamp_normalized(self) -> None:
        decision = RouteDecision.model_validate(decision_payload())
        self.assertEqual(decision.decided_at.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(decision.decided_at.utcoffset().total_seconds(), 0.0)


class CatalogAndCodeTests(unittest.TestCase):
    """Capability catalog and controlled code validation."""

    def test_every_capability_accepted(self) -> None:
        for capability in CAPABILITIES:
            with self.subTest(capability=capability):
                decision = RouteDecision.model_validate(
                    decision_payload("fast", allowed_capabilities=[capability])
                )
                self.assertEqual(decision.allowed_capabilities, (capability,))

    def test_unsupported_capability_rejected(self) -> None:
        for capability in ("web_search", "Document_Retrieval", "planner", ""):
            with self.subTest(capability=capability), self.assertRaises(ValidationError):
                RouteDecision.model_validate(
                    decision_payload("fast", allowed_capabilities=[capability])
                )

    def test_valid_route_codes_accepted(self) -> None:
        for route in ("fixed.help", "fixed.capability_overview", "terminal.deny", "a"):
            with self.subTest(route=route):
                decision = RouteDecision.model_validate(decision_payload(route=route))
                self.assertEqual(decision.route, route)

    def test_invalid_route_codes_rejected(self) -> None:
        for route in ("Fixed.Help", " fixed.help", "fixed help", "fixed/help", "1fixed", ""):
            with self.subTest(route=route), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(route=route))

    def test_valid_rationale_codes_accepted(self) -> None:
        for code in ("query.single_document_need", "policy.high_risk_requires_flow"):
            with self.subTest(code=code):
                decision = RouteDecision.model_validate(decision_payload(rationale_code=code))
                self.assertEqual(decision.rationale_code, code)

    def test_invalid_rationale_codes_rejected(self) -> None:
        for code in ("Denied", "policy denied", "policy@denied", ""):
            with self.subTest(code=code), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(rationale_code=code))

    def test_valid_policy_version_accepted(self) -> None:
        for version in ("0.1.0", "1.0.0", "12.4.37"):
            with self.subTest(version=version):
                decision = RouteDecision.model_validate(decision_payload(policy_version=version))
                self.assertEqual(decision.policy_version, version)

    def test_invalid_policy_version_rejected(self) -> None:
        for version in ("1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(policy_version=version))


class FilterReferenceTests(unittest.TestCase):
    """Approved filter reference validation."""

    def test_valid_filter_reference(self) -> None:
        reference = RouteFilterRef.model_validate(filter_payload(3))
        self.assertEqual(reference.filter_type, "authorization.scope")
        self.assertEqual(reference.filter_ref, "scope-set:employee-self-service-v3")

    def test_blank_filter_reference_rejected(self) -> None:
        for value in ("", "   "):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RouteFilterRef.model_validate({"filter_type": "a.b", "filter_ref": value})

    def test_padded_filter_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteFilterRef.model_validate({"filter_type": "a.b", "filter_ref": " scope:x "})

    def test_nul_filter_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteFilterRef.model_validate({"filter_type": "a.b", "filter_ref": "scope\x00x"})

    def test_oversized_filter_reference_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteFilterRef.model_validate({"filter_type": "a.b", "filter_ref": "s" * 257})

    def test_filter_reference_preserved_exactly(self) -> None:
        value = "official-sources:education-v2"
        reference = RouteFilterRef.model_validate(
            {"filter_type": "official-source.allowlist", "filter_ref": value}
        )
        self.assertEqual(reference.filter_ref, value)

    def test_invalid_filter_type_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteFilterRef.model_validate(
                {"filter_type": "Authorization.Scope", "filter_ref": "scope:x"}
            )

    def test_duplicate_filter_references_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                flow_payload(filters=[filter_payload(1), filter_payload(1)])
            )

    def test_thirty_two_filters_accepted(self) -> None:
        decision = RouteDecision.model_validate(
            flow_payload(filters=[filter_payload(index) for index in range(32)])
        )
        self.assertEqual(len(decision.filters), 32)

    def test_thirty_three_filters_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                flow_payload(filters=[filter_payload(index) for index in range(33)])
            )

    def test_filter_order_preserved(self) -> None:
        payloads = [filter_payload(index) for index in (7, 2, 5)]
        decision = RouteDecision.model_validate(flow_payload(filters=payloads))
        self.assertEqual(
            [item.filter_ref for item in decision.filters],
            [item["filter_ref"] for item in payloads],
        )


class BudgetTests(unittest.TestCase):
    """Count-based budget validation."""

    def test_strict_integer_values_accepted(self) -> None:
        budget = RouteBudget.model_validate(budget_payload(max_steps=2, max_parallel_steps=2))
        self.assertEqual(budget.max_steps, 2)
        self.assertEqual(budget.max_parallel_steps, 2)

    def test_non_integer_values_rejected(self) -> None:
        for value in ("1", 1.5, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RouteBudget.model_validate(budget_payload(max_steps=value))

    def test_booleans_rejected_as_budget_integers(self) -> None:
        for name, _ in COUNTER_LIMITS:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteBudget.model_validate(budget_payload(**{name: True}))

    def test_every_global_maximum_accepted(self) -> None:
        payload = budget_payload(**{name: limit for name, limit in COUNTER_LIMITS})
        budget = RouteBudget.model_validate(payload)
        for name, limit in COUNTER_LIMITS:
            with self.subTest(name=name):
                self.assertEqual(getattr(budget, name), limit)

    def test_values_over_each_maximum_rejected(self) -> None:
        for name, limit in COUNTER_LIMITS:
            payload = budget_payload(max_steps=5, max_parallel_steps=3)
            payload[name] = limit + 1
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteBudget.model_validate(payload)

    def test_negative_values_rejected(self) -> None:
        for name, _ in COUNTER_LIMITS:
            payload = budget_payload(max_steps=1, max_parallel_steps=1)
            payload[name] = -1
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteBudget.model_validate(payload)

    def test_parallel_steps_greater_than_steps_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteBudget.model_validate(budget_payload(max_steps=1, max_parallel_steps=2))

    def test_zero_steps_with_parallelism_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteBudget.model_validate(budget_payload(max_steps=0, max_parallel_steps=1))

    def test_positive_steps_without_parallelism_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteBudget.model_validate(budget_payload(max_steps=2, max_parallel_steps=0))

    def test_all_zero_budget_reported(self) -> None:
        self.assertTrue(RouteBudget.model_validate(budget_payload()).is_all_zero())
        self.assertFalse(
            RouteBudget.model_validate(budget_payload(max_answer_repairs=1)).is_all_zero()
        )


class PlannerInvariantTests(unittest.TestCase):
    """Planner flag agreement with the selected lane."""

    def test_non_composite_lanes_reject_planner_required(self) -> None:
        for lane in LANES:
            if lane == "composite":
                continue
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(lane, planner_required=True))

    def test_composite_rejects_planner_not_required(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("composite", planner_required=False))


class TerminalLaneTests(unittest.TestCase):
    """Terminal lane invariants."""

    def test_terminal_lanes_require_all_zero_budget(self) -> None:
        for lane in TERMINAL_LANES:
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(
                    decision_payload(lane, budget=budget_payload(max_steps=1, max_parallel_steps=1))
                )

    def test_terminal_lanes_reject_capabilities(self) -> None:
        for lane in TERMINAL_LANES:
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(
                    decision_payload(lane, allowed_capabilities=["document_retrieval"])
                )

    def test_terminal_lanes_reject_required_facts(self) -> None:
        for lane in TERMINAL_LANES:
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(lane, required_facts=["fact.a"]))

    def test_terminal_lanes_reject_filters(self) -> None:
        for lane in TERMINAL_LANES:
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(lane, filters=[filter_payload()]))

    def test_terminal_lanes_reject_approved_flow_reference(self) -> None:
        for lane in TERMINAL_LANES:
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                RouteDecision.model_validate(
                    decision_payload(lane, approved_flow_ref=APPROVED_FLOW_REF)
                )

    def test_terminal_lanes_require_route_and_rationale(self) -> None:
        for field in ("route", "rationale_code"):
            payload = decision_payload("deny")
            del payload[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RouteDecision.model_validate(payload)


class FastLaneTests(unittest.TestCase):
    """Fast lane invariants."""

    def test_fast_rejects_zero_capabilities(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("fast", allowed_capabilities=[]))

    def test_fast_rejects_two_capabilities(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "fast", allowed_capabilities=["document_retrieval", "official_search"]
                )
            )

    def test_fast_requires_at_least_one_fact(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("fast", required_facts=[]))

    def test_fast_requires_exactly_one_step(self) -> None:
        for steps, parallel in ((0, 0), (2, 1), (2, 2)):
            with self.subTest(steps=steps), self.assertRaises(ValidationError):
                RouteDecision.model_validate(
                    decision_payload(
                        "fast",
                        budget=budget_payload(max_steps=steps, max_parallel_steps=parallel),
                    )
                )

    def test_fast_rejects_replanning(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "fast",
                    budget=budget_payload(max_steps=1, max_parallel_steps=1, max_replans=1),
                )
            )

    def test_fast_permits_bounded_retry_and_repair(self) -> None:
        decision = RouteDecision.model_validate(
            decision_payload(
                "fast",
                budget=budget_payload(
                    max_steps=1,
                    max_parallel_steps=1,
                    max_retrieval_retries=1,
                    max_analytics_repairs=1,
                    max_answer_repairs=1,
                ),
            )
        )
        self.assertEqual(decision.budget.max_retrieval_retries, 1)
        self.assertEqual(decision.budget.max_answer_repairs, 1)


class CompositeLaneTests(unittest.TestCase):
    """Composite lane invariants."""

    def test_composite_requires_capability(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("composite", allowed_capabilities=[]))

    def test_composite_requires_fact(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("composite", required_facts=[]))

    def test_composite_requires_two_steps(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "composite", budget=budget_payload(max_steps=1, max_parallel_steps=1)
                )
            )

    def test_composite_accepts_five_steps(self) -> None:
        decision = RouteDecision.model_validate(
            decision_payload("composite", budget=budget_payload(max_steps=5, max_parallel_steps=3))
        )
        self.assertEqual(decision.budget.max_steps, 5)

    def test_composite_rejects_six_steps(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "composite", budget=budget_payload(max_steps=6, max_parallel_steps=3)
                )
            )

    def test_composite_permits_one_replan(self) -> None:
        decision = RouteDecision.model_validate(
            decision_payload(
                "composite",
                budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
            )
        )
        self.assertEqual(decision.budget.max_replans, 1)

    def test_composite_rejects_approved_flow_reference(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload("composite", approved_flow_ref=APPROVED_FLOW_REF)
            )


class DeterministicLaneTests(unittest.TestCase):
    """Deterministic lane invariants."""

    def test_fixed_route_requires_zero_budget(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "deterministic", budget=budget_payload(max_steps=1, max_parallel_steps=1)
                )
            )

    def test_fixed_route_rejects_facts_or_filters(self) -> None:
        for overrides in ({"required_facts": ["fact.a"]}, {"filters": [filter_payload()]}):
            with self.subTest(overrides=tuple(overrides)), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload("deterministic", **overrides))

    def test_executable_flow_requires_fact(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(flow_payload(required_facts=[]))

    def test_executable_flow_requires_steps(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(flow_payload(budget=budget_payload()))

    def test_executable_flow_accepts_multiple_bounded_steps(self) -> None:
        decision = RouteDecision.model_validate(
            flow_payload(
                allowed_capabilities=["rule_evaluator", "official_search"],
                budget=budget_payload(max_steps=5, max_parallel_steps=3),
            )
        )
        self.assertEqual(decision.budget.max_parallel_steps, 3)

    def test_deterministic_rejects_replanning(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                flow_payload(
                    budget=budget_payload(max_steps=2, max_parallel_steps=1, max_replans=1)
                )
            )

    def test_approved_flow_reference_accepted_for_deterministic_lane(self) -> None:
        decision = RouteDecision.model_validate(flow_payload())
        self.assertEqual(decision.approved_flow_ref, APPROVED_FLOW_REF)


class RiskTests(unittest.TestCase):
    """Effective risk and approved-flow interaction."""

    def test_unresolved_risk_fast_without_approved_flow_rejected(self) -> None:
        for level in ("high", "unknown"):
            with self.subTest(level=level), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload("fast", effective_risk_level=level))

    def test_unresolved_risk_fast_with_approved_flow_accepted(self) -> None:
        for level in ("high", "unknown"):
            with self.subTest(level=level):
                decision = RouteDecision.model_validate(
                    decision_payload(
                        "fast",
                        effective_risk_level=level,
                        approved_flow_ref=APPROVED_FLOW_REF,
                        rationale_code="policy.high_risk_requires_flow",
                    )
                )
                self.assertEqual(decision.effective_risk_level, level)

    def test_normal_risk_fast_without_approved_flow_accepted(self) -> None:
        for level in ("normal", "elevated"):
            with self.subTest(level=level):
                decision = RouteDecision.model_validate(
                    decision_payload("fast", effective_risk_level=level)
                )
                self.assertIsNone(decision.approved_flow_ref)

    def test_unsupported_risk_level_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload(effective_risk_level="critical"))


class CollectionTests(unittest.TestCase):
    """Collection defaults, uniqueness, ordering, and bounds."""

    def test_missing_collections_become_empty_tuples(self) -> None:
        decision = RouteDecision.model_validate(decision_payload())
        self.assertEqual(decision.allowed_capabilities, ())
        self.assertEqual(decision.required_facts, ())
        self.assertEqual(decision.filters, ())

    def test_explicit_null_collections_rejected(self) -> None:
        for field in ("allowed_capabilities", "required_facts", "filters"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(**{field: None}))

    def test_duplicate_capabilities_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload(
                    "composite",
                    allowed_capabilities=["document_retrieval", "document_retrieval"],
                )
            )

    def test_capability_order_preserved(self) -> None:
        ordered = ["official_search", "document_retrieval", "rule_evaluator"]
        decision = RouteDecision.model_validate(
            decision_payload("composite", allowed_capabilities=ordered)
        )
        self.assertEqual(list(decision.allowed_capabilities), ordered)

    def test_five_capabilities_accepted(self) -> None:
        decision = RouteDecision.model_validate(
            decision_payload("composite", allowed_capabilities=list(CAPABILITIES))
        )
        self.assertEqual(len(decision.allowed_capabilities), 5)

    def test_duplicate_required_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload("composite", required_facts=["fact.a", "fact.a"])
            )

    def test_required_fact_order_preserved(self) -> None:
        ordered = ["fact.c", "fact.a", "fact.b"]
        decision = RouteDecision.model_validate(
            decision_payload("composite", required_facts=ordered)
        )
        self.assertEqual(list(decision.required_facts), ordered)

    def test_thirty_two_required_facts_accepted(self) -> None:
        facts = [f"fact.{index}" for index in range(32)]
        decision = RouteDecision.model_validate(decision_payload("composite", required_facts=facts))
        self.assertEqual(len(decision.required_facts), 32)

    def test_thirty_three_required_facts_rejected(self) -> None:
        facts = [f"fact.{index}" for index in range(33)]
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("composite", required_facts=facts))

    def test_invalid_required_fact_code_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload("composite", required_facts=["Fact.A"]))


class ForbiddenFieldTests(unittest.TestCase):
    """Unknown and forbidden field rejection."""

    def test_root_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload(unexpected="value"))

    def test_forbidden_root_fields_rejected(self) -> None:
        for name in FORBIDDEN_FIELDS:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteDecision.model_validate(decision_payload(**{name: "value"}))

    def test_forbidden_nested_filter_fields_rejected(self) -> None:
        for name in FORBIDDEN_FIELDS:
            payload = filter_payload()
            payload[name] = "value"
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteFilterRef.model_validate(payload)

    def test_forbidden_nested_budget_fields_rejected(self) -> None:
        for name in FORBIDDEN_FIELDS:
            payload: dict[str, object] = dict(budget_payload())
            payload[name] = 1
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RouteBudget.model_validate(payload)


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    """Immutability and serialization behavior."""

    def test_root_model_immutable(self) -> None:
        decision = RouteDecision.model_validate(decision_payload("fast"))
        with self.assertRaises(ValidationError):
            decision.lane = "composite"

    def test_nested_models_immutable(self) -> None:
        decision = RouteDecision.model_validate(flow_payload())
        with self.assertRaises(ValidationError):
            decision.budget.max_steps = 4
        with self.assertRaises(ValidationError):
            decision.filters[0].filter_ref = "scope-set:other"

    def test_json_round_trip(self) -> None:
        original = RouteDecision.model_validate(flow_payload())
        restored = RouteDecision.model_validate_json(original.model_dump_json())
        self.assertEqual(restored, original)


class SchemaTests(unittest.TestCase):
    """Generated and committed JSON Schema behavior."""

    def setUp(self) -> None:
        self.schema = RouteDecision.model_json_schema()

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:route-decision:1.0.0")

    def test_root_schema_closed(self) -> None:
        self.assertIs(self.schema["additionalProperties"], False)

    def test_nested_schemas_closed(self) -> None:
        self.assertEqual(set(self.schema["$defs"]), {"RouteBudget", "RouteFilterRef"})
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertIs(definition["additionalProperties"], False)

    def test_committed_schema_matches_generated_schema(self) -> None:
        content = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.assertEqual(json.loads(content), self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        content = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("}\n"))
        self.assertFalse(content.endswith("\n\n"))

    def test_lane_catalog_in_schema(self) -> None:
        self.assertEqual(tuple(self.schema["properties"]["lane"]["enum"]), LANES)

    def test_capability_catalog_in_schema(self) -> None:
        self.assertEqual(
            tuple(self.schema["properties"]["allowed_capabilities"]["items"]["enum"]),
            CAPABILITIES,
        )

    def test_forbidden_property_names_absent(self) -> None:
        declared = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            declared.update(definition["properties"])
        for name in FORBIDDEN_FIELDS:
            with self.subTest(name=name):
                self.assertNotIn(name, declared)

    def test_nested_models_have_no_schema_version(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(name=name):
                self.assertNotIn("schema_version", definition["properties"])


class ExportTests(unittest.TestCase):
    """Package export surface."""

    def test_public_exports_available(self) -> None:
        expected = {
            "CapabilityName",
            "RouteBudget",
            "RouteDecision",
            "RouteFilterRef",
            "RouteLane",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in sorted(expected):
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_private_validation_aliases_not_exported(self) -> None:
        for name in ("_CanonicalCode", "_OpaqueRef", "_Uuid4", "_Capabilities", "_Filters"):
            with self.subTest(name=name):
                self.assertNotIn(name, contracts.__all__)


CODE_STRATEGY = st.from_regex(r"\A[a-z][a-z0-9._:-]{0,8}\Z")


class RouteDecisionPropertyTests(unittest.TestCase):
    """Bounded property-based checks for route decision invariants."""

    @given(st.lists(st.sampled_from(CAPABILITIES), min_size=1, max_size=5, unique=True))
    def test_unique_capability_tuples_preserve_order(self, capabilities: list[str]) -> None:
        decision = RouteDecision.model_validate(
            decision_payload("composite", allowed_capabilities=capabilities)
        )
        self.assertEqual(list(decision.allowed_capabilities), capabilities)

    @given(st.lists(st.sampled_from(CAPABILITIES), min_size=1, max_size=4, unique=True))
    def test_duplicate_capability_rejected(self, capabilities: list[str]) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(
                decision_payload("composite", allowed_capabilities=[*capabilities, capabilities[0]])
            )

    @given(
        st.lists(CODE_STRATEGY, min_size=1, max_size=6, unique=True),
        st.lists(CODE_STRATEGY, min_size=1, max_size=6, unique=True),
    )
    def test_unique_fact_and_filter_tuples_preserve_order(
        self, facts: list[str], filter_types: list[str]
    ) -> None:
        filters = [
            {"filter_type": filter_type, "filter_ref": f"scope-set:{index}"}
            for index, filter_type in enumerate(filter_types)
        ]
        decision = RouteDecision.model_validate(
            decision_payload("composite", required_facts=facts, filters=filters)
        )
        self.assertEqual(list(decision.required_facts), facts)
        self.assertEqual([item.filter_type for item in decision.filters], filter_types)

    @given(
        st.integers(min_value=1, max_value=5),
        st.integers(min_value=0, max_value=1),
        st.integers(min_value=0, max_value=1),
        st.integers(min_value=0, max_value=1),
    )
    def test_valid_budget_values_round_trip(
        self, steps: int, retries: int, analytics_repairs: int, answer_repairs: int
    ) -> None:
        parallel = min(3, steps)
        budget = RouteBudget.model_validate(
            budget_payload(
                max_steps=steps,
                max_parallel_steps=parallel,
                max_retrieval_retries=retries,
                max_analytics_repairs=analytics_repairs,
                max_answer_repairs=answer_repairs,
            )
        )
        restored = RouteBudget.model_validate_json(budget.model_dump_json())
        self.assertEqual(restored, budget)

    @given(st.sampled_from(FORBIDDEN_FIELDS), st.sampled_from(LANES))
    def test_forbidden_fields_always_rejected(self, name: str, lane: str) -> None:
        with self.assertRaises(ValidationError):
            RouteDecision.model_validate(decision_payload(lane, **{name: "value"}))


if __name__ == "__main__":
    unittest.main()
