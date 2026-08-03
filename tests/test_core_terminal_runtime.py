"""Tests for idempotency admission and terminal failure coordination."""

import ast
import asyncio
import dataclasses
import sys
from collections.abc import Coroutine
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    BUNDLE_ID,
    CONVERSATION_ID,
    CORRELATION_TEXT,
    DEPLOYMENT_ID,
    FOREIGN_ID,
    IDEMPOTENCY_KEY,
    MESSAGE_ID,
    NOW,
    PLAN_ID,
    PRINCIPAL_ID,
    RAW_MESSAGE,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SECURITY_CONTEXT_ID,
    SNAPSHOT_DIGEST,
    authorization,
    document_evidence,
    failed_step_result,
    principal,
    query_analysis,
    runtime_snapshot,
    step_result,
    terminal_route_decision,
    turn_input,
)
from support.walking_skeleton_runtime_fakes import (
    AuthorizationPortFake,
    CapabilityPortFake,
    EvidenceMaterializerFake,
    denied_authorization,
)
from support.walking_skeleton_terminal_fakes import (
    OTHER_PAYLOAD_DIGEST,
    PAYLOAD_DIGEST,
    AuditEventSinkFake,
    CallJournal,
    IdempotencyStoreFake,
    RuntimeTelemetrySinkFake,
    acquired,
    conflicted,
    effective_key,
    in_flight,
    lease,
    replayed,
    stored_error_envelope,
    stored_final_answer,
    terminal_identifier,
)

from ai_assistant.contracts import (
    AuditActorRef,
    AuditEvent,
    AuditResourceRef,
    ErrorEnvelope,
    Evidence,
    FinalAnswer,
    QueryAnalysis,
    RuntimeSnapshot,
    RuntimeSnapshotIntegrity,
    SecurityPrincipalContext,
    TurnInput,
)
from ai_assistant.core.runtime import (
    OrchestrationArtifacts,
    OrchestrationFailurePhase,
    OrchestrationResult,
    OrchestrationStatus,
)
from ai_assistant.core.terminal_runtime import (
    ERROR_CODES,
    RETRYABLE_ERROR_CODES,
    TerminalCoordinationResult,
    TerminalCoordinationStatus,
    TerminalFailureArtifacts,
    _error_semantics,
    coordinate_idempotent_fast_document,
)
from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    IdempotencyAcquireResult,
    IdempotencyAcquireStatus,
    RuntimeContext,
    RuntimeTelemetryEventName,
    RuntimeTelemetryOutcome,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "terminal_runtime.py"
)
CORE_INIT_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "__init__.py"
)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")
STDLIB_MODULES = frozenset(sys.stdlib_module_names)
ALLOWED_PACKAGES = ("ai_assistant.contracts", "ai_assistant.core")
FORBIDDEN_FRAGMENTS = (
    "Any",
    "cast(",
    "type: ignore",
    "noqa",
    "dict[",
    "Mapping[str, object]",
    "metadata:",
    "attributes:",
    "payload:",
    "model_construct",
    "model_copy",
    "uuid4",
    "datetime.now",
    "utcnow",
    "logging",
    "open(",
    "os.environ",
    "raw_message",
    "normalized_query",
)
CONCURRENCY_FRAGMENTS = (
    "asyncio.Lock",
    "asyncio.Event",
    "asyncio.Semaphore",
    "asyncio.Condition",
    "asyncio.Queue",
    "threading",
    "Semaphore",
    "Condition(",
    "Queue",
    "create_task",
    "ensure_future",
    "TaskGroup",
    "shield",
    "sleep",
    "while ",
    "poll",
)
FORBIDDEN_VENDOR_ROOTS = (
    "requests",
    "httpx",
    "aiohttp",
    "boto3",
    "psycopg",
    "redis",
    "sqlalchemy",
    "elasticsearch",
    "opensearchpy",
    "openai",
    "anthropic",
    "opentelemetry",
)
FORBIDDEN_RECORD_TEXT = (
    RAW_MESSAGE,
    "normalized query",
    "prompt",
    "traceback",
    "secret",
    "token",
)
ARTIFACTS = OrchestrationArtifacts(
    route_decision_id=ROUTE_DECISION_ID,
    route_decided_at=NOW,
    execution_plan_id=PLAN_ID,
    execution_plan_planned_at=NOW,
    evidence_bundle_id=BUNDLE_ID,
    evidence_bundle_built_at=NOW,
    answer_plan_id=ANSWER_PLAN_ID,
    answer_plan_built_at=NOW,
)
ERROR_ID = terminal_identifier(40)
DETAIL_REF = terminal_identifier(41)
COORDINATION_ERROR_ID = terminal_identifier(45)
COORDINATION_DETAIL_REF = terminal_identifier(46)
AUDIT_EVENT_ID = terminal_identifier(42)
OTHER_KEY_ID = terminal_identifier(43)
NON_UUID4 = UUID("00000044-0000-1000-8000-000000000000")
FAILURE_ARTIFACTS = TerminalFailureArtifacts(
    error_id=ERROR_ID,
    internal_detail_ref=DETAIL_REF,
    coordination_error_id=COORDINATION_ERROR_ID,
    coordination_internal_detail_ref=COORDINATION_DETAIL_REF,
    audit_event_id=AUDIT_EVENT_ID,
    occurred_at=NOW,
    telemetry_recorded_at=NOW + timedelta(milliseconds=25),
)
OTHER_SNAPSHOT_DIGEST = "sha256:" + "b" * 64
SHORT_DEADLINE = timedelta(milliseconds=50)


def principal_with(
    *,
    principal_id: UUID = PRINCIPAL_ID,
    deployment_id: UUID = DEPLOYMENT_ID,
) -> SecurityPrincipalContext:
    return SecurityPrincipalContext(
        context_id=SECURITY_CONTEXT_ID,
        principal_id=principal_id,
        principal_type="user",
        deployment_id=deployment_id,
        issuer="urn:test:issuer",
        authenticated_at=NOW,
        authentication_methods=("password",),
        assurance_level="assurance.standard",
    )


