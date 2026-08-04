"""Tests for the WS-004B bounded Walking Skeleton terminal closure."""

import ast
import asyncio
import sys
from collections.abc import Coroutine
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from support.walking_skeleton_closure_fakes import ReplayCapableIdempotencyStoreFake
from support.walking_skeleton_finalization_fakes import (
    AnswerRendererFake,
    CitationSourceResolverFake,
    faithful_draft,
    resolved_source,
)
from support.walking_skeleton_finalization_fakes import (
    artifacts as finalization_artifacts_for,
)
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    BUNDLE_ID,
    DEPLOYMENT_ID,
    IDEMPOTENCY_KEY,
    NOW,
    PLAN_ID,
    PRINCIPAL_ID,
    ROUTE_DECISION_ID,
    SNAPSHOT_DIGEST,
    SNAPSHOT_ID,
    answer_plan,
    authorization,
    document_evidence,
    query_analysis,
    runtime_context,
    step_result,
)
from support.walking_skeleton_runtime_fakes import (
    AuthorizationPortFake,
    CapabilityPortFake,
    EvidenceMaterializerFake,
    denied_authorization,
)
from support.walking_skeleton_terminal_fakes import (
    AuditEventSinkFake,
    CallJournal,
    RuntimeTelemetrySinkFake,
    effective_key,
    terminal_identifier,
)

import ai_assistant.core as core_package
from ai_assistant.contracts import (
    ErrorEnvelope,
    FinalAnswer,
    RuntimeSnapshot,
    RuntimeSnapshotIntegrity,
    SecurityPrincipalContext,
    TurnInput,
)
from ai_assistant.core.runtime import OrchestrationArtifacts, OrchestrationStatus
from ai_assistant.core.terminal_runtime import TerminalFailureArtifacts
from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    RuntimeContext,
    RuntimeTelemetryEventName,
    RuntimeTelemetryOutcome,
    RuntimeTelemetryRecord,
)
from ai_assistant.core.walking_skeleton import (
    TerminalCompletionArtifacts,
    WalkingSkeletonDisposition,
    WalkingSkeletonResult,
    run_idempotent_fast_document,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "walking_skeleton.py"
)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")
STDLIB_MODULES = frozenset(sys.stdlib_module_names)
ALLOWED_PACKAGES = ("ai_assistant.contracts", "ai_assistant.core")
FORBIDDEN_FRAGMENTS = (
    "Any",
    "cast(",
    "type: ignore",
    "noqa",
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
    "sentinel-raw-message",
    "normalized query",
    "prompt",
    "traceback",
    "secret",
    "token",
    "Document store",
    "store:main",
    "locator:1",
)

PAYLOAD_DIGEST = "a" * 64
OTHER_PAYLOAD_DIGEST = "c" * 64
FINALIZATION_ENTERED_AT = NOW

ORCHESTRATION_ARTIFACTS = OrchestrationArtifacts(
    route_decision_id=ROUTE_DECISION_ID,
    route_decided_at=NOW,
    execution_plan_id=PLAN_ID,
    execution_plan_planned_at=NOW,
    evidence_bundle_id=BUNDLE_ID,
    evidence_bundle_built_at=NOW,
    answer_plan_id=ANSWER_PLAN_ID,
    answer_plan_built_at=NOW,
)

TERMINAL_FAILURE_ARTIFACTS = TerminalFailureArtifacts(
    error_id=terminal_identifier(40),
    internal_detail_ref=terminal_identifier(41),
    coordination_error_id=terminal_identifier(45),
    coordination_internal_detail_ref=terminal_identifier(46),
    audit_event_id=terminal_identifier(42),
    occurred_at=NOW,
    telemetry_recorded_at=NOW + timedelta(milliseconds=1),
)

FINALIZATION_ARTIFACTS = finalization_artifacts_for()


def completion_identifier(index: int) -> UUID:
    """Return a deterministic version 4 UUID reserved for closure tests."""
    return UUID(f"{index:08d}-0000-4000-8000-000000000000")


AUDIT_EVENT_ID = completion_identifier(70)
STOPPED_ERROR_ID = completion_identifier(71)
STOPPED_DETAIL_REF = completion_identifier(72)
FINALIZATION_ERROR_ID = completion_identifier(73)
COORDINATION_ERROR_ID = completion_identifier(74)
COORDINATION_DETAIL_REF = completion_identifier(75)
NON_UUID4 = UUID("00000076-0000-1000-8000-000000000000")


def completion_artifacts(
    *,
    audit_event_id: UUID = AUDIT_EVENT_ID,
    stopped_error_id: UUID = STOPPED_ERROR_ID,
    stopped_internal_detail_ref: UUID = STOPPED_DETAIL_REF,
    finalization_error_id: UUID = FINALIZATION_ERROR_ID,
    coordination_error_id: UUID = COORDINATION_ERROR_ID,
    coordination_internal_detail_ref: UUID = COORDINATION_DETAIL_REF,
    occurred_at: datetime = NOW + timedelta(milliseconds=4),
    telemetry_recorded_at: datetime = NOW + timedelta(milliseconds=6),
) -> TerminalCompletionArtifacts:
    return TerminalCompletionArtifacts(
        audit_event_id=audit_event_id,
        stopped_error_id=stopped_error_id,
        stopped_internal_detail_ref=stopped_internal_detail_ref,
        finalization_error_id=finalization_error_id,
        coordination_error_id=coordination_error_id,
        coordination_internal_detail_ref=coordination_internal_detail_ref,
        occurred_at=occurred_at,
        telemetry_recorded_at=telemetry_recorded_at,
    )


