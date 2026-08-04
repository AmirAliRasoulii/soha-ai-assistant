# AuditEvent 1.0.0

Status: Accepted and implemented as a bounded baseline
Owner: Chat Runtime Audit Boundary


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation acceptance
becomes effective when the CP-000R commit is reviewed and merged.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| A `runtime.turn.completed` audit event emitted before durable idempotency completion is a **pre-completion** signal. It is not proof of durable turn completion, and durable completion is **not** implemented today (audit finding C-006, HIGH audit semantics) | CP-001 for typed audit contracts and versioning, CP-009 for application-service audit semantics and emission, CP-012 for durable persistence and delivery adapters, AI-002 for request and run lifecycle and terminal transitions, AI-007 for answer-finalization and publication hooks |
| The full outcome taxonomy required by the architecture is not yet typed here (audit finding G-012). The required outcomes are `answered`, `partial`, `clarification_required`, `abstained`, `policy_rejected`, `authorization_denied`, `failed`, and `authorization_denied` must remain distinct from `policy_rejected` | CP-001 for the typed contract, CP-009 for emission semantics, AI-002 for terminal lifecycle transitions, AI-007 for finalization hooks |
| Runtime lineage is not fully carried. The complete future lineage requirement is organization, actor scope, subject, time scope, source version, policy version, `ConfigurationRelease`, `RuntimeSnapshot`, and run or request identifier. `AuditEvent 1.0.0` does not contain that complete lineage, and this document does not claim that it does (audit finding G-013) | CP-001 for the typed lineage contract, CP-009 for emission, CP-012 for durable persistence and delivery, AI-002 for run lifecycle, AI-007 for publication hooks |
| Audit remains fail-closed; telemetry and evaluation export remain fail-open. The two must not be conflated | Unchanged rule |
## Purpose

`AuditEvent` is the canonical AI Core contract for a safe, minimal, replayable
audit fact emitted by trusted AI runtime code. It carries references and
controlled codes describing what happened, to what, by whom, and with what
outcome, without carrying any raw diagnostic, prompt, model, provider, user,
or secret content.

## AI Core boundary

This contract defines only the immutable typed audit payload. It does not
implement:

- CloudEvents SDK integration or a CloudEvents model;
- message broker publishing (Kafka, RabbitMQ, Celery, or other queue clients);
- database or filesystem persistence, or append-only storage;
- retry or delivery behavior, or an audit repository;
- logging or tracing SDK integration;
- HTTP transport or background workers;
- encryption, signing, or retention execution;
- audit record lookup.

CloudEvents wrapping, delivery, storage, integrity, and retention are
operational adapter responsibilities. See
`docs/adr/ADR-002-audit-event-and-cloudevents-boundary.md`.

## Field tables

### AuditActorRef

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `actor_type` | `"user"` \| `"service"` \| `"system"` | yes | trusted identity kind |
| `principal_id` | UUID4 or null | conditional | required for `user`/`service`, must be null for `system` |
| `security_context_id` | UUID4 or null | conditional | required for `user`/`service`, must be null for `system` |

### AuditResourceRef

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `resource_type` | canonical code | yes | e.g. `document`, `conversation` |
| `resource_id` | string, 1-256 | yes | opaque, preserved exactly, not parsed |
| `classification` | canonical code or null | no | default null |