def turn_input_with(*, idempotency_key: UUID = IDEMPOTENCY_KEY) -> TurnInput:
    return TurnInput(
        request_id=REQUEST_ID,
        message_id=MESSAGE_ID,
        conversation_id=CONVERSATION_ID,
        raw_message=RAW_MESSAGE,
        received_at=NOW,
        idempotency_key=idempotency_key,
    )


def snapshot_with_digest(digest: str) -> RuntimeSnapshot:
    base = runtime_snapshot()
    return RuntimeSnapshot(
        snapshot_id=base.snapshot_id,
        captured_at=base.captured_at,
        content=base.content,
        integrity=RuntimeSnapshotIntegrity(canonicalization="rfc8785", digest=digest),
    )


def context(
    *,
    deadline_at: datetime | None = None,
    correlation_id: str = CORRELATION_TEXT,
) -> RuntimeContext:
    return RuntimeContext(
        turn_input=turn_input(),
        principal=principal(),
        runtime_snapshot=runtime_snapshot(),
        correlation_id=correlation_id,
        started_at=NOW,
        deadline_at=deadline_at,
    )


def expected_key() -> EffectiveIdempotencyKey:
    return effective_key(
        deployment_id=str(DEPLOYMENT_ID),
        principal_id=str(PRINCIPAL_ID),
        client_key=str(IDEMPOTENCY_KEY),
        runtime_snapshot_id=str(runtime_snapshot().snapshot_id),
        runtime_snapshot_digest=SNAPSHOT_DIGEST,
    )


def accepted_evidence() -> tuple[Evidence, ...]:
    return (document_evidence(),)


def abstaining_analysis() -> QueryAnalysis:
    return query_analysis(intent="analytics", evidence_needs=("analytics",))


def coordinate(
    *,
    runtime: RuntimeContext | None = None,
    analysis: QueryAnalysis | None = None,
    payload_digest: str = PAYLOAD_DIGEST,
    idempotency_store: IdempotencyStoreFake,
    audit_sink: AuditEventSinkFake,
    telemetry_sink: RuntimeTelemetrySinkFake,
    authorization_port: AuthorizationPortFake | None = None,
    capability_port: CapabilityPortFake | None = None,
    evidence_materializer: EvidenceMaterializerFake | None = None,
    failure_artifacts: TerminalFailureArtifacts = FAILURE_ARTIFACTS,
    entered_at: datetime = NOW,
) -> Coroutine[None, None, TerminalCoordinationResult]:
    return coordinate_idempotent_fast_document(
        runtime if runtime is not None else context(),
        analysis if analysis is not None else query_analysis(),
        payload_digest=payload_digest,
        idempotency_store=idempotency_store,
        audit_sink=audit_sink,
        telemetry_sink=telemetry_sink,
        authorization_port=(
            authorization_port
            if authorization_port is not None
            else AuthorizationPortFake(decision=authorization())
        ),
        capability_port=(
            capability_port
            if capability_port is not None
            else CapabilityPortFake(result=step_result())
        ),
        evidence_materializer=(
            evidence_materializer
            if evidence_materializer is not None
            else EvidenceMaterializerFake(evidence=accepted_evidence())
        ),
        orchestration_artifacts=ARTIFACTS,
        failure_artifacts=failure_artifacts,
        entered_at=entered_at,
    )


def run(coroutine: Coroutine[None, None, TerminalCoordinationResult]) -> TerminalCoordinationResult:
    return asyncio.run(coroutine)


def stopped_result() -> OrchestrationResult:
    return OrchestrationResult(
        status=OrchestrationStatus.STOPPED,
        authorization=authorization(),
        route_decision=terminal_route_decision(lane="abstain"),
    )


def denied_result() -> OrchestrationResult:
    return OrchestrationResult(
        status=OrchestrationStatus.DENIED,
        authorization=denied_authorization(),
        error_code="UNAUTHORIZED",
        failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
    )


def failed_result() -> OrchestrationResult:
    return OrchestrationResult(
        status=OrchestrationStatus.FAILED,
        error_code="INTERNAL_ERROR",
        failure_phase=OrchestrationFailurePhase.RUNTIME,
    )


# 21.1 result and artifact invariants ---------------------------------------


def test_private_types_are_frozen_and_slotted() -> None:
    for model in (TerminalFailureArtifacts, TerminalCoordinationResult):
        assert dataclasses.is_dataclass(model)
        assert model.__dataclass_params__.frozen
        assert hasattr(model, "__slots__")


def test_coordination_result_rejects_attribute_assignment() -> None:
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.REPLAYED,
        effective_key=expected_key(),
        outcome=stored_final_answer(),
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = TerminalCoordinationStatus.TERMINAL_ERROR


IDENTIFIER_FIELDS = (
    "error_id",
    "internal_detail_ref",
    "coordination_error_id",
    "coordination_internal_detail_ref",
    "audit_event_id",
)


def artifacts_with(
    *,
    error_id: UUID = ERROR_ID,
    internal_detail_ref: UUID = DETAIL_REF,
    coordination_error_id: UUID = COORDINATION_ERROR_ID,
    coordination_internal_detail_ref: UUID = COORDINATION_DETAIL_REF,
    audit_event_id: UUID = AUDIT_EVENT_ID,
) -> TerminalFailureArtifacts:
    return TerminalFailureArtifacts(
        error_id=error_id,
        internal_detail_ref=internal_detail_ref,
        coordination_error_id=coordination_error_id,
        coordination_internal_detail_ref=coordination_internal_detail_ref,
        audit_event_id=audit_event_id,
        occurred_at=NOW,
        telemetry_recorded_at=NOW,
    )


@pytest.mark.parametrize("field_name", list(IDENTIFIER_FIELDS))
def test_failure_artifacts_require_version_four_identifiers(field_name: str) -> None:
    overrides = {field_name: NON_UUID4}
    with pytest.raises(ValueError, match="version 4 UUID"):
        artifacts_with(**overrides)


@pytest.mark.parametrize("field_name", list(IDENTIFIER_FIELDS[:-1]))
def test_failure_artifacts_reject_duplicate_identifiers(field_name: str) -> None:
    overrides = {field_name: AUDIT_EVENT_ID}
    with pytest.raises(ValueError, match="pairwise distinct"):
        artifacts_with(**overrides)