def expected_key() -> EffectiveIdempotencyKey:
    return effective_key(
        deployment_id=str(DEPLOYMENT_ID),
        principal_id=str(PRINCIPAL_ID),
        client_key=str(IDEMPOTENCY_KEY),
        runtime_snapshot_id=str(runtime_context().runtime_snapshot.snapshot_id),
        runtime_snapshot_digest=SNAPSHOT_DIGEST,
    )


def run_environment(
    *,
    context_obj: RuntimeContext | None = None,
    analysis=None,
    payload_digest: str = PAYLOAD_DIGEST,
    idempotency_store: ReplayCapableIdempotencyStoreFake | None = None,
    audit_sink: AuditEventSinkFake | None = None,
    telemetry_sink: RuntimeTelemetrySinkFake | None = None,
    authorization_port: AuthorizationPortFake | None = None,
    capability_port: CapabilityPortFake | None = None,
    evidence_materializer: EvidenceMaterializerFake | None = None,
    renderer: AnswerRendererFake | None = None,
    citation_source_resolver: CitationSourceResolverFake | None = None,
    completion: TerminalCompletionArtifacts | None = None,
    finalization_artifacts=None,
    entered_at: datetime = NOW,
    finalization_entered_at: datetime = FINALIZATION_ENTERED_AT,
    generation_mode: str = "deterministic_template",
):
    plan = answer_plan()
    return run_idempotent_fast_document(
        context_obj if context_obj is not None else runtime_context(),
        analysis if analysis is not None else query_analysis(),
        payload_digest=payload_digest,
        idempotency_store=(
            idempotency_store
            if idempotency_store is not None
            else ReplayCapableIdempotencyStoreFake()
        ),
        audit_sink=audit_sink if audit_sink is not None else AuditEventSinkFake(),
        telemetry_sink=(
            telemetry_sink if telemetry_sink is not None else RuntimeTelemetrySinkFake()
        ),
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
            else EvidenceMaterializerFake(evidence=(document_evidence(),))
        ),
        renderer=(
            renderer if renderer is not None else AnswerRendererFake(draft=faithful_draft(plan))
        ),
        citation_source_resolver=(
            citation_source_resolver
            if citation_source_resolver is not None
            else CitationSourceResolverFake(sources=(resolved_source(),))
        ),
        orchestration_artifacts=ORCHESTRATION_ARTIFACTS,
        terminal_failure_artifacts=TERMINAL_FAILURE_ARTIFACTS,
        finalization_artifacts=(
            finalization_artifacts if finalization_artifacts is not None else FINALIZATION_ARTIFACTS
        ),
        completion_artifacts=completion if completion is not None else completion_artifacts(),
        entered_at=entered_at,
        finalization_entered_at=finalization_entered_at,
        generation_mode=generation_mode,
    )


def run(coroutine: Coroutine[object, object, WalkingSkeletonResult]) -> WalkingSkeletonResult:
    return asyncio.run(coroutine)


class _BlockingTelemetrySinkFake:
    """A blocking RuntimeTelemetrySink double, local to this test module.

    Defined here, rather than by extending the shared
    support.walking_skeleton_terminal_fakes.RuntimeTelemetrySinkFake (which is
    owned by WS-003B/WS-004A and out of this revision's authorized scope), so
    that R1-05's cancellation-during-terminal-telemetry proof does not require
    touching a file outside the four this revision is scoped to.

    Only the terminal telemetry call (the second emit call for a stored
    outcome: coordinate_idempotent_fast_document's own runtime_started record
    is emitted first, before orchestration even begins) blocks on the gate;
    blocking that earlier record would prevent audit/completion from ever
    running and would not exercise cancellation "during terminal telemetry"
    as required.
    """

    def __init__(
        self,
        *,
        journal: CallJournal | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
        block_from_call: int = 2,
    ) -> None:
        self._journal = journal
        self._started = started
        self._gate = gate
        self._block_from_call = block_from_call
        self.calls = 0
        self.records: tuple[RuntimeTelemetryRecord, ...] = ()
        self.observed_cancellation = False

    async def emit(self, record: RuntimeTelemetryRecord) -> None:
        self.calls += 1
        self.records = (*self.records, record)
        if self.calls < self._block_from_call:
            return
        if self._journal is not None:
            self._journal.record("telemetry")
        if self._started is not None:
            self._started.set()
        if self._gate is not None:
            try:
                await self._gate.wait()
            except asyncio.CancelledError:
                self.observed_cancellation = True
                raise


# 1. result and artifact invariants ------------------------------------------


def test_walking_skeleton_result_is_frozen_and_slotted() -> None:
    assert WalkingSkeletonResult.__dataclass_params__.frozen is True
    assert WalkingSkeletonResult.__slots__ == (
        "disposition",
        "effective_key",
        "outcome",
        "lease",
        "orchestration_result",
    )


def test_terminal_completion_artifacts_is_frozen_and_slotted() -> None:
    assert TerminalCompletionArtifacts.__dataclass_params__.frozen is True
    instance = completion_artifacts()
    with pytest.raises(FrozenInstanceError):
        instance.audit_event_id = instance.audit_event_id


def test_disposition_enum_is_closed() -> None:
    assert {member.value for member in WalkingSkeletonDisposition} == {
        "replayed",
        "passthrough",
        "stored",
        "withheld",
    }


def test_completion_artifacts_rejects_non_uuid4() -> None:

    with pytest.raises(ValueError):
        completion_artifacts(audit_event_id=NON_UUID4)


def test_completion_artifacts_rejects_colliding_identifiers() -> None:

    with pytest.raises(ValueError):
        completion_artifacts(stopped_error_id=AUDIT_EVENT_ID)


def test_completion_artifacts_rejects_naive_timestamps() -> None:

    with pytest.raises(ValueError):
        completion_artifacts(occurred_at=datetime(2026, 1, 1, 12, 0))


