# ErrorEnvelope 1.0.0

Status: Accepted and implemented as a bounded baseline
Owner: Chat Runtime Error Boundary
Schema identity: `urn:ai-assistant:contracts:error-envelope:1.0.0`
JSON Schema dialect: `https://json-schema.org/draft/2020-12/schema`


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation acceptance
becomes effective when the CP-000R commit is reviewed and merged.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| Clarification and abstention are currently surfaced through this envelope. That is a deliberate **transitional** arrangement (audit finding C-005); clarification and abstention are legitimate answer outcomes, not errors | AI-002 with AI-006 |
| `RouteDecision 1.0.0` already provides a terminal `deny` lane. An authorization deny happens before routing and reaches the caller as `UNAUTHORIZED`; a route or policy deny is `RouteDecision(lane="deny")` and reaches the caller as `POLICY_REJECTED`. What is missing is complete terminal handling of `RouteDecision(lane="deny")` in the bounded Runtime and the Walking Skeleton (`DEF-118`), not a contract field | AI-002 |
| `UNAUTHORIZED` and `POLICY_REJECTED` must remain distinguishable and must never be collapsed into one generic failure, and no error message may leak the existence or metadata of unauthorized content | Unchanged rule |
## Purpose

`ErrorEnvelope` is the single canonical internal representation of a failed or
non-successful outcome inside the AI Core. It carries stable machine-readable
error semantics, a safe localization key, bounded retry eligibility, request and
run correlation, and an opaque reference to an internal error record. It carries
no raw implementation detail.

Every component of the AI Core that reports an error condition produces this
contract. Transport adapters, product surfaces, and operational tooling consume
it.

## AI Core boundary

This contract defines types and validation only. It does not implement:

- HTTP status mapping;
- RFC 9457 `type`, `title`, `status`, `detail`, or `instance` members;
- response headers or `application/problem+json` serialization;
- any web framework, exception middleware, or transport integration;
- logging, tracing SDK integration, metrics, or alerting;
- error persistence, error-record storage, or error-detail lookup;
- localization rendering or message catalogs;
- retry execution or retry policy.

See `docs/adr/ADR-001-error-envelope-and-http-problem-details.md` for the HTTP
Problem Details boundary decision.

## Structure

```
ErrorEnvelope
  schema_version   literal "1.0.0"
  error_id         UUID v4
  correlation_id   UUID v4
  error            DomainError

DomainError
  code                 ErrorCode
  safe_message_key     str
  retryable            bool
  internal_detail_ref  UUID v4
```

`DomainError` is a nested immutable value object. It has no `schema_version` of
its own and inherits the root envelope schema version.

### ErrorEnvelope fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `schema_version` | literal `"1.0.0"` | no, defaults to `"1.0.0"` | any other value is rejected |
| `error_id` | UUID version 4 | yes | unique occurrence identifier; other UUID versions rejected |
| `correlation_id` | UUID version 4 | yes | request and run correlation identifier; other UUID versions rejected |
| `error` | `DomainError` | yes | closed nested object |

Unknown fields are rejected at the root. The following members are deliberately
absent and are rejected: `occurred_at`, `request_id`, `run_id`, `trace_id`,
`http_status`, `title`, `detail`, `instance`, `headers`, `retry_after`,
`metadata`, `context`, `attributes`. They belong to future contracts or to
adapters outside the AI Core.

### DomainError fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `code` | `ErrorCode` | yes | exactly one of the fourteen approved codes |
| `safe_message_key` | string, 1 to 128 characters | yes | must equal `error.<lowercase code>`; only lowercase ASCII letters, digits, dots, underscores, and hyphens; must begin with `error.` |
| `retryable` | boolean | yes | must match the fixed retryability of the code |
| `internal_detail_ref` | UUID version 4 | yes | opaque reference to an internal error record |

Unknown fields are rejected inside `DomainError` as well.

## Error code catalog

Version 1.0.0 permits exactly these codes. Custom, provider-specific, and
extension codes are not permitted.