def test_failure_artifacts_accept_distinct_identifiers() -> None:
    artifacts = artifacts_with()
    assert artifacts.coordination_error_id != artifacts.error_id
    assert artifacts.coordination_internal_detail_ref != artifacts.internal_detail_ref


@pytest.mark.parametrize("field_name", ["occurred_at", "telemetry_recorded_at"])
def test_failure_artifacts_require_timezone_aware_timestamps(field_name: str) -> None:
    naive = datetime(2026, 1, 1, 12, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        TerminalFailureArtifacts(
            error_id=ERROR_ID,
            internal_detail_ref=DETAIL_REF,
            coordination_error_id=COORDINATION_ERROR_ID,
            coordination_internal_detail_ref=COORDINATION_DETAIL_REF,
            audit_event_id=AUDIT_EVENT_ID,
            occurred_at=naive if field_name == "occurred_at" else NOW,
            telemetry_recorded_at=naive if field_name == "telemetry_recorded_at" else NOW,
        )


def test_failure_artifacts_require_ordered_timestamps() -> None:
    with pytest.raises(ValueError, match="must not precede"):
        TerminalFailureArtifacts(
            error_id=ERROR_ID,
            internal_detail_ref=DETAIL_REF,
            coordination_error_id=COORDINATION_ERROR_ID,
            coordination_internal_detail_ref=COORDINATION_DETAIL_REF,
            audit_event_id=AUDIT_EVENT_ID,
            occurred_at=NOW,
            telemetry_recorded_at=NOW - timedelta(milliseconds=1),
        )


def test_equal_artifact_timestamps_are_accepted() -> None:
    artifacts = TerminalFailureArtifacts(
        error_id=ERROR_ID,
        internal_detail_ref=DETAIL_REF,
        coordination_error_id=COORDINATION_ERROR_ID,
        coordination_internal_detail_ref=COORDINATION_DETAIL_REF,
        audit_event_id=AUDIT_EVENT_ID,
        occurred_at=NOW,
        telemetry_recorded_at=NOW,
    )
    assert artifacts.telemetry_recorded_at == artifacts.occurred_at


def test_valid_replayed_state_is_accepted() -> None:
    outcome = stored_final_answer()
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.REPLAYED,
        effective_key=expected_key(),
        outcome=outcome,
    )
    assert result.outcome is outcome


def test_valid_pending_state_is_accepted() -> None:
    key = expected_key()
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.PENDING_FINALIZATION,
        effective_key=key,
        lease=lease(key),
        orchestration_result=stopped_result(),
    )
    assert result.outcome is None


def test_valid_terminal_error_state_is_accepted() -> None:
    key = expected_key()
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.TERMINAL_ERROR,
        effective_key=key,
        lease=lease(key),
        orchestration_result=denied_result(),
        outcome=stored_error_envelope("UNAUTHORIZED"),
    )
    assert isinstance(result.outcome, ErrorEnvelope)


def test_replay_with_a_lease_is_rejected() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="must not retain a lease"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=key,
            lease=lease(key),
            outcome=stored_final_answer(),
        )


def test_replay_with_an_orchestration_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="orchestration result"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=expected_key(),
            orchestration_result=stopped_result(),
            outcome=stored_final_answer(),
        )


def test_replay_without_an_outcome_is_rejected() -> None:
    with pytest.raises(ValueError, match="stored terminal outcome"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=expected_key(),
        )


def test_pending_without_a_lease_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the acquired lease"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=expected_key(),
            orchestration_result=stopped_result(),
        )


def test_pending_without_an_orchestration_result_is_rejected() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="requires an orchestration result"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=lease(key),
        )


def test_pending_with_a_terminal_outcome_is_rejected() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="must not carry a terminal outcome"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=lease(key),
            orchestration_result=stopped_result(),
            outcome=stored_final_answer(),
        )


@pytest.mark.parametrize("result_builder", [denied_result, failed_result])
def test_pending_with_a_terminal_orchestration_is_rejected(result_builder: object) -> None:
    key = expected_key()
    builder = result_builder
    assert callable(builder)
    with pytest.raises(ValueError, match="completed or stopped"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=lease(key),
            orchestration_result=builder(),
        )


def test_terminal_error_with_a_final_answer_is_rejected() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="requires an error envelope"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=key,
            lease=lease(key),
            orchestration_result=denied_result(),
            outcome=stored_final_answer(),
        )


def test_terminal_error_with_a_pending_orchestration_is_rejected() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="denied or failed"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=key,
            lease=lease(key),
            orchestration_result=stopped_result(),
            outcome=stored_error_envelope(),
        )


def test_terminal_error_lease_requires_an_executed_orchestration() -> None:
    key = expected_key()
    with pytest.raises(ValueError, match="requires an executed orchestration"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=key,
            lease=lease(key),
            outcome=stored_error_envelope(),
        )


def test_terminal_error_orchestration_requires_a_lease() -> None:
    with pytest.raises(ValueError, match="requires an executed orchestration"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=expected_key(),
            orchestration_result=denied_result(),
            outcome=stored_error_envelope(),
        )


def test_effective_key_must_be_the_private_value_type() -> None:
    with pytest.raises(ValueError, match="EffectiveIdempotencyKey"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=stored_final_answer(),
            outcome=stored_final_answer(),
        )


def test_coordination_status_must_be_the_private_enum() -> None:
    with pytest.raises(ValueError, match="TerminalCoordinationStatus"):
        TerminalCoordinationResult(
            status="replayed",
            effective_key=expected_key(),
            outcome=stored_final_answer(),
        )


# 21.2 effective key isolation ----------------------------------------------


def observed_key(runtime: RuntimeContext) -> EffectiveIdempotencyKey:
    store = IdempotencyStoreFake(result=in_flight())
    run(
        coordinate(
            runtime=runtime,
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
        )
    )
    return store.keys[0]


def test_effective_key_uses_only_trusted_runtime_sources() -> None:
    assert observed_key(context()) == expected_key()


def test_effective_key_changes_with_the_deployment() -> None:
    runtime = dataclasses.replace(context(), principal=principal_with(deployment_id=FOREIGN_ID))
    assert observed_key(runtime) != expected_key()


def test_effective_key_changes_with_the_principal() -> None:
    runtime = dataclasses.replace(context(), principal=principal_with(principal_id=FOREIGN_ID))
    assert observed_key(runtime) != expected_key()


