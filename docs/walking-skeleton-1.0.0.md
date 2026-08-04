# Walking Skeleton 1.0.0 — Terminal Closure

## Status

This document describes the WS-004B terminal closure of the bounded fast
document Walking Skeleton. It closes DEF-002, DEF-083, DEF-087, and DEF-091
for the bounded flow described below. **This is not a production-ready
system.** It is a bounded, in-process proof of the full turn lifecycle using
test-fake adapters only.

## Scope

WS-004B adds exactly one new module, `src/ai_assistant/core/walking_skeleton.py`,
which provides `run_idempotent_fast_document(...)`: the outermost trusted Core
entry point for one bounded turn:

```
TurnInput
  -> idempotency admission            (WS-003B, reused)
  -> authorization                    (WS-002/WS-003A, reused)
  -> deterministic routing            (WS-002, reused)
  -> planning                         (WS-002, reused)
  -> capability execution             (WS-002, reused)
  -> evidence materialization         (WS-002, reused)
  -> EvidenceBundle                   (WS-002, reused)
  -> AnswerPlan                       (WS-002, reused)
  -> trusted finalization             (WS-004A, reused)
  -> FinalAnswer or ErrorEnvelope
  -> AuditEvent                       (WS-004B, new)
  -> idempotency completion           (WS-004B, new)
  -> terminal telemetry               (WS-004B, new)
  -> deterministic replay             (WS-003B, reused; WS-004B, verified end to end)
```

WS-004B owns exactly one new concern: audit-before-complete terminal closure,
fail-closed audit and completion, fail-open terminal telemetry, and the
idempotent replay contract of the whole turn. Every other stage is reused,
unmodified, from `runtime.py`, `terminal_runtime.py`, and `finalization.py`
via `coordinate_idempotent_fast_document(...)` and
`finalize_pending_answer(...)`.

### Explicitly out of scope

- No HTTP adapter of any kind.
- No production idempotency adapter (no database, cache, or distributed lock
  implementation).
- No production audit adapter (no log shipping, no persistent audit store).
- No production telemetry adapter (no metrics/tracing backend integration).
- No real model adapter (no LLM or provider SDK call of any kind).
- No department management model or department configuration surface.
- No streaming responses.
- No retries of any kind, at any layer.
- No load-test qualification. Concurrency here is validated only for two
  single-process fake-adapter callers sharing one in-memory test double; it
  says nothing about horizontal scaling, multi-replica behavior, or real
  network/storage latency.
- No Admin Website, Control Plane, or persistent stores.

## Trust boundaries

`walking_skeleton.py` is trusted Core code. It:

- Never reimplements effective idempotency-key derivation, authorization,
  routing, planning, step validation, evidence management, answer planning,
  render validation, citation compilation, or `FinalAnswer` construction —
  all of those remain owned by the existing WS-002/WS-003A/WS-003B/WS-004A
  modules.
- Calls `coordinate_idempotent_fast_document(...)` exactly once per turn and
  branches only on its result.
- Calls `finalize_pending_answer(...)` exactly once, only for a
  `PENDING_FINALIZATION` result whose orchestration status is `COMPLETED`.
- Constructs `AuditEvent` and `RuntimeTelemetryRecord` values using only
  already-trusted, already-validated identifiers and artifacts supplied by
  the caller (`TerminalCompletionArtifacts`) or produced by the reused
  stages. It never fabricates or repairs an identifier.
- Never inspects `analysis` before idempotency admission — that ordering is
  owned entirely by the existing coordinator.

## Idempotency and replay semantics

On a `REPLAYED` coordination result, WS-004B returns the exact stored
`FinalAnswer` or `ErrorEnvelope` object identity with no lease, no
orchestration result, and calls no port, sink, or store beyond whatever the
accepted coordinator already performed. No authorization, capability,
materialization, render, citation resolution, audit, telemetry, or
completion call happens on replay.