def test_completion_artifacts_rejects_telemetry_before_occurred() -> None:

    with pytest.raises(ValueError):
        completion_artifacts(
            occurred_at=NOW + timedelta(milliseconds=10),
            telemetry_recorded_at=NOW,
        )


def test_completion_artifacts_rejects_collision_with_finalization_artifacts() -> None:

    with pytest.raises(ValueError):
        run(
            run_environment(
                completion=completion_artifacts(
                    audit_event_id=FINALIZATION_ARTIFACTS.final_answer_id
                )
            )
        )


def test_completion_artifacts_rejects_collision_with_terminal_failure_artifacts() -> None:

    with pytest.raises(ValueError):
        run(
            run_environment(
                completion=completion_artifacts(audit_event_id=TERMINAL_FAILURE_ARTIFACTS.error_id)
            )
        )


def test_entered_at_must_be_timezone_aware() -> None:

    with pytest.raises(ValueError):
        run(run_environment(entered_at=datetime(2026, 1, 1, 12, 0)))


def test_finalization_entered_at_must_not_precede_entered_at() -> None:

    with pytest.raises(ValueError):
        run(
            run_environment(
                entered_at=NOW,
                finalization_entered_at=NOW - timedelta(milliseconds=1),
            )
        )


def test_completion_occurred_at_must_not_precede_finalization_entered_at() -> None:

    with pytest.raises(ValueError):
        run(
            run_environment(
                finalization_entered_at=NOW + timedelta(milliseconds=10),
                completion=completion_artifacts(occurred_at=NOW + timedelta(milliseconds=1)),
            )
        )


# 2. full answered flow -------------------------------------------------------


def test_full_answered_flow_sequence_and_result_shape() -> None:
    journal = CallJournal()
    store = ReplayCapableIdempotencyStoreFake(journal=journal)
    audit_sink = AuditEventSinkFake(journal=journal)
    telemetry_sink = RuntimeTelemetrySinkFake(journal=journal)
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(document_evidence(),))
    plan = answer_plan()
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))

    result = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, FinalAnswer)
    assert result.outcome.outcome == "answered"
    assert result.lease is not None
    assert result.orchestration_result is not None
    assert result.lease.key == result.effective_key

    assert authorization_port.calls == 1
    assert capability_port.calls == 1
    assert materializer.calls == 1
    assert renderer.calls == 1
    assert resolver.calls == 1
    assert audit_sink.calls == 1
    assert len(store.complete_calls) == 1
    assert len(store.abandon_calls) == 0

    assert audit_sink.events[0].outcome == "success"
    assert audit_sink.events[0].reason_codes == ()
    assert audit_sink.events[0].error_id is None

    completed_outcomes = store.stored_outcome(result.effective_key)
    assert completed_outcomes is result.outcome

    # R1-02: prove the actual terminal closure ordering using one shared
    # journal across the audit sink, the idempotency fake's own completion
    # call, and the telemetry sink, rather than a fragile full-runtime event
    # list (coordinator telemetry, e.g. runtime_started, happens earlier and
    # is deliberately excluded by asserting only the ordered terminal suffix
    # starting at the first "audit" entry).
    audit_index = journal.entries.index("audit")
    assert journal.entries[audit_index:] == ("audit", "complete", "telemetry")

    telemetry_names = tuple(record.event_name for record in telemetry_sink.records)
    assert RuntimeTelemetryEventName.RUNTIME_COMPLETED in telemetry_names
    completed_record = telemetry_sink.records[-1]
    assert completed_record.outcome == RuntimeTelemetryOutcome.ANSWERED
    assert completed_record.error_code is None


# 3. abstained flow ------------------------------------------------------------