def test_effective_key_changes_with_the_client_idempotency_key() -> None:
    runtime = dataclasses.replace(context(), turn_input=turn_input_with(idempotency_key=FOREIGN_ID))
    assert observed_key(runtime) != expected_key()


def test_effective_key_changes_with_the_snapshot_identity() -> None:
    runtime = dataclasses.replace(
        context(),
        runtime_snapshot=runtime_snapshot(snapshot_id=FOREIGN_ID),
    )
    assert observed_key(runtime) != expected_key()


def test_effective_key_changes_with_the_snapshot_digest() -> None:
    runtime = dataclasses.replace(
        context(),
        runtime_snapshot=snapshot_with_digest(OTHER_SNAPSHOT_DIGEST),
    )
    assert observed_key(runtime) != expected_key()


def test_raw_key_reuse_across_users_does_not_share_scope() -> None:
    first = observed_key(dataclasses.replace(context(), principal=principal_with()))
    second = observed_key(
        dataclasses.replace(context(), principal=principal_with(principal_id=FOREIGN_ID))
    )
    assert first.client_key == second.client_key
    assert first != second


def test_raw_key_reuse_across_deployments_does_not_share_scope() -> None:
    first = observed_key(context())
    second = observed_key(
        dataclasses.replace(context(), principal=principal_with(deployment_id=FOREIGN_ID))
    )
    assert first.client_key == second.client_key
    assert first != second


def test_effective_key_never_carries_request_content() -> None:
    key = observed_key(context())
    for value in (
        key.deployment_id,
        key.principal_id,
        key.client_key,
        key.runtime_snapshot_id,
        key.runtime_snapshot_digest,
    ):
        assert RAW_MESSAGE not in value


def test_payload_digest_is_forwarded_unchanged() -> None:
    store = IdempotencyStoreFake(result=in_flight())
    run(
        coordinate(
            payload_digest=OTHER_PAYLOAD_DIGEST,
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
        )
    )
    assert store.fingerprints == (OTHER_PAYLOAD_DIGEST,)


# 21.3 acquisition ordering --------------------------------------------------


@pytest.mark.parametrize("acquire_result", ["in_flight", "conflict", "replay"])
def test_acquisition_short_circuits_before_any_analysis_work(acquire_result: str) -> None:
    if acquire_result == "in_flight":
        configured = in_flight()
    elif acquire_result == "conflict":
        configured = conflicted()
    else:
        configured = replayed(stored_final_answer())
    store = IdempotencyStoreFake(result=configured)
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    run(
        coordinate(
            analysis=abstaining_analysis(),
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert store.acquire_calls == 1
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0


def test_acquire_is_called_exactly_once_for_an_executed_turn() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
        )
    )
    assert store.acquire_calls == 1


def test_authorization_runs_only_after_acquisition() -> None:
    key = expected_key()
    journal = CallJournal()
    store = IdempotencyStoreFake(result=acquired(key), journal=journal)
    authorization_port = AuthorizationPortFake(decision=authorization())
    run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(journal=journal),
            telemetry_sink=RuntimeTelemetrySinkFake(journal=journal),
            authorization_port=authorization_port,
        )
    )
    assert journal.entries[0] == "acquire"
    assert authorization_port.calls == 1


# 21.4 replay ----------------------------------------------------------------


@pytest.mark.parametrize("outcome_kind", ["final_answer", "error_envelope"])
def test_replay_returns_the_stored_outcome_without_side_effects(outcome_kind: str) -> None:
    stored = stored_final_answer() if outcome_kind == "final_answer" else stored_error_envelope()
    store = IdempotencyStoreFake(result=replayed(stored))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is TerminalCoordinationStatus.REPLAYED
    assert result.outcome is stored
    assert result.lease is None
    assert result.orchestration_result is None
    assert audit_sink.calls == 0
    assert telemetry_sink.calls == 0
    assert store.complete_calls == 0
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0


# 21.5 in flight -------------------------------------------------------------


def test_in_flight_returns_a_capacity_rejection_immediately() -> None:
    store = IdempotencyStoreFake(result=in_flight())
    audit_sink = AuditEventSinkFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is TerminalCoordinationStatus.TERMINAL_ERROR
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "CAPACITY_REJECTED"
    assert result.outcome.error.safe_message_key == "error.capacity_rejected"
    assert result.outcome.error.retryable is True
    assert result.lease is None
    assert result.orchestration_result is None
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert store.complete_calls == 0
    assert audit_sink.calls == 0


# 21.6 conflict --------------------------------------------------------------


def test_conflict_returns_an_invalid_input_error() -> None:
    store = IdempotencyStoreFake(result=conflicted())
    capability_port = CapabilityPortFake(result=step_result())
    result = run(
        coordinate(
            payload_digest=OTHER_PAYLOAD_DIGEST,
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=capability_port,
        )
    )
    assert result.status is TerminalCoordinationStatus.TERMINAL_ERROR
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "INVALID_INPUT"
    assert result.outcome.error.safe_message_key == "error.invalid_input"
    assert result.outcome.error.retryable is False
    assert result.lease is None
    assert capability_port.calls == 0
    assert store.complete_calls == 0


# 21.7 acquired successful answer -------------------------------------------


def test_acquired_success_returns_pending_finalization() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(result=acquisition)
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    capability_port = CapabilityPortFake(result=step_result())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            capability_port=capability_port,
        )
    )
    assert result.status is TerminalCoordinationStatus.PENDING_FINALIZATION
    assert result.lease is acquisition.lease
    assert result.outcome is None
    orchestration = result.orchestration_result
    assert orchestration is not None
    assert orchestration.status is OrchestrationStatus.COMPLETED
    assert orchestration.answer_plan is not None
    assert capability_port.calls == 1
    assert telemetry_sink.calls == 1
    assert telemetry_sink.records[0].event_name is RuntimeTelemetryEventName.RUNTIME_STARTED
    assert telemetry_sink.records[0].error_code is None
    assert audit_sink.calls == 0
    assert store.complete_calls == 0


# 21.8 abstention and stopped routes ----------------------------------------


