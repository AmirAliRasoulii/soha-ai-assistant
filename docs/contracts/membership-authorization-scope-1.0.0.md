# Membership and Authorization Scope Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/membership.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`,
  `docs/control-plane/CP-000A-authorization-matrix.md`
- Schema artifacts:
  - `schemas/node-membership/1.0.0.schema.json` — `urn:ai-assistant:contracts:node-membership:1.0.0`
  - `schemas/scoped-role-assignment/1.0.0.schema.json` — `urn:ai-assistant:contracts:scoped-role-assignment:1.0.0`
- Deferred items addressed: DEF-105 (membership and scoped-role shapes),
  DEF-106 (explicit authorization scope reference)

## Purpose

Express who is attached to which node, and which role is granted over which
explicit set of nodes, without expressing any access decision.

## Shapes

| Type | Purpose |
| --- | --- |
| `ValidityWindow` | Half-open validity (`valid_from`, nullable `valid_until`). |
| `RoleRef` | Versioned role catalog reference. |
| `PermissionRef` | Versioned permission catalog reference. |
| `AuthorizationScopeRef` | Organization plus an explicit, enumerated tuple of node references. |
| `NodeMembership` | One principal attached to one node with a kind, status, and validity. |
| `ScopedRoleAssignment` | One principal granted one role over one explicit scope. |

## Invariants

1. `NodeMembership` has no permission, role, or access field. Membership alone
   grants nothing; many-to-many membership is expressed as several records.
2. `AuthorizationScopeRef` has exactly two fields and no `include_descendants`,
   `recursive`, `subtree`, or wildcard flag. Parent, child, and sibling access is
   therefore never implicit — a scope is an enumerated node set.
3. Every node in a scope must belong to the scope's organization; duplicates are
   rejected; the scope must be non-empty and is bounded by `MAX_SCOPE_NODES`.
4. A `ScopedRoleAssignment`'s scope organization must equal the assignment's
   organization, and a membership's node organization must equal the membership's
   organization.
5. Role and permission codes are canonical machine codes bound to a catalog
   revision; a human role label is not a permission.
6. `valid_until`, when present, must be strictly after `valid_from`.
7. All instants are timezone-aware and normalized to UTC; every model is frozen
   and rejects unknown fields.

## Out of scope

Policy evaluation, scope expansion, hierarchy traversal, effective-permission
computation, and delegation belong to CP-002. Retrieval filtering belongs to
CP-003/CP-005.

## Versioning

New family at `1.0.0`. Adding a descendant-expansion flag later would be a
semantic break and requires a new major version plus a CP-002 decision.

## Tests

`tests/test_control_plane_contracts.py::MembershipAndScopeTests`.
