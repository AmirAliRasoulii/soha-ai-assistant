"""Bounded asynchronous orchestration of the canonical fast document flow."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from ai_assistant.contracts import (
    AnswerPlan,
    AuthorizationDecision,
    Evidence,
    EvidenceBundle,
    ExecutionPlan,
    QueryAnalysis,
    RouteDecision,
    StepResult,
)
from ai_assistant.contracts.errors import ErrorCode
from ai_assistant.core.answer_planning import build_answer_plan
from ai_assistant.core.evidence_manager import build_evidence_bundle
from ai_assistant.core.planning import build_fast_execution_plan
from ai_assistant.core.ports import (
    AuthorizationPort,
    CapabilityPort,
    EvidenceMaterializerPort,
)
from ai_assistant.core.routing import DOCUMENT_CAPABILITY, route_query
from ai_assistant.core.step_validation import validate_step_result
from ai_assistant.core.types import (
    AuthorizedRuntimeContext,
    CapabilityInvocation,
    EvidenceMaterializationRequest,
    RuntimeContext,
)

TIMEOUT_ERROR_CODE: ErrorCode = "DEPENDENCY_TIMEOUT"
INTERNAL_ERROR_CODE: ErrorCode = "INTERNAL_ERROR"
UNAUTHORIZED_ERROR_CODE: ErrorCode = "UNAUTHORIZED"
TERMINAL_LANES = ("clarify", "abstain")


class OrchestrationStatus(StrEnum):
    COMPLETED = "completed"
    STOPPED = "stopped"
    DENIED = "denied"
    FAILED = "failed"


class OrchestrationFailurePhase(StrEnum):
    RUNTIME = "runtime"
    AUTHORIZATION = "authorization"
    CAPABILITY = "capability"
    EVIDENCE_MATERIALIZATION = "evidence_materialization"


@dataclass(frozen=True, slots=True)
class OrchestrationArtifacts:
    """Injected identifiers and timestamps for every artifact of one turn."""

    route_decision_id: UUID
    route_decided_at: datetime
    execution_plan_id: UUID
    execution_plan_planned_at: datetime
    evidence_bundle_id: UUID
    evidence_bundle_built_at: datetime
    answer_plan_id: UUID
    answer_plan_built_at: datetime

    def __post_init__(self) -> None:
        identifiers: tuple[tuple[str, UUID], ...] = (
            ("route_decision_id", self.route_decision_id),
            ("execution_plan_id", self.execution_plan_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("answer_plan_id", self.answer_plan_id),
        )
        for name, identifier in identifiers:
            if identifier.version != 4:
                raise ValueError(f"{name} must be a version 4 UUID")
        moments: tuple[tuple[str, datetime], ...] = (
            ("route_decided_at", self.route_decided_at),
            ("execution_plan_planned_at", self.execution_plan_planned_at),
            ("evidence_bundle_built_at", self.evidence_bundle_built_at),
            ("answer_plan_built_at", self.answer_plan_built_at),
        )
        for name, moment in moments:
            if moment.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        # Artifact times are injected, never generated here, so an out of order
        # sequence is a caller defect rather than something to repair.
        ordered = tuple(moment for _, moment in moments)
        if list(ordered) != sorted(ordered):
            raise ValueError("artifact timestamps must be nondecreasing in pipeline order")


@dataclass(frozen=True, slots=True)
class OrchestrationResult:
    """Private immutable outcome of one bounded orchestration attempt."""

    status: OrchestrationStatus
    authorization: AuthorizationDecision | None = None
    route_decision: RouteDecision | None = None
    execution_plan: ExecutionPlan | None = None
    step_result: StepResult | None = None
    evidence_bundle: EvidenceBundle | None = None
    answer_plan: AnswerPlan | None = None
    error_code: ErrorCode | None = None
    failure_phase: OrchestrationFailurePhase | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, OrchestrationStatus):
            raise ValueError("status must be an OrchestrationStatus")
        if self.failure_phase is not None and not isinstance(
            self.failure_phase, OrchestrationFailurePhase
        ):
            raise ValueError("failure_phase must be an OrchestrationFailurePhase")
        if self.status is OrchestrationStatus.COMPLETED:
            self._require_completed_shape()
        elif self.status is OrchestrationStatus.STOPPED:
            self._require_stopped_shape()
        elif self.status is OrchestrationStatus.DENIED:
            self._require_denied_shape()
        else:
            self._require_failed_shape()

    def _require_allowed_authorization(self) -> None:
        authorization = self.authorization
        if authorization is None or authorization.effect != "allow":
            raise ValueError("this outcome requires an allowed authorization decision")

    def _require_no_failure(self) -> None:
        if self.error_code is not None or self.failure_phase is not None:
            raise ValueError("a non failed outcome must not carry failure classification")

    def _require_completed_shape(self) -> None:
        self._require_allowed_authorization()
        route_decision = self.route_decision
        if route_decision is None or route_decision.lane != "fast":
            raise ValueError("a completed orchestration requires a fast lane route decision")
        if self.execution_plan is None:
            raise ValueError("a completed orchestration requires an execution plan")
        step_result = self.step_result
        if step_result is None or step_result.status != "success":
            raise ValueError("a completed orchestration requires a successful step result")
        if self.evidence_bundle is None:
            raise ValueError("a completed orchestration requires an evidence bundle")
        if self.answer_plan is None:
            raise ValueError("a completed orchestration requires an answer plan")
        self._require_no_failure()

    def _require_stopped_shape(self) -> None:
        self._require_allowed_authorization()
        route_decision = self.route_decision
        if route_decision is None or route_decision.lane not in TERMINAL_LANES:
            raise ValueError("a stopped orchestration requires a clarify or abstain route")
        if self.execution_plan is not None or self.step_result is not None:
            raise ValueError("a stopped orchestration must not carry execution artifacts")
        if self.evidence_bundle is not None or self.answer_plan is not None:
            raise ValueError("a stopped orchestration must not carry evidence artifacts")
        self._require_no_failure()

    def _require_denied_shape(self) -> None:
        authorization = self.authorization
        if authorization is None or authorization.effect != "deny":
            raise ValueError("a denied orchestration requires a denying authorization decision")
        if self.route_decision is not None or self.execution_plan is not None:
            raise ValueError("a denied orchestration must not carry routing artifacts")
        if self.step_result is not None:
            raise ValueError("a denied orchestration must not carry a step result")
        if self.evidence_bundle is not None or self.answer_plan is not None:
            raise ValueError("a denied orchestration must not carry evidence artifacts")
        if self.error_code != UNAUTHORIZED_ERROR_CODE:
            raise ValueError("a denied orchestration requires the UNAUTHORIZED error code")
        if self.failure_phase is not OrchestrationFailurePhase.AUTHORIZATION:
            raise ValueError("a denied orchestration requires the authorization phase")

    def _require_failed_shape(self) -> None:
        if self.error_code is None:
            raise ValueError("a failed orchestration requires an error code")
        if self.failure_phase is None:
            raise ValueError("a failed orchestration requires a failure phase")
        if self.evidence_bundle is not None or self.answer_plan is not None:
            raise ValueError("a failed orchestration must not carry evidence artifacts")
        # Partial artifacts are only credible in execution order: anything else
        # would describe a turn that could not have happened.
        if self.route_decision is not None:
            self._require_allowed_authorization()
        if self.execution_plan is not None and self.route_decision is None:
            raise ValueError("a failed orchestration with a plan requires a route decision")
        if self.step_result is not None and self.execution_plan is None:
            raise ValueError("a failed orchestration with a step result requires a plan")


@dataclass(slots=True)
class _ActivePhase:
    """Local, request scoped record of the asynchronous phase being awaited."""

    phase: OrchestrationFailurePhase = OrchestrationFailurePhase.RUNTIME


def _require_entry(context: RuntimeContext, entered_at: datetime) -> None:
    if entered_at.utcoffset() is None:
        raise ValueError("entered_at must be timezone-aware")
    if entered_at < context.started_at:
        raise ValueError("entered_at must not precede the runtime start")


def _require_decision_binding(context: RuntimeContext, decision: AuthorizationDecision) -> None:
    if decision.request_id != context.turn_input.request_id:
        raise ValueError("authorization decision request_id must match the runtime context")
    if decision.security_context_id != context.principal.context_id:
        raise ValueError("authorization decision security_context_id must match the principal")


def _failed(
    error_code: ErrorCode,
    phase: OrchestrationFailurePhase,
    *,
    authorization: AuthorizationDecision | None = None,
    route_decision: RouteDecision | None = None,
    execution_plan: ExecutionPlan | None = None,
    step_result: StepResult | None = None,
) -> OrchestrationResult:
    # Only classification and already validated artifacts are returned: no
    # exception text, provider payload, or evidence content ever leaves here.
    return OrchestrationResult(
        status=OrchestrationStatus.FAILED,
        authorization=authorization,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step_result=step_result,
        error_code=error_code,
        failure_phase=phase,
    )


async def _authorize(
    context: RuntimeContext,
    authorization_port: AuthorizationPort,
) -> AuthorizationDecision | None:
    try:
        return await authorization_port.authorize(context)
    except asyncio.CancelledError:
        # Cancellation, including the structured timeout, is never an outcome.
        raise
    except Exception:
        return None


async def _execute_step(
    capability_port: CapabilityPort,
    invocation: CapabilityInvocation,
) -> StepResult | None:
    try:
        return await capability_port.execute(invocation)
    except asyncio.CancelledError:
        raise
    except Exception:
        return None


async def _materialize(
    evidence_materializer: EvidenceMaterializerPort,
    request: EvidenceMaterializationRequest,
) -> tuple[Evidence, ...] | None:
    try:
        return await evidence_materializer.materialize(request)
    except asyncio.CancelledError:
        raise
    except Exception:
        return None


async def _run_pipeline(
    context: RuntimeContext,
    analysis: QueryAnalysis,
    *,
    authorization_port: AuthorizationPort,
    capability_port: CapabilityPort,
    evidence_materializer: EvidenceMaterializerPort,
    artifacts: OrchestrationArtifacts,
    active: _ActivePhase,
) -> OrchestrationResult:
    active.phase = OrchestrationFailurePhase.AUTHORIZATION
    decision = await _authorize(context, authorization_port)
    if decision is None:
        return _failed(INTERNAL_ERROR_CODE, OrchestrationFailurePhase.AUTHORIZATION)
    _require_decision_binding(context, decision)
    if decision.effect == "deny":
        return OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=decision,
            error_code=UNAUTHORIZED_ERROR_CODE,
            failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
        )
    authorized_context = AuthorizedRuntimeContext(runtime=context, authorization=decision)
    route_decision = route_query(
        authorized_context,
        analysis,
        decision_id=artifacts.route_decision_id,
        decided_at=artifacts.route_decided_at,
    )
    if route_decision.lane in TERMINAL_LANES:
        return OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=decision,
            route_decision=route_decision,
        )
    execution_plan = build_fast_execution_plan(
        authorized_context,
        analysis,
        route_decision,
        plan_id=artifacts.execution_plan_id,
        planned_at=artifacts.execution_plan_planned_at,
    )
    # The canonical plan holds exactly one step; this flow schedules nothing.
    step = execution_plan.steps[0]
    if capability_port.capability_name != step.capability or step.capability != DOCUMENT_CAPABILITY:
        return _failed(
            INTERNAL_ERROR_CODE,
            OrchestrationFailurePhase.CAPABILITY,
            authorization=decision,
            route_decision=route_decision,
            execution_plan=execution_plan,
        )
    invocation = CapabilityInvocation(
        context=authorized_context,
        query_analysis=analysis,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step=step,
    )
    active.phase = OrchestrationFailurePhase.CAPABILITY
    raw_result = await _execute_step(capability_port, invocation)
    if raw_result is None:
        return _failed(
            INTERNAL_ERROR_CODE,
            OrchestrationFailurePhase.CAPABILITY,
            authorization=decision,
            route_decision=route_decision,
            execution_plan=execution_plan,
        )
    # A defective step result is a trusted boundary violation, so this call is
    # deliberately not guarded: its ValueError must reach the caller.
    step_result = validate_step_result(
        authorized_context,
        route_decision,
        execution_plan,
        raw_result,
    )
    if step_result.status == "failed":
        failure_code = step_result.failure_code
        if failure_code is None:
            raise ValueError("a failed step result must carry a failure code")
        return _failed(
            failure_code,
            OrchestrationFailurePhase.CAPABILITY,
            authorization=decision,
            route_decision=route_decision,
            execution_plan=execution_plan,
            step_result=step_result,
        )
    request = EvidenceMaterializationRequest(
        context=authorized_context,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step_results=(step_result,),
    )
    active.phase = OrchestrationFailurePhase.EVIDENCE_MATERIALIZATION
    evidence = await _materialize(evidence_materializer, request)
    if evidence is None:
        return _failed(
            INTERNAL_ERROR_CODE,
            OrchestrationFailurePhase.EVIDENCE_MATERIALIZATION,
            authorization=decision,
            route_decision=route_decision,
            execution_plan=execution_plan,
            step_result=step_result,
        )
    evidence_bundle = build_evidence_bundle(
        authorized_context,
        route_decision,
        execution_plan,
        (step_result,),
        evidence,
        bundle_id=artifacts.evidence_bundle_id,
        built_at=artifacts.evidence_bundle_built_at,
    )
    answer_plan = build_answer_plan(
        authorized_context,
        analysis,
        route_decision,
        execution_plan,
        evidence_bundle,
        answer_plan_id=artifacts.answer_plan_id,
        built_at=artifacts.answer_plan_built_at,
    )
    return OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=decision,
        route_decision=route_decision,
        execution_plan=execution_plan,
        step_result=step_result,
        evidence_bundle=evidence_bundle,
        answer_plan=answer_plan,
    )


async def orchestrate_fast_document(
    context: RuntimeContext,
    analysis: QueryAnalysis,
    *,
    authorization_port: AuthorizationPort,
    capability_port: CapabilityPort,
    evidence_materializer: EvidenceMaterializerPort,
    artifacts: OrchestrationArtifacts,
    entered_at: datetime,
) -> OrchestrationResult:
    """Run one bounded authorization first fast document turn."""
    _require_entry(context, entered_at)
    active = _ActivePhase()
    deadline_at = context.deadline_at
    if deadline_at is None:
        return await _run_pipeline(
            context,
            analysis,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=evidence_materializer,
            artifacts=artifacts,
            active=active,
        )
    remaining_seconds = (deadline_at - entered_at).total_seconds()
    if remaining_seconds <= 0:
        # The runtime budget was already spent before any port was reachable.
        return _failed(TIMEOUT_ERROR_CODE, OrchestrationFailurePhase.RUNTIME)
    try:
        async with asyncio.timeout(remaining_seconds):
            return await _run_pipeline(
                context,
                analysis,
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=evidence_materializer,
                artifacts=artifacts,
                active=active,
            )
    except TimeoutError:
        return _failed(TIMEOUT_ERROR_CODE, active.phase)