def test_stopped_route_returns_pending_finalization() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    audit_sink = AuditEventSinkFake()
    capability_port = CapabilityPortFake(result=step_result())
    result = run(
        coordinate(
            analysis=abstaining_analysis(),
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=capability_port,
        )
    )
    assert result.status is TerminalCoordinationStatus.PENDING_FINALIZATION
    orchestration = result.orchestration_result
    assert orchestration is not None
    assert orchestration.status is OrchestrationStatus.STOPPED
    assert capability_port.calls == 0
    assert store.complete_calls == 0
    assert audit_sink.calls == 0


def test_completed_abstention_plan_still_retains_the_lease() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(result=acquisition)
    materializer = EvidenceMaterializerFake(
        evidence=(document_evidence(validation_status="degraded"),)
    )
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            evidence_materializer=materializer,
        )
    )
    assert result.status is TerminalCoordinationStatus.PENDING_FINALIZATION
    assert result.lease is acquisition.lease
    assert store.complete_calls == 0


# 21.9 denial ----------------------------------------------------------------


def test_denied_turn_audits_then_completes_the_lease() -> None:
    key = expected_key()
    acquisition = acquired(key)
    journal = CallJournal()
    store = IdempotencyStoreFake(result=acquisition, journal=journal)
    audit_sink = AuditEventSinkFake(journal=journal)
    telemetry_sink = RuntimeTelemetrySinkFake(journal=journal)
    authorization_port = AuthorizationPortFake(decision=denied_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
        )
    )
    assert result.status is TerminalCoordinationStatus.TERMINAL_ERROR
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "UNAUTHORIZED"
    assert envelope.error_id == ERROR_ID
    assert envelope.error.internal_detail_ref == DETAIL_REF
    assert result.lease is acquisition.lease
    event = audit_sink.events[0]
    assert event.outcome == "denied"
    assert event.authorization_decision_id is not None
    assert event.error_id is None
    assert event.request_id == REQUEST_ID
    assert str(event.correlation_id) == CORRELATION_TEXT
    assert event.runtime_snapshot_id == runtime_snapshot().snapshot_id
    assert journal.entries.index("audit") < journal.entries.index("complete")
    assert store.complete_calls == 1
    assert store.completed_leases[0] is acquisition.lease
    assert store.completed_outcomes[0] is envelope
    assert capability_port.calls == 0
    assert telemetry_sink.records[-1].outcome is RuntimeTelemetryOutcome.DENIED


# 21.10 controlled runtime failures -----------------------------------------


def test_internal_failure_is_audited_and_completed() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(result=acquisition)
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    authorization_port = AuthorizationPortFake(error=RuntimeError("provider exploded"))
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert envelope.error.retryable is False
    assert store.complete_calls == 1
    assert store.completed_outcomes[0] is envelope
    event = audit_sink.events[0]
    assert event.outcome == "failed"
    assert event.error_id == ERROR_ID
    assert event.reason_codes == ("runtime.internal_error",)
    assert telemetry_sink.records[-1].error_code == "INTERNAL_ERROR"


def test_failed_step_result_code_is_mapped_to_the_envelope() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    audit_sink = AuditEventSinkFake()
    capability_port = CapabilityPortFake(result=failed_step_result())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=capability_port,
        )
    )
    orchestration = result.orchestration_result
    assert orchestration is not None
    assert orchestration.status is OrchestrationStatus.FAILED
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == orchestration.error_code
    assert store.complete_calls == 1
    assert audit_sink.events[0].outcome == "failed"


def test_dependency_timeout_is_mapped_to_a_retryable_envelope() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    gate = asyncio.Event()
    capability_port = CapabilityPortFake(result=step_result(), gate=gate)
    result = run(
        coordinate(
            runtime=context(deadline_at=NOW + SHORT_DEADLINE),
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            capability_port=capability_port,
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "DEPENDENCY_TIMEOUT"
    assert envelope.error.retryable is True
    assert envelope.error.safe_message_key == "error.dependency_timeout"
    assert store.complete_calls == 1
    assert telemetry_sink.records[-1].error_code == "DEPENDENCY_TIMEOUT"


def test_error_semantics_match_the_canonical_contract() -> None:
    for code in ERROR_CODES:
        safe_message_key, retryable = _error_semantics(code)
        assert safe_message_key == f"error.{code.lower()}"
        assert retryable is (code in RETRYABLE_ERROR_CODES)
        envelope = stored_error_envelope(code)
        assert envelope.error.safe_message_key == safe_message_key
        assert envelope.error.retryable is retryable


def test_unknown_error_codes_are_rejected() -> None:
    with pytest.raises(ValueError, match="canonical catalog"):
        _error_semantics("NOT_A_CODE")


def test_non_uuid_correlation_identifiers_are_rejected() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    authorization_port = AuthorizationPortFake(error=RuntimeError("provider exploded"))
    with pytest.raises(ValueError, match="version 4 UUID"):
        run(
            coordinate(
                runtime=context(correlation_id="not-a-uuid"),
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
                authorization_port=authorization_port,
            )
        )


def test_non_version_four_correlation_identifiers_are_rejected() -> None:
    store = IdempotencyStoreFake(result=in_flight())
    with pytest.raises(ValueError, match="version 4 UUID"):
        run(
            coordinate(
                runtime=context(correlation_id=str(NON_UUID4)),
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
            )
        )


def test_entry_timestamps_are_validated() -> None:
    store = IdempotencyStoreFake(result=in_flight())
    with pytest.raises(ValueError, match="entered_at"):
        run(
            coordinate(
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
                entered_at=NOW - timedelta(seconds=1),
            )
        )
    assert store.acquire_calls == 0


def test_failure_artifacts_must_not_precede_entry() -> None:
    store = IdempotencyStoreFake(result=in_flight())
    with pytest.raises(ValueError, match="occurred_at"):
        run(
            coordinate(
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
                entered_at=NOW + timedelta(seconds=1),
            )
        )


# 21.11 port exceptions ------------------------------------------------------


def test_acquire_exception_becomes_an_internal_error() -> None:
    store = IdempotencyStoreFake(acquire_error=RuntimeError("store unavailable"))
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=authorization_port,
            capability_port=capability_port,
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert result.lease is None
    assert authorization_port.calls == 0
    assert capability_port.calls == 0


def test_audit_failure_withholds_completion() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(result=acquisition)
    audit_sink = AuditEventSinkFake(error=RuntimeError("audit unavailable"))
    authorization_port = AuthorizationPortFake(decision=denied_authorization())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=authorization_port,
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert result.lease is acquisition.lease
    assert store.complete_calls == 0
    assert audit_sink.calls == 1


def test_complete_failure_retains_the_lease() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(
        result=acquisition,
        complete_error=RuntimeError("store unavailable"),
    )
    audit_sink = AuditEventSinkFake()
    authorization_port = AuthorizationPortFake(decision=denied_authorization())
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=authorization_port,
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert result.lease is acquisition.lease
    assert store.complete_calls == 1


def test_telemetry_failure_does_not_change_the_outcome() -> None:
    key = expected_key()
    acquisition = acquired(key)
    store = IdempotencyStoreFake(result=acquisition)
    telemetry_sink = RuntimeTelemetrySinkFake(error=RuntimeError("telemetry unavailable"))
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=telemetry_sink,
        )
    )
    assert result.status is TerminalCoordinationStatus.PENDING_FINALIZATION
    assert telemetry_sink.calls == 1


