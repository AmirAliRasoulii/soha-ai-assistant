"""Typed fakes for the WS-004B walking skeleton terminal closure tests.

This module reuses the existing WS-002, WS-003A, WS-003B, and WS-004A fixture
and fake modules wherever possible. It adds exactly one new stateful fake that
those modules do not already provide: a multi-key, replay-capable idempotency
store, plus small typed call-journal records for it.
"""

import asyncio
from dataclasses import dataclass

from ai_assistant.core.types import (
    EffectiveIdempotencyKey,
    IdempotencyAcquireResult,
    IdempotencyAcquireStatus,
    IdempotencyLease,
    TerminalOutcome,
)
from support.walking_skeleton_terminal_fakes import CallJournal


@dataclass(frozen=True, slots=True)
class AcquireCallRecord:
    key: EffectiveIdempotencyKey
    request_fingerprint: str


@dataclass(frozen=True, slots=True)
class CompleteCallRecord:
    lease: IdempotencyLease
    outcome: TerminalOutcome


@dataclass(frozen=True, slots=True)
class AbandonCallRecord:
    lease: IdempotencyLease


@dataclass(slots=True)
class _StoredEntry:
    lease: IdempotencyLease
    request_fingerprint: str
    outcome: TerminalOutcome | None = None


class ReplayCapableIdempotencyStoreFake:
    """A stateful, multi-key idempotency store fake with true replay semantics.

    This is a test-only mutable store, never a production idempotency adapter:
    it is process-local and unbounded on purpose, existing only so tests can
    observe admission, completion, and replay behavior across more than one
    effective key, and can gate or fail a `complete` call to exercise WS-004B's
    fail-closed completion and cancellation handling.

    Conflict semantics mirror the canonical IdempotencyStorePort contract
    proven by tests/test_core_terminal_runtime.py
    (test_conflict_returns_an_invalid_input_error): for a given effective key,
    a request_fingerprint that differs from the one already stored is always
    a CONFLICT, regardless of whether the existing entry has already
    completed. The stored fingerprint for an existing entry is never
    overwritten by a later acquire call.
    """

    def __init__(
        self,
        *,
        complete_error: BaseException | None = None,
        complete_started: asyncio.Event | None = None,
        complete_gate: asyncio.Event | None = None,
        journal: CallJournal | None = None,
    ) -> None:
        self._entries: dict[EffectiveIdempotencyKey, _StoredEntry] = {}
        self._complete_error = complete_error
        self._complete_started = complete_started
        self._complete_gate = complete_gate
        self._journal = journal
        self.acquire_calls: list[AcquireCallRecord] = []
        self.complete_calls: list[CompleteCallRecord] = []
        self.abandon_calls: list[AbandonCallRecord] = []

    async def acquire(
        self,
        key: EffectiveIdempotencyKey,
        request_fingerprint: str,
    ) -> IdempotencyAcquireResult:
        self.acquire_calls.append(
            AcquireCallRecord(key=key, request_fingerprint=request_fingerprint)
        )
        existing = self._entries.get(key)
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                # Same effective key, different fingerprint: always a
                # conflict, whether or not the existing entry has completed.
                # The stored fingerprint is never overwritten.
                return IdempotencyAcquireResult(status=IdempotencyAcquireStatus.CONFLICT)
            if existing.outcome is not None:
                return IdempotencyAcquireResult(
                    status=IdempotencyAcquireStatus.REPLAY,
                    outcome=existing.outcome,
                )
            return IdempotencyAcquireResult(status=IdempotencyAcquireStatus.IN_FLIGHT)
        new_lease = IdempotencyLease(
            lease_id=f"lease-{len(self._entries) + 1}",
            key=key,
            request_fingerprint=request_fingerprint,
        )
        self._entries[key] = _StoredEntry(lease=new_lease, request_fingerprint=request_fingerprint)
        return IdempotencyAcquireResult(
            status=IdempotencyAcquireStatus.ACQUIRED,
            lease=new_lease,
        )

    async def complete(self, lease: IdempotencyLease, outcome: TerminalOutcome) -> None:
        if self._complete_started is not None:
            self._complete_started.set()
        if self._complete_gate is not None:
            await self._complete_gate.wait()
        if self._complete_error is not None:
            raise self._complete_error
        entry = self._entries.get(lease.key)
        if entry is None or entry.lease is not lease:
            raise ValueError("complete called with an unknown lease")
        self.complete_calls.append(CompleteCallRecord(lease=lease, outcome=outcome))
        entry.outcome = outcome
        if self._journal is not None:
            self._journal.record("complete")

    async def abandon(self, lease: IdempotencyLease) -> None:
        self.abandon_calls.append(AbandonCallRecord(lease=lease))
        entry = self._entries.get(lease.key)
        if entry is not None and entry.lease is lease:
            del self._entries[lease.key]

    def stored_outcome(self, key: EffectiveIdempotencyKey) -> TerminalOutcome | None:
        entry = self._entries.get(key)
        return None if entry is None else entry.outcome
