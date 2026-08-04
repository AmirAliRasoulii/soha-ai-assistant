# AnswerPlan 1.0.0

Status: Accepted and implemented as a bounded baseline
Owner: Answer Planning Boundary


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation was
accepted at commit `8d94c6a`.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| Answer planning consumes evidence but grants no authorization. A plan never adds a source that authorization did not already permit | Unchanged rule |
| No minimal typed `GenerationRequest` boundary exists between planning and generation (audit finding G-008). The future generator input must carry only the sanitized question, approved claims, approved caveats, bounded authorized evidence content, answer constraints, and response locale, and must never receive the full `RuntimeContext`, the full principal, roles or groups, the `AuthorizationDecision`, raw source-management metadata, or provider credentials | AI-007 |
| Evidence already carries `authority` as a controlled code and typed validity and source-time windows. Authority-driven conflict precedence and caveat generation are still not contractually expressible, because that code is not yet bound to trusted Source Registry authority metadata and the temporal values are not yet revalidated against `SourceRevision` state | AI-007 with CP-005 |
| Semantic claim validation is not yet contractual. The required future validation is deterministic numeric checks, semantic faithfulness and entailment checking, unsupported-claim rejection, bounded repair, and safe abstention or fallback (audit finding G-010) | AI-007 |
## Purpose

AnswerPlan is the immutable, validated semantic plan used to generate exactly
one user-facing response. It carries controlled identifiers, controlled
codes, and structural references only. It never carries answer prose,
prompts, model output, or resolvable source locators.

## AI Core boundary

AnswerPlan is produced after the deterministic Evidence Manager has already:

- normalized evidence;
- evaluated fact coverage;
- detected conflicts;
- made the sufficiency decision;
- constructed allowed claims;
- constructed prohibited claims.

AnswerPlan does not decide whether evidence is sufficient, does not create
new claims, does not select new evidence, does not resolve conflicts, and
does not invoke tools, capabilities, retrieval, SQL, or models.

AnswerPlan is not: answer text; a model prompt; a system prompt; an
EvidenceBundle; a FinalAnswer; a citation object; a source locator; a
generator request containing arbitrary context; a conversation response; an
HTTP contract; a provider object; or a persistence model.

## Relationship to EvidenceBundle

AnswerPlan references an EvidenceBundle by `evidence_bundle_id` only. The
Pydantic contract cannot dereference this identifier, so it cannot itself
prove that a planned claim, prohibited claim code, or cited evidence ID
exists in that bundle. A future, trusted AnswerPlanValidator performs that
exact binding (see "EvidenceBundle binding" below).

## Reason AnswerPlan cannot decide sufficiency

Sufficiency, conflict detection, and claim construction require inspecting
raw evidence content, which AnswerPlan never carries. AnswerPlan only
receives the already-decided outcome (`decision`) and the already-constructed
allowed and prohibited claim shapes. It structurally enforces internal
consistency of the plan; it cannot and does not re-derive the sufficiency
decision from evidence.

## Reused contracts

Reused without modification: `ContractModel`, `EvidenceDecision`,
`EvidenceSubjectRef`, `SchemaVersion`, `UtcDateTime`. AnswerPlan does not
embed `EvidenceBundle`, `AllowedEvidenceClaim`, `Evidence`, `ExecutionPlan`,
or `FinalAnswer`.

## Field tables

### AnswerPlan

| Field | Type | Notes |
| --- | --- | --- |
| schema_version | Literal["1.0.0"] | defaults to ANSWER_PLAN_SCHEMA_VERSION |
| answer_plan_id | UUID4 | |
| request_id | UUID4 | |
| evidence_bundle_id | UUID4 | |
| route_decision_id | UUID4 | |
| plan_id | UUID4 | |
| authorization_decision_id | UUID4 | |
| runtime_snapshot_id | UUID4 | |
| correlation_id | UUID4 | |
| built_at | UtcDateTime | |
| decision | EvidenceDecision | answer / partial_answer / clarify / abstain |
| answer_type | AnswerType | |
| sections | tuple[AnswerSection, ...] | 1..8, unique by section_id, ordered |
| claims | tuple[AnswerClaimPlan, ...] | default (), 0..32, unique by claim_id, ordered |
| caveats | tuple[AnswerCaveat, ...] | default (), 0..32, unique by caveat_id, ordered |
| citation_slots | tuple[CitationSlot, ...] | default (), 0..64, unique by slot_id, ordered |
| tone_constraints | AnswerToneConstraints | |
| prohibited_claim_codes | tuple[canonical code, ...] | default (), 0..64, unique, ordered |
| prohibited_content_codes | tuple[canonical code, ...] | 1..32, unique, ordered |
| decision_reason_codes | tuple[canonical code, ...] | 1..16, unique, ordered |
| length_budget | AnswerLengthBudget | |
| answer_plan_builder_version | SchemaVersion | |

