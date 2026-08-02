# FinalAnswer Contract 1.0.0

## 1. Purpose

`FinalAnswer` is the single successfully finalized answer artifact produced by the AI Core.
It is the only structure that may leave the core as a completed answer for one request turn.
It exists after the `AnswerPlan` has been approved, after generation and rendering, after claim
validation, after citation compilation, and after final validation. Nothing downstream may add,
remove, reorder, translate, summarize, or repair its content.

## 2. Position in the pipeline

```
TurnInput -> QueryAnalysis -> RouteDecision -> ExecutionPlan -> StepResult
          -> EvidenceBundle -> AnswerPlan -> generation and rendering
          -> claim validation -> citation compilation -> final validation
          -> FinalAnswer
```

The contract is the hand-off point between the AI Core and any presentation adapter.

## 3. What FinalAnswer is not

`FinalAnswer` is not raw generator output, not a draft, not an `AnswerPlan`, not an
`EvidenceBundle`, not an `ErrorEnvelope`, not an HTTP response body, not an RFC 9457 problem
document, not an exception, not an audit record, not a trace span, not a model provider response,
not a prompt, not a persistence row, not a citation resolver, not a source registry, not a
localization catalog, not a rendering engine, not conversation state, and not a streaming event.

## 4. Out of scope for this contract

This contract does not implement generation, rendering, claim validation, citation compilation,
citation resolution, source registries, localization, HTTP mapping, middleware, persistence,
telemetry, streaming, orchestration, retry, or factories. It only declares and validates shape.

## 5. Trust boundary

Generator output is untrusted. Only trusted AI Core finalization code may construct a
`FinalAnswer`. Pydantic validation here is structural only: it can prove that a claim item is
marked `supported`, but it cannot prove that the sentence is true. Semantic guarantees remain the
responsibility of the trusted validation stages that run before construction.

## 6. Terminal outcome catalog

| Outcome | Meaning |
| --- | --- |
| `answered` | The question was answered completely from validated evidence. |
| `partially_answered` | Part of the question was answered; the remainder is disclosed. |
| `clarification_required` | The turn ends by asking the user for a required clarification. |
| `abstained` | The system deliberately declined to answer. |
| `failed` | Finalization failed after a valid `AnswerPlan` existed. |

There is no `denied` outcome. Authentication, authorization, policy rejection, and malformed
requests are decided before an `AnswerPlan` exists and travel on the `ErrorEnvelope` path.

## 7. Failure boundary

`outcome == "failed"` is reserved for post-plan finalization failures only. Because a plan always
exists by then, `answer_plan_id` is required for every outcome including `failed`.

## 8. Schema identity and versioning

- `schema_version` is the literal `"1.0.0"` and is defined by the module constant
  `FINAL_ANSWER_SCHEMA_VERSION`.
- The JSON Schema dialect is `https://json-schema.org/draft/2020-12/schema`.
- The schema identifier is `urn:ai-assistant:contracts:final-answer:1.0.0`.
- Nested models never carry their own `schema_version`; the root owns versioning.

## 9. Model configuration

Every model inherits `ContractModel`: `extra="forbid"`, `frozen=True`, `validate_default=True`.
Unknown fields are rejected at the root and at every nested boundary. Instances are immutable, so
downstream mutation is impossible.

## 10. Root fields

| Field | Type | Notes |
| --- | --- | --- |
| `schema_version` | `Literal["1.0.0"]` | Defaulted from the module constant. |
| `final_answer_id` | UUID4 | Identity of this artifact. |
| `request_id` | UUID4 | Turn request identity. |
| `answer_plan_id` | UUID4 | Required for every outcome. |
| `evidence_bundle_id` | UUID4 | Bundle the citations were compiled from. |
| `route_decision_id` | UUID4 | Routing lineage. |
| `plan_id` | UUID4 | Execution plan lineage. |
| `authorization_decision_id` | UUID4 | Authorization lineage. |
| `runtime_snapshot_id` | UUID4 | Runtime and configuration lineage. |
| `correlation_id` | UUID4 | Cross-component correlation. |
| `finalized_at` | `UtcDateTime` | Timezone-aware, normalized to UTC. |
| `outcome` | `FinalOutcome` | Terminal outcome. |
| `validated_content` | `FinalValidatedContent \| None` | Absent only for `failed`. |
| `citations` | tuple of `FinalCitation`, max 64 | Defaults to empty. |
| `outcome_reason_codes` | tuple of canonical codes, max 16 | Defaults to empty. |
| `safe_error` | `DomainError \| None` | Present only for `failed`. |
| `freshness_note` | `FinalFreshnessNote` | Always present. |
| `applied_length_budget` | `AnswerLengthBudget` | The budget actually applied. |
| `response_metadata` | `FinalResponseMetadata` | Trace-safe structural summary. |
| `finalizer_version` | `SchemaVersion` | Version of the finalization component. |

