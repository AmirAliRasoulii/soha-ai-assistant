# StepResult 1.0.0

Status: Accepted and implemented as a bounded baseline

Owner: Capability Execution Boundary

Schema identity: `urn:ai-assistant:contracts:step-result:1.0.0`

JSON Schema dialect: `https://json-schema.org/draft/2020-12/schema`


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation was
accepted at commit `8d94c6a`.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| Capability execution results carry no authorization decision of their own. A successful step never implies the retrieved units were eligible; eligibility is decided before retrieval | Unchanged rule |
| No typed evidence-eligibility validator exists, so per-unit eligibility is not yet contractually re-verified at this boundary (audit finding G-007). The future deterministic validation must cover authorized scope membership, organization, classification ceiling, source active state, source revision eligibility, source digest, effective time, authority, the `SUPERSEDES` / `SUPPLEMENTS` relation, and current revocation state | AI-003 with AI-006 |
| Post-retrieval checks remain defense in depth only; their absence never widens a filter | Unchanged rule |
## Purpose

`StepResult` is the immutable, validated result envelope produced after one
planned capability step attempt. It records what the attempt produced, what it
failed to produce, whether another attempt is permitted, and which provider
neutral implementation produced the outcome. It carries controlled metadata and
immutable references only.

## AI Core boundary

This repository is the pure, provider-neutral AI Core. `StepResult` is not:

- an upstream provider response;
- a raw database result;
- a raw retrieval response;
- an arbitrary typed-output dictionary;
- a planner message;
- an `ExecutionPlan`;
- an Evidence object;
- a retry loop;
- an executor;
- an HTTP response;
- an exception object;
- a logging record;
- a provider-specific result.

The contract performs structural validation only. It never executes a step,
never retries, and never dereferences a plan, an artifact, or an evidence
record.

## Root fields

| Field | Type | Rules |
| --- | --- | --- |
| `schema_version` | `Final[Literal["1.0.0"]]` | default `"1.0.0"`; any other value is rejected |
| `result_id` | UUID4 | version 4 enforced |
| `request_id` | UUID4 | version 4 enforced |
| `plan_id` | UUID4 | version 4 enforced; never dereferenced |
| `step_id` | canonical code | 1..128, `^[a-z][a-z0-9._:-]*$` |
| `runtime_snapshot_id` | UUID4 | version 4 enforced |
| `correlation_id` | UUID4 | AI Core correlation primitive |
| `completed_at` | UtcDateTime | aware input required; normalized to UTC |
| `status` | StepStatus | `success`, `partial`, `failed` |
| `typed_outputs` | tuple of StepTypedOutputRef | default `()`, maximum 16, unique by `fact_id`, order preserving |
| `missing_fact_ids` | tuple of canonical codes | default `()`, maximum 16, unique, order preserving |
| `evidence_refs` | tuple of StepEvidenceRef | default `()`, maximum 32, unique by `evidence_id`, order preserving |
| `latency_ms` | strict integer | 0..2147483647; booleans rejected |
| `retry` | StepRetryMetadata | required |
| `failure_code` | ErrorCode or null | default null |
| `internal_detail_ref` | UUID4 or null | default null; opaque reference to a protected record |
| `provenance` | StepProvenance | required |

Missing collections become empty tuples. Explicit null collections are
rejected. No collection is sorted automatically.

## Nested model: StepTypedOutputRef

| Field | Type | Rules |
| --- | --- | --- |
| `fact_id` | canonical code | 1..128, controlled pattern |
| `value_type` | canonical code | controlled fact-type code |
| `data_scope` | FactDataScope | `general` or `personal` |
| `schema_ref` | opaque artifact reference | 1..256, non-blank, no NUL, no surrounding whitespace |
| `value_ref` | opaque artifact reference | preserved exactly as accepted |
| `sha256` | digest | exactly 64 lowercase hexadecimal characters |

## Nested model: StepEvidenceRef

| Field | Type | Rules |
| --- | --- | --- |
| `evidence_id` | UUID4 | version 4 enforced |
| `supports_fact_ids` | tuple of canonical codes | 1..16, unique, order preserving |

## Nested model: StepRetryMetadata

| Field | Type | Rules |
| --- | --- | --- |
| `attempt` | strict integer | 1..2; booleans rejected |
| `max_attempts` | strict integer | 1..2; booleans rejected |
| `retryable` | bool | retry eligibility only |
| `previous_result_id` | UUID4 or null | default null |