On a `PENDING_FINALIZATION` result, WS-004B performs exactly one audit call,
at most one idempotency completion call, and at most one best-effort
telemetry call, in that fixed order, before returning a `STORED` (success) or
`WITHHELD` (audit/completion failure) result.

The effective key used for admission and replay continues to isolate:

- deployment,
- principal,
- the caller-supplied idempotency key,
- runtime snapshot ID,
- runtime snapshot digest.

A later request under the same effective key replays the same stored object
identity with no downstream work. A request that shares only the raw client
idempotency key, but differs in any of the other scope dimensions above, is a
different effective key and never replays another scope's outcome. WS-004B
does not implement TTL, polling, locks, or an in-memory production store; a
mutable stateful store is provided only as a test fake
(`ReplayCapableIdempotencyStoreFake`).

### Effective-key conflict behavior

Within a single effective key, the idempotency store additionally compares
the caller's `request_fingerprint` (the payload digest bound to the turn)
against the fingerprint already stored for that key:

- same effective key + same fingerprint + already-completed outcome ->
  `IdempotencyAcquireStatus.REPLAY`;
- same effective key + same fingerprint + an open, not-yet-completed lease ->
  `IdempotencyAcquireStatus.IN_FLIGHT`;
- same effective key + a different fingerprint -> `IdempotencyAcquireStatus.CONFLICT`.

A conflict is surfaced by the existing, reused coordinator
(`coordinate_idempotent_fast_document`) as `TerminalCoordinationStatus.TERMINAL_ERROR`
with `ErrorEnvelope(code="INVALID_INPUT")`, exactly like the canonical
`IdempotencyStorePort` contract proven in `tests/test_core_terminal_runtime.py`.
WS-004B receives this as a `PASSTHROUGH` result: it never repeats
authorization, orchestration, capability invocation, finalization, its own
audit call, idempotency completion, or its own terminal telemetry call for a
conflicting request. The stored fingerprint for an existing entry is never
overwritten by a later, differing request.

## STOPPED clarify/abstain mapping

For a `PENDING_FINALIZATION` result whose orchestration status is `STOPPED`,
WS-004B never calls the renderer, the citation resolver, or the finalizer,
and never fabricates an `ExecutionPlan`, `EvidenceBundle`, `AnswerPlan`, or
`FinalAnswer`. It deterministically maps the already-accepted terminal route:

- `RouteDecision.lane == "clarify"` -> `ErrorEnvelope(code="AMBIGUOUS_REQUEST")`
- `RouteDecision.lane == "abstain"` -> `ErrorEnvelope(code="NO_EVIDENCE")`

using `completion_artifacts.stopped_error_id` and
`completion_artifacts.stopped_internal_detail_ref`, and canonical
`safe_message_key`/`retryable`/`correlation_id` semantics from the existing
`ErrorEnvelope` contract. Any other stopped route lane is rejected with
`ValueError`; this is a pre-plan outcome and always remains on the
`ErrorEnvelope` path, never a fabricated `FinalAnswer`.

## Audit-before-complete ordering

For every pending terminal outcome, WS-004B performs, in this exact order:

1. construct the terminal outcome (already produced by the reused stages),
2. construct the `AuditEvent`,
3. `audit_sink.emit(event)`,
4. `idempotency_store.complete(lease, outcome)`,
5. best-effort terminal telemetry,
6. return the `STORED` result.

Audit is fail-closed: idempotency completion is only attempted after the
audit event has been accepted. Completion is likewise fail-closed with
respect to retries: a completion failure never retries and never abandons
the lease.

### Fail-closed audit behavior

If `audit_sink.emit` raises an ordinary exception, WS-004B does not call
idempotency completion, does not retry the audit, and does not abandon the
lease. It emits a best-effort `runtime_failed` / `INTERNAL_ERROR` telemetry
record and returns `WITHHELD` with a freshly identified
`ErrorEnvelope(INTERNAL_ERROR)` built from
`completion_artifacts.coordination_error_id` and
`completion_artifacts.coordination_internal_detail_ref`. The original
`FinalAnswer` or stopped `ErrorEnvelope` is withheld and never stored.