def test_abstained_final_answer_closes_as_success() -> None:
    from support.walking_skeleton_finalization_fakes import planned_answer

    # ORCHESTRATION_ARTIFACTS fixes answer_plan_id to ANSWER_PLAN_ID regardless
    # of decision, since the id comes from the artifacts fixture, not the
    # evidence decision; match that exact id here so the draft realizes the
    # actual plan the real orchestration builds.
    abstain_plan = planned_answer(decision="abstain", answer_plan_id=ANSWER_PLAN_ID)
    draft = faithful_draft(abstain_plan)
    renderer = AnswerRendererFake(draft=draft)
    audit_sink = AuditEventSinkFake()

    # An evidence item that materializes but fails validation drives the real
    # WS-002 orchestration to a completed, abstain-decision evidence bundle
    # (the same pattern proven by test_core_runtime.py's
    # test_unacceptable_evidence_completes_as_an_abstention).
    materializer = EvidenceMaterializerFake(
        evidence=(document_evidence(validation_status="degraded"),)
    )

    result = run(
        run_environment(
            evidence_materializer=materializer,
            renderer=renderer,
            audit_sink=audit_sink,
            finalization_artifacts=finalization_artifacts_for(citation_ids=()),
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, FinalAnswer)
    assert result.outcome.outcome == "abstained"
    assert audit_sink.events[0].outcome == "success"
    assert audit_sink.events[0].reason_codes == ("runtime.abstained",)
    assert audit_sink.events[0].error_id is None


# 4. STOPPED clarify / abstain --------------------------------------------------


def _stopped_authorization_port() -> AuthorizationPortFake:
    return AuthorizationPortFake(decision=authorization())


def test_stopped_clarify_maps_to_ambiguous_request() -> None:
    renderer = AnswerRendererFake(draft=None)
    resolver = CitationSourceResolverFake()
    audit_sink = AuditEventSinkFake()
    store = ReplayCapableIdempotencyStoreFake()

    analysis = query_analysis(ambiguity_level="blocking", ambiguity_codes=("query.ambiguous",))

    result = run(
        run_environment(
            analysis=analysis,
            renderer=renderer,
            citation_source_resolver=resolver,
            audit_sink=audit_sink,
            idempotency_store=store,
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "AMBIGUOUS_REQUEST"
    assert renderer.calls == 0
    assert resolver.calls == 0
    assert audit_sink.events[0].outcome == "failed"
    assert audit_sink.events[0].error_id == STOPPED_ERROR_ID
    assert len(store.complete_calls) == 1


def test_stopped_abstain_maps_to_no_evidence() -> None:
    renderer = AnswerRendererFake(draft=None)
    resolver = CitationSourceResolverFake()
    audit_sink = AuditEventSinkFake()
    store = ReplayCapableIdempotencyStoreFake()
    materializer = EvidenceMaterializerFake(evidence=())
    capability_port = CapabilityPortFake(result=step_result())

    # R1-03: an analytics intent deterministically fails the real router's
    # fast-lane shape check (src/ai_assistant/core/routing.py:
    # _is_supported_fast_shape requires intent == "factual") and, because
    # ambiguity_level stays the default "none", the router deterministically
    # resolves this to the pre-plan abstain terminal lane
    # (ABSTAIN_ROUTE = "abstain.unsupported_flow") rather than the clarify
    # lane. This is a single deterministic outcome, not one of two legitimate
    # closures: the orchestrator stops immediately after routing, before any
    # ExecutionPlan, EvidenceBundle, or AnswerPlan is ever built, and before
    # the capability port, evidence materializer, renderer, or citation
    # resolver are ever invoked.
    analysis = query_analysis(intent="analytics")

    result = run(
        run_environment(
            analysis=analysis,
            evidence_materializer=materializer,
            capability_port=capability_port,
            renderer=renderer,
            citation_source_resolver=resolver,
            audit_sink=audit_sink,
            idempotency_store=store,
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "NO_EVIDENCE"

    # R2-03: prove this genuinely came from a pre-plan STOPPED orchestration on
    # the abstain route, not merely that the terminal envelope happens to carry
    # the right error code.
    orchestration_result = result.orchestration_result
    assert orchestration_result is not None
    assert orchestration_result.status is OrchestrationStatus.STOPPED
    assert orchestration_result.route_decision is not None
    assert orchestration_result.route_decision.lane == "abstain"
    assert orchestration_result.execution_plan is None
    assert orchestration_result.step_result is None
    assert orchestration_result.evidence_bundle is None
    assert orchestration_result.answer_plan is None

    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert renderer.calls == 0
    assert resolver.calls == 0
    assert audit_sink.calls == 1
    assert audit_sink.events[0].outcome == "failed"
    assert audit_sink.events[0].error_id == STOPPED_ERROR_ID
    assert len(store.complete_calls) == 1


# 4b. real failed FinalAnswer flow (R1-04) ---------------------------------------


def test_failed_final_answer_flow_stores_and_replays_exact_object() -> None:
    journal = CallJournal()
    store = ReplayCapableIdempotencyStoreFake(journal=journal)
    audit_sink = AuditEventSinkFake(journal=journal)
    telemetry_sink = RuntimeTelemetrySinkFake(journal=journal)
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(document_evidence(),))
    # R1-04: the canonical finalizer failure mechanism. An ordinary renderer
    # exception (not ValueError, not CancelledError) is swallowed by
    # finalize_pending_answer's _render helper
    # (src/ai_assistant/core/finalization.py) and mapped to a safe,
    # INTERNAL_ERROR FinalAnswer(outcome="failed") via _failed_answer, bound
    # to the real turn artifacts. No invalid artifact is constructed by hand.
    renderer = AnswerRendererFake(error=RuntimeError("renderer backend unavailable"))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))

    result = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, FinalAnswer)
    assert result.outcome.outcome == "failed"
    safe_error = result.outcome.safe_error
    assert safe_error is not None
    assert safe_error.code == "INTERNAL_ERROR"

    assert audit_sink.calls == 1
    assert audit_sink.events[0].event_type == "runtime.turn.failed"
    assert audit_sink.events[0].outcome == "failed"
    assert audit_sink.events[0].error_id == FINALIZATION_ERROR_ID
    assert audit_sink.events[0].internal_detail_ref == safe_error.internal_detail_ref

    telemetry_names = tuple(record.event_name for record in telemetry_sink.records)
    assert RuntimeTelemetryEventName.RUNTIME_FAILED in telemetry_names
    failed_record = telemetry_sink.records[-1]
    assert failed_record.outcome == RuntimeTelemetryOutcome.FAILED
    assert failed_record.error_code == "INTERNAL_ERROR"

    # The internal detail reference stays server-side: it is bound onto the
    # safe error and the audit event, never rendered as message/code text.
    assert safe_error.internal_detail_ref == FINALIZATION_ARTIFACTS.failure_internal_detail_ref

    stored = store.stored_outcome(result.effective_key)
    assert stored is result.outcome

    audit_index = journal.entries.index("audit")
    assert journal.entries[audit_index:] == ("audit", "complete", "telemetry")

    before_authorization_calls = authorization_port.calls
    before_capability_calls = capability_port.calls
    before_materializer_calls = materializer.calls
    before_renderer_calls = renderer.calls
    before_resolver_calls = resolver.calls
    before_audit_calls = audit_sink.calls
    before_complete_calls = len(store.complete_calls)

    replay = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )

    assert replay.disposition is WalkingSkeletonDisposition.REPLAYED
    assert replay.outcome is result.outcome
    assert authorization_port.calls == before_authorization_calls
    assert capability_port.calls == before_capability_calls
    assert materializer.calls == before_materializer_calls
    assert renderer.calls == before_renderer_calls
    assert resolver.calls == before_resolver_calls
    assert audit_sink.calls == before_audit_calls
    assert len(store.complete_calls) == before_complete_calls


