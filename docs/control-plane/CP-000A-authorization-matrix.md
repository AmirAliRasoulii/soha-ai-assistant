# CP-000A Authorization Matrix (conceptual baseline, revision R1)

Status: Accepted architecture baseline (originated as CP-000A revision R1; CP-000R consistency repair applied, and CP-000R was accepted at commit `8d94c6a`)
Implementation remains owned by the packages identified in this document.
Owner: Control Plane / Authorization Scope Baseline
Companions: `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`,
`docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`,
`docs/control-plane/CP-000B-source-lifecycle-matrix.md`

This matrix is a conceptual baseline for review. Actions and actors are conceptual; neither
catalog is final, and no cell is an unconditional grant. No cell may be implemented as a static
role check.

## Scope of this matrix

This matrix covers **organization, node, membership, role, and audit-scope authorization only**.

**`docs/control-plane/CP-000B-source-lifecycle-matrix.md` is the single canonical matrix for every
source registry and content lifecycle action.** This document deliberately states no per-actor cell
for any source action. Where an earlier revision of this file stated source lifecycle rows, those rows
are removed and delegated, because two documents stating source permissions produced the confirmed
contradiction recorded as audit finding C-001. If this document and CP-000B ever appear to disagree
about a source action, CP-000B wins and this document is in error.

## Cell semantics

| Symbol | Meaning |
|---|---|
| `SCOPE` | Allowed only within the actor's explicitly assigned scope. No sibling, ancestor, or descendant breadth is implied |
| `POLICY` | Allowed only through an active versioned policy that matches the actor; missing policy is deny |
| `CLASS` | Additionally bounded by the actor's classification allowance, applied as a ceiling after allow evaluation |
| `RAW` | Requires the separate raw-content inspection permission plus a recorded reason and an audit obligation |
| `FLOW` | Requires the approval workflow; the role alone does not complete the action |
| `NOROLE` | Not granted by role alone; requires an explicit assignment or explicit versioned delegation |
| `AUDIT` | Carries a mandatory audit obligation; the action is not complete until the audit record is written |
| `DELEGATED` | Not decided here. The canonical cell lives in `CP-000B` |
| `DENY` | Denied by default in this baseline |

Actors: GSA = Global System Admin, OA = Organization Admin, NM = Node Manager,
DS = Data Steward, REV = Reviewer, AUD = Auditor, EU = End User,
GUEST = anonymous guest (`AnonymousGuest`, see ADR-CP-002).

## Matrix

