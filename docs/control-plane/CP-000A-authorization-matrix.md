# CP-000A Authorization Matrix (conceptual baseline, revision R1)

Status: proposed for CP-000A architect review, revision R1 (not accepted, no implementation
authorized)
Owner: Control Plane / Authorization Scope Baseline
Companions: `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`,
`docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`

This matrix is a conceptual baseline for review. Actions and actors are conceptual; neither
catalog is final, and no cell is an unconditional grant. No cell may be implemented as a static
role check.

## Cell semantics

| Symbol | Meaning |
|---|---|
| `SCOPE` | Allowed only within the actor's explicitly assigned scope. No sibling, ancestor, or descendant breadth is implied |
| `POLICY` | Allowed only through an active versioned policy that matches the actor; missing policy is deny |
| `CLASS` | Additionally bounded by the actor's classification allowance, applied as a ceiling after allow evaluation |
| `RAW` | Requires the separate raw-content inspection permission plus a recorded reason and an audit obligation |
| `FLOW` | Requires the approval workflow; the role alone does not complete the action |
| `NOROLE` | Not granted by role alone; requires an explicit assignment or explicit versioned delegation |
| `DENY` | Denied by default in this baseline |

Actors: GSA = Global System Admin, OA = Organization Admin, NM = Node Manager,
DS = Data Steward, REV = Reviewer, AUD = Auditor, EU = End User,
GUEST = anonymous guest (`AnonymousGuest`, see ADR-CP-002).

## Matrix

| Action | GSA | OA | NM | DS | REV | AUD | EU | GUEST |
|---|---|---|---|---|---|---|---|---|
| view node metadata | `SCOPE` platform scope | `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned | `SCOPE` assigned | `SCOPE` audit scope | `POLICY` | `DENY` unless separately published public metadata |
| manage node | `SCOPE` + `FLOW` | `SCOPE` organization | `SCOPE` assigned node only, `NOROLE` for siblings/descendants | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| manage memberships | `SCOPE` + `FLOW` | `SCOPE` organization | `SCOPE` assigned node only, `NOROLE` beyond it | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| view source metadata | `POLICY` (admin metadata scope where assigned) | `POLICY` / `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned | `SCOPE` assigned review queue | `SCOPE` audit scope | `POLICY` | `POLICY`, `anonymous-public` only |
| read source content | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS` | `POLICY` + `CLASS`, `anonymous-public` + public classification only |
| draft source | `NOROLE` | `SCOPE` organization, `NOROLE` per node | `NOROLE` | `SCOPE` assigned scopes only | `DENY` | `DENY` | `DENY` | `DENY` |
| update draft | `NOROLE` | `SCOPE` | `NOROLE` | `SCOPE` own assigned scopes | `DENY` | `DENY` | `DENY` | `DENY` |
| submit for review | `NOROLE` | `SCOPE` | `NOROLE` | `SCOPE` + `FLOW` | `DENY` | `DENY` | `DENY` | `DENY` |
| review | `NOROLE` | `NOROLE` | `NOROLE` | `NOROLE` (Data Steward role alone grants no review capability) | `SCOPE` + `FLOW` | `DENY` | `DENY` | `DENY` |
| approve | `NOROLE` | `SCOPE` + `FLOW` | `NOROLE` | `DENY` | `SCOPE` + `FLOW` | `DENY` | `DENY` | `DENY` |
| activate | `NOROLE` | `SCOPE` + `FLOW` | `NOROLE` | `NOROLE` | `DENY` (approval is not activation) | `DENY` | `DENY` | `DENY` |
| disable/revoke | `SCOPE` + `FLOW` | `SCOPE` + `FLOW` | `NOROLE` | `SCOPE` assigned scopes + `FLOW` | `DENY` | `DENY` | `DENY` | `DENY` |
| inspect audit metadata | `SCOPE` platform scope | `SCOPE` organization | `NOROLE` | `NOROLE` | `NOROLE` | `SCOPE` audit scope | `DENY` | `DENY` |
| inspect raw content | `RAW` | `RAW` | `RAW` | `RAW` | `RAW` | `RAW` | `DENY` | `DENY` |

## Explicit statements

1. Metadata access never implies content access. Global System Admin metadata visibility grants
   no raw-content access.
2. `read source content` uses ordinary visibility-policy authorization for **every**
   authenticated actor. An administrative role alone grants no read privilege, and an
   administrator entitled by the same ordinary policy as any other user needs no `RAW`.
3. `RAW` appears only for `inspect raw content`, or for another explicitly named administrative
   inspection action. It always requires a separate permission, a recorded reason, and an audit
   obligation.
4. A Global System Admin or Auditor may read a normal source when an ordinary visibility policy
   entitles them; their administrative role by itself entitles them to nothing.
5. Node Manager capability is confined to the assigned node. Sibling and descendant management
   requires an explicit assignment or an explicit versioned delegation policy.
6. Data Steward may manage sources only within assigned scopes. The Data Steward role alone grants no review capability; whether the same principal may also hold Reviewer capability and review their own submission remains an explicit governance decision.
7. Reviewer approval does not imply activation permission; approval and activation are distinct
   capabilities.
8. End User receives no management capability by default, and no audit or raw-content access.
9. Guest (`AnonymousGuest`) receives no organization, node, subtree, role, group, or principal
   scope, and no management, audit, upload, update, approval, activation, revoke, deletion, or
   raw-content capability under any policy. Guest reads require `anonymous-public` plus the
   platform-approved public classification.
10. Authentication failure never downgrades to Guest. A request is intentionally processed
    either as Guest or as an authenticated principal.
11. Guest retrieval is still filtered retrieval, using a trusted non-bypassable public
    security-scope filter. No actor has an unfiltered retrieval path.
12. Every allowed read path runs through the mandatory retrieval pre-filter built from the
    authorization decision. Post-retrieval filtering is not an accepted implementation.
13. `NOROLE` cells are deliberate: platform-wide or organization-wide roles do not silently
    acquire node-scoped operational capability.
14. Cross-organization access to non-public organizational resources is always denied. The only
    cross-organization read is an `anonymous-public` resource, which is a publication decision
    by the owning organization and grants nothing else.

## Open decisions

| Open decision | Why open | Deciding package | Evidence required |
|---|---|---|---|
| Final action catalog | Actions here are conceptual and must be reconciled with real control-plane operations | Control-plane role/action catalog package | Approved control-plane operation list |
| Final role catalog and role-to-action bindings | Baseline roles are conceptual; bindings must be versioned artifacts | Same catalog package | Confirmed operating models for university, company, hospital |
| Whether any node metadata may be published to guests, and how | Guest node-metadata access is denied by default in R1 | Control-plane publication package | Concrete public-directory requirements |
| Two-person approval and self-review requirements per action | Whether an author may review or approve their own submission is unresolved | Control-plane policy governance package | Regulatory obligations, staffing reality, risk analysis |
| Raw-content inspection reason codes and retention of inspection records | Depends on the unresolved audit and retention model | Compliance package | Legal review per deployment type |
| Delegation model for descendant management | `NOROLE` is the safe default; a delegation artifact shape is undecided | Control-plane delegation package | Real delegation scenarios per deployment |
| Platform-approved public classification code | Guest reads depend on a single approved code | Classification package | Approved classification taxonomy |
| Auditor scope definition | "Audit scope" is not yet a defined artifact | Audit package | Audit obligations and separation-of-duties requirements |