## Nested model: StepProvenance

| Field | Type | Rules |
| --- | --- | --- |
| `capability` | CapabilityName | reused literal catalog |
| `operation` | canonical code | controlled capability-operation code |
| `implementation_version` | SchemaVersion | stable `MAJOR.MINOR.PATCH` |
| `input_digest` | digest | 64 lowercase hexadecimal characters |

## Status catalog

| Status | Meaning |
| --- | --- |
| `success` | every intended typed output was produced and validated |
| `partial` | at least one output exists and at least one intended output is missing |
| `failed` | no usable typed output was produced |

`partial` is a first-class state. Partial success must never be represented as
`success` plus an informal message.

## Typed-output reference semantics

- the actual value is never embedded;
- `schema_ref` identifies the approved typed-output schema;
- `value_ref` identifies the validated immutable output value;
- `sha256` binds the reference to exact bytes or canonical serialized content;
- trusted execution code validates the output before the reference exists;
- the contract does not dereference, load, parse, or persist the value;
- `value`, `data`, `payload`, `content`, `json`, `typed_output` and
  `raw_output` are forbidden inside this model.

## Evidence-reference semantics

- an evidence reference points at the future Evidence contract;
- evidence content, snippets, citations and source metadata are not embedded;
- evidence identifiers are unique within one result;
- every reference supports at least one fact;
- every supported fact identifier must appear in `typed_outputs`;
- duplicate supported fact identifiers are rejected;
- reference order and supported-fact order are preserved;
- outputs are not required to carry evidence, because deterministic rule and
  calculation results may rely on provenance or upstream validated facts.

## Latency semantics

`latency_ms` records total elapsed execution time for the attempt. It is a
nonnegative strict integer and operational metadata only. It is not an SLA, a
deadline, or a scheduling instruction. `deadline_ms`, `timeout_ms`,
`started_at` and `provider_latency` are not part of this contract.

## Retry semantics

- `attempt <= max_attempts`;
- a first attempt must not reference a previous result;
- a second attempt requires `max_attempts == 2` and a previous result
  reference;
- a result must not reference itself as `previous_result_id`;
- `retryable == true` requires `attempt < max_attempts`, so the final permitted
  attempt can never be marked retryable;
- `max_attempts == 1` requires `retryable == false`.

Two total attempts express exactly one bounded retry. The model records
eligibility only; it does not schedule, delay, execute, or budget a retry.

## Failure-code semantics

The retryable `ErrorCode` values are exactly `DEPENDENCY_TIMEOUT`,
`TRANSIENT_DEPENDENCY`, `RATE_LIMITED` and `CAPACITY_REJECTED`.

When `retry.retryable` is true the status must be `partial` or `failed`, the
failure code must be one of those four codes, and another attempt must remain.
A retryable-class code may still be non-retryable when the retry budget is
exhausted, the current attempt is final, or trusted policy suppresses the
retry. `success` requires a null failure code; `partial` and `failed` require a
non-null failure code. No user-facing error text is derived here.

## Provenance semantics

Capability and operation must match the referenced `ExecutionPlan` step. The
input digest represents the validated canonical step input. The implementation
version identifies provider-neutral capability implementation behavior.
Provider model names, endpoint names, SDK objects and credentials are
forbidden. Trusted validation compares provenance against the referenced plan
and runtime snapshot; this contract cannot dereference those references.

## Success invariants

- at least one typed output;
- `missing_fact_ids` empty;
- `failure_code` null;
- `internal_detail_ref` null;
- `retry.retryable` false.

A zero-output deterministic fixed response does not create a `StepResult`.

## Partial invariants

- at least one typed output;
- at least one missing fact identifier;
- non-null failure code.

A partial result may be retryable only when every retry invariant holds.

## Failed invariants

- no typed outputs;
- at least one missing fact identifier;
- no evidence references;
- non-null failure code.

A result carrying usable typed outputs must be `partial`, never `failed`. Raw
exception text is never stored. `internal_detail_ref` may point at a protected
operational error record that this contract never loads.

## Output and missing-fact invariants

Typed-output fact identifiers are unique, missing fact identifiers are unique,
and no fact identifier appears in both collections. Both orders are preserved.
The contract cannot prove that these identifiers were declared by the
referenced plan; the future StepResultValidator must compare them with the
referenced `PlanStep`.