| Code | Meaning | Message key | Retryable |
| --- | --- | --- | --- |
| `INVALID_INPUT` | The request payload violated an input contract. | `error.invalid_input` | false |
| `UNAUTHENTICATED` | No trusted identity was established. | `error.unauthenticated` | false |
| `UNAUTHORIZED` | The trusted identity is not permitted to perform the operation. | `error.unauthorized` | false |
| `AMBIGUOUS_REQUEST` | The request cannot be resolved to a single intent. | `error.ambiguous_request` | false |
| `POLICY_REJECTED` | A policy decision denied the operation. | `error.policy_rejected` | false |
| `NO_EVIDENCE` | No sufficient grounded evidence was available. | `error.no_evidence` | false |
| `CONFLICTING_EVIDENCE` | Available evidence is mutually inconsistent. | `error.conflicting_evidence` | false |
| `SCHEMA_INVALID` | A structured output or internal payload failed schema validation. | `error.schema_invalid` | false |
| `DEPENDENCY_TIMEOUT` | A dependency did not answer within its deadline. | `error.dependency_timeout` | true |
| `TRANSIENT_DEPENDENCY` | A dependency failed in a transient, recoverable way. | `error.transient_dependency` | true |
| `BUDGET_EXCEEDED` | A cost, token, or step budget was exhausted. | `error.budget_exceeded` | false |
| `RATE_LIMITED` | A rate limit was reached. | `error.rate_limited` | true |
| `CAPACITY_REJECTED` | The system shed load rather than accept the work. | `error.capacity_rejected` | true |
| `INTERNAL_ERROR` | An unclassified internal failure occurred. | `error.internal_error` | false |

## Safe message key semantics

The accepted value must equal `f"error.{code.lower()}"` exactly. The contract
performs no trimming, lowercasing, repair, or normalization: a padded, uppercase,
or mismatched key is rejected rather than corrected, and an accepted value is
preserved byte for byte.

The key is a stable identifier, not a message. It contains no user text, no
provider text, and no interpolated values. Resolving the key to a localized
Persian or English message is the responsibility of a presentation layer outside
the AI Core.

## Retryability semantics

`retryable = true` means only that the same operation is eligible for a bounded,
policy-controlled retry. It never authorizes an immediate retry, an unbounded
retry, or a retry without backoff. Exactly these codes are retryable:

```
DEPENDENCY_TIMEOUT
TRANSIENT_DEPENDENCY
RATE_LIMITED
CAPACITY_REJECTED
```

All other codes are non-retryable. The contract rejects any inconsistent
code and retryability combination in either direction, so a producer cannot
claim a retry that policy does not allow or hide one that it does. Retry
execution, backoff, jitter, budgets, and circuit breaking are implemented
elsewhere.

## Terminal outcome semantics

These codes can represent legitimate product-domain outcomes and do not always
imply an HTTP error response:

```
AMBIGUOUS_REQUEST
POLICY_REJECTED
NO_EVIDENCE
CONFLICTING_EVIDENCE
```

For example, `NO_EVIDENCE` may later appear inside a valid `FinalAnswer` with an
`abstain` terminal outcome, and `AMBIGUOUS_REQUEST` may drive a clarification
turn. Therefore:

```
ErrorCode is not an HTTP status code.
```

The HTTP adapter decides whether an occurrence becomes a successful domain
response, a deny, clarify, or abstain `FinalAnswer`, or an RFC 9457 problem
response. That decision is not implemented in this task.

## Trusted producer rules

- Only trusted runtime code inside the AI Core creates an `ErrorEnvelope`.
- No client may supply `error_id`, `correlation_id`, `code`, `retryable`, or
  `internal_detail_ref`. Client-supplied values must never be echoed into the
  envelope.
- Model output is never a trusted source for any error field. A model may not
  choose an error code, a message key, or a retry flag.
- Provider exceptions must be classified and sanitized into one approved code
  before an envelope is constructed. The raw exception is never carried.
- A Pydantic `ValidationError` is never exposed directly. It is classified as
  `INVALID_INPUT` or `SCHEMA_INVALID` and its detail is recorded internally.

## Artifact of the internal detail reference

`internal_detail_ref` is an opaque UUID version 4. It is not an error message, an
exception, a URL, a filesystem path, a trace dump, a provider response, or an
HTTP `instance` value, and no raw detail may be encoded into it. This contract
neither resolves nor persists the reference.

## Sensitive data restrictions

Both models are closed, so any unknown field is rejected at every level. The
following names in particular are rejected and never appear in the generated
schema:

```
message safe_message exception exception_type stack_trace traceback cause debug
raw_error raw_response provider_response provider_error sql query system_prompt
prompt api_key access_token token secret password credentials http_status
headers type title detail instance endpoint url filesystem_path email user_name
```

