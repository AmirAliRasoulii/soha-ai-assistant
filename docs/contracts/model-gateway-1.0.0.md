# Model Gateway Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/model_gateway.py` with the
  `ModelGatewayPort` protocol in `src/ai_assistant/core/ports.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`,
  `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`
- Schema artifacts:
  - `schemas/model-invocation-request/1.0.0.schema.json` — `urn:ai-assistant:contracts:model-invocation-request:1.0.0`
  - `schemas/model-invocation-result/1.0.0.schema.json` — `urn:ai-assistant:contracts:model-invocation-result:1.0.0`
- Deferred items addressed: DEF-037 (provider-neutral model port)

## Purpose

Define the only shape in which AI Core may ask for a model completion, and the
only shape in which it may receive one, so that no provider concept, credential,
or transport detail can reach Core.

## Shapes

| Type | Purpose |
| --- | --- |
| `ModelMessage` | Bounded, sanitized role/content pair. |
| `ModelInvocationRequest` | Logical pool, purpose, messages, output budget, sampling knobs, optional structured-output schema reference, stream flag, issue/deadline instants, runtime snapshot id. |
| `ModelInvocationAttemptRef` | One bounded attempt: index, deployment reference, start instant, outcome, reason code. |
| `ProviderSelectionLineage` | Attempt sequence, selected deployment, derived `fallback_used`. |
| `ModelInvocationUsage` | Input/output token counts. |
| `ModelInvocationResult` | Outcome, optional content, finish reason, reason code, usage, selection lineage, completion instant, opaque internal detail reference. |
| `ModelStreamChunk` | Ordered stream delta with an explicit final marker. |
| `ModelGatewayPort` (Core) | `async invoke(request)` and `stream(request)` returning an async iterator of chunks. |

## Invariants

1. **Provider-neutral**: a request addresses a `LogicalModelPoolRef` only. There
   is no provider, model name, deployment, endpoint, base URL, header, or
   credential field, and `extra="forbid"` rejects injection of one.
2. **Deadline-aware and cancellable**: `deadline_at` is required and must be
   strictly after `issued_at`; `cancelled` and `timed_out` are first-class result
   outcomes.
3. **Bounded**: message count, per-message length, output token budget, sampling
   ranges, and attempt count all have hard bounds.
4. **Sanitized**: message content rejects empty/whitespace-only text and control
   characters.
5. Only a `completed` result may carry content and a finish reason; every other
   outcome must carry a reason code and no content.
6. A completed result must name a selected deployment that actually completed an
   attempt; attempt indexes are unique; at most one attempt may complete.
7. Stream chunks are ordered by `sequence_index`; a non-final chunk must carry a
   delta.
8. Provider-side error text never crosses the boundary: only canonical reason
   codes and an opaque `internal_detail_ref`.

## Out of scope

The concrete gateway adapter, provider SDK usage, credential resolution, and
transport are CP-012 obligations. Retry policy, fallback execution, budget
enforcement, and prompt construction are AI-008 obligations. Pool composition and
probe execution are CP-008 obligations.

## Tests

`tests/test_source_and_lineage_contracts.py::ModelGatewayContractTests` and the
provider-neutrality/import-boundary scans in `tests/test_cp001_boundary.py`.
