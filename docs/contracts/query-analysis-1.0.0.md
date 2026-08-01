# QueryAnalysis 1.0.0

- Status: proposed for local verification
- Owner: Query Understanding Boundary
- Schema identifier: `urn:ai-assistant:contracts:query-analysis:1.0.0`
- JSON Schema dialect: `https://json-schema.org/draft/2020-12/schema`
- Artifact: `schemas/query-analysis/1.0.0.schema.json`

## Purpose

QueryAnalysis is the immutable, validated set of structured query features produced at the
query understanding boundary of the AI Core. It carries a server-derived normalized query,
a structured intent, entity and time analysis, ambiguity, personal and multi-part flags,
risk, evidence needs, an advisory confidence value, the analyzer version, and the request
and runtime correlation identifiers.

QueryAnalysis is evidence used by later stages. It is not a decision.

## AI Core boundary

This repository is the pure, provider-neutral AI Core. Version 1.0.0 contains only the
typed contract. The following remain outside the contract and outside this task: the query
analyzer runtime, prompt templates, model invocation, structured-output retry, entity and
time resolvers, ConversationContext, standalone-query construction, RouteDecision, routing
policy, capability and planner selection, authorization, retrieval, logging, tracing,
persistence, and HTTP models or adapters.

## Root field table

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `schema_version` | literal `1.0.0` | no | `1.0.0` | Any other value is rejected. |
| `analysis_id` | UUID v4 | yes | none | Identity of this analysis result. |
| `request_id` | UUID v4 | yes | none | Correlates with the originating request. |
| `message_id` | UUID v4 | yes | none | Correlates with the analyzed message. |
| `runtime_snapshot_id` | UUID v4 | yes | none | Correlates with the runtime snapshot in force. |
| `analyzed_at` | UtcDateTime | yes | none | Aware timestamp normalized to UTC. |
| `normalized_query` | derived query text | yes | none | 1..32000 characters, preserved exactly. |
| `intent` | QueryIntent | yes | none | Closed catalog. |
| `entities` | tuple of QueryEntity | no | empty tuple | Maximum 32, unique by `(entity_type, mention)`. |
| `time_expressions` | tuple of QueryTimeExpression | no | empty tuple | Maximum 16, unique by `(time_type, expression)`. |
| `ambiguity_level` | AmbiguityLevel | yes | none | Closed catalog. |
| `ambiguity_codes` | tuple of canonical codes | no | empty tuple | Maximum 16, unique, order preserved. |
| `is_personal` | bool | yes | none | Query semantics only, not identity. |
| `is_multi_part` | bool | yes | none | Query contains multiple distinct asks. |
| `risk_level` | RiskLevel | yes | none | Closed catalog. |
| `risk_signals` | tuple of canonical codes | no | empty tuple | Maximum 16, unique, order preserved. |
| `evidence_needs` | tuple of EvidenceNeed | yes | none | 1..6 entries, unique, order preserved. |
| `confidence` | float | yes | none | Finite, 0.0..1.0, advisory only. |
| `analyzer_version` | SchemaVersion | yes | none | Semantic version of the producing analyzer. |

## QueryEntity field table

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `entity_type` | canonical code | yes | none | 1..128 characters, `^[a-z][a-z0-9._:-]*$`. |
| `mention` | mention text | yes | none | 1..512 characters, preserved exactly. |
| `resolution_status` | EntityResolutionStatus | yes | none | `resolved`, `unresolved`, or `ambiguous`. |
| `canonical_id` | opaque identifier or null | no | null | 1..256 characters, resolver-minted. |
| `candidate_ids` | tuple of opaque identifiers | no | empty tuple | Maximum 8, unique, order preserved. |

## QueryTimeExpression field table

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `expression` | time-expression text | yes | none | 1..512 characters, preserved exactly. |
| `time_type` | TimeExpressionType | yes | none | Closed catalog. |
| `resolution_status` | EntityResolutionStatus | yes | none | Same catalog as entities. |
| `canonical_value` | opaque identifier or null | no | null | Resolver-produced representation. |
| `candidate_values` | tuple of opaque identifiers | no | empty tuple | Maximum 8, unique, order preserved. |

## Intent catalog

`greeting`, `capability_help`, `factual`, `procedural`, `status`, `eligibility`,
`comparison`, `analytics`, `unknown`.

The catalog is closed in 1.0.0. Unknown or unsupported intent values fail validation.
Safe fallback handling of imperfect model output belongs to the future analyzer
implementation, not to the contract.

## Evidence-need catalog

`none`, `document`, `analytics`, `personal`, `rule`, `official_source`.

Rules:

- at least one evidence need is required;
- at most six evidence needs are accepted;
- evidence needs are unique and order preserving;
- `none` must be the only evidence need when present, so `("none", "document")` is rejected;
- `personal` requires `is_personal == true`;
- the reverse implication is not enforced: a personal query may need other evidence.

## Entity semantics

An entity records a mention observed in the query together with the resolver state for that
mention. Cross-field invariants:

