# Evidence and EvidenceBundle 1.0.0

- Status: proposed for local verification
- Owner: Evidence Normalization and Sufficiency Boundary
- Schema identity: `urn:ai-assistant:contracts:evidence:1.0.0`
- Dialect: JSON Schema Draft 2020-12
- Artifact: `schemas/evidence/1.0.0.schema.json`

## Purpose

Evidence 1.0.0 defines the normalized, validated evidence records produced from accepted
StepResult outputs, and the deterministic EvidenceBundle that records required-fact coverage,
conflicts, sufficiency, and the claims that later stages are allowed to make.

## AI Core boundary

This repository is the pure, provider-neutral AI Core. The contract is not a retrieval engine,
an Evidence Manager, a conflict detector, a persistence layer, an HTTP contract, or a
provider-specific object. It carries controlled metadata, immutable artifact references,
digests, source locators, typed fact-support declarations, security and retention labels, and
deterministic bundle decisions. Source content and structured results stay outside the
contract behind opaque artifact references.

## Why Evidence and EvidenceBundle are one contract family

The five Evidence variants describe individual validated records. EvidenceBundle describes the
deterministic outcome of normalization, coverage, compatibility, conflict detection,
sufficiency and allowed-claim construction. Splitting them would leave the boundary between
evidence and the future AnswerPlan undefined, so both live in one closed contract family.

The language model never decides whether evidence is sufficient, which conflict wins, which
claims are allowed, or whether the answer is complete, partial, clarifying or abstaining.
Trusted deterministic code makes those decisions and records them here.

## Common evidence fields

| Field | Type | Rules |
| --- | --- | --- |
| `evidence_id` | UUID4 | unique within the bundle |
| `evidence_type` | variant literal | discriminator |
| `subject` | EvidenceSubjectRef | referenced subject only |
| `valid_time` | EvidenceValidityWindow | validity context |
| `source_time` | EvidenceSourceTime | observation and publication |
| `source` | EvidenceSourceRef | provider-neutral source |
| `authority` | canonical code | controlled authority catalog |
| `security_scope` | EvidenceSecurityScope | descriptive label |
| `validation_status` | validated, degraded | accepted evidence only |
| `freshness` | current, stale, unknown | not confidence |
| `provenance` | EvidenceProvenance | plan and step binding |
| `allowed_uses` | tuple of canonical codes | 1..8, unique, ordered |
| `retention_class` | canonical code | retention catalog code |
| `supports_fact_ids` | tuple of canonical codes | 1..16, unique, ordered |

Allowed-use examples include `claim_support`, `citation`, `calculation` and `rule_input`.
They are controlled catalog codes, not a closed schema enum.

## Nested models

| Model | Fields | Rules |
| --- | --- | --- |
| `EvidenceSubjectRef` | `subject_type`, `subject_ref` | canonical code, opaque reference |
| `EvidenceValidityWindow` | `as_of`, `valid_from`, `valid_to` | ordered window bounds |
| `EvidenceSourceTime` | `observed_at`, `published_at` | published at or before observed |
| `EvidenceSourceRef` | `source_type`, `source_ref`, `source_version` | provider-neutral |
| `EvidenceSecurityScope` | `scope_ref`, `data_scope`, `classification` | descriptive only |
| `EvidenceProvenance` | `step_result_id`, `plan_id`, `step_id`, `capability`, `operation`, `materializer_version`, `input_digest` | UUID4, canonical codes, digest |
| `RejectedEvidenceRef` | `evidence_id`, `evidence_type`, `reason_codes` | 1..16 reason codes |
| `FactEvidenceMapEntry` | `fact_id`, `evidence_ids` | 1..64 accepted identifiers |
| `EvidenceConflict` | `conflict_id`, `fact_id`, `evidence_ids`, `status`, `resolution_code`, `controlling_evidence_id` | 2..16 identifiers |
| `AllowedEvidenceClaim` | `claim_id`, `claim_code`, `claim_type`, `subject`, `supporting_fact_ids`, `evidence_ids` | no claim prose |
| `ProhibitedEvidenceClaim` | `claim_code`, `reason_codes` | disjoint from allowed codes |

### Validation aliases

| Alias | Rule |
| --- | --- |
| canonical code | 1..128 characters, pattern `^[a-z][a-z0-9._:-]*$`, never repaired |
| opaque reference | 1..256 characters, no NUL, no surrounding whitespace, preserved exactly |
| digest | exactly 64 lowercase hexadecimal characters |
| identifier | UUID version 4 |
| score | strict finite float between 0.0 and 1.0 |

## Evidence-type catalog

