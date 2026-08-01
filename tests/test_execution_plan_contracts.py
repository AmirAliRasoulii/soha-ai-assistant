"""Contract tests for the bounded execution plan, schema version 1.0.0."""

import json
import unittest
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.execution_plan import (
    ExecutionPlan,
    PlanFactSpec,
    PlanInputBinding,
    PlanParallelGroup,
    PlanStep,
)

PLAN_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
ROUTE_DECISION_ID = "33333333-3333-4333-8333-333333333333"
AUTHORIZATION_DECISION_ID = "44444444-4444-4444-8444-444444444444"
RUNTIME_SNAPSHOT_ID = "55555555-5555-4555-8555-555555555555"
PARENT_PLAN_ID = "77777777-7777-4777-8777-777777777777"
UUID1_VALUE = "66666666-6666-1666-8666-666666666666"
PLANNED_AT = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC_HOUR = 8

UUID_FIELDS = (
    "plan_id",
    "request_id",
    "route_decision_id",
    "authorization_decision_id",
    "runtime_snapshot_id",
)
LANES = ("deterministic", "fast", "composite")
COMPOSITION_TYPES = (
    "single",
    "sectioned",
    "comparison",
    "rule_join",
    "temporal_join",
    "aggregate",
)
MISSING_EVIDENCE_POLICIES = ("partial", "clarify", "abstain")
INPUT_SOURCE_KINDS = (
    "query_analysis",
    "route_decision",
    "runtime_snapshot",
    "approved_artifact",
    "step_output",
)
FACT_SCOPES = ("general", "personal")
CAPABILITIES = (
    "document_retrieval",
    "semantic_analytics",
    "personal_selector",
    "rule_evaluator",
    "official_search",
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
    "rationale",
    "rationale_text",
    "reasoning",
    "chain_of_thought",
    "answer",
    "clarification_message",
    "denial_message",
    "tool",
    "tool_name",
    "tool_arguments",
    "function_call",
    "sql",
    "query",
    "statement",
    "where",
    "predicate",
    "filter_expression",
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
    "headers",
    "http_status",
    "metadata",
    "attributes",
    "input_value",
    "output_value",
    "typed_output",
    "evidence",
    "evidence_ids",
    "error",
    "exception",
    "retry_loop",
    "deadline_ms",
    "token_budget",
    "cost_budget",
)
SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "execution-plan" / "1.0.0.schema.json"
)


def budget_payload(**overrides: object) -> dict[str, object]:
    """Build a route budget payload with all counters at zero by default."""
    payload: dict[str, object] = {
        "max_steps": 0,
        "max_parallel_steps": 0,
        "max_replans": 0,
        "max_retrieval_retries": 0,
        "max_analytics_repairs": 0,
        "max_answer_repairs": 0,
    }
    payload.update(overrides)
    return payload


def fact_payload(
    fact_id: str = "fact.document",
    value_type: str = "type.document",
    data_scope: str = "general",
) -> dict[str, object]:
    """Build a typed produced-fact declaration."""
    return {"fact_id": fact_id, "value_type": value_type, "data_scope": data_scope}


def binding_payload(
    input_name: str = "input.subject",
    source_kind: str = "query_analysis",
    source_ref: str = "analysis.subject",
    source_step_id: str | None = None,
    value_type: str = "type.subject",
    data_scope: str = "general",
) -> dict[str, object]:
    """Build a typed input binding payload."""
    return {
        "input_name": input_name,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "source_step_id": source_step_id,
        "value_type": value_type,
        "data_scope": data_scope,
    }


def step_payload(
    step_id: str = "step.retrieve",
    capability: str = "document_retrieval",
    operation: str = "document.retrieve",
    depends_on: list[str] | None = None,
    input_bindings: list[dict[str, object]] | None = None,
    produces: list[dict[str, object]] | None = None,
    required: bool = True,
) -> dict[str, object]:
    """Build a plan step payload."""
    return {
        "step_id": step_id,
        "capability": capability,
        "operation": operation,
        "depends_on": list(depends_on or []),
        "input_bindings": list(input_bindings or []),
        "produces": list(produces if produces is not None else [fact_payload()]),
        "required": required,
    }


def group_payload(group_id: str, step_ids: list[str]) -> dict[str, object]:
    """Build a parallel group payload."""
    return {"group_id": group_id, "step_ids": list(step_ids)}


def analysis_step() -> dict[str, object]:
    """Build a semantic analytics step consuming a retrieved document fact."""
    return step_payload(
        step_id="step.analyze",
        capability="semantic_analytics",
        operation="analytics.execute_logical_plan",
        depends_on=["step.retrieve"],
        input_bindings=[
            binding_payload(
                input_name="input.document",
                source_kind="step_output",
                source_ref="fact.document",
                source_step_id="step.retrieve",
                value_type="type.document",
            )
        ],
        produces=[fact_payload("fact.analysis", "type.analysis")],
    )


def plan_payload(lane: str = "fast", **overrides: object) -> dict[str, object]:
    """Build a valid plan payload for the requested execution lane."""
    payload: dict[str, object] = {
        "plan_id": PLAN_ID,
        "request_id": REQUEST_ID,
        "route_decision_id": ROUTE_DECISION_ID,
        "authorization_decision_id": AUTHORIZATION_DECISION_ID,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "planned_at": PLANNED_AT,
        "lane": lane,
        "goal": "goal.answer_question",
        "allowed_capabilities": ["document_retrieval"],
        "required_facts": ["fact.document"],
        "steps": [step_payload()],
        "parallel_groups": [group_payload("group.retrieve", ["step.retrieve"])],
        "composition_type": "single",
        "success_condition": "all_required_facts",
        "missing_evidence_policy": "clarify",
        "budget": budget_payload(max_steps=1, max_parallel_steps=1),
        "revision": 0,
        "parent_plan_id": None,
        "plan_builder_version": "1.0.0",
    }
    if lane == "composite":
        payload["allowed_capabilities"] = ["document_retrieval", "semantic_analytics"]
        payload["required_facts"] = ["fact.analysis"]
        payload["steps"] = [step_payload(), analysis_step()]
        payload["parallel_groups"] = [
            group_payload("group.retrieve", ["step.retrieve"]),
            group_payload("group.analyze", ["step.analyze"]),
        ]
        payload["composition_type"] = "sectioned"
        payload["budget"] = budget_payload(max_steps=3, max_parallel_steps=2)
    payload.update(overrides)
    return payload