Omitted collections become empty tuples. Explicit `null` for a collection is rejected. Nothing is
auto-sorted, deduplicated, or repaired.

## 11. Validated content structure

`FinalValidatedContent` holds `sections`, a tuple of 1 to 8 `FinalAnswerSection` values, unique by
`section_id`. Each section holds 1 to 32 items, unique by `(item_kind, item_id)`, and the pair
must also be unique across all sections, so every item appears in exactly one section. A section
is never empty. Section order and item order are the exact user-visible order.

Sections carry no title, heading, body, or free text. A presentation adapter renders headings from
a versioned `section_type` catalog.

## 12. Claim and caveat semantics

`FinalClaimContent` has `item_kind == "claim"` and `validation_status == "supported"`. It realizes
exactly one planned claim, adds no new factual claim, and embeds no citation marker.
`FinalCaveatContent` has `item_kind == "caveat"` and `validation_status == "authorized"`. It
realizes a required caveat without omitting, weakening, or contradicting it, and hides no claim
inside caveat prose. Claim identifiers and caveat identifiers live in separate namespaces, so the
same textual identifier used as a claim and as a caveat denotes two distinct items.

Neither model carries evidence identifiers, claim codes, claim types, subjects, supporting fact
identifiers, confidence values, or reasoning.

## 13. Rendered text rules

`rendered_text` is a strict string of 1 to 4000 characters. NUL is rejected, leading and trailing
whitespace are rejected, and the value is never trimmed or repaired. Unicode, Persian, and
embedded newlines are allowed because they are legitimate answer content.

## 14. Citation structure

`FinalCitation` realizes exactly one planned citation slot: `citation_id` (UUID4), `slot_id`,
`target_kind`, `target_id`, `placement`, and 1 to 32 `sources` unique by `evidence_id`.
Citations are unique by `citation_id` and by `slot_id`, and two citations may not repeat the same
target, placement, and source set. Order is preserved exactly.

`FinalCitationSource` exposes `evidence_id`, `evidence_type`, `display_label`, `source_version`,
and `locator_ref`. There is no URL, URI, href, path, page number, section number, quote, excerpt,
snippet, document text, raw locator, or source content anywhere in a citation.

## 15. Citation compiler boundary

Citations are produced by trusted Citation Compiler code from the referenced `EvidenceBundle`. This
contract does not resolve, fetch, deduplicate, rank, or format citations. `locator_ref` is opaque:
it excludes whitespace, `/`, `\`, `?`, `#`, URL schemes, and filesystem paths, so it cannot be
dereferenced and grants no access by itself.

## 16. Content and citation linkage

Every citation must target an item that exists in `validated_content` with a matching kind. Every
claim item must be covered by at least one citation. A caveat may stand without a citation.
Citations are impossible when there is no validated content.

## 17. Freshness semantics

| Status | `data_as_of` | `reason_codes` |
| --- | --- | --- |
| `current` | required | optional |
| `stale` | required | at least one |
| `mixed` | optional | at least one |
| `unknown` | forbidden | at least one |
| `not_applicable` | forbidden | forbidden |

Freshness prose is never stored. When the user must be told about staleness, that statement must be
a planned and validated caveat item.

## 18. Applied length budget

`applied_length_budget` reuses `AnswerLengthBudget` and records the budget actually applied during
finalization. Section, claim, caveat, citation, and character counts must all be within it.

