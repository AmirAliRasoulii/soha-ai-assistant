"""Typed configurable port fakes for the WS-003B terminal coordination tests."""

import asyncio
from uuid import UUID

from ai_assistant.contracts import (
    AnswerLengthBudget,
    AuditEvent,
    DomainError,
    ErrorEnvelope,
    FinalAnswer,
    FinalAnswerSection,
    FinalCitation,
    FinalCitationSource,
    FinalClaimContent,
    FinalFreshnessNote,
    FinalResponseMetadata,
    FinalValidatedContent,
)
from ai_assistant.contracts.errors import ErrorCode
from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    IdempotencyAcquireResult,
    IdempotencyAcquireStatus,
    IdempotencyLease,
    RuntimeTelemetryRecord,
    TerminalOutcome,
)
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    AUTHORIZATION_ID,
    BUNDLE_ID,
    CORRELATION_ID,
    EVIDENCE_ID,
    HEX_DIGEST,
    NOW,
    PLAN_ID,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SNAPSHOT_ID,
)

LEASE_ID = "lease-1"
PAYLOAD_DIGEST = HEX_DIGEST
OTHER_PAYLOAD_DIGEST = "c" * 64
CLAIM_TEXT = "Sentinel claim text."
CLAIM_ITEM_ID = "claim.answer"


def terminal_identifier(index: int) -> UUID:
    """Return a deterministic version 4 UUID reserved for terminal fixtures."""
    return UUID(f"{index:08d}-0000-4000-8000-000000000000")


FINAL_ANSWER_ID = terminal_identifier(30)
STORED_ERROR_ID = terminal_identifier(31)
CITATION_ID = terminal_identifier(32)
STORED_DETAIL_REF = terminal_identifier(33)


def effective_key(
    *,
    deployment_id: str,
    principal_id: str,
    client_key: str,
    runtime_snapshot_id: str,
    runtime_snapshot_digest: str,
) -> EffectiveIdempotencyKey:
    """Build an effective key through the normal constructor."""
    return EffectiveIdempotencyKey(
        deployment_id=deployment_id,
        principal_id=principal_id,
        client_key=client_key,
        runtime_snapshot_id=runtime_snapshot_id,
        runtime_snapshot_digest=runtime_snapshot_digest,
    )


def lease(
    key: EffectiveIdempotencyKey,
    *,
    lease_id: str = LEASE_ID,
    request_fingerprint: str = PAYLOAD_DIGEST,
) -> IdempotencyLease:
    """Build a lease for the supplied effective key."""
    return IdempotencyLease(
        lease_id=lease_id,
        key=key,
        request_fingerprint=request_fingerprint,
    )


def acquired(key: EffectiveIdempotencyKey) -> IdempotencyAcquireResult:
    return IdempotencyAcquireResult(
        status=IdempotencyAcquireStatus.ACQUIRED,
        lease=lease(key),
    )


def replayed(outcome: TerminalOutcome) -> IdempotencyAcquireResult:
    return IdempotencyAcquireResult(
        status=IdempotencyAcquireStatus.REPLAY,
        outcome=outcome,
    )


def in_flight() -> IdempotencyAcquireResult:
    return IdempotencyAcquireResult(status=IdempotencyAcquireStatus.IN_FLIGHT)


def conflicted() -> IdempotencyAcquireResult:
    return IdempotencyAcquireResult(status=IdempotencyAcquireStatus.CONFLICT)


def stored_error_envelope(code: ErrorCode = "DEPENDENCY_TIMEOUT") -> ErrorEnvelope:
    """Build an already accepted ErrorEnvelope for replay tests."""
    retryable = code in (
        "DEPENDENCY_TIMEOUT",
        "TRANSIENT_DEPENDENCY",
        "RATE_LIMITED",
        "CAPACITY_REJECTED",
    )
    return ErrorEnvelope(
        error_id=STORED_ERROR_ID,
        correlation_id=CORRELATION_ID,
        error=DomainError(
            code=code,
            safe_message_key=f"error.{code.lower()}",
            retryable=retryable,
            internal_detail_ref=STORED_DETAIL_REF,
        ),
    )