| Type | Capability | Data scope | Purpose |
| --- | --- | --- | --- |
| `document` | `document_retrieval` | any | governed document chunk reference |
| `sql` | `semantic_analytics` | `general` | semantic-layer aggregate reference |
| `selector` | `personal_selector` | `personal` | personal selector result reference |
| `rule` | `rule_evaluator` | any | deterministic rule outcome reference |
| `web` | `official_search` | `general` | allowlisted official page reference |

### Validation and freshness catalogs

| Validation status | Meaning |
| --- | --- |
| `validated` | passed every materialization check |
| `degraded` | usable under trusted policy with recorded weakness |

| Freshness | Meaning |
| --- | --- |
| `current` | inside the freshness policy window |
| `stale` | outside the window, still referenced |
| `unknown` | freshness could not be established |

Freshness is a time property. It is never a confidence score.

## Document evidence

Fields: `document_ref`, `document_version`, `chunk_ref`, `locator_ref`, `content_ref`,
`content_sha256`, `ranking_score`. Provenance capability must be `document_retrieval`. The
ranking score is retrieval-local metadata and must never be read as global answer confidence.
Document text is not embedded and locator resolution is deferred to the citation boundary.

## SQL evidence

Fields: `semantic_query_ref`, `semantic_catalog_version`, `result_ref`, `result_sha256`,
`metric_codes`, `filter_codes`, `result_shape`, `suppression_applied`. Provenance capability
must be `semantic_analytics` and the data scope must be `general`. No SQL string, table,
column, row or database payload is stored.

## Selector evidence

Fields: `selector_ref`, `result_ref`, `result_sha256`, `field_codes`. Provenance capability
must be `personal_selector` and the data scope must be `personal`. No personal value is
embedded, and the contract grants no permission to resolve the references.

## Rule evidence

Fields: `rule_bundle_ref`, `rule_code`, `rule_version`, `outcome_ref`, `outcome_sha256`,
`input_evidence_ids`. Provenance capability must be `rule_evaluator`. An item cannot reference
itself, and every input identifier must be accepted in the same bundle. Rule logic and result
values are not embedded.

## Web evidence

Fields: `page_ref`, `allowlist_ref`, `locator_ref`, `content_ref`, `content_sha256`.
Provenance capability must be `official_search` and the data scope must be `general`. No raw
URL, personal query or personal content is represented. The allowlist reference identifies the
approved official-source policy. The contract does not fetch or dereference the page.

## Source and locator references

Source, document, chunk, page, locator, content, result and outcome references are opaque
artifact references. They are never interpreted as URLs, filesystem paths, cloud locations,
endpoints, credentials, SQL or executable expressions. Digests bind a reference to the exact
immutable artifact that was validated during materialization.

## Security scope and retention

`EvidenceSecurityScope` is a descriptive binding of an opaque scope reference, a data scope and
a classification code. A personal data scope is a label, not authorization: authorization must
already have completed before evidence is materialized.

Retention rules:

- this contract does not authorize persistence;
- evidence metadata and opaque references may be retained for replay, audit and evaluation
  only under approved policy;
- referenced content and structured result artifacts have independent retention and access
  controls;
- personal selector evidence requires personal-data retention controls;
- raw source payloads, SQL, provider responses, credentials and exception text must never be
  copied into an EvidenceBundle;
- telemetry should normally use bundle ID, evidence IDs, evidence types, fact coverage,
  freshness, validation status, conflict count, decision, reason codes and correlation ID.

## Provenance semantics

Provenance binds each evidence record to the StepResult and plan step that produced it, the
capability and operation that were executed, the materializer version, and a digest of the
materialization input. No provider, model, endpoint, SDK or credential field is permitted.

## Rejected evidence

Rejected records never appear in `accepted_evidence`. They are represented by
`RejectedEvidenceRef` with an identifier, an evidence type and 1..16 reason codes. Rejected
source content and raw error text are never carried.

## Required-fact coverage

Every required fact ID must appear exactly once across `fact_map` and `missing_fact_ids`. No
fact is left uncovered and no fact appears in both collections. Unknown facts are rejected in
either collection. The bundle cannot dereference StepResult or ExecutionPlan to compute this;
it only validates that a partition already exists.

## Exact fact map

A fact-map entry lists the accepted evidence that supports one required fact. The map is exact
in both directions: every accepted evidence support declaration must appear in the matching
fact-map entry, and every fact-map relationship must be declared by the referenced evidence's
`supports_fact_ids`. No hidden or unmatched support relationship is permitted.

## Conflict semantics