## 19. Character counting rule

The canonical character count is the sum of `len(item.rendered_text)` over every item in every
section, measured in Unicode code points. Citation labels, UI separators, UI headings, and
transport or JSON syntax are excluded. The value must equal `response_metadata.character_count`
and must not exceed `applied_length_budget.max_characters`.

## 20. Trace-safe metadata

`FinalResponseMetadata` carries `response_locale`, `answer_type`, `generation_mode`,
`validation_status`, `degraded`, and the five counts. It carries no user identity, session
identity, message text, source content, model or provider name, token count, cost, latency, HTTP
status, or vendor trace identifier. Component and configuration versions are reachable through
`runtime_snapshot_id`, and the finalizer version stays a root field.

## 21. Metadata count invariants

For every non-failed outcome, all five declared counts must exactly equal the counts computed from
`validated_content` and `citations`. For `failed`, all five counts must be zero.

## 22. Outcome invariants

- `answered`: content present, at least one claim, every claim cited, no safe error, no outcome
  reason codes, locale present, answer type present and not `clarification` or `abstention`,
  generation mode not `none`, validation status `passed`.
- `partially_answered`: as above plus at least one caveat, at least one outcome reason code, and
  `degraded == True`.
- `clarification_required`: content present, no claim items, at least one caveat, at least one
  reason code, answer type `clarification`, any citation targets a caveat.
- `abstained`: same shape with answer type `abstention`.
- `failed`: no content, no citations, safe error present, at least one reason code, freshness
  `not_applicable`, locale `None`, answer type `None`, generation mode `none`, validation status
  `not_applicable`, `degraded == True`, all counts zero.

## 23. Safe-error integration

`safe_error` reuses `DomainError` unchanged. `ErrorEnvelope` is not embedded, because it owns its
own identity and schema version and belongs to the transport error path. No second error code
catalog, retryability rule, or message-key map is defined here. Raw exception text, provider text,
HTTP status codes, and stack traces are impossible by construction.

Permitted failure codes: `SCHEMA_INVALID`, `DEPENDENCY_TIMEOUT`, `TRANSIENT_DEPENDENCY`,
`BUDGET_EXCEEDED`, `RATE_LIMITED`, `CAPACITY_REJECTED`, `INTERNAL_ERROR`.

Prohibited failure codes: `INVALID_INPUT`, `UNAUTHENTICATED`, `UNAUTHORIZED`, `AMBIGUOUS_REQUEST`,
`POLICY_REJECTED`, `NO_EVIDENCE`, `CONFLICTING_EVIDENCE`.

## 24. AnswerPlan binding

Trusted finalization code, not this contract, must verify externally that: the plan identifier
matches the approved plan; every planned section appears once; every planned claim and caveat is
realized once; every planned citation slot is realized once; and the plan answer type maps to the
outcome as `answer -> answered`, `partial_answer -> partially_answered`,
`clarify -> clarification_required`, `abstain -> abstained`.

## 25. EvidenceBundle binding

Every cited `evidence_id` must belong to the referenced `EvidenceBundle` and must have been
allowed for the target item. That check requires the bundle and therefore lives outside this
contract.

## 26. Content-validation boundary

`validation_status` records that trusted validation ran and passed. The contract does not re-run
claim validation, entailment checking, or policy evaluation.

## 27. Sensitive-data restrictions

No raw prompt, chain of thought, model reasoning, provider payload, retrieved document text, SQL
text, connection string, credential, token, personal identifier, or internal hostname may appear
in any field. Human-readable text is allowed only in `rendered_text`, `display_label`, and the
`safe_message_key` inside `DomainError`.

## 28. Forbidden field catalog