### Nested models

**AnswerToneConstraints**: `response_locale` (locale tag), `tone_codes`
(tuple of canonical codes, 1..8, unique, ordered).

**AnswerLengthBudget**: `max_characters` (1..16000), `max_sections` (1..8),
`max_claims` (0..32), `max_caveats` (0..32), `max_citations` (0..64). All
strict integers; booleans and floats are rejected.

**AnswerSectionItemRef**: `item_kind` (AnswerSectionItemKind), `item_id`
(canonical code).

**AnswerSection**: `section_id` (canonical code), `section_type` (canonical
code), `items` (tuple[AnswerSectionItemRef, ...], 1..32, unique by
`(item_kind, item_id)`, ordered).

**AnswerClaimPlan**: `claim_id`, `claim_code`, `claim_type` (canonical
codes), `subject` (EvidenceSubjectRef), `supporting_fact_ids` (tuple of
canonical codes, 1..16, unique, ordered), `evidence_ids` (tuple of UUID4,
1..32, unique, ordered).

**AnswerCaveat**: `caveat_id`, `caveat_code` (canonical codes),
`related_claim_ids` (tuple of canonical codes, default (), 0..16, unique,
ordered), `evidence_ids` (tuple of UUID4, default (), 0..32, unique,
ordered), `reason_codes` (tuple of canonical codes, 1..16, unique, ordered).

**CitationSlot**: `slot_id` (canonical code), `target_kind`
(CitationTargetKind), `target_id` (canonical code), `evidence_ids` (tuple of
UUID4, 1..32, unique, ordered), `placement` (CitationPlacement).

## Answer-type catalog

`direct`, `summary`, `explanation`, `comparison`, `procedure`, `status`,
`eligibility`, `analytics`, `composite`, `clarification`, `abstention`.
Unknown values fail validation. `clarification` is required for `clarify`
decisions and forbidden otherwise; `abstention` is required for `abstain`
decisions and forbidden otherwise.

## Decision semantics

AnswerPlan reuses `EvidenceDecision` (`answer`, `partial_answer`, `clarify`,
`abstain`) rather than defining a second decision catalog.

- **answer**: `answer_type` is not `clarification` or `abstention`; at least
  one claim exists; every claim has a citation slot; caveats are optional.
- **partial_answer**: same claim and citation rules as `answer`, plus at
  least one caveat must exist, explicitly retaining the limitation that
  caused the partial decision.
- **clarify**: `answer_type` must be `clarification`; `claims` must be
  empty; at least one caveat must exist; any citation slots must target
  caveats only; the plan contains no clarification prose.
- **abstain**: `answer_type` must be `abstention`; `claims` must be empty;
  at least one caveat must exist; any citation slots must target caveats
  only; the plan contains no abstention prose.

## Section and ordered-item semantics

Sections form an exact presentation partition: every planned claim and
caveat appears in exactly one section item, never zero and never more than
one. A `claim` item cannot reference a caveat and a `caveat` item cannot
reference a claim. Section order is the tuple order of `AnswerPlan.sections`;
item order is the tuple order of `AnswerSection.items`. No section may be
empty. No title, heading, or body text field exists on a section; a future
presentation catalog maps `section_type` to localized rendering behavior.

## Claim semantics

An `AnswerClaimPlan` stores only identifiers, codes, a subject reference,
supporting fact IDs, and evidence IDs — never prose, a value, or a
confidence score. Its fields must match one `AllowedEvidenceClaim` in the
referenced EvidenceBundle exactly; the AnswerPlan contract itself cannot
prove this binding. Planned claim codes must be unique, and no planned claim
code may also appear in `prohibited_claim_codes`.

## Required-caveat semantics

An `AnswerCaveat` is required semantic content represented by controlled
codes only, never prose. `related_claim_ids` must reference claims that
exist in `claims`. Caveat-code catalogs such as `missing_fact`,
`unresolved_conflict`, `stale_evidence`, `degraded_evidence`,
`scope_limitation`, `partial_result`, `clarification_required`, and
`no_safe_answer` are open controlled catalogs and are not closed in JSON
Schema.