def deterministic_flow_payload(**overrides: object) -> dict[str, object]:
    """Build a valid multi-step deterministic predefined flow payload."""
    payload = plan_payload(
        "deterministic",
        allowed_capabilities=["document_retrieval", "semantic_analytics"],
        required_facts=["fact.analysis"],
        steps=[step_payload(), analysis_step()],
        parallel_groups=[
            group_payload("group.retrieve", ["step.retrieve"]),
            group_payload("group.analyze", ["step.analyze"]),
        ],
        composition_type="rule_join",
        budget=budget_payload(max_steps=2, max_parallel_steps=1),
    )
    payload.update(overrides)
    return payload


class SchemaVersionTests(unittest.TestCase):
    """Schema version literal behavior."""

    def test_default_schema_version(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        self.assertEqual(plan.schema_version, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(schema_version="1.1.0"))


class ValidPlanTests(unittest.TestCase):
    """Valid plans for each supported execution lane."""

    def test_valid_fast_plan(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("fast"))
        self.assertEqual(plan.lane, "fast")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.composition_type, "single")

    def test_valid_composite_plan(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(len(plan.parallel_groups), 2)
        self.assertEqual(plan.required_facts, ("fact.analysis",))

    def test_valid_deterministic_single_step_plan(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("deterministic"))
        self.assertEqual(plan.lane, "deterministic")
        self.assertEqual(plan.composition_type, "single")

    def test_valid_deterministic_multi_step_plan(self) -> None:
        plan = ExecutionPlan.model_validate(deterministic_flow_payload())
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.composition_type, "rule_join")

    def test_every_lane_accepted(self) -> None:
        for lane in LANES:
            with self.subTest(lane=lane):
                self.assertEqual(ExecutionPlan.model_validate(plan_payload(lane)).lane, lane)

    def test_unsupported_lane_rejected(self) -> None:
        for lane in ("clarify", "deny", "Fast", ""):
            with self.subTest(lane=lane), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(lane))


class IdentifierAndTimestampTests(unittest.TestCase):
    """Identifier and timestamp validation."""

    def test_uuid4_enforced_for_every_identifier(self) -> None:
        for field in UUID_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(**{field: UUID1_VALUE}))

    def test_uuid4_enforced_for_parent_plan_id(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(
                    "composite",
                    revision=1,
                    parent_plan_id=UUID1_VALUE,
                    budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
                )
            )

    def test_identifiers_parsed_as_uuid(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        self.assertEqual(plan.plan_id, UUID(PLAN_ID))
        self.assertEqual(plan.route_decision_id, UUID(ROUTE_DECISION_ID))

    def test_naive_planned_timestamp_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(planned_at="2026-01-01T12:00:00"))

    def test_non_utc_timestamp_normalized(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        self.assertEqual(plan.planned_at.hour, EXPECTED_UTC_HOUR)
        self.assertEqual(plan.planned_at.utcoffset().total_seconds(), 0.0)


class LiteralCatalogTests(unittest.TestCase):
    """Closed literal catalogs."""

    def test_every_composition_type_accepted(self) -> None:
        for composition in COMPOSITION_TYPES:
            with self.subTest(composition=composition):
                payload = (
                    plan_payload("fast")
                    if composition == "single"
                    else plan_payload("composite", composition_type=composition)
                )
                plan = ExecutionPlan.model_validate(payload)
                self.assertEqual(plan.composition_type, composition)

    def test_unsupported_composition_type_rejected(self) -> None:
        for composition in ("merge", "Single", ""):
            with self.subTest(composition=composition), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(composition_type=composition))

    def test_every_missing_evidence_policy_accepted(self) -> None:
        for policy in MISSING_EVIDENCE_POLICIES:
            with self.subTest(policy=policy):
                plan = ExecutionPlan.model_validate(plan_payload(missing_evidence_policy=policy))
                self.assertEqual(plan.missing_evidence_policy, policy)

    def test_unsupported_missing_evidence_policy_rejected(self) -> None:
        for policy in ("retry", "Partial", ""):
            with self.subTest(policy=policy), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(missing_evidence_policy=policy))

    def test_every_input_source_kind_accepted(self) -> None:
        for kind in INPUT_SOURCE_KINDS:
            with self.subTest(kind=kind):
                source_step_id = "step.retrieve" if kind == "step_output" else None
                binding = PlanInputBinding.model_validate(
                    binding_payload(source_kind=kind, source_step_id=source_step_id)
                )
                self.assertEqual(binding.source_kind, kind)

    def test_unsupported_input_source_kind_rejected(self) -> None:
        for kind in ("external_api", "StepOutput", ""):
            with self.subTest(kind=kind), self.assertRaises(ValidationError):
                PlanInputBinding.model_validate(binding_payload(source_kind=kind))

    def test_both_fact_scopes_accepted(self) -> None:
        for scope in FACT_SCOPES:
            with self.subTest(scope=scope):
                fact = PlanFactSpec.model_validate(fact_payload(data_scope=scope))
                self.assertEqual(fact.data_scope, scope)

    def test_unsupported_fact_scope_rejected(self) -> None:
        for scope in ("confidential", "General", ""):
            with self.subTest(scope=scope), self.assertRaises(ValidationError):
                PlanFactSpec.model_validate(fact_payload(data_scope=scope))

    def test_success_condition_literal_accepted(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        self.assertEqual(plan.success_condition, "all_required_facts")

    def test_unsupported_success_condition_rejected(self) -> None:
        for condition in ("any_fact", "partial", ""):
            with self.subTest(condition=condition), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(success_condition=condition))