# 5. replay --------------------------------------------------------------------


def test_replay_returns_identical_stored_object_with_no_downstream_calls() -> None:
    store = ReplayCapableIdempotencyStoreFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(document_evidence(),))
    plan = answer_plan()
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()

    first = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )
    assert first.disposition is WalkingSkeletonDisposition.STORED

    second = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )

    assert second.disposition is WalkingSkeletonDisposition.REPLAYED
    assert second.outcome is first.outcome
    assert second.lease is None
    assert second.orchestration_result is None
    assert authorization_port.calls == 1
    assert capability_port.calls == 1
    assert materializer.calls == 1
    assert renderer.calls == 1
    assert resolver.calls == 1
    assert audit_sink.calls == 1
    assert len(store.complete_calls) == 1


def test_effective_key_isolation_across_client_keys() -> None:
    store = ReplayCapableIdempotencyStoreFake()
    plan = answer_plan()

    def env(idempotency_key: UUID) -> Coroutine[object, object, WalkingSkeletonResult]:
        context_obj = runtime_context()
        # TurnInput is a Pydantic contract model, not a stdlib dataclass;
        # RuntimeContext is a stdlib frozen dataclass. Build a fully validated
        # TurnInput through the real constructor (never model_copy(update=...))
        # via the shared _turn_input_with helper.
        new_turn_input = _turn_input_with(idempotency_key=idempotency_key)
        new_context = replace(context_obj, turn_input=new_turn_input)
        return run_environment(
            context_obj=new_context,
            idempotency_store=store,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )

    first = run(env(IDEMPOTENCY_KEY))
    other_key = UUID("00000099-0000-4000-8000-000000000000")
    second = run(env(other_key))

    assert first.disposition is WalkingSkeletonDisposition.STORED
    assert second.disposition is WalkingSkeletonDisposition.STORED
    assert first.outcome is not second.outcome
    assert first.effective_key != second.effective_key


# 5b. idempotency conflict (R1-01) ----------------------------------------------


def test_conflicting_fingerprint_returns_invalid_input_passthrough() -> None:
    store = ReplayCapableIdempotencyStoreFake()
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(document_evidence(),))
    plan = answer_plan()
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()

    def env(payload_digest: str) -> Coroutine[object, object, WalkingSkeletonResult]:
        return run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
            payload_digest=payload_digest,
        )

    first = run(env(PAYLOAD_DIGEST))
    assert first.disposition is WalkingSkeletonDisposition.STORED

    before_authorization_calls = authorization_port.calls
    before_capability_calls = capability_port.calls
    before_materializer_calls = materializer.calls
    before_renderer_calls = renderer.calls
    before_resolver_calls = resolver.calls
    before_audit_calls = audit_sink.calls
    before_complete_calls = len(store.complete_calls)
    before_telemetry_calls = telemetry_sink.calls

    # Same deployment, principal, client idempotency key, and RuntimeSnapshot
    # identity/digest (all held constant by the shared runtime_context()
    # default), but a different payload digest/request fingerprint for the
    # same effective key: the canonical store contract (proven by
    # tests/test_core_terminal_runtime.py::
    # test_conflict_returns_an_invalid_input_error) requires this to be a
    # CONFLICT, never a silent fingerprint overwrite or a repeated run.
    second = run(env(OTHER_PAYLOAD_DIGEST))

    assert second.disposition is WalkingSkeletonDisposition.PASSTHROUGH
    assert isinstance(second.outcome, ErrorEnvelope)
    assert second.outcome.error.code == "INVALID_INPUT"
    assert second.outcome.error.safe_message_key == "error.invalid_input"
    assert second.outcome.error.retryable is False
    assert second.lease is None
    assert second.orchestration_result is None
    assert second.effective_key == first.effective_key

    # No authorization, orchestration, capability invocation, finalization,
    # WS-004B audit, or idempotency completion is repeated for the conflict.
    assert authorization_port.calls == before_authorization_calls
    assert capability_port.calls == before_capability_calls
    assert materializer.calls == before_materializer_calls
    assert renderer.calls == before_renderer_calls
    assert resolver.calls == before_resolver_calls
    assert audit_sink.calls == before_audit_calls
    assert len(store.complete_calls) == before_complete_calls

    # The coordinator itself (owned by WS-003B, not WS-004B) does classify
    # the admission-time conflict with exactly one new failure telemetry
    # record; this is not WS-004B's own terminal telemetry being repeated,
    # since PASSTHROUGH never reaches WS-004B's terminal closure at all.
    assert telemetry_sink.calls == before_telemetry_calls + 1
    assert telemetry_sink.records[-1].outcome == RuntimeTelemetryOutcome.FAILED
    assert telemetry_sink.records[-1].error_code == "INVALID_INPUT"


# 5c. effective-key isolation dimensions (R1-06) --------------------------------


def _turn_input_with(*, idempotency_key: UUID) -> TurnInput:
    """Construct a fully validated TurnInput with exactly one field overridden.

    Reads every other field from the canonical runtime_context() fixture's own
    TurnInput (never model_copy(update=...)), then rebuilds through the real
    Pydantic constructor so the result still passes normal contract validation.
    """
    base = runtime_context().turn_input
    return TurnInput(
        request_id=base.request_id,
        message_id=base.message_id,
        conversation_id=base.conversation_id,
        raw_message=base.raw_message,
        received_at=base.received_at,
        idempotency_key=idempotency_key,
    )


