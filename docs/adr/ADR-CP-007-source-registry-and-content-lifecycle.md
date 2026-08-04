# ADR-CP-007: Source Registry and Content Lifecycle

Status: Accepted architecture baseline (originated as CP-000B; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000B architecture package
Owner: Control Plane / Source Registry Baseline
Scope: conceptual model and lifecycle for persistent knowledge sources only. No typed contract,
database schema, ORM, API, admin surface, storage, ingestion, index, or retrieval design is
decided here.
Companions: `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`,
`docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`,
`docs/control-plane/CP-000A-authorization-matrix.md`,
`docs/control-plane/CP-000B-source-lifecycle-matrix.md`

## Existing contract boundary

The existing Core contract boundary already represents source identity and version opaquely
through `EvidenceSourceRef` (`source_type`, `source_ref`, and `source_version`). Existing
evidence and citation contracts also include `DocumentEvidence`, `FinalCitationSource`,
`ResolvedCitationSource`, `CitationSourceResolverPort`, `EvidenceSecurityScope`, and an
`index_snapshot` artifact reference.

This ADR defines `KnowledgeSource`, `SourceRevision`, visibility-policy binding, source and
revision status, revocation, disablement, archival, purge, and content-artifact references only
as conceptual Control Plane constructs. Typed contract shapes remain deferred to CP-001. No
branch, commit, working-tree, database, transport, or provider assumption is part of this ADR.

## Context

The existing contracts consume a source as three opaque codes -- `source_type`, `source_ref`,
`source_version` -- and require citations to resolve to a specific source version through a
resolver port. Nothing in the repository defines what produces those codes, what makes a source
version trustworthy, or what makes it stop being retrievable.

CP-000A supplies the authorization half: organizational nodes, memberships, scoped roles,
versioned visibility policy definitions, classification ceilings, and a mandatory retrieval
pre-filter. It deliberately deferred the source lifecycle. Without this package, the two halves
cannot meet: a visibility policy has nothing durable to bind to, and revocation has no defined
meaning.

The product requirement is narrow and concrete: administrators register uploaded documents and
official URLs, review and activate them, publish new versions without breaking existing
citations, and remove content from answers immediately when something is wrong -- without
waiting for re-indexing or physical deletion.

## Decision

A-1. Exactly two persistent source types are supported initially: `uploaded_document` and
`official_url`. No connector framework, general web search source, chat attachment registry,
crawler framework, external SaaS integration, or database/mail/filesystem connector is
introduced. Those remain future capabilities.

A-2. An `official_url` is a registered persistent source with an administrative owner, a bound
visibility policy, a classification, and a revision history. It is never an unrestricted
web-search result.

A-3. Stable identity and immutable content are separate concepts: `KnowledgeSource` is the
stable administrative identity, `SourceRevision` is an immutable content-and-policy snapshot
after activation.

A-4. At most one revision of a source is active at a time. Editing an activated revision in
place is forbidden. Updating a source creates a new draft revision.

A-5. Source lifecycle and revision lifecycle are separate state machines and are never merged
into one enum.

A-6. Administrative ownership is an administration pointer only. It grants no read, no
visibility change, no classification change, and no raw-content inspection.

A-7. Uploader-submitted metadata is untrusted input until validated and persisted as an
approved artifact. Missing visibility policy means draft-only and deny, never a default.

A-8. Retrieval eligibility is a conjunction of trusted state checks (see "Runtime eligibility
invariant"). Any failure excludes the revision; no failure ever falls back to unfiltered
retrieval.

A-9. "Delete" is not a product operation. It resolves to one of `disable`, `revoke`, `archive`,
or `request physical purge`.

## Conceptual domain model

Conceptual entities and value objects, not ORM models, tables, or typed contracts. Existing
repository documentation uses plain fenced blocks rather than Mermaid, so that convention is
followed.

Diagram 1 -- conceptual source/revision relationship:

```text
Organization (ADR-CP-001)
└── OrganizationalNode  <---- administrative_owner_node_ref (administration only, no read)
        |
        |  administers
        v
KnowledgeSource                       (source_ref, stable identity, source_status)
├── current_active_revision_ref  ----> at most one ACTIVE SourceRevision
└── SourceRevision*                    (immutable after activation)
     ├── v1  SUPERSEDED   supersedes_revision_ref: none
     ├── v2  ACTIVE       supersedes_revision_ref: v1
     └── v3  DRAFT        supersedes_revision_ref: none until activation

SourceRevision binds:
     content_artifact_ref   (uploaded_document)  |  official_url_ref (official_url)
     visibility_policy_ref  ----> VisibilityPolicyDefinition revision (ADR-CP-002)
     classification         ----> ceiling evaluated by authorization (ADR-CP-002)
     content_digest         ----> trusted integrity value

Evidence and citations reference a revision, never a mutable source body.
```

## KnowledgeSource semantics

Conceptual fields (at minimum):

| Field | Meaning | Trust |
|---|---|---|
| `source_ref` | Stable opaque identity of the source; never reused, never derived from a title or URL | Control-plane assigned |
| `organization_ref` | Owning organization; immutable for the life of the source | Control-plane assigned |
| `source_type` | `uploaded_document` or `official_url`; immutable for the life of the source | Validated against the supported set |
| `administrative_owner_node_ref` | The node authorized to administer the source | Validated; never inferred from labels |
| `current_active_revision_ref` | The single active revision, or none | Control-plane derived |
| `source_status` | `ACTIVE`, `DISABLED`, `REVOKED`, or `ARCHIVED` | Control-plane state machine |
| `created_at` | Creation timestamp | Control-plane assigned |
| `created_by_principal_ref` | Authenticated creating principal | Trusted identity fact |

K-1. A source has exactly one current administrative owner node, which must be a valid node in
the same organization. Cross-organization ownership is invalid input, not a policy question.

K-2. Administrative ownership does not grant read access, does not change visibility, does not
change classification, and does not grant raw-content inspection. Membership in the owner node
grants nothing (ADR-CP-002 A-2, U-2).

K-3. Ownership may be changed by an explicitly authorized administrator. Ownership is **not**
immutable, and no origin-and-destination approval workflow is mandated by this baseline.

K-4. Ownership changes are independently audited and ownership history remains auditable. A
change of owner must never be inferable only from current state.

K-5. `administrative_owner_node_ref` must never be inferred from display labels, uploader-typed
unit names, or uploader-provided organization metadata (ADR-CP-001 R-2).

K-6. `source_ref` remains stable across every revision, ownership change, policy rebinding, and
lifecycle transition, so that citations and audit records stay resolvable.

K-7. A source with no activated revision is never retrievable, regardless of `source_status`.

## SourceRevision semantics

Conceptual fields (at minimum):

| Field | Meaning |
|---|---|
| `source_revision_ref` | Stable opaque identity of this revision |
| `source_ref` | Owning source identity |
| `revision_number` | Monotonic ordinal within the source |
| `title` | Human-facing title captured in the revision, never an authorization input |
| `content_artifact_ref` | For `uploaded_document`: managed immutable content artifact reference |
| `official_url_ref` | For `official_url`: the registered URL and its normalized trusted representation |
| `visibility_policy_ref` | The single approved `VisibilityPolicyDefinition` revision bound to this revision |
| `classification` | Sensitivity attribute; a ceiling input, never a grant |
| `revision_status` | `DRAFT`, `IN_REVIEW`, `APPROVED`, `ACTIVE`, `SUPERSEDED`, or `REJECTED` |
| `content_digest` | Trusted integrity value over the immutable revision payload; uploaded-document content or normalized official-URL registration payload |
| `created_at` / `created_by_principal_ref` | Draft creation facts |
| `approved_at` / `approved_by_principal_ref` | Approval facts, absent until approved |
| `activated_at` / `activated_by_principal_ref` | Activation facts, absent until activated |
| `supersedes_revision_ref` | The revision this one displaced at activation, if any |
| `effective_from` | Trusted business effective time of this revision. See "Source temporal metadata" |
| `valid_until` | Nullable trusted end of business validity; null means open-ended |
| `published_at` | Optional business publication time; may be unknown |
| `observed_at` | Trusted fetch/ingestion observation time |
| `authority_class_ref` | Trusted authority classification reference. See "Source authority" |
| `issuer_ref` | Trusted reference to the issuing body or authority for this revision |
| `authority_assignment_policy_ref` | The versioned policy revision under which authority was assigned or confirmed |

R-1. Exactly one content locator is present per revision, determined by `source_type`:
`content_artifact_ref` for `uploaded_document`, `official_url_ref` for `official_url`. Both
present, or neither, is invalid.

R-2. Physical storage is not prescribed. `content_artifact_ref` is a reference to a managed
immutable artifact; where and how it is stored is an open decision.

R-3. For `official_url`, the revision captures the registered URL plus its normalized trusted
representation. Crawling, fetch frequency, robots handling, and webpage extraction are **not**
designed here.

R-4. After activation a revision is immutable in every field, including title, policy binding,
classification, and digest. Change means a new revision.

R-5. Every revision binds exactly one visibility policy revision and one classification. A
revision without a policy binding cannot leave draft.

R-5A (pinned visibility policy revision). `visibility_policy_ref` is a **pinned exact immutable
`VisibilityPolicyDefinition` revision**, not a policy identity that follows whichever revision is
currently active. There is no follow-active behavior in v1:

```text
no implicit follow-latest
no model-selected policy revision
no client-selected active revision
missing policy revision      -> fail closed (deny, draft-only)
inactive or revoked revision -> source ineligible
```

Authorization and audit records carry the exact consulted policy revision. Changing the binding
never mutates an active `SourceRevision` in place: it requires a new immutable source revision, or a
future explicitly versioned and audited migration mechanism. Emergency policy revocation invalidates
the affected source eligibility immediately. Full semantics are in
`docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md` under "Pinned visibility policy
binding".

R-6. `content_digest` is trusted metadata. For `uploaded_document` it covers the managed
content payload; for `official_url` it covers the normalized registered-URL revision payload.
Digesting fetched webpage content belongs to the future ingestion package. A revision whose
immutable payload does not match its digest is ineligible, not repaired at read time.

R-7. Approval and activation facts are recorded separately, by potentially different principals,
because the two permissions are distinct.

## Source authority

Authority answers "how authoritative is this source", which is a different question from "who may
read it". It exists because evidence-based answering needs deterministic conflict precedence, and
because a model must never invent that precedence itself.

Conceptual trusted authority metadata:

```text
authority_class_ref                 trusted authority classification
issuer_ref (or authority_ref)       the issuing body or authority
authority_assignment_policy_ref     the versioned policy under which authority was assigned
```

AU-1. A contributor **may propose** authority metadata when creating or editing a draft. A proposal
is a request, not a fact (U-4).

AU-2. The Central Source Approver confirms the proposed authority, or assigns it from an approved
versioned catalog. Authority becomes trusted only through that workflow.

AU-3. Authority values supplied by an LLM, a client, a filename, or document text are **untrusted**
and may never be persisted as trusted authority metadata.

AU-4. Authority is **not an authorization grant**. High authority never widens visibility, never
bypasses classification, and never substitutes for a visibility policy.

AU-5. Authority **may** affect deterministic conflict precedence, retrieval ranking, and the caveats
attached to a generated answer. Those effects must be deterministic and explainable, never model
judgement.

AU-6. Authority catalogs and authority profiles are versioned artifacts. Changing a catalog is a
versioned, audited control-plane change, not a free-text edit.

AU-7. The exact typed fields, the catalog shape, and the ranking function remain CP-001 and CP-005
work. This ADR fixes the semantics and the trust boundary only.

## Source temporal metadata

T-1. `effective_from` is the trusted **business** effective time of the revision: the time from
which the content is considered to apply. When it is absent, the trusted default is the activation
time.

T-2. `valid_until` is **nullable and open-ended**. Null means the revision stays valid until an
explicit lifecycle or security action ends it. Null is never interpreted as expired, and it is never
silently replaced with a computed horizon.

T-3. `published_at` is the optional **business publication** time. It may be unknown, and unknown is
recorded as unknown rather than guessed.

T-4. `observed_at` is the trusted **fetch or ingestion observation** time: when the platform saw
this content.

T-5. File upload time is **not** business publication time. Equating them is explicitly forbidden:
an uploaded circular from 2019 does not become a 2026 publication because it was uploaded in 2026.

T-6. Temporal metadata is trusted control-plane output. It is never parsed from document text by a
model, never taken from a filename, and never supplied by a client as an authorization or
eligibility input. Retrieval consumes it through the `valid_from` / `valid_until` rules in
`docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md` (L-9A to L-9C).

T-7. Missing, malformed, or untrusted temporal metadata never broadens eligibility.

## Source relationships

```text
SUPERSEDES     relation between revisions of the SAME KnowledgeSource
SUPPLEMENTS    versioned relation between SEPARATE KnowledgeSources
no relation    the sources are independent
```

SR-1. One `KnowledgeSource` still has **at most one active revision**. Supersession is the
same-source mechanism, and it does not create two concurrently active revisions.

SR-2. Activating a newer revision of the same source supersedes the previous revision atomically
(see "Update and versioning rules").

SR-3. Superseded content is retained for audit, for historical citation resolvability, and for
explicit historical queries. Supersession changes retrieval eligibility, not resolvability (W-3).

SR-4. `SUPPLEMENTS` is a versioned relation **between separate `KnowledgeSource` instances**. Two
supplemental sources may both remain active and both remain retrievable at the same time. A
supplement never silently deactivates the source it supplements. This is why a supplement cannot be
modeled as a second active revision of one source.

SR-5. Absence of a relationship means the sources are independent. Independence is the default.

SR-6. An LLM must **not** infer, create, or modify these relationships. Relationships are trusted
control-plane facts created by an authorized actor.

SR-7. `AMENDS` and `PARTIALLY_SUPERSEDES` remain **explicitly deferred**. Partial amendment must not
be guessed: until a typed relation exists, a document that partially changes another is registered
as an independent or supplemental source, never as a partial override.

## Source metadata classes

Source metadata is not one resource. Reading "source metadata" is split into four distinct
resources, because a citation footnote and an internal review queue are not the same data.

| Metadata class | Contents | Who may read it |
| --- | --- | --- |
| `CitationSafePublishedSourceMetadata` | Only the minimum published facts needed for citation and explanation: title, source type, issuer or authority as published, publication or effective time, and the stable citation reference | Readable by any actor already entitled to read the content through ordinary policy, including End User and Guest |
| `ManagementSourceMetadata` | Internal ownership, administrative owner node, review state, internal locator, legal hold, purge state, workflow detail, and internal status detail | Requires explicit management permission in scope. Never granted by a general "view metadata" permission |
| `LifecycleAuditMetadata` | Lifecycle audit trail: who submitted, approved, rejected, activated, revoked, and why | Requires audit or lifecycle-audit permission in scope |
| `RawSourceContent` | The raw stored payload or raw registered fetch payload | Requires the separate raw-content inspection permission, a recorded reason, and an audit obligation |

M-1. Citation-safe metadata may include **only** the minimum published facts needed for citation and
explanation. It is a data-minimization boundary, not a convenience subset.

M-2. Guest and ordinary End User do **not** receive management metadata through a general "view
metadata" permission. There is no permission in this baseline that grants both citation metadata and
management metadata as one bundle.

M-3. Administrative owner identity, review queue position, audit reason, raw locator, internal status
detail, and purge or legal-hold metadata are management or audit metadata. They are never part of
citation metadata.

M-4. Per-actor semantics for each of these four read actions are in
`docs/control-plane/CP-000B-source-lifecycle-matrix.md`, which is the canonical source-action matrix.

## Workflow boundary

These lifecycles are separate and must not be conflated. Each has its own failure modes and its own
owner package.

```text
SourceRevision business lifecycle     (this ADR)
ingestion validation                  (ingestion package)
quarantine                            (ingestion/security package)
parsing / OCR                         (CP-006)
index-build lifecycle                 (CP-006)
index activation                      (CP-006)
physical cleanup                      (storage/compliance package)
```

WB-1. Business approval does **not** imply that any ingestion, parsing, OCR, or index-build step
succeeded. `APPROVED` is a business decision about the content, not a technical success signal.

WB-2. Source activation requires **all applicable gates** to pass: business approval, ingestion
validation, and index availability where retrieval depends on it. A failure in any applicable gate
blocks activation.

WB-3. A revision that is business-approved but not technically ready is not eligible for retrieval.
It fails closed rather than being served without an index.

WB-4. Conversely, a successful index build never substitutes for business approval. Neither
direction implies the other.

## Supported source types

| Type | What it is | What it is not |
|---|---|---|
| `uploaded_document` | A document registered as a persistent source, whose content is a managed immutable artifact | Not a chat attachment, not an ad-hoc file reference |
| `official_url` | A registered persistent URL source with owner, policy, classification, and revisions | Not a web-search result, not a crawl seed, not an unrestricted fetch target |

S-1. The supported set is closed in this baseline. Adding a type is a versioned control-plane
change with its own package, not a configuration value.

S-2. Chat attachments are explicitly outside the registry. A future package may decide whether
and how an attachment is promoted into an `uploaded_document`.

S-3. Unsupported or unknown `source_type` fails closed at validation.

## Required uploader metadata

U-1. When creating a new source or a new draft revision, the authorized actor must provide or
select: `title`, `source_type`, `administrative_owner_node_ref`, `visibility_policy_ref`,
`classification`, and either the uploaded content or the official URL.

U-2. The control plane validates, and rejects on any failure:

- the actor may administer the selected owner node;
- the owner node belongs to the stated organization;
- the visibility policy revision is active and selectable within the actor's delegated scope;
- the classification is permitted within that scope;
- the actor cannot widen access beyond delegated authority;
- the source type is supported;
- the submitted content or URL satisfies validation requirements.

U-3. Missing `visibility_policy_ref` means deny and draft-only. Missing visibility is never
defaulted to organization-wide, anonymous-public, or any other value.

U-4. Uploader-submitted metadata is untrusted until validated and persisted as an approved
artifact. Until then it is a request, not a fact, and no authorization decision may consult it
(ADR-CP-002 forbidden inputs).

U-5. Selecting metadata is never policy authoring. Creating, approving, and activating visibility
policy definitions are separate permissions held elsewhere (ADR-CP-002 U-5).

## Administrative ownership, visibility, and classification binding

O-1. Managers with explicit delegated permission may change administrative ownership, bind a
different approved visibility policy revision, and change classification within delegated bounds.
These three operations are independent and separately authorized.

O-2. Changing ownership must not automatically change visibility, classification, content, the
active revision, or read authorization. A reorganization is not a republication.

O-3. Changing visibility or classification is authorization-relevant and requires an audited new
revision or an equivalent versioned, audited policy-binding change record. It is never an
in-place edit of an activated revision (A-4, R-4).

O-4. A widening change -- to a broader policy or a lower classification -- is bounded by the
acting principal's delegated authority. Widening beyond that authority is denied, not escalated.

O-5. Exact approval requirements for these operations remain versioned deployment policy. This
baseline mandates separability and auditability, not a specific workflow.

## Source approval workflow (v1)

The accepted v1 workflow is a **single centrally assigned Source Approver**, not one approver per
faculty or department:

```text
Department Contributor
    -> create / upload / edit own draft
    -> submit
        -> Central Source Approver
            -> read the pending review surface
            -> approve or reject the business decision

Control Plane Application Service
    -> after business approval
    -> after every applicable validation, ingestion, and index gate
    -> transition the revision to ACTIVE
    -> automatically mark the previous active revision SUPERSEDED
```

AP-1. Department contributors may hold `source.create`, `source.upload`, `source.edit_own_draft`, and
`source.submit` within their delegated scope.

AP-2. The Central Source Approver holds `source.review`, `source.approve`, and `source.reject`.

AP-3. `source.review` permits reading pending source submissions from **all departments**, because
that is the required review surface for a single central approver. It does **not** independently
grant access to unrelated active or restricted content, and it is not a general read permission.

AP-4. The same principal must not approve a source submission that they created, authored, uploaded,
or submitted. Holding `source.approve` does not override this v1 self-approval prohibition. Uploading or
submitting is never approving.

AP-5. v1 does **not** introduce one approver per faculty or department. That remains a possible
future governance option, not a current requirement.

AP-6. The Global or System Account Administrator **assigns** the approver capability. Assigning the
capability does not make that administrator a source author: account and permission administration is
separate from content authorship, and no administrative role acquires ordinary source-authoring
permission implicitly.

AP-7. `source.approve` records **business approval only**. It does not by itself make a revision
`ACTIVE`. `ACTIVE` eligibility additionally requires all applicable validation, ingestion, and index
gates to have passed. Approval alone never activates a source.

AP-8. After business approval and all required technical gates, the Control Plane may perform the
`ACTIVE` transition. Whether that happens in the same command or in a separate application-service
step is owned by **CP-009 Control Plane Application Services**. v1 introduces no new human-facing
`source.activate` permission.

AP-9. A contributor or client **may propose** temporal metadata in a draft. The proposal is
**untrusted**. Only validated, confirmed, and persisted Control Plane metadata is used by
authorization, retrieval, or evidence eligibility. A client can never directly supply trusted
temporal metadata.

AP-10. The exact configurable separation-of-duties model beyond the mandatory AP-4 same-principal
self-approval prohibition remains open, and the required
review-surface contract for the approver is future work (CP-001, CP-009).

## Source lifecycle

| State | Meaning | Rules |
|---|---|---|
| `ACTIVE` | The source may expose its active revision to authorized retrieval | Still subject to every eligibility condition; ACTIVE is permission to be evaluated, not permission to be read |
| `DISABLED` | Temporary operational suspension | Excluded from new retrieval; historical audit remains; may be re-enabled by authorized action; does not imply the content is untrusted |
| `REVOKED` | Immediate fail-closed removal from eligibility | Excluded immediately; must not wait for re-indexing or physical deletion; downstream cache invalidation is required; historical audit remains; re-enablement is not an ordinary operation |
| `ARCHIVED` | Administrative historical state | Not eligible for new retrieval; retained according to retention policy; visible only through authorized historical/audit workflows |

L-1. Revocation grounds include untrusted content, security incident, incorrect publication,
license or legal withdrawal, data leakage risk, and a compromised official URL.

L-2. Revocation requires an explicit action, a recorded reason, and audit. It is never a side
effect of another operation.

L-3. A revoked source may require a new source or an explicitly approved recovery process. There
is no ordinary un-revoke.

L-4. `DISABLED` and `REVOKED` differ in intent and in re-entry cost, not in retrieval effect:
both exclude immediately.

L-5. No source state makes an inactive revision retrievable, and no source state bypasses
authorization.

## Revision lifecycle

| State | Meaning | Retrievable |
|---|---|---|
| `DRAFT` | Mutable working revision | Not retrievable |
| `IN_REVIEW` | Submitted, under review | Not retrievable |
| `APPROVED` | Review passed, not yet activated | Not retrievable until activated |
| `ACTIVE` | Immutable, current revision of the source | Eligible, subject to authorization and the full eligibility conjunction |
| `SUPERSEDED` | Displaced by a later activation | Not retrievable ordinarily; available for audit, citation resolution, and controlled rollback |
| `REJECTED` | Review failed | Not retrievable |

Diagram 2 -- source and revision state transitions:

```text
REVISION
  DRAFT ---- submit ----> IN_REVIEW ---- approve ----> APPROVED ---- activate ----> ACTIVE
    ^                         |                                                       |
    |                         +---- reject ----> REJECTED                             |
    |                                                                                  |
    +---- new draft (update) ------------------------------------------------------+   |
                                                                                   |   |
  previous ACTIVE ---- displaced atomically by activation ----> SUPERSEDED <--------+---+
  SUPERSEDED ---- audited rollback activation ----> ACTIVE   (history is not mutated)

SOURCE
  ACTIVE <---- re-enable (authorized) ---- DISABLED
  ACTIVE ---- disable ----> DISABLED
  ACTIVE | DISABLED ---- revoke (explicit action + reason + audit) ----> REVOKED
  ACTIVE | DISABLED ---- archive ----> ARCHIVED
  REVOKED ---- no ordinary transition out (recovery is an approved exception)
  ARCHIVED ---- retention-governed; request physical purge is a separate authority
```

V-1. `DRAFT` may be edited by authorized source managers in assigned scope. No other state is
editable.

V-2. `IN_REVIEW`, `APPROVED`, and `REJECTED` are not retrievable. Approval is not publication.

V-3. Activating a new revision atomically makes the previous active revision `SUPERSEDED`. There
is no observable interval with two active revisions and none with zero where one previously
existed.

V-4. `SUPERSEDED` remains available for audit, existing citation resolution, and controlled
rollback. It is never available to ordinary retrieval.

V-5. Business approval never activates a revision. `source.approve` records business approval only;
after approval and all required validation, ingestion, and index gates pass, the Control Plane
application service may transition the revision to `ACTIVE`, and activating a newer same-source
revision automatically marks the previous active revision `SUPERSEDED`. The `ACTIVE` transition and the
`SUPERSEDED` effect are lifecycle and application-service operations, not additional human-facing v1
permissions, and whether they occur in one command or a separate application-service step is CP-009
work (`AP-7`, `AP-8`). The architecture supports separation of duties; no two-person rule is mandated
here.

V-6. A rejected revision is terminal for that revision. Continuing means a new draft.

## Update and versioning rules

Required flow: active revision v1 -> create draft v2 (v1 untouched and still active) ->
submit for review -> approve -> activate v2 (atomic) -> v1 becomes `SUPERSEDED`.

W-1. Updating content never overwrites an active revision.

W-2. Source identity remains stable across updates; only `current_active_revision_ref` changes.

W-3. Citations and audit records referencing v1 remain resolvable after v2 is activated.
Supersession changes retrieval eligibility, not resolvability.

W-4. Rollback does not mutate history. It means selecting an eligible prior approved revision
through an audited activation command, or creating an equivalent new activation record.

W-5. A revision may not be re-activated if its policy binding or classification is no longer
valid; the eligibility conjunction is re-evaluated at activation time, not inherited.

W-6. The final event-storage implementation is not prescribed. The invariant is that activation,
supersession, and rollback are recoverable facts, not derived guesses.

## Delete, revoke, archive, and purge semantics

D-1. Immediate physical hard deletion is not the ordinary product meaning of "delete".

D-2. Four distinct conceptual operations are exposed: `disable`, `revoke`, `archive`, and
`request physical purge`. A user-facing delete command must resolve to exactly one of them, and
the resolution must be explicit to the acting administrator.

D-3. Physical purge is separate from revocation; is subject to retention, legal hold, audit, and
compliance policy; may be asynchronous; must never be required for immediate retrieval
exclusion; and remains an open implementation and compliance decision.

D-4. Retrieval exclusion is always achieved by state, never by waiting for storage or index
operations to complete.

D-5. Node Managers and Organization Admins may manage sources only through explicitly granted
actions within assigned scope. Global administration grants no raw-content access (ADR-CP-002
A-2, A-6).

## Runtime eligibility invariant

A source revision is eligible for retrieval only when **all** of the following hold:

1. `source_status` is `ACTIVE`.
2. `revision_status` is `ACTIVE`.
3. The revision is the source's `current_active_revision_ref`.
4. The bound visibility policy revision is active and valid.
5. Classification authorization passes against the actor's ceiling (ADR-CP-002 K-3).
6. The source is not revoked.
7. The content/revision digest matches trusted metadata.
8. The authorization decision grants the required security scope.
9. Current trusted time is greater than or equal to `effective_from`.
10. `valid_until` is null, **or** current trusted time is less than or equal to `valid_until`.

E-1. The conjunction is evaluated from trusted state and versioned artifacts only. No condition
may be satisfied by uploader metadata, client input, document content, or LLM output.

E-2. An empty authorized scope produces no results. It never produces unscoped results.

E-3. No state failure may fall back to unfiltered retrieval. Every failure is exclusion.

E-4. Post-retrieval removal is insufficient; the exclusion must be applied before retrieval, as
required by ADR-CP-002 E-1.

E-5. The physical index filter is **not** designed here. This ADR defines only the invariant
that the retrieval path must enforce.

E-6. Guest reads follow the same conjunction, with the additional CP-000A constraints:
`anonymous-public` policy plus the platform-approved public classification.

E-7. Temporal validity is part of the conjunction, not a post-filter. Missing, malformed, or untrusted
temporal metadata fails closed: the revision is excluded, never included. A null `valid_until` means
open-ended eligibility until an explicit lifecycle or security action ends it, and is never treated as
expired.

E-8. Draft or client-proposed temporal values remain untrusted until validated, confirmed, and
persisted by the Control Plane (`AP-9`). Only trusted persisted values may satisfy conditions 9 and 10.
This aligns with the trusted `valid_from` / `valid_until` index metadata in
`docs/control-plane/CP-000C-index-isolation-blueprint.md` and with the temporal-derivation limitation
recorded in `docs/contracts/evidence-1.0.0.md`, where the derivation and revalidation of those values is
still future work.

## Authorization boundaries

B-1. Administrative role alone grants no ordinary read and no raw-content access. An
administrator reads a source only when an ordinary visibility policy entitles them, exactly as
any other principal (ADR-CP-002 A-2).

B-2. Raw-content inspection is a separate named action requiring its own permission, a recorded
reason, and an audit obligation (ADR-CP-002 A-6).

B-3. Management capability is bounded by assigned scope. A Node Manager gains nothing over
sibling or descendant nodes without explicit delegation (ADR-CP-001 default-deny table).

B-4. Lifecycle actions are individually authorized. Holding one lifecycle permission never
implies another; the action list and per-actor semantics are in
`docs/control-plane/CP-000B-source-lifecycle-matrix.md`.

B-5. Personal, transactional, and clinical records -- patient records above all -- are outside
this registry and must not be modeled as knowledge sources (ADR-CP-002 B-1).

## Failure behavior

| Condition | Behavior |
|---|---|
| Missing or unresolvable visibility policy binding | Draft-only; deny; never retrievable |
| Owner node invalid, unknown, or in another organization | Reject the operation as invalid input |
| Unsupported `source_type` | Reject at validation |
| Both or neither content locator present | Reject as invalid revision |
| Digest mismatch | Revision ineligible; no repair at read time; incident-worthy |
| Source revoked, disabled, or archived | Immediate exclusion from new retrieval |
| No activated revision | Not retrievable regardless of source status |
| Activation requested with missing business approval | Refuse the transition; no revision becomes `ACTIVE` without a recorded `source.approve` decision |
| Activation requested with missing or failed technical gates | Refuse the transition; business approval never substitutes for validation, ingestion, or index gates |
| Unauthorized Control Plane lifecycle transition | Refuse and audit; the `ACTIVE` transition is a Control Plane application-service operation, and v1 exposes no human-facing `source.activate` permission |
| Eligibility state unreadable or inconsistent | Fail closed: exclude, never include |
| Authorization decision missing or expired | No retrieval, never unfiltered retrieval |

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| One mutable source record edited in place | Destroys citation resolvability and audit; makes "what did the answer cite" unanswerable |
| One combined status enum for source and revision | Conflates operational suspension with review state; every consumer would need to guess which meaning applies |
| Multiple simultaneously active revisions | Ambiguous retrieval and unexplainable decisions; breaks `current_active_revision_ref` |
| Physical deletion as the meaning of delete | Cannot be immediate, cannot be audited, conflicts with retention and legal hold, and is not needed for exclusion |
| Revocation implemented by re-indexing or purge | Exclusion would depend on background work completing; unacceptable for security incidents |
| Hard-deleting superseded revisions | Breaks existing citations, audit, and rollback |
| Rollback by mutating history or editing a superseded revision | Destroys the audit trail; replaced by audited re-activation |
| Ownership as read access | Would make administration a shadow read path; contradicts CP-000A |
| Immutable ownership | Real reorganizations occur; immutability would force source re-creation and citation loss |
| Ownership change cascading to visibility or classification | Reorganization would silently republish content |
| Defaulting missing visibility to organization-wide or anonymous-public | Catastrophic default; absence is deny |
| Trusting uploader-supplied organization or unit names | Client-controlled organization spoofing (CP-000A forbidden inputs) |
| Introducing a connector or crawler framework now | Out of scope; would import fetching, scheduling, and trust problems this baseline cannot resolve |
| Treating web-search results as sources | No owner, no policy binding, no revision identity, no audit |
| Registering chat attachments as sources | Different trust, lifetime, and ownership model; deferred deliberately |
| Per-source index or collection to express exclusion | Authorization by topology; rejected by CP-000A V-6 |
| Post-retrieval filtering of revoked content | Content has already left the trust boundary |

## Consequences

- Citations remain resolvable across updates because revisions are immutable and superseded
  revisions are retained.
- Revocation is instant and independent of storage and index work, at the cost of requiring every
  retrieval path to consult trusted state before returning results.
- Every content change requires a review-and-activation cycle, which is slower than editing and
  is the intended trade.
- Two state machines mean consumers must check both; the eligibility conjunction exists so no
  consumer invents its own combination.
- Superseded and archived revisions accumulate, making retention and purge policy a real
  obligation rather than an afterthought.
- Administrators may administer sources whose content they cannot read.
- Ownership changes are cheap and safe; visibility and classification changes are deliberately
  expensive and audited.
- No storage, index, ingestion, or transport choice is implied, so future packages remain free.

## Explicit open decisions

| Open decision | Why it remains open | Deciding package | Evidence required |
|---|---|---|---|
| Exact content storage backend | Provider-neutral by mandate; artifact reference semantics are decided, storage is not | Storage/adapter package | Durability, immutability, size, cost, and residency requirements |
| Maximum upload size and supported MIME types | No operational data; limits must be platform-owned but the values need evidence | Ingestion package | Real document inventories per deployment type |
| Malware scanning provider and quarantine workflow | Depends on the storage and ingestion decision; quarantine states would extend the revision machine | Ingestion/security package | Security requirements, provider evaluation |
| Official URL validation and fetching mechanism | Crawling, fetch frequency, robots handling, and extraction are explicit non-goals here | Official-URL package | Which URLs must be supported, freshness requirements, site constraints |
| Exact approval and separation-of-duties policy | Baseline mandates separable approval and activation, not a specific workflow or two-person rule | Control-plane policy governance package | Regulatory obligations, risk analysis, staffing reality |
| Retention periods | Jurisdiction and deployment dependent | Compliance package | Legal review per deployment type |
| Legal hold rules | Interacts with purge and with archival visibility | Compliance package | Legal review, litigation-hold requirements |
| Physical purge implementation | May be asynchronous and must never gate exclusion; mechanism undecided | Storage/compliance package | Retention and legal-hold decisions, storage capability |
| Exact lifecycle action codes | Action names here are conceptual and must be reconciled with the CP-000A action catalog | Control-plane role/action catalog package | Approved control-plane operation list |
| Typed Python contract shapes | This package adds no contract by mandate | Future CP contract package | Architect acceptance of ADR-CP-001, ADR-CP-002, and this ADR |
| Index synchronization protocol | Eligibility is defined as an invariant; how the index learns about state changes is retrieval architecture | Retrieval/index package | Index backend choice, latency and consistency requirements |
| Rollback implementation details | The semantic (audited re-activation, no history mutation) is decided; the mechanism and eligibility window are not | Source-registry implementation package | Operational rollback scenarios and audit requirements |
| Whether selected metadata-only changes require full content re-indexing | Depends on the unselected index backend and on how policy bindings are represented physically | Retrieval/index package | Index backend behavior and measured re-index cost |
| Whether a chat attachment may be promoted to `uploaded_document` | Attachment trust and lifetime differ; promotion would need its own validation path | Future attachment package | Product requirement and trust analysis |
| Typed `AMENDS` / `PARTIALLY_SUPERSEDES` relation | Explicitly deferred by SR-7; partial amendment must not be guessed | CP-005 with CP-006 | A real partial-amendment use case and its conflict-resolution requirement |
| Exact `AuthorityProfile` and authority-catalog shape | AU-1 to AU-6 fix the semantics and trust boundary; the typed shape and ranking function are undecided | CP-001 with CP-005 | Approved authority taxonomy per deployment type and conflict-precedence requirements |
| Source Approver review-surface contract | AP-3 fixes what `source.review` means; the read-model and surface contract do not exist | CP-001 with CP-009 | Approved review-queue requirements |
| Versioned audited bulk policy-rebinding migration | R-5A forbids in-place rebinding of an active revision; the migration mechanism is undecided | CP-005 | Real migration scenarios and audit obligations |
| Quarantine or validation-failed revision states | Adding states to the revision machine requires the ingestion decision first | Ingestion package | Scanning and validation workflow decisions |
