# CP-000B Source Lifecycle Matrix (conceptual baseline)

Status: Accepted architecture baseline (originated as CP-000B; CP-000R consistency repair applied, and CP-000R was accepted at commit `8d94c6a`)
Implementation remains owned by the packages identified in this document.
Owner: Control Plane / Source Registry Baseline
Companions: `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`,
`docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`,
`docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`,
`docs/control-plane/CP-000A-authorization-matrix.md`

Conceptual actions and actors only. Neither catalog is final. No cell is an unconditional grant,
and no cell may be implemented as a static role check.

## Legend

| Symbol | Meaning |
|---|---|
| `SCOPE` | Allowed only within the actor's explicitly assigned scope; no sibling, ancestor, or descendant breadth is implied |
| `POLICY` | Allowed only through an active versioned visibility policy that matches the actor; missing policy is deny |
| `FLOW` | Requires the lifecycle workflow; the role alone does not complete the action |
| `APPROVAL` | Requires an approval decision under the active versioned workflow policy; a distinct actor is required only when that policy mandates separation of duties |
| `AUDIT` | Requires a recorded reason and an audit record; the action is not permitted without it |
| `RAW` | Requires the separate raw-content inspection permission plus recorded reason and audit |
| `DENY` | Denied by default in this baseline |
| `EMERGENCY` | Permitted as an explicit incident action, always with `AUDIT`; never an ordinary operation |
| `PERM` | Granted only by an explicitly assigned permission; the actor label alone grants nothing |

## Canonical scope

This document is the **single canonical source lifecycle and source-action matrix**. Where any other
document states a source action permission that conflicts with this matrix, this matrix wins.
`docs/control-plane/CP-000A-authorization-matrix.md` delegates all source actions here and remains
canonical for organization and authorization concepts.

Semantics here are **permission-driven**, not role-driven. An actor name in a column header is a
conceptual grouping for readability. It is never itself a grant: every allow cell requires the named
permission to be explicitly assigned and scoped, and no cell may be implemented as a static role
check.

## Conceptual actors

| Actor | Code | Meaning |
| --- | --- | --- |
| Department Contributor | DC | An authorized contributor in a delegated departmental scope who registers and prepares sources |
| Central Source Approver | CSA | The single centrally assigned reviewer holding `source.review`, `source.approve`, `source.reject` |
| Account/Authorization Administrator | AAA | Administers accounts, roles, and permission assignment |
| End User | EU | An authenticated reader with no management capability |
| Guest | GUEST | `AnonymousGuest`; anonymous reader with no account |
| Auditor | AUD | Holds audit-scope read permission over lifecycle history |
| System AI Administrator | SAA | Holds `ai_configuration.manage` for global AI configuration (CP-000D) |

## Matrix

| Action | DC | CSA | AAA | EU | GUEST | AUD | SAA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| create source (`source.create`) | `PERM` + `SCOPE` delegated scope | `DENY` unless separately assigned | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| upload content (`source.upload`) | `PERM` + `SCOPE` delegated scope | `DENY` unless separately assigned | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| edit own draft (`source.edit_own_draft`) | `PERM` + `SCOPE`, own draft only | `DENY` unless separately assigned | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| submit for review (`source.submit`) | `PERM` + `SCOPE` + `FLOW` | `DENY` unless separately assigned | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| read pending review surface (`source.review`) | `DENY` for the general review surface; own-draft/submission access is governed by `source.edit_own_draft` and `source.submit` | `PERM`, pending submissions across **all** departments | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| approve revision (`source.approve`) | `DENY` | `PERM` + `FLOW` + `APPROVAL` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| reject revision (`source.reject`) | `DENY` | `PERM` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| activate revision (Control Plane lifecycle transition; no human-facing v1 permission) | `DENY` | `DENY`; `source.approve` records business approval only | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| read citation-safe published metadata | `POLICY` | `PERM` review surface, or `POLICY` | `DENY` | `POLICY` | `POLICY`, `anonymous-public` only | `POLICY` | `POLICY` |
| read management metadata | `PERM` + `SCOPE` own delegated scope | `PERM` review surface only | `DENY` | `DENY` | `DENY` | `DENY` unless separately assigned | `DENY` |
| read lifecycle audit metadata | `DENY` unless separately assigned | `DENY` unless separately assigned | `DENY` unless separately assigned | `DENY` | `DENY` | `PERM` + `SCOPE` audit scope | `DENY` |
| read raw source content | `RAW` + `SCOPE` own delegated scope | `RAW` review surface only | `DENY` | `DENY` | `DENY` | `RAW` + `AUDIT` | `DENY` |
| read source through ordinary policy | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY`, `anonymous-public` + public classification only | `POLICY` | `POLICY` |
| assign or change source authority | `PERM` propose only, untrusted until confirmed | `PERM` confirm or assign from approved versioned catalog + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| set source temporal metadata | `PERM` propose only, untrusted until confirmed | `PERM` confirm or set + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| create SourceRelationship | `PERM` propose only | `PERM` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| supersede same-source revision (automatic effect of activating a newer same-source revision) | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| create supplemental source relationship | `PERM` propose only | `PERM` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| change visibility policy binding | `PERM` + `SCOPE` approved policies within delegated bounds, new revision only | `PERM` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| change classification | `PERM` + `SCOPE` within delegated bounds + `AUDIT` | `PERM` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| change administrative owner | `PERM` + `SCOPE` over both source and target node + `AUDIT` | `DENY` unless separately assigned | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| disable | `DENY` by default; requires a separately delegated lifecycle permission, then `SCOPE` + `AUDIT` | `DENY` by default; requires a separately delegated lifecycle permission, then `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| revoke | `DENY` by default; requires a separately delegated lifecycle permission, then `SCOPE` + `AUDIT` + `EMERGENCY` | `DENY` by default; requires a separately delegated lifecycle permission, then `AUDIT` + `EMERGENCY` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| archive | `DENY` by default; requires a separately delegated lifecycle permission, then `SCOPE` + `AUDIT` | `DENY` by default; requires a separately delegated lifecycle permission, then `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| request physical purge | `DENY` unless separately granted purge authority | `DENY` unless separately granted purge authority | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| assign permissions to actors | `DENY` | `DENY` | `PERM` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` |