def _principal_with(*, deployment_id: UUID, principal_id: UUID) -> SecurityPrincipalContext:
    """Construct a fully validated SecurityPrincipalContext with two fields overridden.

    Reads every other field from the canonical runtime_context() fixture's own
    principal, then rebuilds through the real Pydantic constructor.
    """
    base = runtime_context().principal
    return SecurityPrincipalContext(
        context_id=base.context_id,
        principal_id=principal_id,
        principal_type=base.principal_type,
        deployment_id=deployment_id,
        issuer=base.issuer,
        authenticated_at=base.authenticated_at,
        authentication_methods=base.authentication_methods,
        assurance_level=base.assurance_level,
    )


def _runtime_snapshot_with_digest(*, snapshot_id: UUID, digest: str) -> RuntimeSnapshot:
    """Construct a fully validated RuntimeSnapshot with only its integrity digest overridden.

    Reads every other field, including the full content bundle, from the
    canonical runtime_context() fixture's own RuntimeSnapshot, then rebuilds
    through the real Pydantic constructors.
    """
    base = runtime_context(snapshot_id=snapshot_id).runtime_snapshot
    return RuntimeSnapshot(
        snapshot_id=base.snapshot_id,
        captured_at=base.captured_at,
        content=base.content,
        integrity=RuntimeSnapshotIntegrity(
            canonicalization=base.integrity.canonicalization,
            digest=digest,
        ),
    )


def _context_with(
    *,
    deployment_id: UUID = DEPLOYMENT_ID,
    principal_id: UUID = PRINCIPAL_ID,
    idempotency_key: UUID = IDEMPOTENCY_KEY,
    snapshot_id: UUID = SNAPSHOT_ID,
    snapshot_digest: str = SNAPSHOT_DIGEST,
) -> RuntimeContext:
    """Build a RuntimeContext overriding exactly the given key dimensions.

    Every other effective-key dimension is held at its default fixture value.
    Every overridden principal/turn_input/runtime_snapshot value is built by
    _principal_with/_turn_input_with/_runtime_snapshot_with_digest above,
    through real canonical constructors, never model_copy(update=...).
    """
    base = runtime_context(snapshot_id=snapshot_id)
    new_principal = _principal_with(deployment_id=deployment_id, principal_id=principal_id)
    new_turn_input = _turn_input_with(idempotency_key=idempotency_key)
    new_runtime_snapshot = base.runtime_snapshot
    if snapshot_digest != SNAPSHOT_DIGEST:
        new_runtime_snapshot = _runtime_snapshot_with_digest(
            snapshot_id=snapshot_id, digest=snapshot_digest
        )
    return replace(
        base,
        principal=new_principal,
        turn_input=new_turn_input,
        runtime_snapshot=new_runtime_snapshot,
    )


OTHER_DEPLOYMENT_ID = UUID("00000091-0000-4000-8000-000000000000")
OTHER_PRINCIPAL_ID = UUID("00000092-0000-4000-8000-000000000000")
OTHER_SNAPSHOT_ID = UUID("00000093-0000-4000-8000-000000000000")
OTHER_SNAPSHOT_DIGEST = "sha256:" + "b" * 64


def _isolation_case(
    first_context: RuntimeContext,
    second_context: RuntimeContext,
    *,
    first_snapshot_id: UUID = SNAPSHOT_ID,
    second_snapshot_id: UUID = SNAPSHOT_ID,
) -> None:
    store = ReplayCapableIdempotencyStoreFake()
    plan = answer_plan()

    def env(
        context_obj: RuntimeContext, snapshot_id: UUID
    ) -> Coroutine[object, object, WalkingSkeletonResult]:
        return run_environment(
            context_obj=context_obj,
            # QueryAnalysis and the capability StepResult both carry their own
            # runtime_snapshot_id, which routing.py's _require_analysis_binding
            # and step_validation.py's _require_result_lineage require to
            # match the RuntimeContext's; keep both in lockstep with whichever
            # snapshot_id this case is exercising.
            analysis=query_analysis(snapshot_id=snapshot_id),
            capability_port=CapabilityPortFake(result=step_result(snapshot_id=snapshot_id)),
            idempotency_store=store,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )

    first = run(env(first_context, first_snapshot_id))
    second = run(env(second_context, second_snapshot_id))

    # Independent admission and completion: neither run replays the other's
    # scope, and each is completed exactly once in the shared store.
    assert first.disposition is WalkingSkeletonDisposition.STORED
    assert second.disposition is WalkingSkeletonDisposition.STORED
    assert first.outcome is not second.outcome
    assert first.effective_key != second.effective_key
    assert len(store.complete_calls) == 2
    assert store.stored_outcome(first.effective_key) is first.outcome
    assert store.stored_outcome(second.effective_key) is second.outcome


def test_effective_key_isolation_across_deployments() -> None:
    _isolation_case(_context_with(), _context_with(deployment_id=OTHER_DEPLOYMENT_ID))


def test_effective_key_isolation_across_principals() -> None:
    _isolation_case(_context_with(), _context_with(principal_id=OTHER_PRINCIPAL_ID))


def test_effective_key_isolation_across_runtime_snapshot_ids() -> None:
    _isolation_case(
        _context_with(),
        _context_with(snapshot_id=OTHER_SNAPSHOT_ID),
        first_snapshot_id=SNAPSHOT_ID,
        second_snapshot_id=OTHER_SNAPSHOT_ID,
    )


def test_effective_key_isolation_across_runtime_snapshot_digests() -> None:
    _isolation_case(_context_with(), _context_with(snapshot_digest=OTHER_SNAPSHOT_DIGEST))


# 6. existing terminal short-circuits -------------------------------------------


def test_authorization_denial_returns_passthrough() -> None:
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    result = run(
        run_environment(
            authorization_port=AuthorizationPortFake(decision=denied_authorization()),
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
        )
    )
    assert result.disposition is WalkingSkeletonDisposition.PASSTHROUGH
    assert isinstance(result.outcome, ErrorEnvelope)
    # WS-003B already closed this terminal outcome; WS-004B must not duplicate it.
    assert audit_sink.calls == 1
    assert telemetry_sink.calls >= 1


