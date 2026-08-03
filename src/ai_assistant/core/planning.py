"""Deterministic one-step execution plan builder for the fast document flow."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from ai_assistant.contracts import (
    ExecutionPlan,
    FactDataScope,
    PlanFactSpec,
    PlanParallelGroup,
    PlanStep,
    QueryAnalysis,
    RouteDecision,
)
from ai_assistant.core.routing import (
    DOCUMENT_CAPABILITY,
    DOCUMENT_FACT_ID,
    FAST_DOCUMENT_ROUTE,
    ROUTING_POLICY_VERSION,
    SINGLE_DOCUMENT_RATIONALE,
)
from ai_assistant.core.types import AuthorizedRuntimeContext

PLAN_BUILDER_VERSION = "1.0.0"
PLAN_GOAL = "goal.answer_question"
RETRIEVE_STEP_ID = "step.retrieve"
RETRIEVE_OPERATION = "document.retrieve"
RETRIEVE_GROUP_ID = "group.retrieve"
DOCUMENT_VALUE_TYPE = "type.document"
DOCUMENT_DATA_SCOPE: FactDataScope = "general"
FAST_BUDGET_SHAPE = (1, 1, 0, 0, 0, 0)


def _require_analysis_binding(context: AuthorizedRuntimeContext, analysis: QueryAnalysis) -> None:
    turn_input = context.runtime.turn_input
    if analysis.request_id != turn_input.request_id:
        raise ValueError("query analysis request_id must match the runtime context")
    if analysis.message_id != turn_input.message_id:
        raise ValueError("query analysis message_id must match the runtime context")
    if analysis.runtime_snapshot_id != context.runtime.runtime_snapshot.snapshot_id:
        raise ValueError("query analysis runtime_snapshot_id must match the runtime context")


def _require_route_binding(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    route_decision: RouteDecision,
) -> None:
    if route_decision.request_id != context.runtime.turn_input.request_id:
        raise ValueError("route decision request_id must match the runtime context")
    if route_decision.query_analysis_id != analysis.analysis_id:
        raise ValueError("route decision query_analysis_id must match the query analysis")
    if route_decision.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("route decision authorization_decision_id must match the authorization")
    if route_decision.runtime_snapshot_id != context.runtime.runtime_snapshot.snapshot_id:
        raise ValueError("route decision runtime_snapshot_id must match the runtime context")


def _require_canonical_route(route_decision: RouteDecision, *, route_error: str) -> None:
    """Require the exact route shape that WS-002 route_query is able to emit."""
    # Every downstream service calls this validator: a route is trusted for its
    # own semantics, never because an earlier service is assumed to have run.
    if route_decision.lane != "fast" or route_decision.route != FAST_DOCUMENT_ROUTE:
        raise ValueError(route_error)
    if route_decision.allowed_capabilities != (DOCUMENT_CAPABILITY,):
        raise ValueError("the fast.document route requires the document_retrieval capability")
    if route_decision.required_facts != (DOCUMENT_FACT_ID,):
        raise ValueError("the fast.document route requires exactly the document fact")
    if route_decision.effective_risk_level != "normal":
        raise ValueError("the fast.document route requires a normal effective risk level")
    if route_decision.planner_required:
        raise ValueError("the fast.document route must not require a planner")
    if route_decision.approved_flow_ref is not None:
        raise ValueError("the fast.document route must not carry an approved flow reference")
    # Filters are approved constraints: silently dropping them here would widen
    # the authorized scope of everything built from this route.
    if route_decision.filters != ():
        raise ValueError("the fast.document route must not carry filters")
    if route_decision.rationale_code != SINGLE_DOCUMENT_RATIONALE:
        raise ValueError("the fast.document route requires the canonical rationale code")
    if route_decision.policy_version != ROUTING_POLICY_VERSION:
        raise ValueError("the fast.document route requires the canonical policy version")
    _require_single_step_budget(route_decision)


def _require_single_step_budget(route_decision: RouteDecision) -> None:
    budget = route_decision.budget
    observed = (
        budget.max_steps,
        budget.max_parallel_steps,
        budget.max_replans,
        budget.max_retrieval_retries,
        budget.max_analytics_repairs,
        budget.max_answer_repairs,
    )
    if observed != FAST_BUDGET_SHAPE:
        raise ValueError("the fast.document route requires the single step budget")


def _require_plan_matches_route(
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
) -> None:
    if execution_plan.route_decision_id != route_decision.decision_id:
        raise ValueError("execution plan route_decision_id must match the route decision")
    if execution_plan.lane != route_decision.lane:
        raise ValueError("execution plan lane must match the route decision")
    if execution_plan.allowed_capabilities != route_decision.allowed_capabilities:
        raise ValueError("execution plan allowed_capabilities must match the route decision")
    if execution_plan.required_facts != route_decision.required_facts:
        raise ValueError("execution plan required facts must match the route decision")
    if execution_plan.budget != route_decision.budget:
        raise ValueError("execution plan budget must match the route decision")


def _require_canonical_plan_shape(execution_plan: ExecutionPlan, *, subject: str) -> None:
    if execution_plan.goal != PLAN_GOAL:
        raise ValueError(f"{subject} requires the canonical plan goal")
    if (
        execution_plan.composition_type != "single"
        or execution_plan.success_condition != "all_required_facts"
        or execution_plan.missing_evidence_policy != "abstain"
    ):
        raise ValueError(f"{subject} requires the canonical plan policies")
    if execution_plan.revision != 0 or execution_plan.parent_plan_id is not None:
        raise ValueError(f"{subject} requires the initial plan revision")
    if execution_plan.plan_builder_version != PLAN_BUILDER_VERSION:
        raise ValueError(f"{subject} requires the canonical plan builder version")


def _require_canonical_step(execution_plan: ExecutionPlan, *, subject: str) -> PlanStep:
    if len(execution_plan.steps) != 1:
        raise ValueError(f"{subject} requires exactly one plan step")
    step = execution_plan.steps[0]
    expected = (RETRIEVE_STEP_ID, DOCUMENT_CAPABILITY, RETRIEVE_OPERATION)
    if (step.step_id, step.capability, step.operation) != expected:
        raise ValueError(f"{subject} requires the canonical retrieval step")
    if step.depends_on != () or step.input_bindings != () or not step.required:
        raise ValueError(f"{subject} requires an independent required retrieval step")
    if len(step.produces) != 1:
        raise ValueError(f"{subject} requires exactly one produced fact")
    produced = step.produces[0]
    produced_shape = (produced.fact_id, produced.value_type, produced.data_scope)
    canonical_fact = (DOCUMENT_FACT_ID, DOCUMENT_VALUE_TYPE, DOCUMENT_DATA_SCOPE)
    if produced_shape != canonical_fact:
        raise ValueError(f"{subject} requires the canonical document fact")
    return step


def _require_canonical_group(execution_plan: ExecutionPlan, *, subject: str) -> None:
    if len(execution_plan.parallel_groups) != 1:
        raise ValueError(f"{subject} requires exactly one parallel group")
    group = execution_plan.parallel_groups[0]
    if group.group_id != RETRIEVE_GROUP_ID or group.step_ids != (RETRIEVE_STEP_ID,):
        raise ValueError(f"{subject} requires the canonical parallel group")


def _require_canonical_plan(
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    *,
    subject: str,
) -> PlanStep:
    """Require the exact plan shape that build_fast_execution_plan emits."""
    _require_plan_matches_route(route_decision, execution_plan)
    _require_canonical_plan_shape(execution_plan, subject=subject)
    step = _require_canonical_step(execution_plan, subject=subject)
    _require_canonical_group(execution_plan, subject=subject)
    return step


def _require_supported_route(route_decision: RouteDecision) -> Literal["fast"]:
    lane = route_decision.lane
    if lane != "fast":
        raise ValueError("the fast plan builder requires a fast lane route decision")
    _require_canonical_route(
        route_decision,
        route_error="the fast plan builder requires the fast.document route",
    )
    return lane


def build_fast_execution_plan(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    route_decision: RouteDecision,
    *,
    plan_id: UUID,
    planned_at: datetime,
) -> ExecutionPlan:
    """Build the single retrieval step plan authorized by a fast.document route."""
    _require_analysis_binding(context, analysis)
    _require_route_binding(context, analysis, route_decision)
    lane = _require_supported_route(route_decision)
    step = PlanStep(
        step_id=RETRIEVE_STEP_ID,
        capability=DOCUMENT_CAPABILITY,
        operation=RETRIEVE_OPERATION,
        depends_on=(),
        input_bindings=(),
        produces=(
            PlanFactSpec(
                fact_id=DOCUMENT_FACT_ID,
                value_type=DOCUMENT_VALUE_TYPE,
                data_scope=DOCUMENT_DATA_SCOPE,
            ),
        ),
        required=True,
    )
    # One member group only: the contract requires an execution layer, and this
    # layer never implies concurrent scheduling.
    group = PlanParallelGroup(group_id=RETRIEVE_GROUP_ID, step_ids=(RETRIEVE_STEP_ID,))
    return ExecutionPlan(
        plan_id=plan_id,
        request_id=context.runtime.turn_input.request_id,
        route_decision_id=route_decision.decision_id,
        authorization_decision_id=context.authorization.decision_id,
        runtime_snapshot_id=context.runtime.runtime_snapshot.snapshot_id,
        planned_at=planned_at,
        lane=lane,
        goal=PLAN_GOAL,
        allowed_capabilities=route_decision.allowed_capabilities,
        required_facts=route_decision.required_facts,
        steps=(step,),
        parallel_groups=(group,),
        composition_type="single",
        success_condition="all_required_facts",
        missing_evidence_policy="abstain",
        budget=route_decision.budget,
        revision=0,
        parent_plan_id=None,
        plan_builder_version=PLAN_BUILDER_VERSION,
    )
