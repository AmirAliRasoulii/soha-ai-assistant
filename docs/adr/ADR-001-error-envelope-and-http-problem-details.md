# ADR-001: ErrorEnvelope and HTTP Problem Details

Status: accepted for CONTRACT-004 implementation
Date: recorded with the CONTRACT-004 implementation
Owner: Chat Runtime Error Boundary

## Context

This repository is the pure, vendor-neutral AI Core. It contains contracts and
domain logic only, with no transport, framework, storage, or provider code.

Errors must be reported consistently across every component of the core:
validation failures, authorization denials, dependency timeouts, budget
exhaustion, load shedding, and unclassified internal failures. At the same time,
the eventual public HTTP surface needs an interoperable error format, and RFC
9457 Problem Details for HTTP APIs is the current standard for that purpose. RFC
9457 obsoletes RFC 7807 and keeps the same media type,
`application/problem+json`.

Two pressures conflict. An HTTP-shaped error type would be convenient at the
edge, but it would drag status codes, localized prose, headers, and URI
references into a core that has no HTTP concept. A purely internal error type
requires a mapping step at the edge, but keeps the core transport-neutral and
testable.

A further complication: several error conditions in this product are not
failures of the HTTP request at all. Abstaining for lack of evidence, refusing
on policy grounds, or asking for clarification are legitimate product outcomes
that will usually be delivered inside a successful response.

## Decision

1. `ErrorEnvelope` is the canonical error contract inside the AI Core. Every
   internal component that reports an error condition produces it, and no
   component invents an alternative error shape.
2. HTTP adapters outside this repository will use RFC 9457 Problem Details as
   the public error representation.
3. No HTTP-specific member exists in the AI Core contract. `type`, `title`,
   `status`, `detail`, `instance`, `headers`, and `retry_after` are absent and
   are rejected as unknown fields.
4. The eventual HTTP adapter may expose safe problem-details extensions, namely
   `code`, `retryable`, `correlation_id`, and `error_id`.
5. `internal_detail_ref` must never be exposed through the public HTTP response.
   It is an internal correlation handle only.
6. HTTP `title` and `detail` are localized and rendered outside the AI Core,
   from `safe_message_key` and a message catalog. The core never emits prose.
7. HTTP `status` must match the actual HTTP response status, as required by RFC
   9457. The adapter, not the core, owns that value.
8. Product-specific problem types require stable, product-controlled type URIs.
   Type URIs are never derived automatically from an internal error code.
9. The exact error-code-to-HTTP-status mapping is deferred to the API adapter
   contract and is not implemented here.
10. Some domain outcomes may be returned through `FinalAnswer` rather than as
    non-2xx HTTP responses. `AMBIGUOUS_REQUEST`, `POLICY_REJECTED`,
    `NO_EVIDENCE`, and `CONFLICTING_EVIDENCE` are the current examples, so
    `ErrorCode` is not an HTTP status code.

No RFC 9457 Pydantic model is implemented in this repository.

## Consequences

Positive:

- The core stays transport-neutral, so the same contract serves an HTTP API, a
  queue worker, a batch job, or an internal library call.
- Error semantics are machine-readable and stable, and localization is a
  presentation concern rather than a core concern.
- Secrets, prompts, provider payloads, and stack traces have no field to travel
  in, so leakage is prevented structurally rather than by review discipline.
- Domain outcomes are not forced into HTTP failure semantics.

Negative or accepted costs:

- An explicit mapping layer must be written and maintained at the HTTP edge.
- Two representations of an error exist, and the mapping must be tested.
- Adding an error code is a major version change for the closed 1.0.0 contract,
  which makes the catalog deliberately slow to grow.
- Consumers cannot read a human-readable message from the envelope; they must
  resolve the message key.

## Alternatives considered

1. **Use RFC 9457 Problem Details directly as the internal error type.**
   Rejected: it imports HTTP status codes, URI references, and localized prose
   into a core that has no HTTP concept, and it makes non-HTTP callers model an
   HTTP response. It also invites leaking raw diagnostics into `detail`.
2. **Return raw exceptions or Pydantic `ValidationError` to callers.**
   Rejected: raw exception text carries implementation detail, provider content,
   and sometimes user data; it is unstable across library upgrades and cannot be
   safely localized.
3. **A free-form error dictionary or a `metadata` bag.**
   Rejected: an open map cannot be reviewed, cannot be schema-tested, and
   becomes the default hiding place for secrets and raw payloads.
4. **An open, extensible error-code registry with provider-specific codes.**
   Rejected for 1.0.0: provider codes leak vendor identity into the core and
   make client behavior unpredictable. A closed catalog keeps mapping total.
5. **Carry a localized message string in the envelope.**
   Rejected: it duplicates the catalog, mixes presentation into the core, and
   risks embedding user or provider text in logs and audit records.
6. **Derive retryability at the edge instead of in the contract.**
   Rejected: retry eligibility is a property of the error semantics, and
   deriving it separately in each adapter would drift.

## Security considerations

- Both models are closed, so unknown fields such as `message`, `stack_trace`,
  `provider_response`, `api_key`, `sql`, `system_prompt`, or `filesystem_path`
  are rejected rather than silently carried.
- `safe_message_key` is a stable identifier derived deterministically from the
  code. It cannot carry user text, provider text, or interpolated values.
- `internal_detail_ref` is an opaque UUID version 4. It never encodes raw detail
  and is never exposed publicly, so an attacker cannot use a public response to
  learn internal state.
- Only trusted runtime code constructs an envelope. Client input and model output
  are never trusted sources for error fields, which prevents a caller or a model
  from forging an authorization denial, a retry hint, or a correlation identifier.
- Provider exceptions must be classified and sanitized before an envelope is
  built, so provider identity and provider payloads do not reach clients.
- Retryability is validated against the code, so a producer cannot advertise an
  unbounded retry path and cannot be used to amplify load.
- The contract authorizes no persistence and no logging, so retention of the
  internal error record remains governed by audit and operational policy.

## Deferred work

- The HTTP Problem Details adapter and its RFC 9457 model, in the API layer.
- A stable product-controlled problem type URI registry.
- The exact error-code-to-HTTP-status mapping.
- The localization catalog and rendering of `safe_message_key`.
- `Retry-After` semantics and the bounded retry policy that consumes `retryable`.
- Internal error record persistence, retention, and lookup.
- Integration with `AuditEvent`.
- Integration with `FinalAnswer` and `StepResult` terminal outcomes.