def test_in_flight_returns_passthrough_with_no_duplicate_terminal_work() -> None:
    store = ReplayCapableIdempotencyStoreFake()
    plan = answer_plan()

    started = asyncio.Event()
    gate = asyncio.Event()
    blocking_capability = CapabilityPortFake(result=step_result(), started=started, gate=gate)

    async def scenario() -> None:
        first_task = asyncio.ensure_future(
            run_environment(
                idempotency_store=store,
                capability_port=blocking_capability,
                renderer=AnswerRendererFake(draft=faithful_draft(plan)),
                citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
            )
        )
        try:
            await started.wait()

            second = await run_environment(
                idempotency_store=store,
                renderer=AnswerRendererFake(draft=faithful_draft(plan)),
                citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
            )
            assert second.disposition is WalkingSkeletonDisposition.PASSTHROUGH
            assert second.lease is None
            assert second.orchestration_result is None
        finally:
            gate.set()
        first = await first_task
        assert first.disposition is WalkingSkeletonDisposition.STORED

    asyncio.run(scenario())


# 7. audit failure ---------------------------------------------------------------


def test_audit_failure_withholds_the_outcome() -> None:
    journal = CallJournal()
    store = ReplayCapableIdempotencyStoreFake(journal=journal)
    audit_sink = AuditEventSinkFake(
        error=RuntimeError("audit backend unavailable"), journal=journal
    )
    telemetry_sink = RuntimeTelemetrySinkFake(journal=journal)
    plan = answer_plan()

    result = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.WITHHELD
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "INTERNAL_ERROR"
    assert result.lease is not None
    assert result.orchestration_result is not None
    assert len(store.complete_calls) == 0
    assert len(store.abandon_calls) == 0
    # R1-02 negative ordering: audit ordinary failure -> no completion ever
    # attempted. "complete" never appears in the shared journal after the
    # "audit" attempt.
    audit_index = journal.entries.index("audit")
    assert "complete" not in journal.entries[audit_index:]
    # coordinate_idempotent_fast_document already emitted one runtime_started
    # telemetry record on this shared sink before WS-004B's own withheld close
    # emits its best-effort runtime_failed record: ordinary telemetry failures
    # are fail open even on the withheld path, so "no terminal telemetry" is
    # proven here as "no terminal telemetry for the original (answered)
    # outcome", never as "telemetry is skipped entirely".
    assert telemetry_sink.calls == 2
    assert telemetry_sink.records[-1].event_name == RuntimeTelemetryEventName.RUNTIME_FAILED
    assert telemetry_sink.records[-1].outcome == RuntimeTelemetryOutcome.FAILED
    assert telemetry_sink.records[-1].error_code == "INTERNAL_ERROR"
    assert all(
        record.outcome is not RuntimeTelemetryOutcome.ANSWERED for record in telemetry_sink.records
    )


# 8. completion failure ------------------------------------------------------------


def test_completion_failure_withholds_with_distinct_error_identity() -> None:
    store = ReplayCapableIdempotencyStoreFake(complete_error=RuntimeError("store unavailable"))
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    plan = answer_plan()

    result = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.WITHHELD
    assert isinstance(result.outcome, ErrorEnvelope)
    assert result.outcome.error.code == "INTERNAL_ERROR"
    assert audit_sink.calls == 1
    assert audit_sink.events[0].outcome == "success"
    assert audit_sink.events[0].event_id != result.outcome.error_id
    assert len(store.abandon_calls) == 0
    assert result.lease is not None
    # R1-02 negative ordering: audit happened (once, success) but completion
    # ordinarily fails -> no completion is ever recorded.
    assert len(store.complete_calls) == 0
    # Fail-open telemetry still emits its best-effort withheld-path record,
    # but never the original (answered) outcome's terminal telemetry.
    assert telemetry_sink.calls == 2
    assert telemetry_sink.records[-1].event_name == RuntimeTelemetryEventName.RUNTIME_FAILED
    assert telemetry_sink.records[-1].outcome == RuntimeTelemetryOutcome.FAILED
    assert telemetry_sink.records[-1].error_code == "INTERNAL_ERROR"
    assert all(
        record.outcome is not RuntimeTelemetryOutcome.ANSWERED for record in telemetry_sink.records
    )


# 9. telemetry failure ---------------------------------------------------------------


def test_telemetry_failure_does_not_change_stored_outcome() -> None:
    journal = CallJournal()
    store = ReplayCapableIdempotencyStoreFake(journal=journal)
    audit_sink = AuditEventSinkFake(journal=journal)
    telemetry_sink = RuntimeTelemetrySinkFake(
        error=RuntimeError("telemetry backend down"), journal=journal
    )
    plan = answer_plan()

    result = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )
    )

    assert result.disposition is WalkingSkeletonDisposition.STORED
    assert isinstance(result.outcome, FinalAnswer)
    # R1-02 positive ordering even in the failure case: audit happened, then
    # completion happened, then the (failing) terminal telemetry attempt was
    # still made -- and the terminal result is still returned regardless.
    assert audit_sink.calls == 1
    assert len(store.complete_calls) == 1
    audit_index = journal.entries.index("audit")
    assert journal.entries[audit_index:] == ("audit", "complete", "telemetry")


# 10. cancellation ---------------------------------------------------------------------


