# CP-000B Source Lifecycle Matrix (conceptual baseline)

Status: proposed for CP-000B architect review (not accepted, no implementation authorized)
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

Actors: GSA = Global System Admin, OA = Organization Admin, NM = Node Manager,
DS = Data Steward, REV = Reviewer, ACT = Activator, AUD = Auditor, EU = End User,
GUEST = anonymous guest (`AnonymousGuest`, CP-000A).

## Matrix

| Action | GSA | OA | NM | DS | REV | ACT | AUD | EU | GUEST |
|---|---|---|---|---|---|---|---|---|---|
| create source | `SCOPE` platform + `AUDIT` | `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned scopes | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| create draft revision | `SCOPE` + `AUDIT` | `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned scopes | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| update draft | `SCOPE` + `AUDIT` | `SCOPE` | `SCOPE` assigned node | `SCOPE` assigned scopes | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| submit for review | `SCOPE` + `FLOW` | `SCOPE` + `FLOW` | `SCOPE` + `FLOW` | `SCOPE` + `FLOW` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| approve revision | `DENY` unless separately assigned | `SCOPE` + `FLOW` + `APPROVAL` | `DENY` unless separately assigned | `DENY` unless separately assigned; self-approval follows versioned separation-of-duties policy | `SCOPE` + `FLOW` + `APPROVAL` | `DENY` | `DENY` | `DENY` | `DENY` |
| reject revision | `DENY` unless separately assigned | `SCOPE` + `FLOW` + `AUDIT` | `DENY` unless separately assigned | `DENY` | `SCOPE` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` |
| activate revision | `DENY` unless separately assigned | `SCOPE` + `FLOW` + `AUDIT` | `DENY` unless separately assigned | `DENY` | `DENY` (approval is not activation) | `SCOPE` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` |
| rollback revision | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` + `FLOW` + `AUDIT` | `DENY` unless separately assigned | `DENY` | `DENY` | `SCOPE` + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` |
| change administrative owner | `SCOPE` + `AUDIT` | `SCOPE` organization + `AUDIT` | `SCOPE` both source and target node, `DENY` otherwise | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| change visibility policy | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` + `FLOW` + `AUDIT` | `DENY` unless delegated | `SCOPE` approved policies within delegated bounds + `FLOW` + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| change classification | `SCOPE` + `FLOW` + `AUDIT` | `SCOPE` within delegated bounds + `AUDIT` | `DENY` unless delegated | `SCOPE` within delegated bounds + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| disable source | `SCOPE` + `AUDIT` | `SCOPE` + `AUDIT` | `SCOPE` assigned node + `AUDIT` | `SCOPE` assigned scopes + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| re-enable source | `SCOPE` + `AUDIT` | `SCOPE` + `AUDIT` | `SCOPE` assigned node + `AUDIT` | `SCOPE` assigned scopes + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| revoke source | `SCOPE` + `AUDIT` + `EMERGENCY` | `SCOPE` + `AUDIT` + `EMERGENCY` | `SCOPE` assigned node + `AUDIT` + `EMERGENCY` | `SCOPE` assigned scopes + `AUDIT` + `EMERGENCY` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| archive source | `SCOPE` + `AUDIT` | `SCOPE` + `AUDIT` | `SCOPE` assigned node + `AUDIT` | `SCOPE` assigned scopes + `AUDIT` | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| request physical purge | `SCOPE` + `APPROVAL` + `AUDIT`, separate purge authority | `SCOPE` + `APPROVAL` + `AUDIT`, separate purge authority | `DENY` | `DENY` (may request only if separately granted purge authority) | `DENY` | `DENY` | `DENY` | `DENY` | `DENY` |
| view source metadata | `SCOPE` platform metadata scope | `SCOPE` organization | `SCOPE` assigned node | `SCOPE` assigned scopes | `SCOPE` review queue | `SCOPE` activation queue | `SCOPE` audit scope | `POLICY` | `POLICY`, `anonymous-public` only |
| read source through ordinary policy | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY` | `POLICY`, `anonymous-public` + public classification only |
| inspect raw content | `RAW` | `RAW` | `RAW` | `RAW` | `RAW` | `RAW` | `RAW` | `DENY` | `DENY` |
| inspect lifecycle audit | `SCOPE` platform audit scope | `SCOPE` organization | `DENY` unless separately assigned | `DENY` unless separately assigned | `DENY` unless separately assigned | `DENY` unless separately assigned | `SCOPE` audit scope | `DENY` | `DENY` |