### Fail-closed completion behavior

If `idempotency_store.complete` raises an ordinary exception, WS-004B does
not retry, does not abandon the lease, and retains it. It emits the same
kind of best-effort failure telemetry and returns `WITHHELD` with a distinct
coordination error identity, separate from the accepted audit event's error
identity, so the two failure modes remain distinguishable after the fact.

### Fail-open telemetry behavior

Terminal telemetry is best-effort and fail-open: an ordinary exception from
`telemetry_sink.emit` is swallowed and never changes the returned business
outcome, the stored idempotency outcome, or the accepted audit event. This
holds even on the withheld path: when audit or completion has already failed
ordinarily, `_withheld` still makes one best-effort `runtime_failed` /
`INTERNAL_ERROR` telemetry attempt before returning `WITHHELD`. "No terminal
telemetry" after an audit or completion failure therefore means no terminal
telemetry for the *original* outcome (the answer or stopped envelope that was
withheld) is ever emitted — not that telemetry is skipped altogether.

When every stage succeeds, the exact terminal ordering
(`audit.emit` before `idempotency_store.complete` before `telemetry_sink.emit`)
is observable end to end using one shared call journal across the three
fakes; the ordered suffix of that journal, starting at the first audit entry,
is exactly `("audit", "complete", "telemetry")`.

### Cancellation behavior

`asyncio.CancelledError` raised while blocked in audit emission, idempotency
completion, or terminal telemetry always propagates unchanged out of
`run_idempotent_fast_document`. WS-004B never shields, suppresses, or
converts a cancellation into a terminal outcome, and never starts a
background task, retry loop, or cleanup step to run after cancellation.
Cancellation and other programming defects rely entirely on the future
distributed store's lease expiration policy, not on any in-process recovery
logic.

This includes cancellation while blocked specifically in terminal telemetry,
after the audit event has already been accepted and idempotency completion
has already succeeded and stored the terminal artifact: the
`CancelledError` still propagates unchanged, and a subsequent retry of the
same request replays the already-stored terminal object by identity, with no
repeated authorization, orchestration, capability execution, finalization,
audit, or completion.

## Known limitations

- All ports and sinks in this closure are exercised only through in-memory
  test fakes (`tests/support/walking_skeleton_closure_fakes.py` plus the
  existing WS-002/WS-003A/WS-003B/WS-004A fixture and fake modules). No real
  adapter has been built or validated.
- Concurrency behavior is validated only for two single-process async tasks
  sharing one in-memory fake idempotency store; it does not validate
  multi-process or multi-replica behavior, which depends on the future
  distributed store's real locking and lease semantics.
- Performance characteristics (latency, throughput, memory under load) are
  explicitly deferred to PERF-001 and are not measured or claimed here.
- Coverage, lint, and type-checking claims in this delivery are limited to
  what was actually executed in the authoring environment; see the patch's
  closing block for exactly which tools were run.

## Department-isolation compatibility

This package adds no department domain model, no department configuration
surface, and no department-name parsing. It preserves every existing
department-isolation invariant of the reused stages: no global source
fallback, no cross-department evidence merging, no source-label
authorization, no scope broadening after finalization, no resolver calls
during terminal closure, and no evidence inspection in the audit event or
telemetry record it constructs. WS-004B consumes the already-trusted
`FinalAnswer` exactly as produced by `finalize_pending_answer`, without
reconstructing or altering its citations.

## Control Plane boundary

Future department selection remains entirely outside this package:

```
Admin Website
  -> Department-aware Control Plane
  -> immutable RuntimeSnapshot
  -> authorization-filtered evidence
  -> trusted finalization
  -> WS-004B terminal closure
```

WS-004B only ever consumes an already-constructed `RuntimeContext` and
`RuntimeSnapshot`; it has no opinion on how either one was assembled.

## Performance work deferred to PERF-001

No performance tuning, load testing, or capacity planning is in scope for
this package. All such work is deferred to PERF-001.