## Citation-slot semantics

A `CitationSlot` targets exactly one claim or caveat and authorizes citation
placement without carrying any rendered citation, label, or locator. Every
cited evidence ID must already belong to the targeted claim's or caveat's
`evidence_ids`. A caveat citation slot requires the caveat to carry evidence.
Duplicate semantic slots (same target, evidence IDs, and placement) are
rejected. Every planned claim requires at least one citation slot; caveats
may have zero. Not all of a claim's evidence IDs need to be cited — a
trusted citation policy may select the controlling or most useful evidence.

## Tone constraints

`AnswerToneConstraints` carries a `response_locale` and a bounded, unique,
order-preserving tuple of controlled `tone_codes` (1..8). Tone constraints
affect linguistic presentation only. They must never weaken a safety
restriction, hide uncertainty, omit required caveats, change evidence
precedence, change authorization, change the answer decision, or introduce
unsupported claims. No free-form tone instruction or persona text is
permitted.

## Length budget

`AnswerLengthBudget` is a hard structural output budget — not a token
budget, model context budget, provider quota, cost budget, or latency
budget. AnswerPlan enforces `len(sections) <= max_sections`,
`len(claims) <= max_claims`, `len(caveats) <= max_caveats`, and
`len(citation_slots) <= max_citations`. Because no final rendered content
exists yet, AnswerPlan does not calculate a character count; a future
FinalAnswer validator verifies rendered content against `max_characters`.

## Prohibited claims and content

`prohibited_claim_codes` (default (), 0..64, unique, ordered) must never
overlap with planned claim codes. `prohibited_content_codes` (1..32, unique,
ordered) may never be empty. `decision_reason_codes` (1..16, unique,
ordered) may never be empty.

## EvidenceBundle binding

Trusted validation, external to this contract, must compare AnswerPlan with
its referenced EvidenceBundle and verify:

- request ID, route-decision ID, plan ID, authorization-decision ID,
  runtime-snapshot ID, and correlation ID all match;
- `decision` matches, and `decision_reason_codes` are authorized;
- every planned claim exactly matches an allowed claim, including subject
  and supporting fact IDs;
- every prohibited claim code originates from the bundle;
- evidence IDs match or are an approved subset under citation policy;
- all cited evidence is accepted evidence, and no cited evidence is
  rejected evidence;
- every caveat is justified by missing facts, conflicts, freshness,
  degraded evidence, or decision policy;
- unresolved conflicts and missing facts are not hidden;
- answer and partial plans contain no prohibited claim.

The Pydantic contract cannot dereference `evidence_bundle_id` and does not
embed EvidenceBundle.

## Generator boundary

Generator input boundary: AnswerPlan, plus approved Evidence
references/materialized evidence, plus versioned language templates.

The Generator may produce only: natural-language realization of planned
claims; required caveats; section transitions; citation-slot markers.

The Generator may not: call tools; retrieve more evidence; execute SQL;
change the decision; change claim IDs; add facts; remove caveats; create
citation labels; create source locators; expose prompts or reasoning.
Generator output remains untrusted until claim validation and citation
compilation complete.

## Server-side citation boundary

The Citation Compiler must resolve Evidence locators through trusted ports,
create source labels, verify source-version consistency, verify locator
resolvability, attach citations to authorized slots, and reject unsupported
or fabricated citation markers. AnswerPlan contains only citation-slot
declarations; it contains no rendered citation.

## Trust boundary

AnswerPlan is produced by the deterministic Answer Planning boundary and is
structurally validated on construction. It is trusted for structure only.
Semantic correctness against the EvidenceBundle, source resolvability, and
rendered content correctness are established by boundaries outside this
contract (AnswerPlanValidator, Citation Compiler, FinalAnswer validator).

## Security and privacy restrictions

The contract must not contain: actual answer, clarification, or abstention
text; document excerpts; raw evidence content; selector or database values;
SQL; prompts; provider responses; model output; personal values;
credentials; source URLs; filesystem paths; chain-of-thought; or
model-supplied confidence. Subject and evidence references remain opaque;
the contract grants no access to referenced evidence.

## Retention

This contract does not authorize persistence. The plan contains semantic
IDs, controlled codes, and references — not response prose. Plans may be
retained for replay, audit, and evaluation only under approved policy.
Referenced evidence has independent retention and access controls.
Generated drafts and final answers have separate retention controls.
Prompts, raw evidence, personal values, credentials, and model reasoning
must never be copied into AnswerPlan. Telemetry should normally use
answer-plan ID, bundle ID, decision, answer type, section count, claim
count, caveat count, citation count, builder version, and correlation ID.