The closed-model configuration rejects every unknown field, including but not limited to: `text`,
`answer`, `answer_text`, `content`, `body`, `markdown`, `html`, `raw`, `raw_text`, `draft`,
`draft_text`, `completion`, `message`, `messages`, `prompt`, `system_prompt`, `reasoning`,
`chain_of_thought`, `thoughts`, `scratchpad`, `explanation_internal`, `model`, `model_name`,
`provider`, `vendor`, `engine`, `temperature`, `top_p`, `seed`, `tokens`, `token_count`,
`prompt_tokens`, `completion_tokens`, `cost`, `usd_cost`, `latency_ms`, `duration_ms`,
`trace_id`, `span_id`, `request_headers`, `response_headers`, `http_status`, `status_code`,
`url`, `uri`, `href`, `link`, `path`, `file_path`, `page`, `page_number`, `section_number`,
`quote`, `excerpt`, `snippet`, `document_text`, `raw_locator`, `source_content`, `chunk`,
`embedding`, `vector`, `score`, `confidence`, `probability`, `user_id`, `user_email`, `email`,
`session_id`, `tenant_secret`, `credential`, `token`, `api_key`, `password`, `connection_string`,
`sql`, `query_text`, `stack_trace`, `traceback`, `exception`, `error_message`, `internal_message`,
`debug`, `metadata_extra`, `extra`, `attributes`, `properties`, `custom`, and `notes`.

## 29. Retention guidance

A `FinalAnswer` contains user-visible answer text and is therefore subject to the answer-retention
policy of the deployment, not to trace retention. Logs and traces must reference
`final_answer_id` and `correlation_id` instead of embedding the artifact. `locator_ref` values are
opaque and must not be expanded into resolvable addresses in stored logs.

## 30. Immutability and ordering

All models are frozen. Collections are tuples, so JSON round-trips preserve order exactly. The
contract never sorts, deduplicates, or normalizes a collection on the caller's behalf.

## 31. Compatibility

FinalAnswer 1.0.0 is closed and becomes immutable after approval.

PATCH changes must not alter the set of accepted payloads, validation behavior, serialized payload
shape, defaults, ordering, trust semantics, security semantics, or terminal-outcome semantics. A
PATCH release may correct documentation, tests, or internal comments only.

Adding, removing, or renaming a field requires a new major version.

Adding or changing a terminal outcome, generation mode, content-validation status, freshness
status, item kind, discriminator, required field, default, constraint, cross-field invariant, count
definition, budget rule, citation rule, safe-error rule, AnswerPlan binding rule, EvidenceBundle
binding rule, privacy rule, or trust-boundary rule requires a new major version.

Adding a value to a closed Literal or enum is a breaking change for 1.0.0 and requires a new major
version. Every literal catalog in this contract is closed, including the terminal outcomes,
generation modes, content-validation statuses, freshness statuses, item kinds, citation target
kinds, and citation placements.

Controlled values that are represented as validated canonical strings, such as organization-managed
reason codes or section types, may evolve only within their already-declared structural
constraints and must not change the meaning of an existing accepted payload.

A new major version requires a new schema version and a new schema identifier; it never reuses
`urn:ai-assistant:contracts:final-answer:1.0.0`.

FinalAnswer 1.0.0 is immutable after approval.

## 32. JSON Schema artifact

The generated artifact lives at `schemas/final-answer/1.0.0.schema.json`. It is Draft 2020-12, uses
the exact `$id` above, is serialized with two-space indentation, sorted keys, `ensure_ascii=False`,
and a trailing newline, and must stay byte-identical to the schema generated from the model.

## 33. Valid examples

### 33.1 Valid example: `answered`