class CanonicalCodeTests(unittest.TestCase):
    """Canonical code validation for controlled identifiers."""

    def test_valid_goal_preserved(self) -> None:
        for goal in ("goal.answer_question", "goal.compare-policies", "g"):
            with self.subTest(goal=goal):
                self.assertEqual(ExecutionPlan.model_validate(plan_payload(goal=goal)).goal, goal)

    def test_invalid_goal_rejected(self) -> None:
        for goal in ("Goal.Answer", " goal.answer", "goal answer", "goal/answer", "1goal", ""):
            with self.subTest(goal=goal), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(goal=goal))

    def test_invalid_step_and_fact_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(step_payload(step_id="Step.Retrieve"))
        with self.assertRaises(ValidationError):
            PlanFactSpec.model_validate(fact_payload(fact_id="Fact.Document"))
        with self.assertRaises(ValidationError):
            PlanParallelGroup.model_validate(group_payload("Group.One", ["step.retrieve"]))

    def test_valid_plan_builder_version_accepted(self) -> None:
        for version in ("0.1.0", "1.0.0", "12.4.37"):
            with self.subTest(version=version):
                plan = ExecutionPlan.model_validate(plan_payload(plan_builder_version=version))
                self.assertEqual(plan.plan_builder_version, version)

    def test_invalid_plan_builder_version_rejected(self) -> None:
        for version in ("1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(plan_builder_version=version))


class NestedModelTests(unittest.TestCase):
    """Nested fact, binding, step, and group models."""

    def test_valid_fact_specification(self) -> None:
        fact = PlanFactSpec.model_validate(fact_payload("fact.policy", "type.policy", "personal"))
        self.assertEqual(fact.fact_id, "fact.policy")
        self.assertEqual(fact.value_type, "type.policy")
        self.assertEqual(fact.data_scope, "personal")

    def test_unknown_fact_field_rejected(self) -> None:
        payload = fact_payload()
        payload["value"] = "text"
        with self.assertRaises(ValidationError):
            PlanFactSpec.model_validate(payload)

    def test_valid_non_step_binding(self) -> None:
        binding = PlanInputBinding.model_validate(binding_payload())
        self.assertIsNone(binding.source_step_id)

    def test_non_step_binding_with_source_step_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanInputBinding.model_validate(binding_payload(source_step_id="step.retrieve"))

    def test_valid_step_output_binding(self) -> None:
        binding = PlanInputBinding.model_validate(
            binding_payload(
                source_kind="step_output",
                source_ref="fact.document",
                source_step_id="step.retrieve",
            )
        )
        self.assertEqual(binding.source_step_id, "step.retrieve")

    def test_step_output_binding_without_source_step_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanInputBinding.model_validate(
                binding_payload(source_kind="step_output", source_ref="fact.document")
            )

    def test_unknown_binding_field_rejected(self) -> None:
        payload = binding_payload()
        payload["input_value"] = "text"
        with self.assertRaises(ValidationError):
            PlanInputBinding.model_validate(payload)

    def test_step_collection_defaults(self) -> None:
        payload = step_payload()
        del payload["depends_on"]
        del payload["input_bindings"]
        step = PlanStep.model_validate(payload)
        self.assertEqual(step.depends_on, ())
        self.assertEqual(step.input_bindings, ())

    def test_duplicate_input_names_rejected(self) -> None:
        bindings = [
            binding_payload(
                input_name="input.document",
                source_kind="step_output",
                source_ref="fact.document",
                source_step_id="step.retrieve",
            ),
            binding_payload(
                input_name="input.document",
                source_kind="step_output",
                source_ref="fact.other",
                source_step_id="step.retrieve",
            ),
        ]
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(
                step_payload(
                    step_id="step.analyze", depends_on=["step.retrieve"], input_bindings=bindings
                )
            )

    def test_duplicate_dependencies_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(
                step_payload(
                    step_id="step.analyze",
                    depends_on=["step.retrieve", "step.retrieve"],
                    input_bindings=[
                        binding_payload(
                            input_name="input.document",
                            source_kind="step_output",
                            source_ref="fact.document",
                            source_step_id="step.retrieve",
                        )
                    ],
                )
            )

    def test_duplicate_produced_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(step_payload(produces=[fact_payload(), fact_payload()]))

    def test_self_dependency_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(step_payload(depends_on=["step.retrieve"]))

    def test_step_output_binding_requires_declared_dependency(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(
                step_payload(
                    step_id="step.analyze",
                    input_bindings=[
                        binding_payload(
                            input_name="input.document",
                            source_kind="step_output",
                            source_ref="fact.document",
                            source_step_id="step.retrieve",
                        )
                    ],
                )
            )

    def test_declared_dependency_requires_binding_consumer(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(
                step_payload(step_id="step.analyze", depends_on=["step.retrieve"])
            )

    def test_empty_produced_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(step_payload(produces=[]))

    def test_sixteen_produced_facts_accepted(self) -> None:
        facts = [fact_payload(f"fact.item{index}") for index in range(16)]
        step = PlanStep.model_validate(step_payload(produces=facts))
        self.assertEqual(len(step.produces), 16)

    def test_seventeen_produced_facts_rejected(self) -> None:
        facts = [fact_payload(f"fact.item{index}") for index in range(17)]
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(step_payload(produces=facts))

    def test_unknown_step_field_rejected(self) -> None:
        payload = step_payload()
        payload["tool_name"] = "retriever"
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(payload)

    def test_valid_parallel_group(self) -> None:
        group = PlanParallelGroup.model_validate(group_payload("group.one", ["step.retrieve"]))
        self.assertEqual(group.step_ids, ("step.retrieve",))

    def test_empty_parallel_group_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanParallelGroup.model_validate(group_payload("group.one", []))

    def test_three_parallel_steps_accepted(self) -> None:
        group = PlanParallelGroup.model_validate(
            group_payload("group.one", ["step.a", "step.b", "step.c"])
        )
        self.assertEqual(len(group.step_ids), 3)

    def test_four_parallel_steps_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PlanParallelGroup.model_validate(
                group_payload("group.one", ["step.a", "step.b", "step.c", "step.d"])
            )

    def test_unknown_group_field_rejected(self) -> None:
        payload = group_payload("group.one", ["step.retrieve"])
        payload["metadata"] = "value"
        with self.assertRaises(ValidationError):
            PlanParallelGroup.model_validate(payload)


class PlanCollectionTests(unittest.TestCase):
    """Plan-level collection bounds, uniqueness, and order."""

    def test_explicit_null_collections_rejected(self) -> None:
        for field in ("allowed_capabilities", "required_facts", "steps", "parallel_groups"):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(**{field: None}))

    def test_duplicate_plan_step_ids_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            steps=[step_payload(), step_payload()],
            parallel_groups=[group_payload("group.retrieve", ["step.retrieve"])],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_duplicate_parallel_group_ids_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[
                group_payload("group.same", ["step.retrieve"]),
                group_payload("group.same", ["step.analyze"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_duplicate_allowed_capabilities_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(allowed_capabilities=["document_retrieval", "document_retrieval"])
            )

    def test_allowed_capability_order_preserved(self) -> None:
        payload = plan_payload(
            "composite", allowed_capabilities=["semantic_analytics", "document_retrieval"]
        )
        plan = ExecutionPlan.model_validate(payload)
        self.assertEqual(plan.allowed_capabilities, ("semantic_analytics", "document_retrieval"))

    def test_duplicate_required_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(required_facts=["fact.document", "fact.document"])
            )

    def test_required_fact_order_preserved(self) -> None:
        payload = plan_payload(
            "composite",
            required_facts=["fact.analysis", "fact.document"],
        )
        plan = ExecutionPlan.model_validate(payload)
        self.assertEqual(plan.required_facts, ("fact.analysis", "fact.document"))

    def test_five_steps_accepted(self) -> None:
        steps = [step_payload()]
        groups = [group_payload("group.retrieve", ["step.retrieve"])]
        facts = ["fact.document"]
        for index in range(1, 5):
            step_id = f"step.extra{index}"
            fact_id = f"fact.extra{index}"
            steps.append(
                step_payload(
                    step_id=step_id,
                    capability="official_search",
                    operation="official.search_allowlisted",
                    produces=[fact_payload(fact_id, "type.official")],
                )
            )
            groups.append(group_payload(f"group.extra{index}", [step_id]))
            facts.append(fact_id)
        plan = ExecutionPlan.model_validate(
            plan_payload(
                "composite",
                allowed_capabilities=["document_retrieval", "official_search"],
                required_facts=facts,
                steps=steps,
                parallel_groups=groups,
                budget=budget_payload(max_steps=5, max_parallel_steps=1),
            )
        )
        self.assertEqual(len(plan.steps), 5)

    def test_six_steps_rejected(self) -> None:
        steps = [
            step_payload(
                step_id=f"step.item{index}",
                produces=[fact_payload(f"fact.item{index}")],
            )
            for index in range(6)
        ]
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload("composite", steps=steps))

    def test_six_groups_rejected(self) -> None:
        groups = [group_payload(f"group.item{index}", ["step.retrieve"]) for index in range(6)]
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload("composite", parallel_groups=groups))


class ParallelGroupPlanTests(unittest.TestCase):
    """Parallel-group partition and layering invariants."""

    def test_every_step_appears_in_exactly_one_group(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        grouped = [step_id for group in plan.parallel_groups for step_id in group.step_ids]
        self.assertEqual(sorted(grouped), sorted(step.step_id for step in plan.steps))

    def test_missing_step_from_groups_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[group_payload("group.retrieve", ["step.retrieve"])],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_duplicate_step_across_groups_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
                group_payload("group.repeat", ["step.retrieve"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_unknown_grouped_step_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
                group_payload("group.unknown", ["step.missing"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_group_larger_than_budget_parallelism_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            allowed_capabilities=["document_retrieval", "official_search"],
            required_facts=["fact.document", "fact.official"],
            steps=[
                step_payload(),
                step_payload(
                    step_id="step.search",
                    capability="official_search",
                    operation="official.search_allowlisted",
                    produces=[fact_payload("fact.official", "type.official")],
                ),
            ],
            parallel_groups=[group_payload("group.wide", ["step.retrieve", "step.search"])],
            budget=budget_payload(max_steps=2, max_parallel_steps=1),
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_parallel_group_within_budget_accepted(self) -> None:
        payload = plan_payload(
            "composite",
            allowed_capabilities=["document_retrieval", "official_search"],
            required_facts=["fact.document", "fact.official"],
            steps=[
                step_payload(),
                step_payload(
                    step_id="step.search",
                    capability="official_search",
                    operation="official.search_allowlisted",
                    produces=[fact_payload("fact.official", "type.official")],
                ),
            ],
            parallel_groups=[group_payload("group.wide", ["step.retrieve", "step.search"])],
            budget=budget_payload(max_steps=2, max_parallel_steps=2),
        )
        plan = ExecutionPlan.model_validate(payload)
        self.assertEqual(len(plan.parallel_groups), 1)

    def test_dependency_in_same_group_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[group_payload("group.both", ["step.retrieve", "step.analyze"])],
            budget=budget_payload(max_steps=3, max_parallel_steps=2),
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_dependency_in_later_group_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            parallel_groups=[
                group_payload("group.analyze", ["step.analyze"]),
                group_payload("group.retrieve", ["step.retrieve"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_dependency_in_earlier_group_accepted(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        self.assertEqual(plan.parallel_groups[0].step_ids, ("step.retrieve",))
        self.assertEqual(plan.parallel_groups[1].step_ids, ("step.analyze",))


class DagOrderTests(unittest.TestCase):
    """Topological order invariants over the bounded plan graph."""

    def test_dependency_must_reference_existing_step(self) -> None:
        analysis = analysis_step()
        analysis["depends_on"] = ["step.missing"]
        bindings = analysis["input_bindings"]
        assert isinstance(bindings, list)
        binding = bindings[0]
        assert isinstance(binding, dict)
        binding["source_step_id"] = "step.missing"
        payload = plan_payload(
            "composite",
            steps=[step_payload(), analysis],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_forward_dependency_rejected(self) -> None:
        payload = plan_payload(
            "composite",
            steps=[analysis_step(), step_payload()],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_cycle_producing_order_rejected(self) -> None:
        first = step_payload(
            step_id="step.retrieve",
            depends_on=["step.analyze"],
            input_bindings=[
                binding_payload(
                    input_name="input.analysis",
                    source_kind="step_output",
                    source_ref="fact.analysis",
                    source_step_id="step.analyze",
                    value_type="type.analysis",
                )
            ],
        )
        payload = plan_payload(
            "composite",
            steps=[first, analysis_step()],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)


class FactProductionTests(unittest.TestCase):
    """Fact production, consumption, and typed binding invariants."""

    def test_globally_duplicated_produced_fact_rejected(self) -> None:
        duplicate = step_payload(
            step_id="step.search",
            capability="official_search",
            operation="official.search_allowlisted",
            produces=[fact_payload()],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["document_retrieval", "official_search"],
            required_facts=["fact.document"],
            steps=[step_payload(), duplicate],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.search", ["step.search"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_required_fact_must_be_produced(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(required_facts=["fact.missing"]))

    def test_non_required_produced_fact_consumed_later_accepted(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        produced = {fact.fact_id for step in plan.steps for fact in step.produces}
        self.assertIn("fact.document", produced)
        self.assertNotIn("fact.document", plan.required_facts)

    def test_dead_produced_fact_rejected(self) -> None:
        payload = plan_payload(
            steps=[step_payload(produces=[fact_payload(), fact_payload("fact.unused")])]
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_dead_step_rejected(self) -> None:
        dead = step_payload(
            step_id="step.search",
            capability="official_search",
            operation="official.search_allowlisted",
            produces=[fact_payload("fact.official", "type.official")],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["document_retrieval", "official_search"],
            required_facts=["fact.document"],
            steps=[step_payload(), dead],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.search", ["step.search"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_binding_to_unknown_producer_fact_rejected(self) -> None:
        analysis = analysis_step()
        bindings = analysis["input_bindings"]
        assert isinstance(bindings, list)
        binding = bindings[0]
        assert isinstance(binding, dict)
        binding["source_ref"] = "fact.unknown"
        payload = plan_payload(
            "composite",
            steps=[step_payload(), analysis],
            required_facts=["fact.analysis", "fact.document"],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_binding_type_mismatch_rejected(self) -> None:
        analysis = analysis_step()
        bindings = analysis["input_bindings"]
        assert isinstance(bindings, list)
        binding = bindings[0]
        assert isinstance(binding, dict)
        binding["value_type"] = "type.other"
        payload = plan_payload("composite", steps=[step_payload(), analysis])
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_binding_scope_mismatch_rejected(self) -> None:
        personal_step = step_payload(
            step_id="step.personal",
            capability="personal_selector",
            operation="personal.select_self",
            produces=[fact_payload("fact.profile", "type.profile", "personal")],
        )
        consumer = step_payload(
            step_id="step.rule",
            capability="rule_evaluator",
            operation="rule.evaluate",
            depends_on=["step.personal"],
            input_bindings=[
                binding_payload(
                    input_name="input.profile",
                    source_kind="step_output",
                    source_ref="fact.profile",
                    source_step_id="step.personal",
                    value_type="type.profile",
                    data_scope="general",
                )
            ],
            produces=[fact_payload("fact.eligibility", "type.eligibility")],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["personal_selector", "rule_evaluator"],
            required_facts=["fact.eligibility"],
            steps=[personal_step, consumer],
            parallel_groups=[
                group_payload("group.personal", ["step.personal"]),
                group_payload("group.rule", ["step.rule"]),
            ],
            composition_type="rule_join",
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_rule_evaluator_may_consume_personal_fact(self) -> None:
        personal_step = step_payload(
            step_id="step.personal",
            capability="personal_selector",
            operation="personal.select_self",
            produces=[fact_payload("fact.profile", "type.profile", "personal")],
        )
        consumer = step_payload(
            step_id="step.rule",
            capability="rule_evaluator",
            operation="rule.evaluate",
            depends_on=["step.personal"],
            input_bindings=[
                binding_payload(
                    input_name="input.profile",
                    source_kind="step_output",
                    source_ref="fact.profile",
                    source_step_id="step.personal",
                    value_type="type.profile",
                    data_scope="personal",
                )
            ],
            produces=[fact_payload("fact.eligibility", "type.eligibility")],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["personal_selector", "rule_evaluator"],
            required_facts=["fact.eligibility"],
            steps=[personal_step, consumer],
            parallel_groups=[
                group_payload("group.personal", ["step.personal"]),
                group_payload("group.rule", ["step.rule"]),
            ],
            composition_type="rule_join",
        )
        plan = ExecutionPlan.model_validate(payload)
        self.assertEqual(plan.steps[1].input_bindings[0].data_scope, "personal")


class CapabilityAllowlistTests(unittest.TestCase):
    """Capability allowlist invariants."""

    def test_step_capability_must_be_allowlisted(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(allowed_capabilities=["official_search"]))

    def test_allowlisted_capability_must_be_used(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(allowed_capabilities=["document_retrieval", "official_search"])
            )


class AnalyticsScopeTests(unittest.TestCase):
    """Semantic analytics personal-data restriction."""

    def test_analytics_accepts_general_bindings_and_outputs(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        self.assertEqual(plan.steps[1].capability, "semantic_analytics")
        self.assertEqual(plan.steps[1].produces[0].data_scope, "general")

    def test_analytics_rejects_personal_external_binding(self) -> None:
        analysis = analysis_step()
        bindings = analysis["input_bindings"]
        assert isinstance(bindings, list)
        bindings.append(
            binding_payload(
                input_name="input.profile",
                source_kind="approved_artifact",
                source_ref="artifact.profile",
                value_type="type.profile",
                data_scope="personal",
            )
        )
        payload = plan_payload("composite", steps=[step_payload(), analysis])
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_analytics_rejects_personal_step_output_binding(self) -> None:
        personal_step = step_payload(
            step_id="step.personal",
            capability="personal_selector",
            operation="personal.select_self",
            produces=[fact_payload("fact.profile", "type.profile", "personal")],
        )
        analysis = step_payload(
            step_id="step.analyze",
            capability="semantic_analytics",
            operation="analytics.execute_logical_plan",
            depends_on=["step.personal"],
            input_bindings=[
                binding_payload(
                    input_name="input.profile",
                    source_kind="step_output",
                    source_ref="fact.profile",
                    source_step_id="step.personal",
                    value_type="type.profile",
                    data_scope="personal",
                )
            ],
            produces=[fact_payload("fact.analysis", "type.analysis")],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["personal_selector", "semantic_analytics"],
            required_facts=["fact.analysis"],
            steps=[personal_step, analysis],
            parallel_groups=[
                group_payload("group.personal", ["step.personal"]),
                group_payload("group.analyze", ["step.analyze"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_analytics_rejects_personal_produced_fact(self) -> None:
        analysis = analysis_step()
        analysis["produces"] = [fact_payload("fact.analysis", "type.analysis", "personal")]
        payload = plan_payload("composite", steps=[step_payload(), analysis])
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)


class BudgetAndRevisionTests(unittest.TestCase):
    """Budget limits and replan lineage."""

    def test_plan_step_count_cannot_exceed_budget(self) -> None:
        payload = plan_payload(
            "composite", budget=budget_payload(max_steps=1, max_parallel_steps=1)
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_budget_with_zero_steps_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(budget=budget_payload()))

    def test_boolean_revision_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(revision=True))

    def test_initial_revision_with_null_parent_accepted(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        self.assertEqual(plan.revision, 0)
        self.assertIsNone(plan.parent_plan_id)

    def test_initial_revision_with_parent_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(parent_plan_id=PARENT_PLAN_ID))

    def test_replan_revision_with_parent_accepted(self) -> None:
        plan = ExecutionPlan.model_validate(
            plan_payload(
                "composite",
                revision=1,
                parent_plan_id=PARENT_PLAN_ID,
                budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
            )
        )
        self.assertEqual(plan.revision, 1)
        self.assertEqual(plan.parent_plan_id, UUID(PARENT_PLAN_ID))

    def test_replan_revision_without_parent_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(
                    "composite",
                    revision=1,
                    budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
                )
            )

    def test_replan_requires_budget_permitting_one_replan(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload("composite", revision=1, parent_plan_id=PARENT_PLAN_ID)
            )

    def test_revision_two_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload("composite", revision=2, parent_plan_id=PARENT_PLAN_ID)
            )

    def test_self_parent_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(
                    "composite",
                    revision=1,
                    parent_plan_id=PLAN_ID,
                    budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
                )
            )


class FastPlanTests(unittest.TestCase):
    """Fast-lane invariants."""

    def test_fast_requires_exactly_one_step(self) -> None:
        payload = plan_payload(
            "fast",
            allowed_capabilities=["document_retrieval", "semantic_analytics"],
            required_facts=["fact.analysis"],
            steps=[step_payload(), analysis_step()],
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.analyze", ["step.analyze"]),
            ],
            budget=budget_payload(max_steps=2, max_parallel_steps=1),
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_fast_requires_one_group(self) -> None:
        payload = plan_payload(
            "fast",
            parallel_groups=[
                group_payload("group.retrieve", ["step.retrieve"]),
                group_payload("group.spare", ["step.retrieve"]),
            ],
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_fast_requires_matching_capability(self) -> None:
        payload = plan_payload("fast", allowed_capabilities=["official_search"])
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_fast_requires_single_composition(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload("fast", composition_type="sectioned"))

    def test_fast_requires_one_step_budget(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload("fast", budget=budget_payload(max_steps=2, max_parallel_steps=1))
            )

    def test_fast_rejects_replan_revision(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload(
                    "fast",
                    revision=1,
                    parent_plan_id=PARENT_PLAN_ID,
                    budget=budget_payload(max_steps=1, max_parallel_steps=1, max_replans=1),
                )
            )


class CompositePlanTests(unittest.TestCase):
    """Composite-lane invariants."""

    def test_composite_requires_at_least_two_steps(self) -> None:
        payload = plan_payload(
            "composite",
            allowed_capabilities=["document_retrieval"],
            required_facts=["fact.document"],
            steps=[step_payload()],
            parallel_groups=[group_payload("group.retrieve", ["step.retrieve"])],
            composition_type="sectioned",
        )
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    def test_composite_rejects_single_composition(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload("composite", composition_type="single"))

    def test_composite_accepts_five_steps(self) -> None:
        steps = [step_payload(), analysis_step()]
        groups = [
            group_payload("group.retrieve", ["step.retrieve"]),
            group_payload("group.analyze", ["step.analyze"]),
        ]
        facts = ["fact.analysis"]
        for index in range(3):
            step_id = f"step.search{index}"
            fact_id = f"fact.official{index}"
            steps.append(
                step_payload(
                    step_id=step_id,
                    capability="official_search",
                    operation="official.search_allowlisted",
                    produces=[fact_payload(fact_id, "type.official")],
                )
            )
            groups.append(group_payload(f"group.search{index}", [step_id]))
            facts.append(fact_id)
        plan = ExecutionPlan.model_validate(
            plan_payload(
                "composite",
                allowed_capabilities=[
                    "document_retrieval",
                    "semantic_analytics",
                    "official_search",
                ],
                required_facts=facts,
                steps=steps,
                parallel_groups=groups,
                budget=budget_payload(max_steps=5, max_parallel_steps=2),
            )
        )
        self.assertEqual(len(plan.steps), 5)

    def test_composite_permits_one_replan(self) -> None:
        plan = ExecutionPlan.model_validate(
            plan_payload(
                "composite",
                revision=1,
                parent_plan_id=PARENT_PLAN_ID,
                budget=budget_payload(max_steps=3, max_parallel_steps=2, max_replans=1),
            )
        )
        self.assertEqual(plan.budget.max_replans, 1)


class DeterministicPlanTests(unittest.TestCase):
    """Deterministic-lane invariants."""

    def test_one_step_requires_single_composition(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                plan_payload("deterministic", composition_type="sectioned")
            )

    def test_multi_step_rejects_single_composition(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(deterministic_flow_payload(composition_type="single"))

    def test_deterministic_rejects_replan_budget(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                deterministic_flow_payload(
                    budget=budget_payload(max_steps=2, max_parallel_steps=1, max_replans=1)
                )
            )

    def test_deterministic_rejects_replan_revision(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(
                deterministic_flow_payload(revision=1, parent_plan_id=PARENT_PLAN_ID)
            )


class ForbiddenFieldTests(unittest.TestCase):
    """Rejection of unsafe or out-of-boundary fields."""

    def test_root_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(unexpected_field="value"))

    def test_forbidden_root_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                ExecutionPlan.model_validate(plan_payload(**{field: "value"}))

    def test_forbidden_nested_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                fact = fact_payload()
                fact[field] = "value"
                with self.assertRaises(ValidationError):
                    PlanFactSpec.model_validate(fact)
                binding = binding_payload()
                binding[field] = "value"
                with self.assertRaises(ValidationError):
                    PlanInputBinding.model_validate(binding)
                step = step_payload()
                step[field] = "value"
                with self.assertRaises(ValidationError):
                    PlanStep.model_validate(step)
                group = group_payload("group.one", ["step.retrieve"])
                group[field] = "value"
                with self.assertRaises(ValidationError):
                    PlanParallelGroup.model_validate(group)


class ImmutabilityAndRoundTripTests(unittest.TestCase):
    """Immutability and serialization behavior."""

    def test_root_model_immutable(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        with self.assertRaises(ValidationError):
            plan.lane = "composite"

    def test_nested_models_immutable(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload())
        with self.assertRaises(ValidationError):
            plan.steps[0].required = False
        with self.assertRaises(ValidationError):
            plan.steps[0].produces[0].data_scope = "personal"
        with self.assertRaises(ValidationError):
            plan.parallel_groups[0].group_id = "group.other"
        with self.assertRaises(ValidationError):
            plan.budget.max_steps = 2

    def test_json_round_trip(self) -> None:
        plan = ExecutionPlan.model_validate(plan_payload("composite"))
        restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(plan, restored)


class SchemaTests(unittest.TestCase):
    """Generated and committed JSON Schema artifact."""

    def setUp(self) -> None:
        self.schema = ExecutionPlan.model_json_schema()
        self.artifact_text = SCHEMA_ARTIFACT.read_text(encoding="utf-8")

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:execution-plan:1.0.0")

    def test_root_schema_closed(self) -> None:
        self.assertFalse(self.schema["additionalProperties"])

    def test_nested_schemas_closed(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(definition=name):
                self.assertFalse(definition["additionalProperties"])

    def test_committed_schema_matches_generated_schema(self) -> None:
        self.assertEqual(json.loads(self.artifact_text), self.schema)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        self.assertTrue(self.artifact_text.endswith("\n"))

    def test_literal_catalogs_present_in_schema(self) -> None:
        properties = self.schema["properties"]
        self.assertEqual(tuple(properties["lane"]["enum"]), LANES)
        self.assertEqual(tuple(properties["composition_type"]["enum"]), COMPOSITION_TYPES)
        self.assertEqual(
            tuple(properties["missing_evidence_policy"]["enum"]), MISSING_EVIDENCE_POLICIES
        )
        self.assertEqual(properties["success_condition"]["const"], "all_required_facts")
        binding = self.schema["$defs"]["PlanInputBinding"]["properties"]
        self.assertEqual(tuple(binding["source_kind"]["enum"]), INPUT_SOURCE_KINDS)
        self.assertEqual(tuple(binding["data_scope"]["enum"]), FACT_SCOPES)

    def test_capability_catalog_present_in_schema(self) -> None:
        step = self.schema["$defs"]["PlanStep"]["properties"]
        self.assertEqual(tuple(step["capability"]["enum"]), CAPABILITIES)

    def test_forbidden_property_names_absent_from_schema(self) -> None:
        declared = set(self.schema["properties"])
        for definition in self.schema["$defs"].values():
            declared.update(definition.get("properties", {}))
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, declared)

    def test_nested_models_contain_no_schema_version(self) -> None:
        for name, definition in self.schema["$defs"].items():
            with self.subTest(definition=name):
                self.assertNotIn("schema_version", definition.get("properties", {}))


class ExportTests(unittest.TestCase):
    """Public export surface."""

    def test_public_exports_available(self) -> None:
        expected = {
            "CompositionType",
            "ExecutionLane",
            "ExecutionPlan",
            "FactDataScope",
            "InputSourceKind",
            "MissingEvidencePolicy",
            "PlanFactSpec",
            "PlanInputBinding",
            "PlanParallelGroup",
            "PlanStep",
            "SuccessCondition",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))

    def test_private_validation_aliases_not_exported(self) -> None:
        for name in ("_CanonicalCode", "_Uuid4", "_Revision", "_Steps", "_ParallelGroups"):
            with self.subTest(name=name):
                self.assertNotIn(name, contracts.__all__)


CODE_STRATEGY = st.from_regex(r"\A[a-z][a-z0-9._:-]{0,8}\Z")


class ExecutionPlanPropertyTests(unittest.TestCase):
    """Bounded property-based checks over plan structure."""

    @staticmethod
    def _chain_payload(count: int) -> dict[str, object]:
        steps: list[dict[str, object]] = []
        groups: list[dict[str, object]] = []
        for index in range(count):
            step_id = f"step.item{index}"
            bindings: list[dict[str, object]] = []
            depends_on: list[str] = []
            if index > 0:
                depends_on = [f"step.item{index - 1}"]
                bindings = [
                    binding_payload(
                        input_name="input.previous",
                        source_kind="step_output",
                        source_ref=f"fact.item{index - 1}",
                        source_step_id=f"step.item{index - 1}",
                        value_type="type.item",
                    )
                ]
            steps.append(
                step_payload(
                    step_id=step_id,
                    depends_on=depends_on,
                    input_bindings=bindings,
                    produces=[fact_payload(f"fact.item{index}", "type.item")],
                )
            )
            groups.append(group_payload(f"group.item{index}", [step_id]))
        lane = "fast" if count == 1 else "composite"
        return plan_payload(
            lane,
            allowed_capabilities=["document_retrieval"],
            required_facts=[f"fact.item{count - 1}"],
            steps=steps,
            parallel_groups=groups,
            composition_type="single" if count == 1 else "sectioned",
            budget=budget_payload(max_steps=count, max_parallel_steps=1),
        )

    @given(count=st.integers(min_value=1, max_value=5))
    def test_topologically_ordered_chains_accepted(self, count: int) -> None:
        plan = ExecutionPlan.model_validate(self._chain_payload(count))
        self.assertEqual(len(plan.steps), count)

    @given(count=st.integers(min_value=2, max_value=5))
    def test_reversed_chain_rejected(self, count: int) -> None:
        payload = self._chain_payload(count)
        steps = payload["steps"]
        assert isinstance(steps, list)
        payload["steps"] = list(reversed(steps))
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(payload)

    @given(
        capabilities=st.lists(st.sampled_from(CAPABILITIES), min_size=1, max_size=5, unique=True)
    )
    def test_capability_and_group_order_preserved(self, capabilities: list[str]) -> None:
        steps: list[dict[str, object]] = []
        groups: list[dict[str, object]] = []
        facts: list[str] = []
        for index, capability in enumerate(capabilities[:3]):
            step_id = f"step.item{index}"
            fact_id = f"fact.item{index}"
            steps.append(
                step_payload(
                    step_id=step_id,
                    capability=capability,
                    operation="capability.invoke",
                    produces=[fact_payload(fact_id, "type.item")],
                )
            )
            groups.append(group_payload(f"group.item{index}", [step_id]))
            facts.append(fact_id)
        used = capabilities[:3]
        count = len(used)
        payload = plan_payload(
            "fast" if count == 1 else "composite",
            allowed_capabilities=used,
            required_facts=facts,
            steps=steps,
            parallel_groups=groups,
            composition_type="single" if count == 1 else "sectioned",
            budget=budget_payload(max_steps=max(count, 1), max_parallel_steps=1),
        )
        plan = ExecutionPlan.model_validate(payload)
        self.assertEqual(list(plan.allowed_capabilities), used)
        self.assertEqual(
            [group.group_id for group in plan.parallel_groups],
            [f"group.item{index}" for index in range(count)],
        )

    @given(value_type=CODE_STRATEGY, scope=st.sampled_from(FACT_SCOPES))
    def test_typed_producer_consumer_bindings_round_trip(self, value_type: str, scope: str) -> None:
        producer = step_payload(
            step_id="step.produce",
            capability="personal_selector",
            operation="personal.select_self",
            produces=[fact_payload("fact.produced", value_type, scope)],
        )
        consumer = step_payload(
            step_id="step.consume",
            capability="rule_evaluator",
            operation="rule.evaluate",
            depends_on=["step.produce"],
            input_bindings=[
                binding_payload(
                    input_name="input.produced",
                    source_kind="step_output",
                    source_ref="fact.produced",
                    source_step_id="step.produce",
                    value_type=value_type,
                    data_scope=scope,
                )
            ],
            produces=[fact_payload("fact.result", "type.result")],
        )
        payload = plan_payload(
            "composite",
            allowed_capabilities=["personal_selector", "rule_evaluator"],
            required_facts=["fact.result"],
            steps=[producer, consumer],
            parallel_groups=[
                group_payload("group.produce", ["step.produce"]),
                group_payload("group.consume", ["step.consume"]),
            ],
            composition_type="rule_join",
        )
        plan = ExecutionPlan.model_validate(payload)
        restored = ExecutionPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(plan, restored)

    @given(field=st.sampled_from(FORBIDDEN_FIELDS))
    def test_sampled_forbidden_fields_rejected(self, field: str) -> None:
        with self.assertRaises(ValidationError):
            ExecutionPlan.model_validate(plan_payload(**{field: "value"}))
        nested = step_payload()
        nested[field] = "value"
        with self.assertRaises(ValidationError):
            PlanStep.model_validate(nested)


if __name__ == "__main__":
    unittest.main()