## Required v1 behavior

```text
Department Contributor
    -> create / upload / edit own draft / submit, within delegated scope

Central Source Approver
    -> read pending review surface for ALL departments
    -> approve or reject the business decision

Control Plane Application Service
    -> after business approval and every applicable technical gate
    -> transition the revision to ACTIVE
    -> automatically mark the previous active revision SUPERSEDED

Account/Authorization Administrator
    -> assign permissions
    -> NO implicit ordinary source authorship

System AI Administrator
    -> NO implicit source authorship
```

## Explicit statements

1. Every allow cell is permission-driven. A role label never grants access, and no cell may be
   implemented as a static role check.
2. There is **one centrally assigned Source Approver** in v1. This baseline does **not** introduce one
   approver per faculty or department. Per-department approvers remain a possible future governance
   option, not a v1 requirement.
3. `source.review` permits reading pending source submissions from **all departments**, because that
   is the required review surface for a single central approver. It does **not** independently grant
   access to unrelated active or restricted content, and it is not a general read permission.
4. **The same principal must not approve a source submission that they created, authored, uploaded,
   or submitted.** Holding `source.approve` does not override this v1 self-approval prohibition;
   creating, uploading, or submitting is never approving.
5. The exact future configurable separation-of-duties model beyond the mandatory same-principal
   self-approval prohibition in statement 4 remains **open**. This
   baseline mandates that submission and approval are separately permissioned, not a specific
   two-person rule.
6. Approval is not activation. `source.approve` records a business decision; activation additionally
   requires that **all applicable gates pass**, including ingestion validation and index availability
   where retrieval depends on it (ADR-CP-007, "Workflow boundary"). Business approval alone never
   proves that any ingestion, parsing, OCR, or index-build step succeeded.
7. The Account/Authorization Administrator assigns permissions and gains **no** implicit ordinary
   source authorship. Assigning the approver capability does not make the assigner an approver or an
   author.
8. The System AI Administrator (`ai_configuration.manage`) has **no** implicit source authorship. AI
   configuration administration and knowledge-source authorship are separate capabilities.
9. Source metadata is four distinct resources, not one: citation-safe published metadata, management
   metadata, lifecycle audit metadata, and raw source content (ADR-CP-007, "Source metadata classes").
   Guest and ordinary End User do **not** receive management metadata through a general "view
   metadata" permission.
10. Citation-safe published metadata contains only the minimum published facts needed for citation and
    explanation. Administrative owner, review-queue state, audit reason, raw locator, internal status
    detail, and purge or legal-hold metadata are never part of it.
11. Source authority is **proposed** by a contributor and **confirmed or assigned** by the Central
    Source Approver from an approved versioned catalog. Authority supplied by an LLM, a client, a
    filename, or document text is untrusted. Authority is not an authorization grant.
12. Source temporal metadata is trusted control-plane output. Upload time is never treated as business
    publication time. **`valid_until` may be null**, and a null `valid_until` means open-ended
    eligibility until an explicit lifecycle or security action ends it. Null is never treated as
    expired.
13. Each approved or active `SourceRevision` carries a **pinned exact immutable
    `VisibilityPolicyDefinition` revision**. There is no follow-active behavior: no implicit
    follow-latest, no model-selected revision, no client-selected revision. A missing policy revision
    fails closed, and an inactive or revoked revision makes the source ineligible. Changing the
    binding requires a new immutable source revision or a future versioned audited migration, never an
    in-place edit of an active revision.