### AuditEvent

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `schema_version` | literal `"1.0.0"` | default | `Final[Literal["1.0.0"]]` |
| `event_id` | UUID4 | yes | delivery deduplication identity |
| `event_type` | canonical code | yes | e.g. `runtime.completed` |
| `occurred_at` | UtcDateTime | yes | normalized to UTC |
| `producer` | canonical code | yes | producing component |
| `correlation_id` | UUID4 | yes | request/run correlation |
| `request_id` | UUID4 | yes | originating request |
| `actor` | AuditActorRef | yes | trusted identity reference |
| `action` | canonical code | yes | audited action |
| `resource` | AuditResourceRef or null | no | default null |
| `outcome` | `"success"` \| `"denied"` \| `"failed"` | yes | terminal outcome of the action |
| `reason_codes` | tuple of canonical codes, max 16 | no | default empty, unique, order preserved |
| `authorization_decision_id` | UUID4 or null | conditional | required when `outcome = denied` |
| `runtime_snapshot_id` | UUID4 | yes | required for every outcome |
| `error_id` | UUID4 or null | conditional | required when `outcome = failed`, forbidden otherwise |
| `internal_detail_ref` | UUID4 or null | no | opaque, never resolved by this contract |
| `retention_class` | canonical code | yes | audit retention policy class |
| `sensitivity` | canonical code | yes | audit sensitivity class |

## Actor semantics

- `user` and `service` actors must carry both `principal_id` and
  `security_context_id`.
- `system` actors must carry neither field.
- Mixed or partial identity references (for example one identifier present
  and the other null) are rejected.
- The contract stores no email, display name, role list, group list, token,
  session, or provider claim; those live in `SecurityPrincipalContext`, not
  in the audit payload.

## Resource semantics

- `resource_id` is an opaque string. It is never parsed as a URL, filesystem
  path, SQL fragment, or query text.
- The accepted value is preserved exactly; blank, NUL-containing, or
  leading/trailing-whitespace values are rejected.
- `resource` may be entirely absent when the audited action has no single
  affected resource.

## Outcome invariants

| Outcome | `error_id` | `reason_codes` | `authorization_decision_id` |
| --- | --- | --- | --- |
| `success` | must be null | may be empty | may be present or absent |
| `denied` | must be null | at least one required | required |
| `failed` | required | at least one required | may be present or absent |

For every outcome, `runtime_snapshot_id`, `request_id`, and `correlation_id`
are required, and `internal_detail_ref`, when present, is an opaque UUID
only. No value is derived or repaired automatically.

## Event type semantics

`event_type` is a controlled, namespaced canonical code, not a free user
string. Examples include `runtime.request.accepted`,
`runtime.authorization.denied`, `runtime.completed`, `runtime.failed`, and
`capability.completed`. Version 1.0.0 intentionally does not define a closed
enum. The allowed event types and their operational meaning belong to a
future versioned Audit Event Catalog.

## Trust boundary

- Only trusted server-side runtime code constructs an `AuditEvent`.
- Model output is never a trusted source for audit fields.
- Client input may influence the audited action, but a client cannot
  construct audit fields directly.
- A successful model validation does not prove that the event was
  persisted; persistence is an operational adapter concern.

## Sensitive-data restrictions

All models reject unknown fields. The following names, among others, must
never be declared contract fields: `message`, `raw_message`,
`normalized_query`, `prompt`, `system_prompt`, `completion`, `response`,
`answer`, `citation_text`, `exception`, `stack_trace`, `traceback`,
`raw_error`, `provider_response`, `provider_request`, `model_input`,
`model_output`, `token`, `access_token`, `api_key`, `secret`, `password`,
`credentials`, `email`, `display_name`, `roles`, `groups`, `session`,
`cookie`, `headers`, `http_status`, `sql`, `query`, `url`, `endpoint`,
`filesystem_path`, `trace_id`, `span_id`, `cloud_event`, `specversion`,
`source`, `datacontenttype`, `dataschema`, `data`, `metadata`, `attributes`.

`internal_detail_ref` is opaque and never contains or encodes raw detail.

## Audit, log, trace, and error separation

- `AuditEvent` is not a log record, not a trace span, and not an exception
  envelope.
- `AuditEvent` is not a CloudEvents transport envelope; it is the payload a
  CloudEvents envelope carries.
- Audit, logs, and traces remain separate but correlated through
  `correlation_id` and `request_id`.
- `error_id` references an `ErrorEnvelope` occurrence without embedding it.

## Duplicate and ordering semantics

- `event_id` is the delivery deduplication identity. Consumers must treat
  duplicate deliveries carrying the same `event_id` as the same logical
  event.