## ExecutionPlan binding

Trusted validation must compare the result against the referenced
`ExecutionPlan` and `PlanStep` and verify that:

- `request_id` matches;
- `runtime_snapshot_id` matches;
- `step_id` exists in the plan;
- provenance capability matches the step capability;
- provenance operation matches the step operation;
- every typed-output fact was declared by the step;
- every value type matches the declared fact type;
- every data scope matches the declared fact scope;
- every missing fact was declared by the step;
- output and missing-fact sets do not exceed the step's declared outputs;
- the attempt count respects the route and plan retry budget.

The Pydantic contract cannot dereference `plan_id` and cannot independently
prove these relationships. `ExecutionPlan` and `PlanStep` are never embedded.

## Validation-before-binding flow

Before a `StepTypedOutputRef` exists, trusted capability-boundary code must:

1. validate the raw upstream response;
2. map it into an approved typed-output contract;
3. reject unexpected fields;
4. apply size and security limits;
5. serialize it canonically;
6. calculate the SHA-256 digest;
7. store or register it through a provider-neutral port;
8. construct the immutable reference.

The planner receives only validated typed references and controlled status
metadata. The planner must never receive raw database rows, raw SQL output, raw
search-engine hits, HTML, provider JSON, SDK response objects, exception
messages, or stack traces.

## Trace correlation

`correlation_id` is the AI Core correlation primitive. W3C `traceparent`, span
identifiers and telemetry-vendor identifiers belong to operational adapters and
are deferred.

## Trust boundary

| Layer | Responsibility |
| --- | --- |
| Capability adapter | validates and maps raw upstream responses into approved typed outputs |
| Typed-output registry | stores validated values and returns opaque references and digests |
| Trusted execution boundary | constructs the immutable `StepResult` envelope |
| StepResultValidator | verifies plan, provenance, fact, scope and retry-budget consistency |
| Orchestrator | decides what happens next based on status, missing facts and retry eligibility |

Model-produced data remains untrusted until deterministic validation has
completed.

## Security restrictions

Typed-output and evidence references may point at personal or confidential
data. The contract must never contain actual personal values, user message
text, raw capability output, provider payloads, SQL, credentials, URLs,
filesystem paths, or free-form errors. `data_scope == "personal"` labels output
semantics only and grants no access. Authorization must already have completed
and the referenced plan must have allowed the capability and scope.

## Retention

- this contract does not authorize persistence;
- `StepResult` contains controlled metadata and immutable references, not
  actual output values;
- result envelopes may be retained for replay, audit or evaluation only under
  approved policy;
- actual output payloads, evidence content and protected internal error records
  have separate retention and access controls;
- raw upstream responses, provider payloads, credentials, SQL, exception
  messages and stack traces must never be copied into `StepResult`;
- telemetry should normally use result ID, plan ID, step ID, status,
  capability, operation, failure code, attempt, latency and correlation ID.

## Compatibility

`StepResult` 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads;
- adding, removing or renaming a field is major;
- adding or changing a status literal is major;
- changing success, partial, failure, retry, provenance, output-reference,
  evidence-reference, digest, plan-binding or privacy semantics is major;
- changing `ErrorCode` itself follows the ErrorEnvelope contract's
  compatibility rules;
- adding controlled capability-operation, fact-type or schema-reference catalog
  entries does not change this JSON Schema;
- version 1.0.0 becomes immutable after approval.

## Valid example: success

```json
{
  "schema_version": "1.0.0",
  "result_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "plan_id": "33333333-3333-4333-8333-333333333333",
  "step_id": "step.retrieve",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "correlation_id": "55555555-5555-4555-8555-555555555555",
  "completed_at": "2026-01-01T08:30:00Z",
  "status": "success",
  "typed_outputs": [
    {
      "fact_id": "fact.document",
      "value_type": "type.document",
      "data_scope": "general",
      "schema_ref": "schema:type.document:1.0.0",
      "value_ref": "artifact:0f2c1b",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "missing_fact_ids": [],
  "evidence_refs": [
    {
      "evidence_id": "66666666-6666-4666-8666-666666666666",
      "supports_fact_ids": ["fact.document"]
    }
  ],
  "latency_ms": 120,
  "retry": {
    "attempt": 1,
    "max_attempts": 2,
    "retryable": false,
    "previous_result_id": null
  },
  "failure_code": null,
  "internal_detail_ref": null,
  "provenance": {
    "capability": "document_retrieval",
    "operation": "document.retrieve",
    "implementation_version": "1.0.0",
    "input_digest": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
  }
}
```

