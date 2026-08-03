"""Bounded terminal coordination around the fast document orchestrator."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import get_args
from uuid import UUID

from ai_assistant.contracts import (
    AuditActorRef,
    AuditEvent,
    AuditResourceRef,
    DomainError,
    ErrorEnvelope,
    FinalAnswer,
    QueryAnalysis,
)
from ai_assistant.contracts.errors import ErrorCode
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
    orchestrate_fast_document,
)
from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    IdempotencyAcquireResult,
    IdempotencyAcquireStatus,
    IdempotencyLease,
    RuntimeContext,
    RuntimeTelemetryEventName,
    RuntimeTelemetryOutcome,
    RuntimeTelemetryRecord,
    TerminalOutcome,
)

AUDIT_PRODUCER = "ai-assistant.core.terminal-runtime"
AUDIT_ACTION = "runtime.answer"
DENIED_EVENT_TYPE = "runtime.turn.denied"
FAILED_EVENT_TYPE = "runtime.turn.failed"
AUDIT_RESOURCE_TYPE = "conversation"
AUDIT_RETENTION_CLASS = "retention.standard"
AUDIT_SENSITIVITY = "sensitivity.internal"
DENIED_REASON_CODE = "authorization.denied"
UNAUTHORIZED_ERROR_CODE: ErrorCode = "UNAUTHORIZED"
CAPACITY_ERROR_CODE: ErrorCode = "CAPACITY_REJECTED"
CONFLICT_ERROR_CODE: ErrorCode = "INVALID_INPUT"
INTERNAL_ERROR_CODE: ErrorCode = "INTERNAL_ERROR"
PENDING_STATUSES = (OrchestrationStatus.COMPLETED, OrchestrationStatus.STOPPED)
TERMINAL_STATUSES = (OrchestrationStatus.DENIED, OrchestrationStatus.FAILED)
# Retryability is a property of the canonical code catalog, never a local policy.
RETRYABLE_ERROR_CODES: tuple[ErrorCode, ...] = (
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
)
ERROR_CODES: tuple[str, ...] = get_args(ErrorCode)
HEX_ALPHABET = "0123456789abcdef"
PAYLOAD_DIGEST_LENGTH = 64
_ONE_MILLISECOND = timedelta(milliseconds=1)


class TerminalCoordinationStatus(StrEnum):
    REPLAYED = "replayed"
    PENDING_FINALIZATION = "pending_finalization"
    TERMINAL_ERROR = "terminal_error"


@dataclass(frozen=True, slots=True)
class TerminalFailureArtifacts:
    """Injected identifiers and timestamps for one terminal failure outcome."""

    error_id: UUID
    internal_detail_ref: UUID
    coordination_error_id: UUID
    coordination_internal_detail_ref: UUID
    audit_event_id: UUID
    occurred_at: datetime
    telemetry_recorded_at: datetime

    def __post_init__(self) -> None:
        identifiers: tuple[tuple[str, UUID], ...] = (
            ("error_id", self.error_id),
            ("internal_detail_ref", self.internal_detail_ref),
            ("coordination_error_id", self.coordination_error_id),
            ("coordination_internal_detail_ref", self.coordination_internal_detail_ref),
            ("audit_event_id", self.audit_event_id),
        )
        for name, identifier in identifiers:
            if identifier.version != 4:
                raise ValueError(f"{name} must be a version 4 UUID")
        distinct = frozenset(identifier for _, identifier in identifiers)
        if len(distinct) != len(identifiers):
            raise ValueError("terminal failure identifiers must be pairwise distinct")
        moments: tuple[tuple[str, datetime], ...] = (
            ("occurred_at", self.occurred_at),
            ("telemetry_recorded_at", self.telemetry_recorded_at),
        )
        for name, moment in moments:
            if moment.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.telemetry_recorded_at < self.occurred_at:
            raise ValueError("telemetry_recorded_at must not precede occurred_at")


@dataclass(frozen=True, slots=True)
class TerminalCoordinationResult:
    """Private immutable outcome of one idempotent coordination attempt."""

    status: TerminalCoordinationStatus
    effective_key: EffectiveIdempotencyKey
    lease: IdempotencyLease | None = None
    orchestration_result: OrchestrationResult | None = None
    outcome: TerminalOutcome | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, TerminalCoordinationStatus):
            raise ValueError("status must be a TerminalCoordinationStatus")
        if not isinstance(self.effective_key, EffectiveIdempotencyKey):
            raise ValueError("effective_key must be an EffectiveIdempotencyKey")
        if self.status is TerminalCoordinationStatus.REPLAYED:
            self._require_replayed_shape()
        elif self.status is TerminalCoordinationStatus.PENDING_FINALIZATION:
            self._require_pending_shape()
        else:
            self._require_terminal_error_shape()

    def _require_replayed_shape(self) -> None:
        if self.lease is not None:
            raise ValueError("a replayed coordination must not retain a lease")
        if self.orchestration_result is not None:
            raise ValueError("a replayed coordination must not carry an orchestration result")
        if not isinstance(self.outcome, FinalAnswer | ErrorEnvelope):
            raise ValueError("a replayed coordination requires the stored terminal outcome")

    def _require_pending_shape(self) -> None:
        if self.lease is None:
            raise ValueError("a pending coordination requires the acquired lease")
        result = self.orchestration_result
        if result is None:
            raise ValueError("a pending coordination requires an orchestration result")
        if result.status not in PENDING_STATUSES:
            raise ValueError("a pending coordination requires a completed or stopped run")
        if self.outcome is not None:
            raise ValueError("a pending coordination must not carry a terminal outcome")
        self._require_bound_lease()

    def _require_terminal_error_shape(self) -> None:
        if not isinstance(self.outcome, ErrorEnvelope):
            raise ValueError("a terminal error coordination requires an error envelope")
        result = self.orchestration_result
        if result is not None and result.status not in TERMINAL_STATUSES:
            raise ValueError("a terminal error coordination requires a denied or failed run")
        # A lease exists only for an executed turn: admission level errors never
        # acquired one and must not pretend to hold storage state.
        if (self.lease is None) is not (result is None):
            raise ValueError("a terminal error lease requires an executed orchestration")
        self._require_bound_lease()

    def _require_bound_lease(self) -> None:
        lease = self.lease
        if lease is not None and lease.key != self.effective_key:
            raise ValueError("a retained lease must belong to the derived effective key")


def _require_entry(
    context: RuntimeContext,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> None:
    if entered_at.utcoffset() is None:
        raise ValueError("entered_at must be timezone-aware")
    if entered_at < context.started_at:
        raise ValueError("entered_at must not precede the runtime start")
    if failure_artifacts.occurred_at < entered_at:
        raise ValueError("occurred_at must not precede entered_at")


def _require_payload_digest(payload_digest: str) -> None:
    if len(payload_digest) != PAYLOAD_DIGEST_LENGTH:
        raise ValueError("payload_digest must be 64 lowercase hexadecimal characters")
    for character in payload_digest:
        if character not in HEX_ALPHABET:
            raise ValueError("payload_digest must be 64 lowercase hexadecimal characters")


def _require_bound_acquisition(
    lease: IdempotencyLease | None,
    key: EffectiveIdempotencyKey,
    payload_digest: str,
) -> IdempotencyLease:
    if lease is None:
        raise ValueError("an acquired idempotency result requires a lease")
    if lease.key != key:
        raise ValueError("the acquired lease must belong to the derived effective key")
    if lease.request_fingerprint != payload_digest:
        raise ValueError("the acquired lease must bind the requested payload digest")
    return lease


def _effective_key(context: RuntimeContext) -> EffectiveIdempotencyKey:
    principal = context.principal
    snapshot = context.runtime_snapshot
    return EffectiveIdempotencyKey(
        deployment_id=str(principal.deployment_id),
        principal_id=str(principal.principal_id),
        client_key=str(context.turn_input.idempotency_key),
        runtime_snapshot_id=str(snapshot.snapshot_id),
        runtime_snapshot_digest=snapshot.integrity.digest,
    )


def _correlation_uuid(context: RuntimeContext) -> UUID:
    try:
        correlation_id = UUID(context.correlation_id)
    except ValueError as error:
        raise ValueError("correlation_id must be a version 4 UUID") from error
    if correlation_id.version != 4:
        raise ValueError("correlation_id must be a version 4 UUID")
    return correlation_id


def _error_semantics(code: ErrorCode) -> tuple[str, bool]:
    if code not in ERROR_CODES:
        raise ValueError("error code must belong to the canonical catalog")
    return (f"error.{code.lower()}", code in RETRYABLE_ERROR_CODES)


def _error_envelope(
    context: RuntimeContext,
    code: ErrorCode,
    error_id: UUID,
    internal_detail_ref: UUID,
) -> ErrorEnvelope:
    safe_message_key, retryable = _error_semantics(code)
    return ErrorEnvelope(
        error_id=error_id,
        correlation_id=_correlation_uuid(context),
        error=DomainError(
            code=code,
            safe_message_key=safe_message_key,
            retryable=retryable,
            internal_detail_ref=internal_detail_ref,
        ),
    )


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


def _denied_event(
    context: RuntimeContext,
    authorization_decision_id: UUID,
    failure_artifacts: TerminalFailureArtifacts,
) -> AuditEvent:
    return AuditEvent(
        event_id=failure_artifacts.audit_event_id,
        event_type=DENIED_EVENT_TYPE,
        occurred_at=failure_artifacts.occurred_at,
        producer=AUDIT_PRODUCER,
        correlation_id=_correlation_uuid(context),
        request_id=context.turn_input.request_id,
        actor=_actor(context),
        action=AUDIT_ACTION,
        resource=_resource(context),
        outcome="denied",
        reason_codes=(DENIED_REASON_CODE,),
        authorization_decision_id=authorization_decision_id,
        runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
        retention_class=AUDIT_RETENTION_CLASS,
        sensitivity=AUDIT_SENSITIVITY,
    )


def _failed_event(
    context: RuntimeContext,
    result: OrchestrationResult,
    code: ErrorCode,
    failure_artifacts: TerminalFailureArtifacts,
) -> AuditEvent:
    authorization = result.authorization
    return AuditEvent(
        event_id=failure_artifacts.audit_event_id,
        event_type=FAILED_EVENT_TYPE,
        occurred_at=failure_artifacts.occurred_at,
        producer=AUDIT_PRODUCER,
        correlation_id=_correlation_uuid(context),
        request_id=context.turn_input.request_id,
        actor=_actor(context),
        action=AUDIT_ACTION,
        resource=_resource(context),
        outcome="failed",
        reason_codes=(f"runtime.{code.lower()}",),
        authorization_decision_id=(
            authorization.decision_id if authorization is not None else None
        ),
        runtime_snapshot_id=context.runtime_snapshot.snapshot_id,
        error_id=failure_artifacts.error_id,
        internal_detail_ref=failure_artifacts.internal_detail_ref,
        retention_class=AUDIT_RETENTION_CLASS,
        sensitivity=AUDIT_SENSITIVITY,
    )


def _started_record(context: RuntimeContext, entered_at: datetime) -> RuntimeTelemetryRecord:
    return RuntimeTelemetryRecord(
        event_name=RuntimeTelemetryEventName.RUNTIME_STARTED,
        occurred_at=entered_at,
        request_id=str(context.turn_input.request_id),
        correlation_id=context.correlation_id,
        runtime_snapshot_id=str(context.runtime_snapshot.snapshot_id),
    )


def _failure_record(
    context: RuntimeContext,
    result: OrchestrationResult | None,
    code: ErrorCode,
    outcome: RuntimeTelemetryOutcome,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> RuntimeTelemetryRecord:
    authorization = None if result is None else result.authorization
    plan = None if result is None else result.execution_plan
    step_result = None if result is None else result.step_result
    step = None if plan is None else plan.steps[0]
    return RuntimeTelemetryRecord(
        event_name=RuntimeTelemetryEventName.RUNTIME_FAILED,
        occurred_at=failure_artifacts.telemetry_recorded_at,
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
        error_code=code,
        duration_ms=(failure_artifacts.telemetry_recorded_at - entered_at) // _ONE_MILLISECOND,
    )


async def _acquire(
    idempotency_store: IdempotencyStorePort,
    key: EffectiveIdempotencyKey,
    payload_digest: str,
) -> IdempotencyAcquireResult | None:
    try:
        return await idempotency_store.acquire(key, payload_digest)
    except asyncio.CancelledError:
        raise
    except Exception:
        return None


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


async def _admission_error(
    context: RuntimeContext,
    key: EffectiveIdempotencyKey,
    code: ErrorCode,
    *,
    telemetry_sink: RuntimeTelemetrySink,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> TerminalCoordinationResult:
    envelope = _error_envelope(
        context,
        code,
        failure_artifacts.error_id,
        failure_artifacts.internal_detail_ref,
    )
    await _emit_telemetry(
        telemetry_sink,
        _failure_record(
            context,
            None,
            code,
            RuntimeTelemetryOutcome.FAILED,
            failure_artifacts,
            entered_at,
        ),
    )
    return TerminalCoordinationResult(
        status=TerminalCoordinationStatus.TERMINAL_ERROR,
        effective_key=key,
        outcome=envelope,
    )


async def _withheld_error(
    context: RuntimeContext,
    key: EffectiveIdempotencyKey,
    lease: IdempotencyLease,
    result: OrchestrationResult,
    *,
    telemetry_sink: RuntimeTelemetrySink,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> TerminalCoordinationResult:
    envelope = _error_envelope(
        context,
        INTERNAL_ERROR_CODE,
        failure_artifacts.coordination_error_id,
        failure_artifacts.coordination_internal_detail_ref,
    )
    await _emit_telemetry(
        telemetry_sink,
        _failure_record(
            context,
            result,
            INTERNAL_ERROR_CODE,
            RuntimeTelemetryOutcome.FAILED,
            failure_artifacts,
            entered_at,
        ),
    )
    return TerminalCoordinationResult(
        status=TerminalCoordinationStatus.TERMINAL_ERROR,
        effective_key=key,
        lease=lease,
        orchestration_result=result,
        outcome=envelope,
    )


async def _finalize_terminal_error(
    context: RuntimeContext,
    key: EffectiveIdempotencyKey,
    lease: IdempotencyLease,
    result: OrchestrationResult,
    *,
    idempotency_store: IdempotencyStorePort,
    audit_sink: AuditEventSink,
    telemetry_sink: RuntimeTelemetrySink,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> TerminalCoordinationResult:
    denied = result.status is OrchestrationStatus.DENIED
    code = result.error_code
    if code is None:
        raise ValueError("a terminal orchestration result requires an error code")
    envelope = _error_envelope(
        context,
        code,
        failure_artifacts.error_id,
        failure_artifacts.internal_detail_ref,
    )
    if denied:
        authorization = result.authorization
        if authorization is None:
            raise ValueError("a denied orchestration requires an authorization decision")
        event = _denied_event(context, authorization.decision_id, failure_artifacts)
    else:
        event = _failed_event(context, result, code, failure_artifacts)
    accepted = await _emit_audit(audit_sink, event)
    if not accepted:
        return await _withheld_error(
            context,
            key,
            lease,
            result,
            telemetry_sink=telemetry_sink,
            failure_artifacts=failure_artifacts,
            entered_at=entered_at,
        )
    stored = await _complete(idempotency_store, lease, envelope)
    if not stored:
        return await _withheld_error(
            context,
            key,
            lease,
            result,
            telemetry_sink=telemetry_sink,
            failure_artifacts=failure_artifacts,
            entered_at=entered_at,
        )
    await _emit_telemetry(
        telemetry_sink,
        _failure_record(
            context,
            result,
            code,
            RuntimeTelemetryOutcome.DENIED if denied else RuntimeTelemetryOutcome.FAILED,
            failure_artifacts,
            entered_at,
        ),
    )
    return TerminalCoordinationResult(
        status=TerminalCoordinationStatus.TERMINAL_ERROR,
        effective_key=key,
        lease=lease,
        orchestration_result=result,
        outcome=envelope,
    )


async def coordinate_idempotent_fast_document(
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
    orchestration_artifacts: OrchestrationArtifacts,
    failure_artifacts: TerminalFailureArtifacts,
    entered_at: datetime,
) -> TerminalCoordinationResult:
    """Admit one turn through the idempotency boundary and coordinate its end."""
    _require_entry(context, failure_artifacts, entered_at)
    _require_payload_digest(payload_digest)
    key = _effective_key(context)
    acquisition = await _acquire(idempotency_store, key, payload_digest)
    if acquisition is None:
        return await _admission_error(
            context,
            key,
            INTERNAL_ERROR_CODE,
            telemetry_sink=telemetry_sink,
            failure_artifacts=failure_artifacts,
            entered_at=entered_at,
        )
    if acquisition.status is IdempotencyAcquireStatus.REPLAY:
        stored_outcome = acquisition.outcome
        if stored_outcome is None:
            raise ValueError("a replay acquisition requires a stored terminal outcome")
        # The stored artifact is returned untouched: it is already accepted.
        return TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=key,
            outcome=stored_outcome,
        )
    if acquisition.status is not IdempotencyAcquireStatus.ACQUIRED:
        rejected: ErrorCode = (
            CAPACITY_ERROR_CODE
            if acquisition.status is IdempotencyAcquireStatus.IN_FLIGHT
            else CONFLICT_ERROR_CODE
        )
        return await _admission_error(
            context,
            key,
            rejected,
            telemetry_sink=telemetry_sink,
            failure_artifacts=failure_artifacts,
            entered_at=entered_at,
        )
    lease = _require_bound_acquisition(acquisition.lease, key, payload_digest)
    await _emit_telemetry(telemetry_sink, _started_record(context, entered_at))
    result = await orchestrate_fast_document(
        context,
        analysis,
        authorization_port=authorization_port,
        capability_port=capability_port,
        evidence_materializer=evidence_materializer,
        artifacts=orchestration_artifacts,
        entered_at=entered_at,
    )
    if result.status in PENDING_STATUSES:
        # WS-004 owns finalization, so the lease stays open on purpose.
        return TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=lease,
            orchestration_result=result,
        )
    return await _finalize_terminal_error(
        context,
        key,
        lease,
        result,
        idempotency_store=idempotency_store,
        audit_sink=audit_sink,
        telemetry_sink=telemetry_sink,
        failure_artifacts=failure_artifacts,
        entered_at=entered_at,
    )