- Delivery order is not guaranteed by this contract.
- Append-only persistence is not enforceable by Pydantic and is deferred to
  the operational storage layer.

## Retention statement

- This contract does not authorize persistence.
- Retention of the underlying audit record is governed by audit and
  operational policy, not by this schema.
- The payload contains references and controlled codes only.
- Raw prompts, responses, messages, exceptions, credentials, and provider
  payloads must not be copied into the event.
- `internal_detail_ref` is opaque and contains no raw detail itself.

## CloudEvents mapping boundary

Operational adapters may wrap a serialized `AuditEvent` in a CloudEvents 1.0
envelope for asynchronous delivery. See
`docs/adr/ADR-002-audit-event-and-cloudevents-boundary.md` for the full
mapping and boundary decision. No CloudEvents field or SDK exists in this
repository.

## Compatibility

`AuditEvent` 1.0.0 is closed:

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing, or renaming a field is a major change.
- Changing outcome, identity, correlation, retention, sensitivity, or
  cross-field semantics is a major change.
- Adding new controlled `event_type` values through the future Audit Event
  Catalog does not change this JSON Schema.
- Version 1.0.0 becomes immutable after approval.

## Valid examples

### Success

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "runtime.completed",
  "occurred_at": "2026-01-01T12:00:00+03:30",
  "producer": "runtime",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "request_id": "33333333-3333-4333-8333-333333333333",
  "actor": {
    "actor_type": "user",
    "principal_id": "44444444-4444-4444-8444-444444444444",
    "security_context_id": "55555555-5555-4555-8555-555555555555"
  },
  "action": "runtime.request",
  "outcome": "success",
  "runtime_snapshot_id": "66666666-6666-4666-8666-666666666666",
  "retention_class": "standard",
  "sensitivity": "internal"
}
```

### Denied

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "runtime.authorization.denied",
  "occurred_at": "2026-01-01T12:00:00+03:30",
  "producer": "runtime",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "request_id": "33333333-3333-4333-8333-333333333333",
  "actor": {
    "actor_type": "user",
    "principal_id": "44444444-4444-4444-8444-444444444444",
    "security_context_id": "55555555-5555-4555-8555-555555555555"
  },
  "action": "runtime.request",
  "outcome": "denied",
  "reason_codes": ["policy.denied"],
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "66666666-6666-4666-8666-666666666666",
  "retention_class": "standard",
  "sensitivity": "internal"
}
```

### Failed

```json
{
  "event_id": "11111111-1111-4111-8111-111111111111",
  "event_type": "runtime.failed",
  "occurred_at": "2026-01-01T12:00:00+03:30",
  "producer": "runtime",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "request_id": "33333333-3333-4333-8333-333333333333",
  "actor": { "actor_type": "system" },
  "action": "runtime.request",
  "outcome": "failed",
  "reason_codes": ["dependency.timeout"],
  "error_id": "88888888-8888-4888-8888-888888888888",
  "runtime_snapshot_id": "66666666-6666-4666-8666-666666666666",
  "retention_class": "standard",
  "sensitivity": "internal"
}
```

## Representative invalid examples

- A `denied` event with no `authorization_decision_id`.
- A `failed` event with no `error_id`.
- A `success` event that also carries an `error_id`.
- A `user` actor missing `security_context_id`.
- A `system` actor carrying `principal_id`.
- An event with `reason_codes` containing a duplicate value.
- An event with 17 `reason_codes` entries.
- An event carrying an unknown field such as `prompt`, `stack_trace`, or
  `access_token`.

## Non-goals

- This contract does not define an Audit Event Catalog of allowed
  `event_type` values.
- This contract does not implement CloudEvents wrapping, message broker
  delivery, persistence, or retention execution.
- This contract does not implement logging, tracing, encryption, or
  signing.
- This contract does not decide how `AuditEvent` relates to `FinalAnswer`,
  `StepResult`, or configuration-change auditing; that integration is
  deferred.