```json
{
  "schema_version": "1.0.0",
  "final_answer_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "answer_plan_id": "33333333-3333-4333-8333-333333333333",
  "evidence_bundle_id": "44444444-4444-4444-8444-444444444444",
  "route_decision_id": "55555555-5555-4555-8555-555555555555",
  "plan_id": "66666666-6666-4666-8666-666666666666",
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "88888888-8888-4888-8888-888888888888",
  "correlation_id": "99999999-9999-4999-8999-999999999999",
  "finalized_at": "2026-08-01T12:00:00Z",
  "outcome": "answered",
  "validated_content": {
    "sections": [
      {
        "section_id": "section.summary",
        "section_type": "summary",
        "items": [
          {
            "item_kind": "claim",
            "item_id": "claim.balance",
            "rendered_text": "Your account balance is 1200.",
            "validation_status": "supported"
          }
        ]
      }
    ]
  },
  "citations": [
    {
      "citation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "slot_id": "slot.balance",
      "target_kind": "claim",
      "target_id": "claim.balance",
      "placement": "inline",
      "sources": [
        {
          "evidence_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          "evidence_type": "sql",
          "display_label": "Ledger balance view",
          "source_version": "2026.08.01",
          "locator_ref": "ledger.balance.row-42"
        }
      ]
    }
  ],
  "outcome_reason_codes": [],
  "safe_error": null,
  "freshness_note": {
    "status": "current",
    "data_as_of": "2026-08-01T11:30:00Z",
    "reason_codes": []
  },
  "applied_length_budget": {
    "max_characters": 16000,
    "max_sections": 8,
    "max_claims": 32,
    "max_caveats": 32,
    "max_citations": 64
  },
  "response_metadata": {
    "response_locale": "fa-IR",
    "answer_type": "direct",
    "generation_mode": "model_generated",
    "validation_status": "passed",
    "degraded": false,
    "section_count": 1,
    "claim_count": 1,
    "caveat_count": 0,
    "citation_count": 1,
    "character_count": 29
  },
  "finalizer_version": "1.0.0"
}
```

### 33.2 Valid example: `partially_answered`

```json
{
  "schema_version": "1.0.0",
  "final_answer_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "answer_plan_id": "33333333-3333-4333-8333-333333333333",
  "evidence_bundle_id": "44444444-4444-4444-8444-444444444444",
  "route_decision_id": "55555555-5555-4555-8555-555555555555",
  "plan_id": "66666666-6666-4666-8666-666666666666",
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "88888888-8888-4888-8888-888888888888",
  "correlation_id": "99999999-9999-4999-8999-999999999999",
  "finalized_at": "2026-08-01T12:00:00Z",
  "outcome": "partially_answered",
  "validated_content": {
    "sections": [
      {
        "section_id": "section.summary",
        "section_type": "summary",
        "items": [
          {
            "item_kind": "claim",
            "item_id": "claim.balance",
            "rendered_text": "Your account balance is 1200.",
            "validation_status": "supported"
          },
          {
            "item_kind": "caveat",
            "item_id": "caveat.july",
            "rendered_text": "Data for July is unavailable.",
            "validation_status": "authorized"
          }
        ]
      }
    ]
  },
  "citations": [
    {
      "citation_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      "slot_id": "slot.balance",
      "target_kind": "claim",
      "target_id": "claim.balance",
      "placement": "inline",
      "sources": [
        {
          "evidence_id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          "evidence_type": "sql",
          "display_label": "Ledger balance view",
          "source_version": "2026.08.01",
          "locator_ref": "ledger.balance.row-42"
        }
      ]
    }
  ],
  "outcome_reason_codes": ["partial.missing_period"],
  "safe_error": null,
  "freshness_note": {
    "status": "current",
    "data_as_of": "2026-08-01T11:30:00Z",
    "reason_codes": []
  },
  "applied_length_budget": {
    "max_characters": 16000,
    "max_sections": 8,
    "max_claims": 32,
    "max_caveats": 32,
    "max_citations": 64
  },
  "response_metadata": {
    "response_locale": "fa-IR",
    "answer_type": "direct",
    "generation_mode": "model_generated",
    "validation_status": "passed",
    "degraded": true,
    "section_count": 1,
    "claim_count": 1,
    "caveat_count": 1,
    "citation_count": 1,
    "character_count": 58
  },
  "finalizer_version": "1.0.0"
}
```

### 33.3 Valid example: `clarification_required`

