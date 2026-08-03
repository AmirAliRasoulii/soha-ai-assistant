"""Tests for the deterministic fast document execution plan builder."""

from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    AUTHORIZATION_ID,
    FOREIGN_ID,
    NOW,
    PLAN_ID,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SNAPSHOT_ID,
    authorized_context,
    query_analysis,
    route_budget,
    route_decision,
    route_filter,
    terminal_route_decision,
)

from ai_assistant.contracts import RouteLane
from ai_assistant.core.planning import build_fast_execution_plan


def test_fast_route_produces_a_single_retrieval_plan() -> None:
    plan = build_fast_execution_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        plan_id=PLAN_ID,
        planned_at=NOW,
    )
    assert plan.plan_id == PLAN_ID
    assert plan.planned_at == NOW
    assert plan.request_id == REQUEST_ID
    assert plan.route_decision_id == ROUTE_DECISION_ID
    assert plan.authorization_decision_id == AUTHORIZATION_ID
    assert plan.runtime_snapshot_id == SNAPSHOT_ID
    assert plan.lane == "fast"
    assert plan.goal == "goal.answer_question"
    assert plan.composition_type == "single"
    assert plan.success_condition == "all_required_facts"
    assert plan.missing_evidence_policy == "abstain"
    assert plan.revision == 0
    assert plan.parent_plan_id is None
    assert plan.plan_builder_version == "1.0.0"


def test_plan_step_is_the_canonical_retrieval_step() -> None:
    plan = build_fast_execution_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        plan_id=PLAN_ID,
        planned_at=NOW,
    )
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.step_id == "step.retrieve"
    assert step.capability == "document_retrieval"
    assert step.operation == "document.retrieve"
    assert step.depends_on == ()
    assert step.input_bindings == ()
    assert step.required is True
    assert len(step.produces) == 1
    produced = step.produces[0]
    assert produced.fact_id == "fact.document"
    assert produced.value_type == "type.document"
    assert produced.data_scope == "general"


def test_plan_declares_one_parallel_group() -> None:
    plan = build_fast_execution_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        plan_id=PLAN_ID,
        planned_at=NOW,
    )
    assert len(plan.parallel_groups) == 1
    group = plan.parallel_groups[0]
    assert group.group_id == "group.retrieve"
    assert group.step_ids == ("step.retrieve",)


def test_plan_copies_the_route_allowances_exactly() -> None:
    decision = route_decision()
    plan = build_fast_execution_plan(
        authorized_context(),
        query_analysis(),
        decision,
        plan_id=PLAN_ID,
        planned_at=NOW,
    )
    assert plan.lane == decision.lane
    assert plan.allowed_capabilities == decision.allowed_capabilities
    assert plan.required_facts == decision.required_facts
    assert plan.budget == decision.budget


def test_planning_is_deterministic_for_equal_inputs() -> None:
    context = authorized_context()
    analysis = query_analysis()
    decision = route_decision()
    first = build_fast_execution_plan(context, analysis, decision, plan_id=PLAN_ID, planned_at=NOW)
    second = build_fast_execution_plan(context, analysis, decision, plan_id=PLAN_ID, planned_at=NOW)
    assert first == second


def test_planning_does_not_mutate_its_inputs() -> None:
    decision = route_decision()
    analysis = query_analysis()
    before = (decision.model_dump(), analysis.model_dump())
    build_fast_execution_plan(
        authorized_context(), analysis, decision, plan_id=PLAN_ID, planned_at=NOW
    )
    assert (decision.model_dump(), analysis.model_dump()) == before


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "query analysis request_id must match the runtime context"),
        ("message_id", "query analysis message_id must match the runtime context"),
        ("snapshot_id", "query analysis runtime_snapshot_id must match the runtime context"),
    ],
)
def test_mismatched_analysis_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(**overrides),
            route_decision(),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "route decision request_id must match the runtime context"),
        ("analysis_id", "route decision query_analysis_id must match the query analysis"),
        (
            "authorization_id",
            "route decision authorization_decision_id must match the authorization",
        ),
        ("snapshot_id", "route decision runtime_snapshot_id must match the runtime context"),
    ],
)
def test_mismatched_route_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(**overrides),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


@pytest.mark.parametrize("lane", ["clarify", "abstain", "deny"])
def test_terminal_routes_are_rejected(lane: RouteLane) -> None:
    with pytest.raises(ValueError, match="requires a fast lane route decision"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            terminal_route_decision(lane=lane),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_deterministic_lane_route_is_rejected() -> None:
    decision = route_decision(lane="deterministic", route="deterministic.document_lookup")
    with pytest.raises(ValueError, match="requires a fast lane route decision"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            decision,
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_unknown_fast_route_code_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"requires the fast\.document route"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(route="fast.official"),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_unexpected_capability_is_rejected() -> None:
    decision = route_decision(
        capabilities=("semantic_analytics",),
        required_facts=("fact.document",),
    )
    with pytest.raises(ValueError, match="requires the document_retrieval capability"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            decision,
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_unexpected_required_facts_are_rejected() -> None:
    decision = route_decision(required_facts=("fact.other",))
    with pytest.raises(ValueError, match="requires exactly the document fact"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            decision,
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_approved_flow_reference_is_rejected() -> None:
    decision = route_decision(approved_flow_ref="flow:approved-1")
    with pytest.raises(ValueError, match="must not carry an approved flow reference"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            decision,
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_injected_plan_identifier_and_timestamp_are_used_verbatim() -> None:
    plan = build_fast_execution_plan(
        authorized_context(),
        query_analysis(),
        route_decision(budget=route_budget()),
        plan_id=FOREIGN_ID,
        planned_at=NOW,
    )
    assert plan.plan_id == FOREIGN_ID
    assert plan.planned_at == NOW


def test_route_carrying_filters_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not carry filters"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(filters=(route_filter(),)),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_unresolved_effective_risk_level_is_rejected() -> None:
    decision = route_decision(
        effective_risk_level="high",
        approved_flow_ref="flow:approved-1",
    )
    with pytest.raises(ValueError, match="requires a normal effective risk level"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            decision,
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


@pytest.mark.parametrize(
    "budget",
    [
        route_budget(max_retrieval_retries=1),
        route_budget(max_answer_repairs=1),
        route_budget(max_analytics_repairs=1),
    ],
)
def test_non_single_step_budget_is_rejected(budget: object) -> None:
    with pytest.raises(ValueError, match="requires the single step budget"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(budget=budget),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_wrong_rationale_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical rationale code"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(rationale_code="query.other_reason"),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )


def test_wrong_policy_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical policy version"):
        build_fast_execution_plan(
            authorized_context(),
            query_analysis(),
            route_decision(policy_version="2.0.0"),
            plan_id=PLAN_ID,
            planned_at=NOW,
        )