## Valid example: partial

```json
{
  "schema_version": "1.0.0",
  "result_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "plan_id": "33333333-3333-4333-8333-333333333333",
  "step_id": "step.retrieve",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "correlation_id": "55555555-5555-4555-8555-555555555555",
  "completed_at": "2026-01-01T08:30:00Z",
  "status": "partial",
  "typed_outputs": [
    {
      "fact_id": "fact.document",
      "value_type": "type.document",
      "data_scope": "general",
      "schema_ref": "schema:type.document:1.0.0",
      "value_ref": "artifact:0f2c1b",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    }
  ],
  "missing_fact_ids": ["fact.summary"],
  "evidence_refs": [],
  "latency_ms": 940,
  "retry": {
    "attempt": 1,
    "max_attempts": 2,
    "retryable": true,
    "previous_result_id": null
  },
  "failure_code": "DEPENDENCY_TIMEOUT",
  "internal_detail_ref": "88888888-8888-4888-8888-888888888888",
  "provenance": {
    "capability": "document_retrieval",
    "operation": "document.retrieve",
    "implementation_version": "1.0.0",
    "input_digest": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
  }
}
```

## Valid example: failed

```json
{
  "schema_version": "1.0.0",
  "result_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "plan_id": "33333333-3333-4333-8333-333333333333",
  "step_id": "step.retrieve",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "correlation_id": "55555555-5555-4555-8555-555555555555",
  "completed_at": "2026-01-01T08:30:00Z",
  "status": "failed",
  "typed_outputs": [],
  "missing_fact_ids": ["fact.document"],
  "evidence_refs": [],
  "latency_ms": 1500,
  "retry": {
    "attempt": 2,
    "max_attempts": 2,
    "retryable": false,
    "previous_result_id": "77777777-7777-4777-8777-777777777777"
  },
  "failure_code": "RATE_LIMITED",
  "internal_detail_ref": "88888888-8888-4888-8888-888888888888",
  "provenance": {
    "capability": "official_search",
    "operation": "official.search_allowlisted",
    "implementation_version": "1.0.0",
    "input_digest": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
  }
}
```

## Representative invalid examples

| Violation | Reason |
| --- | --- |
| `status: "success"` with empty `typed_outputs` | a successful step must produce at least one typed fact |
| `status: "success"` with a failure code | success cannot carry an error |
| `status: "failed"` with typed outputs | usable outputs require `partial` |
| `status: "failed"` with evidence references | failed results carry no evidence |
| `status: "partial"` without missing facts | partial requires a missing intended output |
| identical fact identifier in outputs and `missing_fact_ids` | a fact cannot be produced and missing |
| duplicate `fact_id` in `typed_outputs` | outputs are unique by fact |
| evidence supporting an unknown fact | evidence supports declared outputs only |
| `attempt: 2` without `previous_result_id` | a retry must reference its predecessor |
| `attempt: 2` with `retryable: true` | the final permitted attempt is never retryable |
| `retryable: true` with `POLICY_REJECTED` | only transient codes are retryable |
| `previous_result_id` equal to `result_id` | a result cannot be its own predecessor |
| uppercase `sha256` | digests are exactly 64 lowercase hexadecimal characters |
| `" artifact:1 "` as `value_ref` | references are preserved exactly and never trimmed |
| naive `completed_at` | an aware timestamp is required |
| `latency_ms: true` | booleans are rejected by strict integer validation |
| `prompt`, `sql`, `stack_trace` or `api_key` | forbidden field names |

## Non-goals

- executing, scheduling, delaying or budgeting a retry;
- storing or resolving output values, evidence content or error records;
- generating user-facing text;
- modelling provider responses, HTTP responses or logging records;
- proving plan, authorization or runtime consistency without a validator.

## Deferred implementation work

- StepResultValidator;
- `ExecutionPlan` and `PlanStep` binding verification;
- typed-output schema catalog;
- typed-output artifact registry and resolver port;
- output canonicalization;
- capability response adapters;
- protected internal error-record integration;
- retry-budget binding;
- Evidence materialization;
- StepResult-to-Evidence linking;
- replay evaluator;
- latency and outcome metrics;
- integration with `CapabilityRequest` and the Orchestrator.