```json
{
  "schema_version": "1.0.0",
  "final_answer_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "answer_plan_id": "33333333-3333-4333-8333-333333333333",
  "evidence_bundle_id": "44444444-4444-4444-8444-444444444444",
  "route_decision_id": "55555555-5555-4555-8555-555555555555",
  "plan_id": "66666666-6666-4666-8666-666666666666",
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "88888888-8888-4888-8888-888888888888",
  "correlation_id": "99999999-9999-4999-8999-999999999999",
  "finalized_at": "2026-08-01T12:00:00Z",
  "outcome": "clarification_required",
  "validated_content": {
    "sections": [
      {
        "section_id": "section.clarify",
        "section_type": "clarification",
        "items": [
          {
            "item_kind": "caveat",
            "item_id": "caveat.which_account",
            "rendered_text": "Which account should I check?",
            "validation_status": "authorized"
          }
        ]
      }
    ]
  },
  "citations": [],
  "outcome_reason_codes": ["clarify.ambiguous_account"],
  "safe_error": null,
  "freshness_note": {
    "status": "not_applicable",
    "data_as_of": null,
    "reason_codes": []
  },
  "applied_length_budget": {
    "max_characters": 16000,
    "max_sections": 8,
    "max_claims": 32,
    "max_caveats": 32,
    "max_citations": 64
  },
  "response_metadata": {
    "response_locale": "fa-IR",
    "answer_type": "clarification",
    "generation_mode": "deterministic_template",
    "validation_status": "passed",
    "degraded": false,
    "section_count": 1,
    "claim_count": 0,
    "caveat_count": 1,
    "citation_count": 0,
    "character_count": 29
  },
  "finalizer_version": "1.0.0"
}
```

### 33.4 Valid example: `abstained`

```json
{
  "schema_version": "1.0.0",
  "final_answer_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "answer_plan_id": "33333333-3333-4333-8333-333333333333",
  "evidence_bundle_id": "44444444-4444-4444-8444-444444444444",
  "route_decision_id": "55555555-5555-4555-8555-555555555555",
  "plan_id": "66666666-6666-4666-8666-666666666666",
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "88888888-8888-4888-8888-888888888888",
  "correlation_id": "99999999-9999-4999-8999-999999999999",
  "finalized_at": "2026-08-01T12:00:00Z",
  "outcome": "abstained",
  "validated_content": {
    "sections": [
      {
        "section_id": "section.abstain",
        "section_type": "abstention",
        "items": [
          {
            "item_kind": "caveat",
            "item_id": "caveat.no_authorized_source",
            "rendered_text": "I cannot answer this from approved sources.",
            "validation_status": "authorized"
          }
        ]
      }
    ]
  },
  "citations": [],
  "outcome_reason_codes": ["abstain.insufficient_evidence"],
  "safe_error": null,
  "freshness_note": {
    "status": "not_applicable",
    "data_as_of": null,
    "reason_codes": []
  },
  "applied_length_budget": {
    "max_characters": 16000,
    "max_sections": 8,
    "max_claims": 32,
    "max_caveats": 32,
    "max_citations": 64
  },
  "response_metadata": {
    "response_locale": "fa-IR",
    "answer_type": "abstention",
    "generation_mode": "safe_fallback",
    "validation_status": "passed",
    "degraded": true,
    "section_count": 1,
    "claim_count": 0,
    "caveat_count": 1,
    "citation_count": 0,
    "character_count": 43
  },
  "finalizer_version": "1.0.0"
}
```

### 33.5 Valid example: `failed`

```json
{
  "schema_version": "1.0.0",
  "final_answer_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "answer_plan_id": "33333333-3333-4333-8333-333333333333",
  "evidence_bundle_id": "44444444-4444-4444-8444-444444444444",
  "route_decision_id": "55555555-5555-4555-8555-555555555555",
  "plan_id": "66666666-6666-4666-8666-666666666666",
  "authorization_decision_id": "77777777-7777-4777-8777-777777777777",
  "runtime_snapshot_id": "88888888-8888-4888-8888-888888888888",
  "correlation_id": "99999999-9999-4999-8999-999999999999",
  "finalized_at": "2026-08-01T12:00:00Z",
  "outcome": "failed",
  "validated_content": null,
  "citations": [],
  "outcome_reason_codes": ["final.dependency_timeout"],
  "safe_error": {
    "code": "DEPENDENCY_TIMEOUT",
    "safe_message_key": "error.dependency_timeout",
    "retryable": true,
    "internal_detail_ref": "000003e7-1111-4111-8111-0000000003e7"
  },
  "freshness_note": {
    "status": "not_applicable",
    "data_as_of": null,
    "reason_codes": []
  },
  "applied_length_budget": {
    "max_characters": 16000,
    "max_sections": 8,
    "max_claims": 32,
    "max_caveats": 32,
    "max_citations": 64
  },
  "response_metadata": {
    "response_locale": null,
    "answer_type": null,
    "generation_mode": "none",
    "validation_status": "not_applicable",
    "degraded": true,
    "section_count": 0,
    "claim_count": 0,
    "caveat_count": 0,
    "citation_count": 0,
    "character_count": 0
  },
  "finalizer_version": "1.0.0"
}
```