14. `SUPERSEDES` relates revisions of the **same** `KnowledgeSource`; one source still has at most one
    active revision. `SUPPLEMENTS` relates **separate** `KnowledgeSource` instances, and two
    supplemental sources may both remain active. An LLM must never infer these relationships.
    `AMENDS` / `PARTIALLY_SUPERSEDES` remains explicitly deferred.
15. Superseded content remains retained for audit, historical citation resolvability, and explicit
    historical queries. Supersession changes retrieval eligibility, not resolvability.
16. `RAW` always requires a separate permission, a recorded reason, and an audit obligation.
17. End User and Guest have no source-management actions whatsoever.
18. Guest may read only through an active `anonymous-public` policy combined with the
    platform-approved public classification, and Guest retrieval is still filtered retrieval.
19. Revocation requires an explicit action, a recorded reason, and audit. It is never a side effect of
    another operation and never waits for re-indexing or physical deletion.
20. Physical purge requires authority separate from ordinary source management, and is subject to
    retention, legal hold, audit, and compliance policy. It is never required for immediate retrieval
    exclusion.
21. `DENY unless separately assigned` cells are deliberate: broad platform or organization roles do
    not silently acquire source lifecycle capability.
22. Every allowed read path runs through the mandatory retrieval pre-filter and the full runtime
    eligibility conjunction in ADR-CP-007. Post-retrieval removal is not an accepted implementation.
23. `source.approve` records **business approval only** and never by itself activates a source.
    `ACTIVE` eligibility additionally requires all applicable validation, ingestion, and index gates.
    After business approval and all required technical gates, the Control Plane may perform the
    `ACTIVE` transition; whether that occurs in the same command or in a separate application-service
    step is owned by CP-009. v1 introduces no new human-facing `source.activate` permission
    (ADR-CP-007 `AP-7`, `AP-8`).
24. A contributor or client may **propose** temporal metadata in a draft. The proposal is untrusted.
    Only validated, confirmed, and persisted Control Plane metadata is used by authorization,
    retrieval, or evidence eligibility (ADR-CP-007 `AP-9`).
25. **Activation is not a human approver permission in v1.** The `ACTIVE` transition and the
    `SUPERSEDED` effect are lifecycle and application-service operations: after business approval and
    all validation, ingestion, and index gates pass, the Control Plane application service may
    transition the revision to `ACTIVE`, and activating a newer same-source revision automatically
    marks the previous active revision `SUPERSEDED`. Neither the Department Contributor nor the Central
    Source Approver holds an activation or supersession permission, and whether the transition occurs
    in the same command or in a separate application-service step remains CP-009 work.
26. Neither the Department Contributor nor the Central Source Approver automatically receives
    `disable`, `revoke`, `archive`, or physical purge capability. Those actions are `DENY` by default
    and require a separately delegated lifecycle permission. An actor label is never itself an
    authorization grant.

## Open decisions

| Open decision | Why open | Deciding package | Evidence required |
|---|---|---|---|
| Final lifecycle action codes | Actions here are conceptual and must be reconciled with the CP-000A action catalog | Control-plane role/action catalog package | Approved control-plane operation list |
| Final role catalog and role-to-action bindings | Actors are conceptual; bindings must be versioned artifacts | Same catalog package | Confirmed operating models for university, company, hospital |
| Exact configurable separation-of-duties model per action | CP-000R fixes one central approver and forbids the same principal from approving a submission they created, authored, uploaded, or submitted; the wider configurable model is not decided, and no two-person rule is mandated in v1 | Control-plane policy governance package | Regulatory obligations, risk analysis, staffing reality |
| Source Approver review-surface contract | Statement 3 fixes what `source.review` means; the read model and surface contract do not exist | CP-001 with CP-009 | Approved review-queue requirements |
| Whether per-department approvers are introduced after v1 | v1 uses one central approver by decision; scaling evidence may change this later | Control-plane policy governance package | Observed review volume and departmental workload |
| Purge authority definition and holders | Purge is deliberately separated from source management but its authority model is undecided | Compliance/storage package | Retention decisions, legal-hold rules, storage capability |
| Revocation reason codes and their retention | Depends on the unresolved audit and retention model | Compliance package | Legal review per deployment type |
| Delegation artifact for descendant and cross-node management | `DENY unless delegated` is the safe default; the artifact shape is undecided | Control-plane delegation package | Real delegation scenarios per deployment |
| Auditor scope definition | "Audit scope" is not yet a defined artifact | Audit package | Audit obligations and separation-of-duties requirements |
| Whether emergency revocation may bypass scope in an incident | `EMERGENCY` is scoped in this baseline; a break-glass path is not designed | Security incident-response package | Incident-response requirements and abuse analysis |