A conflict names a required fact and 2..16 accepted evidence items that disagree on it.
Duplicate semantic conflicts with the same fact and evidence set are rejected. An unresolved
conflict carries no resolution code or controlling evidence. A resolved conflict requires both,
and the controlling evidence must be one of the conflict's evidence items. The contract records
the outcome; it does not implement precedence policy. An unresolved conflict prevents a fully
sufficient answer.

## Allowed and prohibited claims

An allowed claim may only use facts that are covered in `fact_map`, and only evidence that is
accepted in the bundle. Every evidence ID listed for a claim must support at least one of the
claim's facts, and every claim fact must have at least one listed supporting evidence. Allowed
claims contain no prose fields such as `claim_text`, `statement`, `explanation` or `reasoning`.
Allowed and prohibited claim codes are disjoint. Only allowed claims may reach the future
AnswerPlan builder.

## Evidence decision semantics

`sufficient` is true if and only if `decision` is `answer`. Every bundle carries at least one
decision reason code.

### Answer decision

Requires `sufficient == true`, an empty `missing_fact_ids`, no unresolved conflict, and at
least one allowed claim. Stale or degraded evidence may only support an answer when trusted
policy has already accepted that use; the contract does not implement that policy.

### Partial decision

Requires `sufficient == false` and at least one allowed claim, plus at least one of: a missing
fact, an unresolved conflict, non-current freshness in accepted evidence, or degraded
validation status in accepted evidence. A partial answer never hides missing facts or
unresolved conflicts.

### Clarify decision

Requires `sufficient == false`, at least one missing fact, and no allowed claims. The bundle
carries no clarification prose.

### Abstain decision

Requires `sufficient == false` and no allowed claims, plus at least one of: missing required
facts, an unresolved conflict, or no accepted evidence. The bundle carries no abstention prose.

## StepResult and ExecutionPlan binding

Each accepted evidence item's provenance plan ID must equal the bundle's `plan_id`. Rule
evidence inputs must be accepted evidence in the same bundle. The contract validates these
structural bindings only; it does not load or interpret StepResult or ExecutionPlan content.

## Evidence validation boundary

Trusted evidence materialization performs, before constructing accepted Evidence:

1. resolve StepResult evidence references;
2. validate the evidence-type schema;
3. validate source and locator references;
4. validate artifact digests;
5. verify subject and time compatibility;
6. verify authorization and security scope;
7. verify provenance against StepResult and ExecutionPlan;
8. apply freshness policy;
9. reject unexpected fields;
10. classify accepted, degraded or rejected evidence.

The bundle validator cannot load referenced artifacts or external contracts.

## Evidence Manager boundary

The future deterministic Evidence Manager normalizes evidence, calculates required-fact
coverage, verifies subject and valid-time compatibility, verifies source-time and freshness,
applies authority and precedence policy, detects duplicate and conflicting evidence, resolves
conflicts where policy permits, builds exact fact maps, constructs allowed and prohibited
claims, makes the answer, partial, clarify or abstain decision, and emits replayable decision
reason codes. No LLM call is permitted in this process.

## Trust boundary

Evidence contracts are produced only by trusted deterministic code operating on accepted
StepResult output. The language model may read an EvidenceBundle to compose prose, but it
never edits sufficiency, conflict resolution, allowed claims or the decision field.

## Sensitive data restrictions

Evidence may refer to personal or confidential data. The contract never embeds actual selector
values, document text, raw web content, database rows, SQL, query text, prompt text, model
output, credentials, raw errors, URLs, or filesystem or cloud paths. A `personal` data scope is
a label, not authorization; authorization must already have completed. Trusted code verifies
authorization-decision consistency, plan and request consistency, runtime-snapshot consistency,
scope-reference validity, allowed-use compatibility and retention policy.

## Valid examples

### DocumentEvidence

```json
{
  "evidence_id": "a0000000-0000-4000-8000-000000000001",
  "evidence_type": "document",
  "subject": {"subject_type": "subject.employee", "subject_ref": "subject:7c1f"},
  "valid_time": {"as_of": "2026-01-01T12:00:00+00:00"},
  "source_time": {"observed_at": "2026-01-01T12:00:00+00:00"},
  "source": {
    "source_type": "source.policy-library",
    "source_ref": "source:2b9d",
    "source_version": "source-version:5"
  },
  "authority": "authority.official",
  "security_scope": {
    "scope_ref": "scope:general",
    "data_scope": "general",
    "classification": "classification.internal"
  },
  "validation_status": "validated",
  "freshness": "current",
  "provenance": {
    "step_result_id": "88888888-8888-4888-8888-888888888888",
    "plan_id": "44444444-4444-4444-8444-444444444444",
    "step_id": "step.retrieve",
    "capability": "document_retrieval",
    "operation": "document.retrieve",
    "materializer_version": "1.0.0",
    "input_digest": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
  },
  "allowed_uses": ["claim_support"],
  "retention_class": "retention.standard",
  "supports_fact_ids": ["fact.alpha"],
  "document_ref": "document:41ab",
  "document_version": "document-version:3",
  "chunk_ref": "chunk:9",
  "locator_ref": "locator:page-4",
  "content_ref": "content:8f21",
  "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "ranking_score": 0.82
}
```