- `resolved`: `canonical_id` is required and `candidate_ids` must be empty;
- `unresolved`: `canonical_id` must be null and `candidate_ids` must be empty;
- `ambiguous`: `canonical_id` must be null and `candidate_ids` must contain 2..8 unique values.

Candidates are never sorted or normalized. Canonical identifiers are produced only by a
trusted resolver; model output is never trusted to mint a canonical identifier, and a
mention can never be promoted into a resolved fact by the model alone.

## Time-expression semantics

Time expressions use the same three resolver states and the same cross-field invariants as
entities. The canonical value is an opaque resolver-produced representation, for example an
academic-term identifier or a normalized interval representation. The contract does not
parse, interpret, or calculate time, and does not define calendars or ranges.

## Ambiguity semantics

- `none`: `ambiguity_codes` must be empty;
- `non_blocking`: at least one ambiguity code is required; the turn may proceed with a
  documented assumption;
- `blocking`: at least one ambiguity code is required; the turn cannot be answered safely
  without clarification.

Ambiguity codes are controlled canonical codes, unique, order preserving, and capped at 16.
The decision to actually ask a clarifying question belongs to the future routing policy, not
to this contract.

## Risk semantics

`risk_level` is one of `normal`, `elevated`, `high`, or `unknown`. `risk_signals` is a
bounded, unique, order-preserving tuple of controlled canonical codes explaining the level.
Risk here is analyzer evidence. The deterministic routing policy may upgrade risk but must
never silently downgrade analyzer-reported risk.

## Confidence semantics

`confidence` is a finite float in the inclusive range 0.0..1.0. NaN, positive infinity, and
negative infinity are rejected. Confidence is advisory only and must never be the sole input
to authorization, denial, high-risk routing, capability allowlisting, or policy enforcement.
The contract derives no route and no policy from confidence.

## Normalized query semantics

`normalized_query` is server-derived from `TurnInput.raw_message`. The raw message remains in
TurnInput and is deliberately not duplicated here. Normalization may perform approved
mechanical normalization, but must not add facts, remove material constraints, resolve
genuine ambiguity, invent an entity, convert a personal query into a general query, or
convert a general query into a personal query.

The Pydantic model validates shape only: length bounds, non-whitespace content, absence of
NUL, absence of leading or trailing whitespace, and exact preservation of the accepted value.
It cannot prove semantic fidelity. Semantic normalization and its evaluation are deferred to
the analyzer implementation.

The fields `raw_message`, `raw_query`, `standalone_query`, and `query_rewrite` are
deliberately absent from version 1.0.0.

## Trust boundary by producer

Trusted runtime produces: schema version, analysis identifier, request identifier, message
identifier, runtime snapshot identifier, analyzed timestamp, and analyzer version.

Trusted normalizer produces: the normalized query.

The model may propose, but cannot directly authorize: intent, entity mentions,
time-expression mentions, ambiguity, personal and multi-part flags, risk, evidence needs, and
confidence.

Trusted resolvers produce: canonical entity identifiers, entity candidate identifiers,
canonical time values, and time candidate values.

The validated contract is assembled by trusted analyzer-boundary code. Model output remains
untrusted until schema validation, allowlist validation, resolver validation, and cross-field
validation have all succeeded.

## Route and policy separation

QueryAnalysis is evidence for RouteDecision, not RouteDecision itself.

The future deterministic routing policy may reject analyzer output, upgrade risk, force
clarification, force denial, override evidence needs, or choose a different lane. The model
cannot select the final lane, route, planner, or capability. No route, lane, capability,
planner, budget, plan, or policy field exists in this contract.

## Sensitive-data restrictions

The following names are not declared fields and are rejected as unknown input at the root and
in nested models: `lane`, `route`, `suggested_route`, `capability`, `capabilities`,
`allowed_capabilities`, `suggested_capability`, `planner_required`, `execution_plan`, `plan`,
`budget`, `authorization`, `authorization_decision`, `permission`, `roles`, `groups`,
`policy`, `policy_decision`, `sql`, `query_plan`, `tool`, `tool_name`, `endpoint`, `url`,
`api_key`, `token`, `secret`, `credentials`, `prompt`, `system_prompt`, `model_response`,
`provider_response`, `rationale`, `reasoning`, `chain_of_thought`, `clarification_message`,
`answer`, `raw_message`, `raw_query`, `standalone_query`, `metadata`, `attributes`.

No identity data is carried: no principal identifier, security context identifier, email,
display name, session identifier, role, or group. `is_personal` describes query semantics
only; it does not identify a person and grants no access.

## Retention statement

- QueryAnalysis does not authorize persistence.
- The normalized query and mention text may contain personal or confidential user content.
- QueryAnalysis must not be copied to logs or traces by default.
- Telemetry should use the analysis identifier, request identifier, analyzer version,
  categorical results, and approved redacted attributes.
- Retention and redaction are governed by future privacy and operational policy.

## Compatibility

QueryAnalysis 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing, or renaming a field is a major change.
- Adding or changing an intent, evidence-need, risk-level, ambiguity-level,
  resolution-status, or time-type literal is a major change.
- Changing normalization, confidence, entity-resolution, time-resolution, trust, or
  routing-boundary semantics is a major change.