def test_cancellation_during_audit_emission_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()
    audit_sink = AuditEventSinkFake(started=started, gate=gate)
    plan = answer_plan()

    async def scenario() -> None:
        task = asyncio.ensure_future(
            run_environment(
                audit_sink=audit_sink,
                renderer=AnswerRendererFake(draft=faithful_draft(plan)),
                citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
            )
        )
        try:
            await started.wait()
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
            assert audit_sink.observed_cancellation is True
        finally:
            gate.set()

    asyncio.run(scenario())


def test_cancellation_during_idempotency_completion_propagates() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()
    store = ReplayCapableIdempotencyStoreFake(complete_started=started, complete_gate=gate)
    plan = answer_plan()

    async def scenario() -> None:
        task = asyncio.ensure_future(
            run_environment(
                idempotency_store=store,
                renderer=AnswerRendererFake(draft=faithful_draft(plan)),
                citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
            )
        )
        try:
            await started.wait()
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            gate.set()

    asyncio.run(scenario())


def test_cancellation_during_terminal_telemetry_propagates_then_replays() -> None:
    journal = CallJournal()
    store = ReplayCapableIdempotencyStoreFake(journal=journal)
    audit_sink = AuditEventSinkFake(journal=journal)
    started = asyncio.Event()
    gate = asyncio.Event()
    telemetry_sink = _BlockingTelemetrySinkFake(journal=journal, started=started, gate=gate)
    authorization_port = AuthorizationPortFake(decision=authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(document_evidence(),))
    plan = answer_plan()
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))

    async def scenario() -> None:
        task = asyncio.ensure_future(
            run_environment(
                idempotency_store=store,
                audit_sink=audit_sink,
                telemetry_sink=telemetry_sink,
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
                renderer=renderer,
                citation_source_resolver=resolver,
            )
        )
        try:
            await started.wait()
            # By the time terminal telemetry has started blocking, audit was
            # already accepted and idempotency completion already succeeded:
            # this is genuinely mid-telemetry cancellation, not a fabricated
            # ordering.
            assert audit_sink.calls == 1
            assert len(store.complete_calls) == 1
            task.cancel()

            with pytest.raises(asyncio.CancelledError):
                await task
            assert telemetry_sink.observed_cancellation is True
        finally:
            gate.set()

    asyncio.run(scenario())

    stored_outcome = store.stored_outcome(expected_key())
    assert stored_outcome is not None

    before_authorization_calls = authorization_port.calls
    before_capability_calls = capability_port.calls
    before_materializer_calls = materializer.calls
    before_renderer_calls = renderer.calls
    before_resolver_calls = resolver.calls
    before_audit_calls = audit_sink.calls
    before_complete_calls = len(store.complete_calls)

    replay = run(
        run_environment(
            idempotency_store=store,
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            renderer=renderer,
            citation_source_resolver=resolver,
        )
    )

    assert replay.disposition is WalkingSkeletonDisposition.REPLAYED
    assert replay.outcome is stored_outcome
    assert authorization_port.calls == before_authorization_calls
    assert capability_port.calls == before_capability_calls
    assert materializer.calls == before_materializer_calls
    assert renderer.calls == before_renderer_calls
    assert resolver.calls == before_resolver_calls
    assert audit_sink.calls == before_audit_calls
    assert len(store.complete_calls) == before_complete_calls


# 11. ValueError propagation -----------------------------------------------------------


def test_mismatched_completion_artifacts_ordering_raises_value_error() -> None:

    with pytest.raises(ValueError):
        run(
            run_environment(
                completion=completion_artifacts(occurred_at=NOW - timedelta(days=1)),
                finalization_entered_at=FINALIZATION_ENTERED_AT,
            )
        )


# 12. immutability -----------------------------------------------------------------------


def test_context_and_analysis_are_not_mutated() -> None:
    context_obj = runtime_context()
    analysis = query_analysis()
    plan = answer_plan()

    run(
        run_environment(
            context_obj=context_obj,
            analysis=analysis,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )
    )

    assert context_obj == runtime_context()
    assert analysis == query_analysis()


# 13. safety -----------------------------------------------------------------------------


def test_audit_and_telemetry_omit_unsafe_content() -> None:
    audit_sink = AuditEventSinkFake()
    telemetry_sink = RuntimeTelemetrySinkFake()
    plan = answer_plan()

    run(
        run_environment(
            audit_sink=audit_sink,
            telemetry_sink=telemetry_sink,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            citation_source_resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
        )
    )

    rendered_audit = tuple(str(event) for event in audit_sink.events)
    rendered_telemetry = tuple(str(record) for record in telemetry_sink.records)
    for fragment in FORBIDDEN_RECORD_TEXT:
        for text in (*rendered_audit, *rendered_telemetry):
            assert fragment not in text


# 14. architecture -----------------------------------------------------------------------


def test_core_all_remains_empty() -> None:
    assert core_package.__all__ == ()


def test_module_contains_no_forbidden_fragments() -> None:
    for fragment in FORBIDDEN_FRAGMENTS:
        assert fragment not in MODULE_SOURCE, fragment


def test_module_contains_no_concurrency_primitives() -> None:
    for fragment in CONCURRENCY_FRAGMENTS:
        assert fragment not in MODULE_SOURCE, fragment


def test_module_does_not_call_abandon() -> None:
    assert ".abandon(" not in MODULE_SOURCE


def test_module_imports_only_allowed_packages_and_stdlib() -> None:
    tree = ast.parse(MODULE_SOURCE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root in STDLIB_MODULES or alias.name.startswith(ALLOWED_PACKAGES)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            assert root in STDLIB_MODULES or module.startswith(ALLOWED_PACKAGES), module


def test_module_does_not_import_forbidden_vendor_roots() -> None:
    for root in FORBIDDEN_VENDOR_ROOTS:
        assert f"import {root}" not in MODULE_SOURCE
        assert f"from {root}" not in MODULE_SOURCE