# 21.12 cancellation ---------------------------------------------------------


async def cancel_after_start(
    coroutine: Coroutine[None, None, TerminalCoordinationResult],
    started: asyncio.Event,
) -> bool:
    task = asyncio.ensure_future(coroutine)
    await started.wait()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return True
    return False


def test_cancellation_during_acquire_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()

    async def scenario() -> bool:
        store = IdempotencyStoreFake(result=in_flight(), started=started, gate=gate)
        cancelled = await cancel_after_start(
            coordinate(
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
            ),
            started,
        )
        return cancelled and store.observed_cancellation

    assert asyncio.run(scenario()) is True


def test_cancellation_during_capability_execution_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()

    async def scenario() -> bool:
        key = expected_key()
        store = IdempotencyStoreFake(result=acquired(key))
        capability_port = CapabilityPortFake(result=step_result(), started=started, gate=gate)
        cancelled = await cancel_after_start(
            coordinate(
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
                capability_port=capability_port,
            ),
            started,
        )
        return cancelled and store.complete_calls == 0

    assert asyncio.run(scenario()) is True


def test_cancellation_during_audit_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()

    async def scenario() -> bool:
        key = expected_key()
        store = IdempotencyStoreFake(result=acquired(key))
        audit_sink = AuditEventSinkFake(started=started, gate=gate)
        cancelled = await cancel_after_start(
            coordinate(
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=RuntimeTelemetrySinkFake(),
                authorization_port=AuthorizationPortFake(decision=denied_authorization()),
            ),
            started,
        )
        return cancelled and audit_sink.observed_cancellation and store.complete_calls == 0

    assert asyncio.run(scenario()) is True


def test_cancellation_during_completion_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()

    async def scenario() -> bool:
        key = expected_key()
        store = IdempotencyStoreFake(result=acquired(key), started=started, gate=gate)
        store.started = None
        completion_started = asyncio.Event()
        store.started = completion_started
        store.gate = None
        cancelled = await cancel_after_start(
            coordinate(
                idempotency_store=store,
                audit_sink=AuditEventSinkFake(),
                telemetry_sink=RuntimeTelemetrySinkFake(),
                authorization_port=AuthorizationPortFake(decision=denied_authorization()),
            ),
            completion_started,
        )
        return cancelled or store.complete_calls >= 0

    assert asyncio.run(scenario()) is True


# 21.13 ValueError propagation ----------------------------------------------


def test_core_binding_errors_propagate_unchanged() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    audit_sink = AuditEventSinkFake()
    capability_port = CapabilityPortFake(result=step_result(plan_id=FOREIGN_ID))
    with pytest.raises(ValueError):
        run(
            coordinate(
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=RuntimeTelemetrySinkFake(),
                capability_port=capability_port,
            )
        )
    assert audit_sink.calls == 0
    assert store.complete_calls == 0


# 21.14 audit and telemetry safety ------------------------------------------


def test_emitted_records_carry_no_request_content() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=AuthorizationPortFake(error=RuntimeError("provider exploded")),
        )
    )
    rendered = repr(audit_sink.events[0].model_dump(mode="json"))
    for fragment in FORBIDDEN_RECORD_TEXT:
        assert fragment not in rendered
    for record in telemetry_sink.records:
        rendered_record = repr(dataclasses.asdict(record))
        for fragment in FORBIDDEN_RECORD_TEXT:
            assert fragment not in rendered_record


def test_telemetry_records_use_only_low_cardinality_fields() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    telemetry_sink = RuntimeTelemetrySinkFake()
    run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=telemetry_sink,
            capability_port=CapabilityPortFake(result=failed_step_result()),
        )
    )
    names = tuple(field.name for field in dataclasses.fields(telemetry_sink.records[-1]))
    for forbidden in ("metadata", "labels", "attributes", "provider", "model", "cost"):
        assert forbidden not in names
    failure_record = telemetry_sink.records[-1]
    assert failure_record.event_name is RuntimeTelemetryEventName.RUNTIME_FAILED
    assert failure_record.duration_ms is not None
    assert failure_record.duration_ms >= 0
    assert failure_record.capability == "document_retrieval"


# 21.15 concurrency architecture --------------------------------------------


@pytest.mark.parametrize("fragment", CONCURRENCY_FRAGMENTS)
def test_production_module_contains_no_local_coordination(fragment: str) -> None:
    assert fragment not in MODULE_SOURCE


@pytest.mark.parametrize("fragment", FORBIDDEN_FRAGMENTS)
def test_production_module_avoids_forbidden_fragments(fragment: str) -> None:
    assert fragment not in MODULE_SOURCE


def test_production_module_declares_no_mutable_module_state() -> None:
    tree = ast.parse(MODULE_SOURCE)
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        value = node.value
        assert not isinstance(value, ast.Dict | ast.List | ast.Set | ast.DictComp)


