"""Deterministic validation of one capability step result against its plan."""

from ai_assistant.contracts import ExecutionPlan, PlanStep, RouteDecision, StepResult
from ai_assistant.core.planning import _require_canonical_plan, _require_canonical_route
from ai_assistant.core.types import AuthorizedRuntimeContext, EvidenceMaterializationRequest

SINGLE_ATTEMPT = 1
VALIDATOR_SUBJECT = "the step result validator"
CANONICAL_ROUTE_ERROR = "the step result validator supports the fast.document route only"


def _require_result_lineage(
    context: AuthorizedRuntimeContext,
    execution_plan: ExecutionPlan,
    result: StepResult,
) -> None:
    runtime = context.runtime
    if result.request_id != runtime.turn_input.request_id:
        raise ValueError("step result request_id must match the runtime context")
    if result.plan_id != execution_plan.plan_id:
        raise ValueError("step result plan_id must match the execution plan")
    if result.runtime_snapshot_id != runtime.runtime_snapshot.snapshot_id:
        raise ValueError("step result runtime_snapshot_id must match the runtime context")
    if str(result.correlation_id) != runtime.correlation_id:
        raise ValueError("step result correlation_id must match the runtime context")


def _require_plan_binding(
    context: AuthorizedRuntimeContext,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
) -> None:
    runtime = context.runtime
    if route_decision.request_id != runtime.turn_input.request_id:
        raise ValueError("route decision request_id must match the runtime context")
    if route_decision.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("route decision authorization_decision_id must match the authorization")
    if execution_plan.route_decision_id != route_decision.decision_id:
        raise ValueError("execution plan route_decision_id must match the route decision")
    if execution_plan.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("execution plan authorization_decision_id must match the authorization")
    if execution_plan.runtime_snapshot_id != runtime.runtime_snapshot.snapshot_id:
        raise ValueError("execution plan runtime_snapshot_id must match the runtime context")


def _resolve_plan_step(execution_plan: ExecutionPlan, result: StepResult) -> PlanStep:
    for step in execution_plan.steps:
        if step.step_id == result.step_id:
            return step
    raise ValueError("step result must refer to a step declared by the execution plan")


def _require_capability_binding(step: PlanStep, result: StepResult) -> None:
    if result.provenance.capability != step.capability:
        raise ValueError("step result capability must match the plan step")
    if result.provenance.operation != step.operation:
        raise ValueError("step result operation must match the plan step")


def _require_declared_outputs(step: PlanStep, result: StepResult) -> None:
    declared = {fact.fact_id: fact for fact in step.produces}
    for output in result.typed_outputs:
        specification = declared.get(output.fact_id)
        if specification is None:
            raise ValueError("step result must not produce an undeclared fact")
        if output.value_type != specification.value_type:
            raise ValueError("step result value_type must match the planned fact")
        if output.data_scope != specification.data_scope:
            raise ValueError("step result data_scope must match the planned fact")


def _require_exact_partition(step: PlanStep, result: StepResult) -> None:
    # The contract already forbids a fact that is both produced and missing, so
    # an exact union check is enough to prove the partition.
    planned = {fact.fact_id for fact in step.produces}
    produced = {output.fact_id for output in result.typed_outputs}
    missing = set(result.missing_fact_ids)
    if produced.union(missing) != planned:
        raise ValueError("step result facts must partition the planned facts exactly")


def _require_single_attempt(result: StepResult) -> None:
    retry = result.retry
    if (
        retry.attempt != SINGLE_ATTEMPT
        or retry.max_attempts != SINGLE_ATTEMPT
        or retry.retryable
        or retry.previous_result_id is not None
    ):
        raise ValueError("the fast document flow permits exactly one final attempt")


def validate_step_result(
    context: AuthorizedRuntimeContext,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    result: StepResult,
) -> StepResult:
    """Validate one step result and return the same immutable instance."""
    _require_plan_binding(context, route_decision, execution_plan)
    # The canonical route and plan are re-proven here: this validator never
    # assumes that build_fast_execution_plan produced the supplied plan.
    _require_canonical_route(route_decision, route_error=CANONICAL_ROUTE_ERROR)
    _require_canonical_plan(route_decision, execution_plan, subject=VALIDATOR_SUBJECT)
    _require_result_lineage(context, execution_plan, result)
    step = _resolve_plan_step(execution_plan, result)
    _require_capability_binding(step, result)
    _require_declared_outputs(step, result)
    _require_exact_partition(step, result)
    _require_single_attempt(result)
    # The shared runtime request re-checks the cross artifact invariants that
    # the private Core already owns, so the two paths can never disagree.
    EvidenceMaterializationRequest(
        context=context,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step_results=(result,),
    )
    return result