def stored_final_answer() -> FinalAnswer:
    """Build an already accepted FinalAnswer for replay tests."""
    claim = FinalClaimContent(item_id=CLAIM_ITEM_ID, rendered_text=CLAIM_TEXT)
    section = FinalAnswerSection(
        section_id="section.summary",
        section_type="summary",
        items=(claim,),
    )
    citation = FinalCitation(
        citation_id=CITATION_ID,
        slot_id="slot.answer",
        target_kind="claim",
        target_id=CLAIM_ITEM_ID,
        placement="inline",
        sources=(
            FinalCitationSource(
                evidence_id=EVIDENCE_ID,
                evidence_type="document",
                display_label="Document store",
                source_version="1",
                locator_ref="locator:1",
            ),
        ),
    )
    return FinalAnswer(
        final_answer_id=FINAL_ANSWER_ID,
        request_id=REQUEST_ID,
        answer_plan_id=ANSWER_PLAN_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        finalized_at=NOW,
        outcome="answered",
        validated_content=FinalValidatedContent(sections=(section,)),
        citations=(citation,),
        freshness_note=FinalFreshnessNote(status="current", data_as_of=NOW),
        applied_length_budget=AnswerLengthBudget(
            max_characters=16000,
            max_sections=8,
            max_claims=32,
            max_caveats=32,
            max_citations=64,
        ),
        response_metadata=FinalResponseMetadata(
            response_locale="fa-IR",
            answer_type="direct",
            generation_mode="model_generated",
            validation_status="passed",
            degraded=False,
            section_count=1,
            claim_count=1,
            caveat_count=0,
            citation_count=1,
            character_count=len(CLAIM_TEXT),
        ),
        finalizer_version="1.0.0",
    )


class CallJournal:
    """Ordered record of port calls captured without arbitrary dictionaries."""

    def __init__(self) -> None:
        self.entries: tuple[str, ...] = ()

    def record(self, label: str) -> None:
        self.entries = (*self.entries, label)


class IdempotencyStoreFake:
    """Configurable IdempotencyStorePort double with atomic acquire outcomes."""

    def __init__(
        self,
        *,
        result: IdempotencyAcquireResult | None = None,
        acquire_error: BaseException | None = None,
        complete_error: BaseException | None = None,
        journal: CallJournal | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.result = result
        self.acquire_error = acquire_error
        self.complete_error = complete_error
        self.journal = journal
        self.started = started
        self.gate = gate
        self.acquire_calls = 0
        self.complete_calls = 0
        self.abandon_calls = 0
        self.observed_cancellation = False
        self.keys: tuple[EffectiveIdempotencyKey, ...] = ()
        self.fingerprints: tuple[str, ...] = ()
        self.completed_leases: tuple[IdempotencyLease, ...] = ()
        self.completed_outcomes: tuple[TerminalOutcome, ...] = ()

    def _note(self, label: str) -> None:
        if self.journal is not None:
            self.journal.record(label)

    async def _pause(self) -> None:
        if self.started is not None:
            self.started.set()
        if self.gate is None:
            return
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.observed_cancellation = True
            raise

    async def acquire(
        self,
        key: EffectiveIdempotencyKey,
        request_fingerprint: str,
    ) -> IdempotencyAcquireResult:
        self.acquire_calls += 1
        self.keys = (*self.keys, key)
        self.fingerprints = (*self.fingerprints, request_fingerprint)
        self._note("acquire")
        await self._pause()
        if self.acquire_error is not None:
            raise self.acquire_error
        if self.result is None:
            raise ValueError("the idempotency fake requires a configured acquire result")
        return self.result

    async def complete(self, lease: IdempotencyLease, outcome: TerminalOutcome) -> None:
        self.complete_calls += 1
        self.completed_leases = (*self.completed_leases, lease)
        self.completed_outcomes = (*self.completed_outcomes, outcome)
        self._note("complete")
        await self._pause()
        if self.complete_error is not None:
            raise self.complete_error

    async def abandon(self, lease: IdempotencyLease) -> None:
        self.abandon_calls += 1
        self._note("abandon")


class AuditEventSinkFake:
    """Configurable AuditEventSink double."""

    def __init__(
        self,
        *,
        error: BaseException | None = None,
        journal: CallJournal | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.error = error
        self.journal = journal
        self.started = started
        self.gate = gate
        self.calls = 0
        self.observed_cancellation = False
        self.events: tuple[AuditEvent, ...] = ()

    async def emit(self, event: AuditEvent) -> None:
        self.calls += 1
        self.events = (*self.events, event)
        if self.journal is not None:
            self.journal.record("audit")
        if self.started is not None:
            self.started.set()
        if self.gate is not None:
            try:
                await self.gate.wait()
            except asyncio.CancelledError:
                self.observed_cancellation = True
                raise
        if self.error is not None:
            raise self.error


class RuntimeTelemetrySinkFake:
    """Configurable RuntimeTelemetrySink double."""

    def __init__(
        self,
        *,
        error: BaseException | None = None,
        journal: CallJournal | None = None,
    ) -> None:
        self.error = error
        self.journal = journal
        self.calls = 0
        self.records: tuple[RuntimeTelemetryRecord, ...] = ()

    async def emit(self, record: RuntimeTelemetryRecord) -> None:
        self.calls += 1
        self.records = (*self.records, record)
        if self.journal is not None:
            self.journal.record("telemetry")
        if self.error is not None:
            raise self.error