## Explicit statements

1. Data Steward may create and update drafts only in assigned scope. Stewardship alone grants
   neither approval nor activation; any self-approval restriction is defined by the active
   versioned separation-of-duties policy.
2. Reviewer approval does not grant activation. Approval and activation are distinct permissions
   and may be held by different actors.
3. Activator does not automatically gain draft-editing or raw-content permission. Activation is
   a lifecycle act, not content authority.
4. Node Manager cannot manage sibling or descendant nodes without explicit delegation, and an
   ownership change requires scope over both the current and the target owner node.
5. Organization Admin actions remain organization-scoped. There is no cross-organization
   management action in this baseline.
6. Global System Admin does not automatically receive ordinary read or raw-content access.
   Metadata scope grants no content access; ordinary read is `POLICY` for every actor.
7. `read source through ordinary policy` uses the same visibility-policy authorization for every
   actor. An administrative role alone grants nothing, and an actor entitled by an ordinary
   policy needs no `RAW`.
8. `RAW` appears only for `inspect raw content` and always requires a separate permission, a
   recorded reason, and an audit obligation.
9. End User and Guest have no source-management actions whatsoever.
10. Guest may read only through an active `anonymous-public` policy combined with the
    platform-approved public classification, and Guest retrieval is still filtered retrieval.
11. Revocation requires an explicit action, a recorded reason, and audit. It is never a side
    effect of another operation and never waits for re-indexing or physical deletion.
12. Physical purge requires authority separate from ordinary source management, and is subject to
    retention, legal hold, audit, and compliance policy. It is never required for immediate
    retrieval exclusion.
13. `DENY unless separately assigned` cells are deliberate: broad platform or organization roles
    do not silently acquire node-scoped lifecycle capability.
14. Every allowed read path runs through the mandatory retrieval pre-filter and the full runtime
    eligibility conjunction in ADR-CP-007. Post-retrieval removal is not an accepted
    implementation.

## Open decisions

| Open decision | Why open | Deciding package | Evidence required |
|---|---|---|---|
| Final lifecycle action codes | Actions here are conceptual and must be reconciled with the CP-000A action catalog | Control-plane role/action catalog package | Approved control-plane operation list |
| Final role catalog and role-to-action bindings | Actors are conceptual; bindings must be versioned artifacts | Same catalog package | Confirmed operating models for university, company, hospital |
| Exact approval and separation-of-duties rules per action | Baseline mandates separability, not a specific two-person rule | Control-plane policy governance package | Regulatory obligations, risk analysis, staffing reality |
| Purge authority definition and holders | Purge is deliberately separated from source management but its authority model is undecided | Compliance/storage package | Retention decisions, legal-hold rules, storage capability |
| Revocation reason codes and their retention | Depends on the unresolved audit and retention model | Compliance package | Legal review per deployment type |
| Delegation artifact for descendant and cross-node management | `DENY unless delegated` is the safe default; the artifact shape is undecided | Control-plane delegation package | Real delegation scenarios per deployment |
| Auditor scope definition | "Audit scope" is not yet a defined artifact | Audit package | Audit obligations and separation-of-duties requirements |
| Whether emergency revocation may bypass scope in an incident | `EMERGENCY` is scoped in this baseline; a break-glass path is not designed | Security incident-response package | Incident-response requirements and abuse analysis |
