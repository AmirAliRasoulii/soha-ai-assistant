# Visibility Policy Definition Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/visibility_isolation.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`
  (rules `V-1`..`V-7`, `C-1`..`C-3`, section "Composition (R1-04)"),
  `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md` (per-source
  binding), `docs/control-plane/CP-000B-source-lifecycle-matrix.md`,
  `docs/control-plane/CP-000D-configuration-catalog.md`
- Schema artifacts:
  - `schemas/visibility-policy-definition/1.0.0.schema.json` —
    `urn:ai-assistant:contracts:visibility-policy-definition:1.0.0`
- Deferred items addressed: DEF-103 (typed visibility policy definition shape),
  DEF-104 (pinned per-source policy revision binding)

## Purpose

Express one named, versioned, approved visibility policy definition as a
declarative composition of the closed Layer 1 primitive vocabulary, without
expressing any access decision.

## Shapes

| Type | Purpose |
| --- | --- |
| `VisibilityPredicateKind` | Closed `Literal` over the seven Layer 1 primitives. |
| `VisibilityPredicate` | One primitive occurrence with the operands that primitive requires. |
| `VisibilityAllowClause` | One conjunctive clause: every predicate inside it must match. |
| `VisibilityPolicyStatus` | `draft`, `approved`, `active`, `retired`. |
| `VisibilityPolicyDefinition` | Identity, revision, digest, status, approval, and the clause set. |

The pinned reference a source revision binds is the existing
`VisibilityPolicyRevisionRef` of `source_registry`; `VisibilityPolicyDefinition.revision_ref`
produces exactly that value, so no second reference shape exists.

## Invariants

1. The primitive vocabulary is closed (`V-1`, `V-3`). A predicate kind is a
   `Literal` over `organization_member`, `exact_node_member`, `subtree_member`,
   `scoped_role`, `trusted_group`, `explicit_principal`, and
   `classification_condition`. A new primitive requires new Core code and a new
   contract version, never new data.
2. Composition is declarative (`C-1`). A definition is an OR of clauses and a
   clause is an AND of predicates. There is no expression field, no script
   field, and no administrator-authored deny field (`C-3`); restriction is
   expressed by writing narrower clauses.
3. Operands must match the primitive. Node primitives require at least one node
   reference and every other primitive rejects node references; `subtree_member`
   names exactly one subtree root; `scoped_role` requires a role code;
   `trusted_group` requires a group code; `explicit_principal` requires at least
   one principal; `classification_condition` requires a classification code.
   Repeated node or principal operands are rejected.
4. One clause cannot repeat a primitive kind, because two conjunctive
   occurrences of one kind would require an implicit resolution rule.
5. Hard platform denies, organization isolation for non-public data, revocation,
   disabled membership or node status, and classification ceilings are evaluated
   outside allow clauses (`C-2`) and are therefore unrepresentable here. No
   clause can weaken them.
6. A definition is named, versioned, and identified by a stable identity plus a
   revision label and a content digest (`V-1`). `approved`, `active`, and
   `retired` require a recorded approver and approval instant; a `draft` must not
   record an approval; `approved_at` must not precede `created_at`.
7. Activated revisions are never edited in place (`V-5`): a recorded
   `previous_policy_revision` must differ from `policy_revision`.
8. When the definition names an owning organization, every predicate node must
   belong to that organization. A platform-wide definition, for example an
   anonymous public profile, omits the organization and still names the
   organization of every node operand explicitly.
9. The definition has no permission field, no `allow_all` field, and no
   follow-active-revision field, so a source binding is always an exact
   immutable revision (`V-4`) and an unresolvable reference cannot degrade into
   a permissive default (`V-7`).
10. Clause and predicate collections have hard documented ceilings
    (`MAX_ALLOW_CLAUSES`, `MAX_CLAUSE_PREDICATES`, `MAX_PREDICATE_NODES`,
    `MAX_PREDICATE_PRINCIPALS`) that administrators cannot weaken (`V-1`). All
    instants are timezone-aware; every model is frozen and rejects unknown
    fields.

## Out of scope

Deciding whether a definition allows a given principal, expanding a subtree,
resolving a role to permissions, and applying the retrieval pre-filter are CP-002
obligations. Catalog persistence, approval workflow, activation, rebinding, and
audit emission belong to CP-006 and CP-009. This contract is not the global
`security_policy` configuration artifact (`ADR-CP-002` `O-8`, audit finding
G-016).

## Versioning

New family at `1.0.0`. Adding a Layer 1 primitive, admitting an expression
fragment, or introducing deny language would each be a semantic break requiring a
new major version and an accepted CP-002 decision.

## Tests

`tests/test_visibility_and_isolation_contracts.py::VisibilityPredicateTests`,
`::VisibilityAllowClauseTests`, `::VisibilityPolicyDefinitionTests`,
`::SchemaArtifactTests`.