| Action | GSA | OA | NM | DS | REV | AUD | EU | GUEST |
|---|---|---|---|---|---|---|---|---|
| view node metadata | `SCOPE` platform scope | `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned | `SCOPE` assigned | `SCOPE` audit scope | `POLICY`, default deny | `DENY` |
| manage node (create, rename, configure) | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` organization + `AUDIT` | `SCOPE` assigned node only, `NOROLE` for siblings/descendants | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| move or re-parent node | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` organization + `AUDIT`, both source and destination subtree required | `NOROLE` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| manage memberships | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` organization + `AUDIT` | `SCOPE` assigned node only, `NOROLE` beyond it | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| assign roles and permissions | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` organization + `AUDIT`, never above own scope | `NOROLE` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| inspect audit metadata | `SCOPE` platform scope | `SCOPE` organization | `NOROLE` | `NOROLE` | `NOROLE` | `SCOPE` audit scope | `DENY` | `DENY` |
| all source registry and content lifecycle actions | `DELEGATED` | `DELEGATED` | `DELEGATED` | `DELEGATED` | `DELEGATED` | `DELEGATED` | `DELEGATED` | `DELEGATED` |

## Delegated source actions

The following actions are **not** decided by this document. Their canonical per-actor cells are in
`CP-000B`:

```text
read citation-safe published metadata
read management metadata
read lifecycle audit metadata
read source content
inspect raw source content
create or upload source
edit own draft
submit for review
review pending submissions
approve revision
reject revision
activate revision
supersede revision
disable source
revoke source
archive source
delete source or revision
set source authority metadata
set source temporal metadata
set source relationships
bind visibility policy revision
```

## Explicit statements

1. Metadata access never implies content access. Global System Admin metadata visibility grants
   no raw-content access.
2. Every source action in this baseline is governed by `CP-000B`. This document is not a second
   source of truth for source permissions.
3. Node metadata publication is **default deny**. A node's existence, name, and structure are not
   public facts; they become visible only through an explicit active publication policy
   (ADR-CP-001, "Node metadata publication").
4. Guest (`AnonymousGuest`) is denied node metadata in this baseline. Guest node-metadata exposure
   requires an explicit approved publication policy artifact that does not yet exist.
5. End User node-metadata visibility is `POLICY`, default deny. Organization membership alone does
   not entitle a principal to the full organizational tree.
6. Moving or re-parenting a node requires authorization over **both** the source and the destination
   subtree, is never implicit, and always carries an audit obligation.
7. A node move changes effective authorization for existing content. It must invalidate the derived
   hierarchy path and scope caches; a stale cached path is an authorization defect, not a performance
   defect (ADR-CP-001 `L-6`, `L-7`).
8. The root node of an organization can never be re-parented and is never a valid move target
   (ADR-CP-001 `I-2a`).
9. Role assignment can never grant a scope broader than the assigning actor's own scope. Privilege
   escalation by delegation is prohibited.
10. Node Manager capability is confined to the assigned node. Sibling and descendant management
    requires an explicit assignment or an explicit versioned delegation policy.
11. `NOROLE` cells are deliberate: platform-wide or organization-wide roles do not silently
    acquire node-scoped operational capability.
12. End User receives no management capability by default, and no audit or raw-content access.
13. Guest (`AnonymousGuest`) receives no organization, node, subtree, role, group, or principal
    scope, and no management, audit, upload, update, approval, activation, revoke, deletion, or
    raw-content capability under any policy.
14. Authentication failure never downgrades to Guest. A request is intentionally processed
    either as Guest or as an authenticated principal.
15. Guest retrieval is still filtered retrieval, using a trusted non-bypassable public
    security-scope filter. No actor has an unfiltered retrieval path.
16. Every allowed read path runs through the mandatory retrieval pre-filter built from the
    authorization decision. Post-retrieval filtering is not an accepted implementation.
17. Cross-organization access to non-public organizational resources is always denied. The only
    cross-organization read is an `anonymous-public` resource, which is a publication decision
    by the owning organization and grants nothing else.
18. Role labels, frontend labels, display names, and model output never authorize. Only a trusted
    server-side authorization decision authorizes (ADR-CP-002).
19. Every `AUDIT` cell means the audit record is part of the action. An action whose audit record
    was not written is not a completed action.

## Open decisions

| Open decision | Why open | Deciding package | Evidence required |
|---|---|---|---|
| Final action catalog | Actions here are conceptual and must be reconciled with real control-plane operations | Control-plane role/action catalog package | Approved control-plane operation list |
| Final role catalog and role-to-action bindings | Baseline roles are conceptual; bindings must be versioned artifacts | Same catalog package | Confirmed operating models for university, company, hospital |
| Concrete public node-directory policy shape | Guest and End User node metadata are default deny; the publication artifact shape is undecided | Control-plane publication package (CP-007) | Concrete public-directory requirements |
| Raw-content inspection reason codes and retention of inspection records | Depends on the unresolved audit and retention model | Compliance package | Legal review per deployment type |
| Delegation model for descendant management | `NOROLE` is the safe default; a delegation artifact shape is undecided | Control-plane delegation package | Real delegation scenarios per deployment |
| Platform-approved public classification code | Guest reads depend on a single approved code | Classification package | Approved classification taxonomy |
| Auditor scope definition | "Audit scope" is not yet a defined artifact | Audit package | Audit obligations and separation-of-duties requirements |
| Cache invalidation propagation budget for a node move | The correctness rule is fixed; the acceptable propagation window is not | CP-002 with CP-006 | Measured invalidation latency and risk acceptance |
| Whether node deletion or archive is permitted at all, and its effect on owned content | ADR-CP-001 `L-9` defers root deletion mechanics; content reassignment rules are undecided | CP-002 with CP-003 | Retention obligations and content ownership rules |