## 34. Invalid examples

Each entry starts from a valid payload and applies exactly one mutation.

| # | Name | Mutation | Rejected because |
| --- | --- | --- | --- |
| 1 | `unknown_root_field` | add `"answer_text": "..."` | the root model is closed |
| 2 | `unknown_nested_field` | add `"url"` to a citation source | nested models are closed |
| 3 | `wrong_schema_version` | set `schema_version` to `"1.1.0"` | the version literal is fixed |
| 4 | `non_uuid4_identifier` | set `final_answer_id` to a UUID1 value | UUID version 4 is required |
| 5 | `naive_finalized_at` | drop the timezone offset | `UtcDateTime` requires awareness |
| 6 | `empty_rendered_text` | set `rendered_text` to `""` | minimum length is 1 |
| 7 | `padded_rendered_text` | set `rendered_text` to `" text "` | padding is rejected, never trimmed |
| 8 | `nul_in_rendered_text` | embed a NUL character | control byte is rejected |
| 9 | `empty_section` | set `items` to `[]` | a section needs at least one item |
| 10 | `duplicate_item_in_section` | repeat one claim item | items are unique per section |
| 11 | `duplicate_item_across_sections` | repeat a claim in a second section | items are globally unique |
| 12 | `duplicate_section_id` | repeat a `section_id` | sections are unique |
| 13 | `uncited_claim` | remove the only citation | every claim must be cited |
| 14 | `unknown_citation_target` | point `target_id` at a missing item | citations must resolve |
| 15 | `claim_citation_targets_caveat` | set `target_kind` to `"claim"` for a caveat id | kind and identity must match |
| 16 | `duplicate_slot_id` | repeat a `slot_id` | slots are realized once |
| 17 | `duplicate_evidence_in_citation` | repeat an `evidence_id` in `sources` | sources are unique |
| 18 | `citation_with_no_sources` | set `sources` to `[]` | at least one source is required |
| 19 | `wrong_character_count` | set `character_count` to `28` | counts must match content |
| 20 | `wrong_claim_count` | set `claim_count` to `2` | counts must match content |
| 21 | `budget_exceeded_characters` | set `max_characters` to `10` | content must fit the budget |
| 22 | `answered_with_safe_error` | attach a `safe_error` | success carries no error |
| 23 | `answered_with_reason_codes` | add an outcome reason code | `answered` is unqualified |
| 24 | `answered_without_claim` | keep only a caveat item | `answered` needs a claim |
| 25 | `partial_without_caveat` | remove the caveat item | disclosure is mandatory |
| 26 | `partial_not_degraded` | set `degraded` to `false` | partial answers are degraded |
| 27 | `clarification_with_claim` | add a claim item | clarification asserts nothing |
| 28 | `abstained_wrong_answer_type` | set `answer_type` to `"direct"` | abstention has its own type |
| 29 | `failed_with_content` | keep `validated_content` | failure has no content |
| 30 | `failed_with_prohibited_code` | set the code to `UNAUTHORIZED` | pre-plan codes are prohibited |
| 31 | `failed_not_applicable_freshness` | set freshness to `"current"` | failure discloses no freshness |
| 32 | `current_without_data_as_of` | remove `data_as_of` | `current` requires a timestamp |
| 33 | `unknown_with_data_as_of` | add `data_as_of` | `unknown` forbids a timestamp |
| 34 | `not_applicable_with_reasons` | add a reason code | `not_applicable` forbids reasons |
| 35 | `explicit_null_citations` | set `citations` to `null` | collections are never nullable |
| 36 | `boolean_count` | set `claim_count` to `true` | counts are strict integers |

## 35. Change log

- `1.0.0`: initial contract.