- Version 1.0.0 becomes immutable after approval.

## Valid example: minimal analysis

```json
{
  "schema_version": "1.0.0",
  "analysis_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "message_id": "33333333-3333-4333-8333-333333333333",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "analyzed_at": "2026-01-01T08:30:00Z",
  "normalized_query": "what is the exam schedule",
  "intent": "factual",
  "entities": [],
  "time_expressions": [],
  "ambiguity_level": "none",
  "ambiguity_codes": [],
  "is_personal": false,
  "is_multi_part": false,
  "risk_level": "normal",
  "risk_signals": [],
  "evidence_needs": ["document"],
  "confidence": 0.75,
  "analyzer_version": "1.0.0"
}
```

## Valid example: personal analysis with resolved references

```json
{
  "schema_version": "1.0.0",
  "analysis_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "message_id": "33333333-3333-4333-8333-333333333333",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "analyzed_at": "2026-01-01T08:30:00Z",
  "normalized_query": "what is my grade in compiler design this term",
  "intent": "status",
  "entities": [
    {
      "entity_type": "course",
      "mention": "compiler design",
      "resolution_status": "resolved",
      "canonical_id": "course:cs-431",
      "candidate_ids": []
    }
  ],
  "time_expressions": [
    {
      "expression": "this term",
      "time_type": "academic_term",
      "resolution_status": "resolved",
      "canonical_value": "term:1404-1",
      "candidate_values": []
    }
  ],
  "ambiguity_level": "none",
  "ambiguity_codes": [],
  "is_personal": true,
  "is_multi_part": false,
  "risk_level": "elevated",
  "risk_signals": ["risk.personal_data"],
  "evidence_needs": ["personal"],
  "confidence": 0.9,
  "analyzer_version": "1.0.0"
}
```

## Valid example: blocking ambiguity with candidate references

```json
{
  "schema_version": "1.0.0",
  "analysis_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "message_id": "33333333-3333-4333-8333-333333333333",
  "runtime_snapshot_id": "44444444-4444-4444-8444-444444444444",
  "analyzed_at": "2026-01-01T08:30:00Z",
  "normalized_query": "is the algebra course still open",
  "intent": "eligibility",
  "entities": [
    {
      "entity_type": "course",
      "mention": "algebra",
      "resolution_status": "ambiguous",
      "canonical_id": null,
      "candidate_ids": ["course:math-201", "course:math-311"]
    }
  ],
  "time_expressions": [],
  "ambiguity_level": "blocking",
  "ambiguity_codes": ["ambiguity.entity.course"],
  "is_personal": false,
  "is_multi_part": false,
  "risk_level": "normal",
  "risk_signals": [],
  "evidence_needs": ["official_source"],
  "confidence": 0.4,
  "analyzer_version": "1.0.0"
}
```

## Representative invalid examples

| Invalid input | Reason |
| --- | --- |
| `"schema_version": "1.1.0"` | Only the exact literal `1.0.0` is accepted. |
| `"analysis_id": "...-1..."` (UUID v1) | All identifiers must be version 4 UUIDs. |
| `"analyzed_at": "2026-01-01T12:00:00"` | Naive timestamps are rejected. |
| `"normalized_query": " padded "` | Leading or trailing whitespace is rejected, never trimmed. |
| `"intent": "chit_chat"` | The intent catalog is closed. |
| resolved entity without `canonical_id` | Resolved state requires a resolver-minted identifier. |
| ambiguous entity with one candidate | Ambiguous state requires 2..8 candidates. |
| unresolved entity with `canonical_id` | Unresolved state must not carry a canonical identifier. |
| `"ambiguity_level": "blocking"` with no codes | Non-`none` ambiguity requires at least one code. |
| `"ambiguity_level": "none"` with a code | `none` must carry no ambiguity codes. |
| `"evidence_needs": []` | At least one evidence need is required. |
| `"evidence_needs": ["none", "document"]` | `none` must be exclusive. |
| `"evidence_needs": ["personal"]` with `is_personal: false` | Personal evidence requires the personal flag. |
| `"confidence": 1.5` or `NaN` | Confidence must be finite and within 0.0..1.0. |
| `"route": "analytics"` | Route, policy, and capability fields are forbidden. |
| `"prompt": "..."` | Prompt, rationale, and provider payloads are forbidden. |

## Non-goals

- Selecting a lane, route, planner, or capability.
- Making or recording an authorization or policy decision.
- Executing entity or time resolution.
- Storing raw user input, prompts, provider payloads, or model rationale.
- Persisting, publishing, logging, or tracing the analysis.
- Guaranteeing semantic fidelity of normalization.

## Deferred implementation work

- Query analyzer implementation at the trusted boundary.
- Structured-output prompt and one bounded format-repair attempt.
- Intent, evidence, and risk taxonomy evaluation.
- Entity resolver and time resolver.
- ConversationContext and standalone-query construction.
- Deterministic RouteDecision and routing policy.
- Analyzer evaluation across approved models.
- Normalization fidelity tests.
- Privacy retention and redaction policy.