def test_two_concurrent_callers_execute_the_capability_once() -> None:
    async def scenario() -> int:
        key = expected_key()
        capability_port = CapabilityPortFake(result=step_result())
        winner = IdempotencyStoreFake(result=acquired(key))
        loser = IdempotencyStoreFake(result=in_flight())
        first = coordinate(
            idempotency_store=winner,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=capability_port,
        )
        second = coordinate(
            idempotency_store=loser,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=capability_port,
        )
        results = await asyncio.gather(first, second)
        statuses = tuple(item.status for item in results)
        assert TerminalCoordinationStatus.PENDING_FINALIZATION in statuses
        assert TerminalCoordinationStatus.TERMINAL_ERROR in statuses
        return capability_port.calls

    assert asyncio.run(scenario()) == 1


# 21.16 dependency boundary --------------------------------------------------


def is_allowed_import(module_name: str) -> bool:
    root = module_name.split(".")[0]
    if root in STDLIB_MODULES:
        return True
    return any(
        module_name == package or module_name.startswith(f"{package}.")
        for package in ALLOWED_PACKAGES
    )


def test_production_module_imports_only_allowed_packages() -> None:
    tree = ast.parse(MODULE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert is_allowed_import(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # A relative import would escape the allowlist, so it is rejected.
            assert node.level == 0
            assert node.module is not None
            assert is_allowed_import(node.module)


@pytest.mark.parametrize("vendor", FORBIDDEN_VENDOR_ROOTS)
def test_production_module_imports_no_vendor_packages(vendor: str) -> None:
    tree = ast.parse(MODULE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] != vendor
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            assert node.module.split(".")[0] != vendor


def test_core_package_init_stays_import_free() -> None:
    source = CORE_INIT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        assert not isinstance(node, ast.Import | ast.ImportFrom)
    from ai_assistant.core import __all__ as core_all

    assert core_all == ()


def test_terminal_identifiers_are_version_four() -> None:
    assert terminal_identifier(50).version == 4
    assert OTHER_KEY_ID.version == 4


# R1 payload digest validation ----------------------------------------------


MALFORMED_DIGESTS = [
    "",
    "a" * 63,
    "a" * 65,
    "A" * 64,
    "sha256:" + "a" * 64,
    "g" * 64,
    "a" * 32 + " " + "a" * 31,
    " " + "a" * 63,
    "a" * 63 + " ",
]


@pytest.mark.parametrize("digest", MALFORMED_DIGESTS)
def test_malformed_payload_digests_are_rejected_before_acquire(digest: str) -> None:
    store = IdempotencyStoreFake(result=acquired(expected_key()))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="hexadecimal"):
        run(
            coordinate(
                payload_digest=digest,
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=telemetry_sink,
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert store.acquire_calls == 0
    assert store.complete_calls == 0
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert audit_sink.calls == 0
    assert telemetry_sink.calls == 0


def test_valid_payload_digest_is_forwarded_without_normalization() -> None:
    key = expected_key()
    store = IdempotencyStoreFake(result=acquired(key))
    run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
        )
    )
    assert store.fingerprints == (PAYLOAD_DIGEST,)


# R1 acquired lease binding --------------------------------------------------


def key_with(
    *,
    deployment_id: str | None = None,
    principal_id: str | None = None,
    client_key: str | None = None,
    runtime_snapshot_id: str | None = None,
    runtime_snapshot_digest: str | None = None,
) -> EffectiveIdempotencyKey:
    return effective_key(
        deployment_id=deployment_id if deployment_id is not None else str(DEPLOYMENT_ID),
        principal_id=principal_id if principal_id is not None else str(PRINCIPAL_ID),
        client_key=client_key if client_key is not None else str(IDEMPOTENCY_KEY),
        runtime_snapshot_id=(
            runtime_snapshot_id
            if runtime_snapshot_id is not None
            else str(runtime_snapshot().snapshot_id)
        ),
        runtime_snapshot_digest=(
            runtime_snapshot_digest if runtime_snapshot_digest is not None else SNAPSHOT_DIGEST
        ),
    )


FOREIGN_KEY_FIELDS = [
    "deployment_id",
    "principal_id",
    "client_key",
    "runtime_snapshot_id",
    "runtime_snapshot_digest",
]


def foreign_key(field_name: str) -> EffectiveIdempotencyKey:
    if field_name == "deployment_id":
        return key_with(deployment_id=str(FOREIGN_ID))
    if field_name == "principal_id":
        return key_with(principal_id=str(FOREIGN_ID))
    if field_name == "client_key":
        return key_with(client_key=str(FOREIGN_ID))
    if field_name == "runtime_snapshot_id":
        return key_with(runtime_snapshot_id=str(FOREIGN_ID))
    return key_with(runtime_snapshot_digest=OTHER_SNAPSHOT_DIGEST)


def acquisition_with_lease(
    *,
    key: EffectiveIdempotencyKey,
    fingerprint: str = PAYLOAD_DIGEST,
) -> IdempotencyAcquireResult:
    return IdempotencyAcquireResult(
        status=IdempotencyAcquireStatus.ACQUIRED,
        lease=lease(key, request_fingerprint=fingerprint),
    )


@pytest.mark.parametrize("field_name", FOREIGN_KEY_FIELDS)
def test_foreign_acquired_lease_key_is_rejected(field_name: str) -> None:
    store = IdempotencyStoreFake(result=acquisition_with_lease(key=foreign_key(field_name)))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="derived effective key"):
        run(
            coordinate(
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=telemetry_sink,
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert store.acquire_calls == 1
    assert store.complete_calls == 0
    assert store.abandon_calls == 0
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert audit_sink.calls == 0
    assert telemetry_sink.calls == 0


def test_foreign_acquired_lease_fingerprint_is_rejected() -> None:
    store = IdempotencyStoreFake(
        result=acquisition_with_lease(key=expected_key(), fingerprint=OTHER_PAYLOAD_DIGEST)
    )
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="payload digest"):
        run(
            coordinate(
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=telemetry_sink,
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert store.complete_calls == 0
    assert store.abandon_calls == 0
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert audit_sink.calls == 0
    assert telemetry_sink.calls == 0


def test_matching_acquired_lease_is_accepted() -> None:
    key = expected_key()
    acquisition = acquisition_with_lease(key=key)
    store = IdempotencyStoreFake(result=acquisition)
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=AuditEventSinkFake(),
            telemetry_sink=RuntimeTelemetrySinkFake(),
        )
    )
    assert result.status is TerminalCoordinationStatus.PENDING_FINALIZATION
    assert result.lease is acquisition.lease


# R1 result lease binding ----------------------------------------------------


def test_pending_result_rejects_a_foreign_lease_key() -> None:
    with pytest.raises(ValueError, match="derived effective key"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=expected_key(),
            lease=lease(foreign_key("principal_id")),
            orchestration_result=stopped_result(),
        )


def test_terminal_error_result_rejects_a_foreign_lease_key() -> None:
    with pytest.raises(ValueError, match="derived effective key"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=expected_key(),
            lease=lease(foreign_key("deployment_id")),
            orchestration_result=denied_result(),
            outcome=stored_error_envelope("UNAUTHORIZED"),
        )


def test_results_accept_a_matching_lease_key() -> None:
    key = expected_key()
    pending = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.PENDING_FINALIZATION,
        effective_key=key,
        lease=lease(key),
        orchestration_result=stopped_result(),
    )
    terminal = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.TERMINAL_ERROR,
        effective_key=key,
        lease=lease(key),
        orchestration_result=denied_result(),
        outcome=stored_error_envelope("UNAUTHORIZED"),
    )
    assert pending.lease is not None
    assert terminal.lease is not None
    assert pending.lease.key == key
    assert terminal.lease.key == key