No secret, credential, token, prompt, SQL statement, provider payload, URL,
filesystem location, stack trace, or personal identifier belongs in this
contract.

## Retention

- This contract does not authorize persistence of anything.
- Retention of the internal error record referenced by `internal_detail_ref` is
  governed by audit and operational policy defined elsewhere.
- `internal_detail_ref` contains no raw diagnostic data itself.
- Messages, prompts, tokens, credentials, and provider payloads must never be
  copied into this contract, whether in transit or at rest.

## Compatibility

`ErrorEnvelope 1.0.0` is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing, or renaming a field requires a new major schema version.
- Adding an error code is a major change for this closed version.
- Changing retryability, the message-key mapping, security meaning, or terminal
  outcome semantics is a major change.
- Version 1.0.0 becomes immutable after approval.

## Valid examples

A non-retryable input failure:

```json
{
  "schema_version": "1.0.0",
  "error_id": "11111111-1111-4111-8111-111111111111",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "error": {
    "code": "INVALID_INPUT",
    "safe_message_key": "error.invalid_input",
    "retryable": false,
    "internal_detail_ref": "33333333-3333-4333-8333-333333333333"
  }
}
```

A retryable dependency timeout:

```json
{
  "schema_version": "1.0.0",
  "error_id": "44444444-4444-4444-8444-444444444444",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "error": {
    "code": "DEPENDENCY_TIMEOUT",
    "safe_message_key": "error.dependency_timeout",
    "retryable": true,
    "internal_detail_ref": "55555555-5555-4555-8555-555555555555"
  }
}
```

A domain abstention that an adapter may return as a successful response:

```json
{
  "schema_version": "1.0.0",
  "error_id": "66666666-6666-4666-8666-666666666666",
  "correlation_id": "22222222-2222-4222-8222-222222222222",
  "error": {
    "code": "NO_EVIDENCE",
    "safe_message_key": "error.no_evidence",
    "retryable": false,
    "internal_detail_ref": "77777777-7777-4777-8777-777777777777"
  }
}
```

## Representative invalid examples

| Payload fragment | Rejected because |
| --- | --- |
| `"schema_version": "1.1.0"` | only the literal `1.0.0` is accepted |
| `"code": "PROVIDER_ERROR"` | not in the approved catalog |
| `"code": "INVALID_INPUT", "safe_message_key": "error.no_evidence"` | key does not match the code |
| `"safe_message_key": "error.INVALID_INPUT"` | uppercase is rejected, not lowercased |
| `"safe_message_key": " error.invalid_input"` | padded values are rejected, not trimmed |
| `"safe_message_key": "error.invalid_input\u0000"` | NUL is rejected by the key pattern |
| `"code": "RATE_LIMITED", "retryable": false` | the code is always retryable |
| `"code": "INTERNAL_ERROR", "retryable": true` | the code is never retryable |
| `"error_id": "44444444-4444-1444-8444-444444444444"` | UUID version 1 is not accepted |
| `"internal_detail_ref": null` | the reference is required |
| `"message": "database timeout on host db-1"` | unknown field, raw detail |
| `"http_status": 503` | HTTP members do not exist in the AI Core |
| `"stack_trace": "..."` | unknown field, raw diagnostic data |

## HTTP mapping boundary

This contract is transport-neutral. An HTTP adapter outside the AI Core maps an
occurrence to RFC 9457 Problem Details, chooses the status code, renders the
localized `title` and `detail`, and may expose the safe extensions `code`,
`retryable`, `correlation_id`, and `error_id`. It must never expose
`internal_detail_ref`. The exact code-to-status mapping is deferred to the API
adapter contract.

## Non-goals

- No HTTP model, status mapping, header handling, or problem+json serialization.
- No web framework, middleware, or transport binding.
- No logging, tracing, metrics, or alerting integration.
- No error persistence, retention implementation, or detail lookup service.
- No localization catalog or message rendering.
- No retry policy, backoff, or circuit breaking.
- No provider classification implementation.
- No custom or extensible error codes in 1.0.0.

## Deferred work

- HTTP Problem Details adapter and its RFC 9457 model.
- Stable product-controlled problem type URI registry.
- Exact error-code-to-HTTP-status mapping.
- Localization catalog and rendering of message keys.
- `Retry-After` semantics and the retry policy that consumes `retryable`.
- Internal error record persistence and retention.
- Integration with `AuditEvent`.
- Integration with `FinalAnswer` and `StepResult` terminal outcomes.
