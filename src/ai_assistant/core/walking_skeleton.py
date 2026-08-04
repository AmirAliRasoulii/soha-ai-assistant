"""Bounded terminal closure of the Walking Skeleton fast document flow.

This module is the outermost trusted Core entry point of the bounded fast
document Walking Skeleton. It owns nothing that WS-002, WS-003A, WS-003B, or
WS-004A already own: it calls `coordinate_idempotent_fast_document` exactly
once, branches only on its result, calls `finalize_pending_answer` exactly
once for a completed orchestration, deterministically maps a pre-plan stopped
route to an `ErrorEnvelope`, and then owns exactly one new concern of its own:
audit-before-complete terminal closure, fail-closed audit and completion,
fail-open terminal telemetry, and the idempotent replay contract of the whole
turn.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID

from ai_assistant.contracts import (
    AuditActorRef,
    AuditEvent,
    AuditResourceRef,
    DomainError,
    ErrorEnvelope,
    FinalAnswer,
    FinalGenerationMode,
    QueryAnalysis,
)
from ai_assistant.contracts.errors import ErrorCode
from ai_assistant.core.finalization import (
    AnswerRendererPort,
    CitationSourceResolverPort,
    FinalizationArtifacts,
    finalize_pending_answer,
)
from ai_assistant.core.ports import (
    AuditEventSink,
    AuthorizationPort,
    CapabilityPort,
    EvidenceMaterializerPort,
    IdempotencyStorePort,
    RuntimeTelemetrySink,
)
from ai_assistant.core.runtime import (
    OrchestrationArtifacts,
    OrchestrationResult,
    OrchestrationStatus,
)
from ai_assistant.core.terminal_runtime import (
    TerminalCoordinationResult,
    TerminalCoordinationStatus,
    TerminalFailureArtifacts,
    coordinate_idempotent_fast_document,
)
from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    IdempotencyLease,
    RuntimeContext,
    RuntimeTelemetryEventName,
    RuntimeTelemetryOutcome,
    RuntimeTelemetryRecord,
    TerminalOutcome,
)

AUDIT_PRODUCER = "ai-assistant.core.walking-skeleton"
AUDIT_ACTION = "runtime.answer"
AUDIT_RESOURCE_TYPE = "conversation"
AUDIT_RETENTION_CLASS = "retention.standard"
AUDIT_SENSITIVITY = "sensitivity.internal"
COMPLETED_EVENT_TYPE = "runtime.turn.completed"
FAILED_EVENT_TYPE = "runtime.turn.failed"
ABSTAINED_REASON_CODE = "runtime.abstained"
INTERNAL_ERROR_CODE: ErrorCode = "INTERNAL_ERROR"
AMBIGUOUS_REQUEST_CODE: ErrorCode = "AMBIGUOUS_REQUEST"
NO_EVIDENCE_CODE: ErrorCode = "NO_EVIDENCE"
# Retryability is a property of the canonical code catalog, never a local policy.
RETRYABLE_ERROR_CODES: tuple[ErrorCode, ...] = (
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
)
_ONE_MILLISECOND = timedelta(milliseconds=1)


class WalkingSkeletonDisposition(StrEnum):
    REPLAYED = "replayed"
    PASSTHROUGH = "passthrough"
    STORED = "stored"
    WITHHELD = "withheld"


@dataclass(frozen=True, slots=True)
class WalkingSkeletonResult:
    """Private immutable outcome of one bounded Walking Skeleton closure attempt."""

    disposition: WalkingSkeletonDisposition
    effective_key: EffectiveIdempotencyKey
    outcome: TerminalOutcome
    lease: IdempotencyLease | None = None
    orchestration_result: OrchestrationResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.disposition, WalkingSkeletonDisposition):
            raise ValueError("disposition must be a WalkingSkeletonDisposition")
        if not isinstance(self.effective_key, EffectiveIdempotencyKey):
            raise ValueError("effective_key must be an EffectiveIdempotencyKey")
        if not isinstance(self.outcome, FinalAnswer | ErrorEnvelope):
            raise ValueError("outcome must be a FinalAnswer or ErrorEnvelope")
        if self.disposition is WalkingSkeletonDisposition.REPLAYED:
            self._require_replayed_shape()
        elif self.disposition is WalkingSkeletonDisposition.PASSTHROUGH:
            self._require_passthrough_shape()
        elif self.disposition is WalkingSkeletonDisposition.STORED:
            self._require_stored_shape()
        else:
            self._require_withheld_shape()

    def _require_replayed_shape(self) -> None:
        if self.lease is not None:
            raise ValueError("a replayed result must not retain a lease")
        if self.orchestration_result is not None:
            raise ValueError("a replayed result must not carry an orchestration result")

    def _require_passthrough_shape(self) -> None:
        if not isinstance(self.outcome, ErrorEnvelope):
            raise ValueError("a passthrough result requires an error envelope")
        # A lease exists only for an executed turn: admission level errors never
        # acquired one and must not pretend to hold storage state.
        if (self.lease is None) is not (self.orchestration_result is None):
            raise ValueError("a passthrough lease requires a preserved orchestration result")
        if self.lease is not None and self.lease.key != self.effective_key:
            raise ValueError("a preserved lease must belong to the derived effective key")

    def _require_bound_lease(self) -> None:
        lease = self.lease
        if lease is None:
            raise ValueError("this disposition requires a retained lease")
        if lease.key != self.effective_key:
            raise ValueError("the retained lease must belong to the derived effective key")
        if self.orchestration_result is None:
            raise ValueError("this disposition requires a retained orchestration result")

    def _require_stored_shape(self) -> None:
        self._require_bound_lease()

    def _require_withheld_shape(self) -> None:
        if not isinstance(self.outcome, ErrorEnvelope):
            raise ValueError("a withheld result requires an error envelope")
        if self.outcome.error.code != INTERNAL_ERROR_CODE:
            raise ValueError("a withheld result requires the INTERNAL_ERROR code")
        self._require_bound_lease()


@dataclass(frozen=True, slots=True)
class TerminalCompletionArtifacts:
    """Injected identifiers and timestamps for one terminal closure attempt."""

    audit_event_id: UUID
    stopped_error_id: UUID
    stopped_internal_detail_ref: UUID
    finalization_error_id: UUID
    coordination_error_id: UUID
    coordination_internal_detail_ref: UUID
    occurred_at: datetime
    telemetry_recorded_at: datetime

    def __post_init__(self) -> None:
        identifiers: tuple[tuple[str, UUID], ...] = (
            ("audit_event_id", self.audit_event_id),
            ("stopped_error_id", self.stopped_error_id),
            ("stopped_internal_detail_ref", self.stopped_internal_detail_ref),
            ("finalization_error_id", self.finalization_error_id),
            ("coordination_error_id", self.coordination_error_id),
            ("coordination_internal_detail_ref", self.coordination_internal_detail_ref),
        )
        for name, identifier in identifiers:
            if identifier.version != 4:
                raise ValueError(f"{name} must be a version 4 UUID")
        distinct = frozenset(identifier for _, identifier in identifiers)
        if len(distinct) != len(identifiers):
            raise ValueError("terminal completion identifiers must be pairwise distinct")
        moments: tuple[tuple[str, datetime], ...] = (
            ("occurred_at", self.occurred_at),
            ("telemetry_recorded_at", self.telemetry_recorded_at),
        )
        for name, moment in moments:
            if moment.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.telemetry_recorded_at < self.occurred_at:
            raise ValueError("telemetry_recorded_at must not precede occurred_at")


def _require_run_entry(
    entered_at: datetime,
    finalization_entered_at: datetime,
    completion_artifacts: TerminalCompletionArtifacts,
) -> None:
    if entered_at.utcoffset() is None:
        raise ValueError("entered_at must be timezone-aware")
    if finalization_entered_at.utcoffset() is None:
        raise ValueError("finalization_entered_at must be timezone-aware")
    if finalization_entered_at < entered_at:
        raise ValueError("finalization_entered_at must not precede entered_at")
    if completion_artifacts.occurred_at < finalization_entered_at:
        raise ValueError(
            "completion_artifacts.occurred_at must not precede finalization_entered_at"
        )


def _require_no_identifier_collisions(
    completion_artifacts: TerminalCompletionArtifacts,
    finalization_artifacts: FinalizationArtifacts,
    terminal_failure_artifacts: TerminalFailureArtifacts,
) -> None:
    """Prove the new completion identifiers never collide with prior artifacts.

    This is a pure precondition over injected configuration objects: it never
    inspects the QueryAnalysis under evaluation, so it never violates the rule
    that analysis is not inspected before idempotency admission.
    """
    completion_ids = (
        completion_artifacts.audit_event_id,
        completion_artifacts.stopped_error_id,
        completion_artifacts.stopped_internal_detail_ref,
        completion_artifacts.finalization_error_id,
        completion_artifacts.coordination_error_id,
        completion_artifacts.coordination_internal_detail_ref,
    )
    finalization_ids = (
        finalization_artifacts.final_answer_id,
        finalization_artifacts.failure_internal_detail_ref,
        *finalization_artifacts.citation_ids,
    )
    failure_ids = (
        terminal_failure_artifacts.error_id,
        terminal_failure_artifacts.internal_detail_ref,
        terminal_failure_artifacts.coordination_error_id,
        terminal_failure_artifacts.coordination_internal_detail_ref,
        terminal_failure_artifacts.audit_event_id,
    )
    all_ids = (*completion_ids, *finalization_ids, *failure_ids)
    if len(frozenset(all_ids)) != len(all_ids):
        raise ValueError(
            "terminal completion identifiers must not collide with finalization or "
            "terminal failure identifiers"
        )


def _correlation_uuid(context: RuntimeContext) -> UUID:
    try:
        correlation_id = UUID(context.correlation_id)
    except ValueError as error:
        raise ValueError("correlation_id must be a version 4 UUID") from error
    if correlation_id.version != 4:
        raise ValueError("correlation_id must be a version 4 UUID")
    return correlation_id


def _actor(context: RuntimeContext) -> AuditActorRef:
    principal = context.principal
    return AuditActorRef(
        actor_type=principal.principal_type,
        principal_id=principal.principal_id,
        security_context_id=principal.context_id,
    )


def _resource(context: RuntimeContext) -> AuditResourceRef:
    return AuditResourceRef(
        resource_type=AUDIT_RESOURCE_TYPE,
        resource_id=str(context.turn_input.conversation_id),
    )


def _error_semantics(code: ErrorCode) -> tuple[str, bool]:
    return (f"error.{code.lower()}", code in RETRYABLE_ERROR_CODES)


def _stopped_error_envelope(
    context: RuntimeContext,
    result: OrchestrationResult,
    completion_artifacts: TerminalCompletionArtifacts,
) -> ErrorEnvelope:
    """Deterministically map an accepted terminal route to an ErrorEnvelope.

    This is a pre-plan outcome: no renderer, resolver, or finalizer is ever
    called, and no ExecutionPlan, EvidenceBundle, AnswerPlan, or FinalAnswer
    identifier is ever fabricated for it.
    """
    route_decision = result.route_decision
    if route_decision is None:
        raise ValueError("a stopped orchestration requires a route decision")
    if route_decision.lane == "clarify":
        code = AMBIGUOUS_REQUEST_CODE
    elif route_decision.lane == "abstain":
        code = NO_EVIDENCE_CODE
    else:
        raise ValueError("a stopped orchestration must use the clarify or abstain lane")
    safe_message_key, retryable = _error_semantics(code)
    return ErrorEnvelope(
        error_id=completion_artifacts.stopped_error_id,
        correlation_id=_correlation_uuid(context),
        error=DomainError(
            code=code,
            safe_message_key=safe_message_key,
            retryable=retryable,
            internal_detail_ref=completion_artifacts.stopped_internal_detail_ref,
        ),
    )


def _final_answer_audit_event(
    context: RuntimeContext,
    final_answer: FinalAnswer,
    completion_artifacts: TerminalCompletionArtifacts,
) -> AuditEvent:
    if final_answer.outcome == "answered":
        return AuditEvent(
            event_id=completion_artifacts.audit_event_id,
            event_type=COMPLETED_EVENT_TYPE,
            occurred_at=completion_artifacts.occurred_at,
            producer=AUDIT_PRODUCER,
            correlation_id=_correlation_uuid(context),
            request_id=context.turn_input.request_id,
            actor=_actor(context),
            action=AUDIT_ACTION,
            resource=_resource(context),
            outcome="success",
            reason_codes=(),
            authorization_decision_id=final_answer.authorization_decision_id,
            runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
            retention_class=AUDIT_RETENTION_CLASS,
            sensitivity=AUDIT_SENSITIVITY,
        )
    if final_answer.outcome == "abstained":
        return AuditEvent(
            event_id=completion_artifacts.audit_event_id,
            event_type=COMPLETED_EVENT_TYPE,
            occurred_at=completion_artifacts.occurred_at,
            producer=AUDIT_PRODUCER,
            correlation_id=_correlation_uuid(context),
            request_id=context.turn_input.request_id,
            actor=_actor(context),
            action=AUDIT_ACTION,
            resource=_resource(context),
            outcome="success",
            reason_codes=(ABSTAINED_REASON_CODE,),
            authorization_decision_id=final_answer.authorization_decision_id,
            runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
            retention_class=AUDIT_RETENTION_CLASS,
            sensitivity=AUDIT_SENSITIVITY,
        )
    if final_answer.outcome == "failed":
        safe_error = final_answer.safe_error
        if safe_error is None:
            raise ValueError("a failed final answer requires a safe error")
        return AuditEvent(
            event_id=completion_artifacts.audit_event_id,
            event_type=FAILED_EVENT_TYPE,
            occurred_at=completion_artifacts.occurred_at,
            producer=AUDIT_PRODUCER,
            correlation_id=_correlation_uuid(context),
            request_id=context.turn_input.request_id,
            actor=_actor(context),
            action=AUDIT_ACTION,
            resource=_resource(context),
            outcome="failed",
            reason_codes=(f"runtime.{safe_error.code.lower()}",),
            authorization_decision_id=final_answer.authorization_decision_id,
            runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
            error_id=completion_artifacts.finalization_error_id,
            internal_detail_ref=safe_error.internal_detail_ref,
            retention_class=AUDIT_RETENTION_CLASS,
            sensitivity=AUDIT_SENSITIVITY,
        )
    raise ValueError("finalize_pending_answer must return answered, abstained, or failed")


def _stopped_audit_event(
    context: RuntimeContext,
    result: OrchestrationResult,
    envelope: ErrorEnvelope,
    completion_artifacts: TerminalCompletionArtifacts,
) -> AuditEvent:
    authorization = result.authorization
    if authorization is None:
        raise ValueError("a stopped orchestration requires an authorization decision")
    return AuditEvent(
        event_id=completion_artifacts.audit_event_id,
        event_type=FAILED_EVENT_TYPE,
        occurred_at=completion_artifacts.occurred_at,
        producer=AUDIT_PRODUCER,
        correlation_id=_correlation_uuid(context),
        request_id=context.turn_input.request_id,
        actor=_actor(context),
        action=AUDIT_ACTION,
        resource=_resource(context),
        outcome="failed",
        reason_codes=(f"runtime.{envelope.error.code.lower()}",),
        authorization_decision_id=authorization.decision_id,
        runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
        error_id=envelope.error_id,
        internal_detail_ref=envelope.error.internal_detail_ref,
        retention_class=AUDIT_RETENTION_CLASS,
        sensitivity=AUDIT_SENSITIVITY,
    )


def _audit_event_for(
    context: RuntimeContext,
    orchestration_result: OrchestrationResult,
    outcome: TerminalOutcome,
    completion_artifacts: TerminalCompletionArtifacts,
) -> AuditEvent:
    if isinstance(outcome, FinalAnswer):
        return _final_answer_audit_event(context, outcome, completion_artifacts)
    return _stopped_audit_event(context, orchestration_result, outcome, completion_artifacts)


def _telemetry_shape(
    outcome: TerminalOutcome,
) -> tuple[RuntimeTelemetryEventName, RuntimeTelemetryOutcome, ErrorCode | None]:
    if isinstance(outcome, FinalAnswer):
        if outcome.outcome == "answered":
            return (
                RuntimeTelemetryEventName.RUNTIME_COMPLETED,
                RuntimeTelemetryOutcome.ANSWERED,
                None,
            )
        if outcome.outcome == "abstained":
            return (
                RuntimeTelemetryEventName.RUNTIME_COMPLETED,
                RuntimeTelemetryOutcome.ABSTAINED,
                None,
            )
        if outcome.outcome == "failed":
            safe_error = outcome.safe_error
            if safe_error is None:
                raise ValueError("a failed final answer requires a safe error")
            return (
                RuntimeTelemetryEventName.RUNTIME_FAILED,
                RuntimeTelemetryOutcome.FAILED,
                safe_error.code,
            )
        raise ValueError("finalize_pending_answer must return answered, abstained, or failed")
    return (
        RuntimeTelemetryEventName.RUNTIME_FAILED,
        RuntimeTelemetryOutcome.FAILED,
        outcome.error.code,
    )


def _telemetry_record(
    context: RuntimeContext,
    orchestration_result: OrchestrationResult,
    *,
    event_name: RuntimeTelemetryEventName,
    outcome: RuntimeTelemetryOutcome,
    error_code: ErrorCode | None,
    completion_artifacts: TerminalCompletionArtifacts,
    entered_at: datetime,
) -> RuntimeTelemetryRecord:
    authorization = orchestration_result.authorization
    plan = orchestration_result.execution_plan
    step_result = orchestration_result.step_result
    step = None if plan is None else plan.steps[0]
    return RuntimeTelemetryRecord(
        event_name=event_name,
        occurred_at=completion_artifacts.telemetry_recorded_at,
        request_id=str(context.turn_input.request_id),
        correlation_id=context.correlation_id,
        runtime_snapshot_id=str(context.runtime_snapshot.snapshot_id),
        authorization_decision_id=(
            None if authorization is None else str(authorization.decision_id)
        ),
        plan_id=None if plan is None else str(plan.plan_id),
        step_id=step_result.step_id if step_result is not None else None,
        capability=None if step is None else step.capability,
        outcome=outcome,
        error_code=error_code,
        duration_ms=(completion_artifacts.telemetry_recorded_at - entered_at) // _ONE_MILLISECOND,
    )


async def _emit_audit(audit_sink: AuditEventSink, event: AuditEvent) -> bool:
    try:
        await audit_sink.emit(event)
    except asyncio.CancelledError:
        raise
    except Exception:
        # Audit is fail closed: the terminal outcome is withheld, never stored.
        return False
    return True


async def _complete(
    idempotency_store: IdempotencyStorePort,
    lease: IdempotencyLease,
    outcome: TerminalOutcome,
) -> bool:
    try:
        await idempotency_store.complete(lease, outcome)
    except asyncio.CancelledError:
        raise
    except Exception:
        return False
    return True


async def _emit_telemetry(
    telemetry_sink: RuntimeTelemetrySink,
    record: RuntimeTelemetryRecord,
) -> None:
    try:
        await telemetry_sink.emit(record)
    except asyncio.CancelledError:
        raise
    except Exception:
        # Telemetry is fail open: it may never change a business outcome.
        return


def _withheld_envelope(
    context: RuntimeContext,
    completion_artifacts: TerminalCompletionArtifacts,
) -> ErrorEnvelope:
    safe_message_key, retryable = _error_semantics(INTERNAL_ERROR_CODE)
    return ErrorEnvelope(
        error_id=completion_artifacts.coordination_error_id,
        correlation_id=_correlation_uuid(context),
        error=DomainError(
            code=INTERNAL_ERROR_CODE,
            safe_message_key=safe_message_key,
            retryable=retryable,
            internal_detail_ref=completion_artifacts.coordination_internal_detail_ref,
        ),
    )


async def _withheld(
    context: RuntimeContext,
    pending: TerminalCoordinationResult,
    orchestration_result: OrchestrationResult,
    *,
    telemetry_sink: RuntimeTelemetrySink,
    completion_artifacts: TerminalCompletionArtifacts,
    entered_at: datetime,
) -> WalkingSkeletonResult:
    envelope = _withheld_envelope(context, completion_artifacts)
    await _emit_telemetry(
        telemetry_sink,
        _telemetry_record(
            context,
            orchestration_result,
            event_name=RuntimeTelemetryEventName.RUNTIME_FAILED,
            outcome=RuntimeTelemetryOutcome.FAILED,
            error_code=INTERNAL_ERROR_CODE,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        ),
    )
    return WalkingSkeletonResult(
        disposition=WalkingSkeletonDisposition.WITHHELD,
        effective_key=pending.effective_key,
        outcome=envelope,
        lease=pending.lease,
        orchestration_result=orchestration_result,
    )


async def _close_terminal_outcome(
    context: RuntimeContext,
    pending: TerminalCoordinationResult,
    outcome: TerminalOutcome,
    *,
    idempotency_store: IdempotencyStorePort,
    audit_sink: AuditEventSink,
    telemetry_sink: RuntimeTelemetrySink,
    completion_artifacts: TerminalCompletionArtifacts,
    entered_at: datetime,
) -> WalkingSkeletonResult:
    """Close one pending terminal outcome: audit, then complete, then telemetry.

    Audit is fail closed: an ordinary audit failure never reaches completion.
    Completion is fail closed: an ordinary completion failure never retries and
    never abandons the lease. Telemetry is fail open and never changes the
    returned business outcome. asyncio.CancelledError from any of the three
    always propagates unchanged.
    """
    lease = pending.lease
    orchestration_result = pending.orchestration_result
    if lease is None:
        raise ValueError("a pending finalization requires the acquired lease")
    if orchestration_result is None:
        raise ValueError("a pending finalization requires an orchestration result")

    event = _audit_event_for(context, orchestration_result, outcome, completion_artifacts)
    accepted = await _emit_audit(audit_sink, event)
    if not accepted:
        return await _withheld(
            context,
            pending,
            orchestration_result,
            telemetry_sink=telemetry_sink,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        )
    stored = await _complete(idempotency_store, lease, outcome)
    if not stored:
        return await _withheld(
            context,
            pending,
            orchestration_result,
            telemetry_sink=telemetry_sink,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        )
    event_name, telemetry_outcome, error_code = _telemetry_shape(outcome)
    await _emit_telemetry(
        telemetry_sink,
        _telemetry_record(
            context,
            orchestration_result,
            event_name=event_name,
            outcome=telemetry_outcome,
            error_code=error_code,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        ),
    )
    return WalkingSkeletonResult(
        disposition=WalkingSkeletonDisposition.STORED,
        effective_key=pending.effective_key,
        outcome=outcome,
        lease=lease,
        orchestration_result=orchestration_result,
    )


async def run_idempotent_fast_document(
    context: RuntimeContext,
    analysis: QueryAnalysis,
    *,
    payload_digest: str,
    idempotency_store: IdempotencyStorePort,
    audit_sink: AuditEventSink,
    telemetry_sink: RuntimeTelemetrySink,
    authorization_port: AuthorizationPort,
    capability_port: CapabilityPort,
    evidence_materializer: EvidenceMaterializerPort,
    renderer: AnswerRendererPort,
    citation_source_resolver: CitationSourceResolverPort,
    orchestration_artifacts: OrchestrationArtifacts,
    terminal_failure_artifacts: TerminalFailureArtifacts,
    finalization_artifacts: FinalizationArtifacts,
    completion_artifacts: TerminalCompletionArtifacts,
    entered_at: datetime,
    finalization_entered_at: datetime,
    generation_mode: FinalGenerationMode,
) -> WalkingSkeletonResult:
    """Run and terminally close one bounded idempotent fast document turn.

    This is the outermost trusted Core entry point of the Walking Skeleton. It
    never inspects `analysis` before idempotency admission: the injected
    configuration objects (artifacts, timestamps) are validated first, and
    `analysis` itself is only ever touched inside `coordinate_idempotent_fast_document`,
    which owns that ordering.
    """
    _require_run_entry(entered_at, finalization_entered_at, completion_artifacts)
    _require_no_identifier_collisions(
        completion_artifacts, finalization_artifacts, terminal_failure_artifacts
    )

    pending = await coordinate_idempotent_fast_document(
        context,
        analysis,
        payload_digest=payload_digest,
        idempotency_store=idempotency_store,
        audit_sink=audit_sink,
        telemetry_sink=telemetry_sink,
        authorization_port=authorization_port,
        capability_port=capability_port,
        evidence_materializer=evidence_materializer,
        orchestration_artifacts=orchestration_artifacts,
        failure_artifacts=terminal_failure_artifacts,
        entered_at=entered_at,
    )

    if pending.status is TerminalCoordinationStatus.REPLAYED:
        outcome = pending.outcome
        if outcome is None:
            raise ValueError("a replayed coordination requires a stored terminal outcome")
        return WalkingSkeletonResult(
            disposition=WalkingSkeletonDisposition.REPLAYED,
            effective_key=pending.effective_key,
            outcome=outcome,
        )

    if pending.status is TerminalCoordinationStatus.TERMINAL_ERROR:
        outcome = pending.outcome
        if outcome is None:
            raise ValueError("a terminal error coordination requires a stored error envelope")
        return WalkingSkeletonResult(
            disposition=WalkingSkeletonDisposition.PASSTHROUGH,
            effective_key=pending.effective_key,
            outcome=outcome,
            lease=pending.lease,
            orchestration_result=pending.orchestration_result,
        )

    lease = pending.lease
    orchestration_result = pending.orchestration_result
    if lease is None:
        raise ValueError("a pending finalization requires the acquired lease")
    if orchestration_result is None:
        raise ValueError("a pending finalization requires an orchestration result")
    if lease.key != pending.effective_key:
        raise ValueError("the acquired lease must belong to the derived effective key")

    if orchestration_result.status is OrchestrationStatus.COMPLETED:
        # ValueError and asyncio.CancelledError from finalize_pending_answer are
        # never caught here: a programming defect must never become a terminal
        # outcome, and cancellation must propagate without being caught here.
        final_answer = await finalize_pending_answer(
            context,
            pending,
            renderer=renderer,
            citation_source_resolver=citation_source_resolver,
            artifacts=finalization_artifacts,
            entered_at=finalization_entered_at,
            generation_mode=generation_mode,
        )
        return await _close_terminal_outcome(
            context,
            pending,
            final_answer,
            idempotency_store=idempotency_store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        )

    if orchestration_result.status is OrchestrationStatus.STOPPED:
        envelope = _stopped_error_envelope(context, orchestration_result, completion_artifacts)
        return await _close_terminal_outcome(
            context,
            pending,
            envelope,
            idempotency_store=idempotency_store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            completion_artifacts=completion_artifacts,
            entered_at=entered_at,
        )

    raise ValueError("a pending finalization requires a completed or stopped orchestration result")