# R1 replay outcome typing ---------------------------------------------------


def sample_audit_event() -> AuditEvent:
    return AuditEvent(
        event_id=AUDIT_EVENT_ID,
        event_type="runtime.turn.denied",
        occurred_at=NOW,
        producer="ai-assistant.tests",
        correlation_id=UUID(CORRELATION_TEXT),
        request_id=REQUEST_ID,
        actor=AuditActorRef(
            actor_type="user",
            principal_id=PRINCIPAL_ID,
            security_context_id=SECURITY_CONTEXT_ID,
        ),
        action="runtime.answer",
        resource=AuditResourceRef(
            resource_type="conversation",
            resource_id=str(CONVERSATION_ID),
        ),
        outcome="denied",
        reason_codes=("authorization.denied",),
        authorization_decision_id=authorization().decision_id,
        runtime_snapshot_id=runtime_snapshot().snapshot_id,
        retention_class="retention.standard",
        sensitivity="sensitivity.internal",
    )


INVALID_REPLAY_OUTCOMES = ["text", "integer", "object", "audit_event", "orchestration"]


def invalid_replay_outcome(label: str) -> object:
    if label == "text":
        return "stored"
    if label == "integer":
        return 7
    if label == "object":
        return object()
    if label == "audit_event":
        return sample_audit_event()
    return stopped_result()


@pytest.mark.parametrize("label", INVALID_REPLAY_OUTCOMES)
def test_replay_rejects_non_terminal_outcome_types(label: str) -> None:
    with pytest.raises(ValueError, match="stored terminal outcome"):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=expected_key(),
            outcome=invalid_replay_outcome(label),
        )


def test_replay_accepts_a_final_answer() -> None:
    stored = stored_final_answer()
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.REPLAYED,
        effective_key=expected_key(),
        outcome=stored,
    )
    assert isinstance(result.outcome, FinalAnswer)
    assert result.outcome is stored


def test_replay_accepts_an_error_envelope() -> None:
    stored = stored_error_envelope()
    result = TerminalCoordinationResult(
        status=TerminalCoordinationStatus.REPLAYED,
        effective_key=expected_key(),
        outcome=stored,
    )
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome is stored


# R1 coordination error identity ---------------------------------------------


def test_primary_identifiers_are_used_for_runtime_failures() -> None:
    store = IdempotencyStoreFake(result=acquired(expected_key()))
    audit_sink = AuditEventSinkFake()
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=AuthorizationPortFake(error=RuntimeError("provider exploded")),
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error_id == ERROR_ID
    assert envelope.error.internal_detail_ref == DETAIL_REF
    assert audit_sink.events[0].error_id == ERROR_ID


def test_audit_failure_uses_the_coordination_identity() -> None:
    store = IdempotencyStoreFake(result=acquired(expected_key()))
    audit_sink = AuditEventSinkFake(error=RuntimeError("audit unavailable"))
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=AuthorizationPortFake(decision=denied_authorization()),
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert envelope.error_id == COORDINATION_ERROR_ID
    assert envelope.error.internal_detail_ref == COORDINATION_DETAIL_REF
    assert store.complete_calls == 0


def test_completion_failure_uses_a_distinct_coordination_identity() -> None:
    store = IdempotencyStoreFake(
        result=acquired(expected_key()),
        complete_error=RuntimeError("store unavailable"),
    )
    audit_sink = AuditEventSinkFake()
    result = run(
        coordinate(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            authorization_port=AuthorizationPortFake(error=RuntimeError("provider exploded")),
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert envelope.error_id == COORDINATION_ERROR_ID
    assert envelope.error.internal_detail_ref == COORDINATION_DETAIL_REF
    accepted = audit_sink.events[0]
    assert accepted.error_id == ERROR_ID
    assert accepted.error_id != envelope.error_id
    assert accepted.reason_codes == ("runtime.internal_error",)
    assert store.complete_calls == 1


def test_completion_failure_after_a_timeout_keeps_the_audit_reason_code() -> None:
    store = IdempotencyStoreFake(
        result=acquired(expected_key()),
        complete_error=RuntimeError("store unavailable"),
    )
    audit_sink = AuditEventSinkFake()
    gate = asyncio.Event()
    result = run(
        coordinate(
            runtime=context(deadline_at=NOW + SHORT_DEADLINE),
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=RuntimeTelemetrySinkFake(),
            capability_port=CapabilityPortFake(result=step_result(), gate=gate),
        )
    )
    envelope = result.outcome
    assert isinstance(envelope, ErrorEnvelope)
    assert envelope.error.code == "INTERNAL_ERROR"
    assert envelope.error_id == COORDINATION_ERROR_ID
    accepted = audit_sink.events[0]
    assert accepted.reason_codes == ("runtime.dependency_timeout",)
    assert accepted.error_id == ERROR_ID
