# Organization Hierarchy Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/organization.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`,
  `docs/control-plane/CP-000A-authorization-matrix.md`
- Schema artifacts:
  - `schemas/organization/1.0.0.schema.json` — `urn:ai-assistant:contracts:organization:1.0.0`
  - `schemas/organizational-node/1.0.0.schema.json` — `urn:ai-assistant:contracts:organizational-node:1.0.0`
- Deferred items addressed: DEF-103 (generic recursive hierarchy shape),
  DEF-104 (node lifecycle references)

## Purpose

Provide the transport-neutral typed shape of an organization and of a single node
inside its recursive hierarchy, together with an opaque path reference used by
later packages for scope resolution. This contract carries shape and local
invariants only.

## Shapes

| Type | Purpose |
| --- | --- |
| `NodeTypeRef` | Versioned vocabulary reference (`code`, `vocabulary_revision`). |
| `OrganizationalNodeRef` | Opaque `(organization_id, node_id)` pair used by every other family. |
| `HierarchyPathRef` | Root-to-node ancestor chain with `depth` and `path_revision`. |
| `Organization` | Organization identity, status, root node, lifecycle instants. |
| `OrganizationalNode` | One node: type, display name, parent, status, optional path. |
| `NodeLifecycleRef` | Audit-only reference to a node status transition. |

`NODE_TYPE_DEPARTMENT` is exported as a vocabulary constant only. Node type is a
versioned catalog term, not a Python enum, because the vocabulary is
administratively extensible (ADR-CP-001).

## Invariants

1. A root node has `is_root = true` and no `parent`; a non-root node must have a
   parent. Re-parenting a root is therefore unrepresentable.
2. `parent.organization_id` must equal the node's `organization_id`:
   cross-organization parenting is invalid.
3. A node may not be its own parent, and may not appear in its own
   `ancestor_node_ids`.
4. `depth == len(ancestor_node_ids)`; at depth 0 the node is its own root,
   otherwise `ancestor_node_ids[0]` is the root.
5. `display_name` is validated as human text only. It has no authorization,
   routing, or identity meaning; all references use opaque identifiers.
6. Status change instants may not precede creation instants; all instants are
   timezone-aware and normalized to UTC.
7. `MAX_HIERARCHY_DEPTH = 32` bounds every path reference.

## Out of scope

Persistence, subtree queries, move/re-parent commands, path materialization, and
cache invalidation belong to CP-002 and later packages. Authorization semantics
of a node belong to CP-002; index isolation belongs to CP-003/CP-005.

## Versioning

New family at `1.0.0`. No previously published schema is modified. A future
change to the closed `NodeStatus` union or to path semantics requires a new major
version under the DEF-016 compatibility governance process.

## Tests

`tests/test_control_plane_contracts.py::OrganizationHierarchyTests` covers
construction, rejection of root re-parenting, cross-organization parenting, path
inconsistency, depth bounds, naive datetimes, immutability, round-trip, and JSON
Schema parity.