### SqlEvidence (excerpt of variant-specific fields)

```json
{
  "evidence_type": "sql",
  "semantic_query_ref": "semantic-query:22",
  "semantic_catalog_version": "2.1.0",
  "result_ref": "result:77",
  "result_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "metric_codes": ["metric.headcount"],
  "filter_codes": [],
  "result_shape": "shape.scalar",
  "suppression_applied": false
}
```

### SelectorEvidence (excerpt)

```json
{
  "evidence_type": "selector",
  "selector_ref": "selector:leave-balance",
  "result_ref": "result:13",
  "result_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "field_codes": ["field.balance"]
}
```

### RuleEvidence (excerpt)

```json
{
  "evidence_type": "rule",
  "rule_bundle_ref": "rule-bundle:leave",
  "rule_code": "rule.leave-eligibility",
  "rule_version": "1.2.0",
  "outcome_ref": "outcome:5",
  "outcome_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "input_evidence_ids": ["a0000000-0000-4000-8000-000000000001"]
}
```

### WebEvidence (excerpt)

```json
{
  "evidence_type": "web",
  "page_ref": "page:0a3c",
  "allowlist_ref": "allowlist:official",
  "locator_ref": "locator:section-2",
  "content_ref": "content:1d4e",
  "content_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
```

## Valid bundle examples

### Answer

One required fact, one accepted DocumentEvidence supporting it, an exact fact map, one allowed
claim, `sufficient: true`, `decision: "answer"`.

### Partial answer

Two required facts; one is mapped to accepted evidence and one appears in `missing_fact_ids`.
`sufficient: false`, `decision: "partial_answer"`, at least one allowed claim for the covered
fact.

### Clarify

One required fact with no accepted evidence; the fact appears in `missing_fact_ids`,
`allowed_claims` is empty, `sufficient: false`, `decision: "clarify"`.

### Abstain

No accepted evidence at all, `allowed_claims` empty, `sufficient: false`,
`decision: "abstain"`, with a decision reason code such as `evidence.absent`.

## Representative invalid examples

| Example | Rejection reason |
| --- | --- |
| `decision: "answer"` with `sufficient: false` | sufficiency and decision are inconsistent |
| Accepted evidence in both `accepted_evidence` and `rejected_evidence` | identifiers must be disjoint |
| Fact-map entry referencing an evidence ID not in `accepted_evidence` | fact map must reference accepted evidence only |
| Resolved conflict with `controlling_evidence_id: null` | resolved conflicts require controlling evidence |
| Allowed claim using a fact in `missing_fact_ids` | claims may only use covered facts |
| A `content` field on any evidence variant | raw content is forbidden |

## Compatibility

Evidence 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing or renaming a field is a major change.
- Adding or changing an `EvidenceType`, decision, freshness, validation or conflict-status
  literal is a major change.
- Changing fact-map, support, conflict, sufficiency, claim, provenance, security, source, time,
  digest, retention or decision semantics is a major change.
- Adding controlled authority, source-type, allowed-use, reason, claim-code, metric, field,
  filter or rule catalog entries does not change the JSON Schema.
- Version 1.0.0 becomes immutable after approval.

## Non-goals

- This contract does not retrieve, fetch or dereference any artifact.
- This contract does not detect or resolve conflicts.
- This contract does not compute required-fact coverage or sufficiency; it validates that a
  computed result is internally consistent.
- This contract does not generate claim, clarification or abstention prose.
- This contract does not implement persistence, retention enforcement or an HTTP surface.

## Deferred implementation work

- Evidence artifact registry and resolver port.
- StepResult evidence materializer.
- Deterministic Evidence Manager.
- Required-fact coverage evaluator.
- Subject/time/freshness compatibility evaluator.
- Source authority and precedence policy.
- Conflict detector and conflict resolver.
- Allowed/prohibited claim compiler.
- Sufficiency and answer-decision engine.
- Citation locator resolver.
- Evidence retention and access enforcement.
- Evidence replay and regression fixtures.
- Integration with AnswerPlan and FinalAnswer.