## Valid answer example

```json
{
  "schema_version": "1.0.0",
  "answer_plan_id": "11111111-1111-4111-8111-111111111111",
  "request_id": "22222222-2222-4222-8222-222222222222",
  "evidence_bundle_id": "33333333-3333-4333-8333-333333333333",
  "route_decision_id": "44444444-4444-4444-8444-444444444444",
  "plan_id": "55555555-5555-4555-8555-555555555555",
  "authorization_decision_id": "66666666-6666-4666-8666-666666666666",
  "runtime_snapshot_id": "77777777-7777-4777-8777-777777777777",
  "correlation_id": "88888888-8888-4888-8888-888888888888",
  "built_at": "2026-01-01T12:00:00+00:00",
  "decision": "answer",
  "answer_type": "direct",
  "sections": [{"section_id": "section.one", "section_type": "section.summary", "items": [{"item_kind": "claim", "item_id": "claim.one"}]}],
  "claims": [{"claim_id": "claim.one", "claim_code": "claim.code.one", "claim_type": "claim.type.direct", "subject": {"subject_type": "subject.policy", "subject_ref": "subject:alpha"}, "supporting_fact_ids": ["fact.alpha"], "evidence_ids": ["a0000000-0000-4000-8000-000000000001"]}],
  "caveats": [],
  "citation_slots": [{"slot_id": "citation.one", "target_kind": "claim", "target_id": "claim.one", "evidence_ids": ["a0000000-0000-4000-8000-000000000001"], "placement": "inline"}],
  "tone_constraints": {"response_locale": "en", "tone_codes": ["neutral"]},
  "prohibited_claim_codes": [],
  "prohibited_content_codes": ["content.prohibited.one"],
  "decision_reason_codes": ["reason.answer_ready"],
  "length_budget": {"max_characters": 4000, "max_sections": 8, "max_claims": 32, "max_caveats": 32, "max_citations": 64},
  "answer_plan_builder_version": "1.0.0"
}
```

## Valid partial-answer example

Same shape as above with `decision: "partial_answer"`, a second section
whose item is `{"item_kind": "caveat", "item_id": "caveat.one"}`, and
`caveats: [{"caveat_id": "caveat.one", "caveat_code": "caveat.code.missing_fact", "reason_codes": ["reason.missing_fact"]}]`.

## Valid clarification example

`decision: "clarify"`, `answer_type: "clarification"`, `claims: []`, one
section with a single caveat item, one caveat with evidence and a matching
caveat-targeted citation slot with `placement: "section_end"`.

## Valid abstention example

Same shape as the clarification example with `decision: "abstain"` and
`answer_type: "abstention"`.

## Representative invalid examples

- An `answer` decision with `claims: []` — rejected (answer requires a claim).
- A `clarify` decision that also carries `claims` — rejected.
- A citation slot whose `evidence_ids` are not a subset of the targeted
  claim's `evidence_ids` — rejected.
- A section containing a `claim` item that references a caveat ID —
  rejected.
- A root payload with an added `answer_text` field — rejected (unknown /
  forbidden field).

## Compatibility

AnswerPlan 1.0.0 is closed. PATCH changes must not alter accepted or
serialized payloads. Adding, removing, or renaming a field is a MAJOR
change. Adding or changing an `AnswerType`, item-kind, citation-target, or
placement literal is a MAJOR change. Changing decision, section-partition,
claim, caveat, citation, budget, EvidenceBundle-binding, Generator, or
privacy semantics is a MAJOR change. Adding controlled section-type,
claim-type, caveat, tone, reason, or prohibited-content catalog entries does
not change this JSON Schema. Version 1.0.0 becomes immutable after
approval.

## Non-goals

AnswerPlan does not decide evidence sufficiency, does not select or
construct claims, does not resolve conflicts, does not render answer text,
does not compile citations, and does not enforce a final character budget.

## Deferred implementation work

- Deterministic AnswerPlan builder.
- AnswerPlanValidator performing exact EvidenceBundle binding.
- Section-type and presentation catalog.
- Localized claim realization templates.
- Localized caveat and safe-message catalogs.
- Generator request and draft-output contracts.
- Claim validator.
- Citation-slot renderer.
- Server-side Citation Compiler.
- Evidence locator resolver.
- Final character-budget enforcement.
- AnswerPlan replay and regression fixtures.
- Integration with FinalAnswer.
