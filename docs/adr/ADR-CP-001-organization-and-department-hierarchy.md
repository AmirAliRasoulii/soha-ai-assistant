# ADR-CP-001: Organization and OrganizationalNode Hierarchy

Status: Accepted architecture baseline (originated as CP-000A revision R1; CP-000R consistency repair applied, and CP-000R was accepted at commit `8d94c6a`)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000A-R1 architecture package
Owner: Control Plane / Authorization Scope Baseline
Scope: conceptual domain model only. No database schema, ORM, API, admin surface, or
identity-provider integration is decided here.

## Repository-state note

This document was accepted as an architecture baseline by CP-000R at canonical commit
`6477c1c`, and the contract names referenced below were re-confirmed against that commit.
Acceptance covers the architecture decisions recorded here. It does not claim that any of them
is implemented in Python code, JSON Schema, or persistence: no organization, node, membership,
or node-lifecycle contract exists in the repository yet. Implementation ownership is recorded
under "Explicitly open decisions" and in
`docs/control-plane/CP-000R-architecture-consistency-repair.md`.

## Context

The AI Core already carries trusted identity and authorization *inputs* and *decisions* as
opaque canonical codes: principal identity facts, `roles`, `groups`, `allowed_scopes`,
`data_classification_allowances`, resource `classification`, `reason_codes`, `obligations`,
`constraint_references`, and `policy_version`. What is missing is the organizational
structure those codes refer to: there is no organization, node, membership, or
visibility-policy concept to produce them.

Without an organizational baseline, every future control-plane package would be free to
invent its own meaning for a scope code, which is how a system ends up with several
incompatible authorization models.

Deployments must cover at least a university, a company, and a hospital, whose internal
structures differ in naming and depth but not in kind. Building one authorization system per
deployment type is not acceptable. Deployments must also be able to publish material for
readers who have no account at all, without that capability leaking into organizational
access.

## Decision

1. A deployment has one or more `Organization` aggregates. Every organizational resource
   belongs to exactly one organization, including resources published for anonymous readers.
2. Organizational structure is modeled as a single generic recursive entity,
   `OrganizationalNode`. Structure is expressed by node relationships, not by distinct entity
   types per deployment vocabulary.
3. `Department` is one `NodeType` value. It is not the universal root abstraction and carries
   no privileged semantics.
4. `NodeType` is a dynamic, versioned vocabulary, not a subclass hierarchy. Adding a term
   must never require a new entity, a new authorization path, or new Core code.
5. The initial deployment target is a single organization, but the domain boundary stays
   multi-organization capable: organization identity is an explicit part of node identity,
   membership, and every authorization input.
6. **Cross-organization access to non-public organizational resources is always denied.**
   The single exception is intentional publication: a resource whose active visibility policy
   allows `anonymous-public` is readable by any request actor, including an authenticated
   principal of another organization and an anonymous guest. That is a publication decision by
   the owning organization, not an organizational membership grant, and it introduces no other
   cross-organization mechanism (see ADR-CP-002, R1-02 semantics).
7. Hierarchy conveys structure only. It conveys no access. See "Default-deny hierarchy
   semantics".
8. Authorization semantics are independent of any fixed hierarchy depth, but the control
   plane enforces a platform-owned hard maximum depth and bounded path size that
   administrators cannot disable or weaken (see "Bounded depth").

## Conceptual domain model

Conceptual entities and value objects. These are not ORM models, table definitions, or typed
contracts; they define the vocabulary that future typed contracts must realize.

| Concept | Kind | Definition | Notes |
|---|---|---|---|
| `OrganizationRef` | value object | Stable opaque reference to one organization | Identity only; no display name is authorization-relevant |
| `OrganizationalNodeRef` | value object | Stable opaque reference to one node, qualified by its `OrganizationRef` | A node reference is never valid outside its organization |
| `OrganizationalNode` | entity | One structural unit inside one organization | Identity, `NodeType`, optional parent, status |
| `NodeType` | value object | Dynamic versioned classification code: faculty, department, office, laboratory, ward, clinical-unit, team, project, custom | Vocabulary term only; grants nothing |
| `HierarchyPathRef` | value object | Derived, trusted ancestor chain of a node within its organization, of bounded length | Derived by the control plane, never client-supplied; used by `subtree-member` evaluation |
| `NodeStatus` | value object | Minimum authorization-relevant lifecycle state of a node: `ACTIVE` or `NON_ACTIVE` | Only these two states are authorization-relevant. Archival, deletion, and root-retirement mechanics remain deferred (see "Node lifecycle and structural change") |
| `NodeDisplayName` | value object | Human-facing label | Explicitly excluded from authorization inputs |
| `RequestActor` | conceptual taxonomy | Either `AnonymousGuest` or `AuthenticatedPrincipal` | Defined in ADR-CP-002; referenced here because node-scoped concepts apply only to authenticated principals |

One conceptual domain diagram (existing repository documentation uses plain fenced blocks
rather than Mermaid, so that convention is followed):

```text
Deployment
└── Organization                          (OrganizationRef)
    └── OrganizationalNode                (OrganizationalNodeRef, NodeType, NodeStatus)
        ├── parent: OrganizationalNodeRef | none   (none == organization root node)
        ├── children: OrganizationalNode*          (recursive, same entity)
        └── path:    HierarchyPathRef              (derived, trusted, bounded)

NodeType (dynamic versioned vocabulary, no per-type entity)
    faculty | department | office | laboratory | ward | clinical-unit | team | project | custom

RequestActor (ADR-CP-002)
    ├── AnonymousGuest          -> no organization, node, subtree, role, group, principal scope
    └── AuthenticatedPrincipal  -> memberships and scoped role assignments

Associations owned by ADR-CP-002, shown only for orientation:
    AuthenticatedPrincipal --< Membership >-- OrganizationalNode
    protected source -- visibility_policy_ref --> VisibilityPolicyDefinition (versioned)
    protected source -- security_scope_ref ----> retrieval pre-filter currency
```

## Hierarchy invariants

I-1. Every `OrganizationalNode` belongs to exactly one organization, and that binding is
immutable for the life of the node.

I-2. Every organization has **exactly one** root node. The root node has no parent. Every
non-root node has exactly one parent. A second parentless node inside one organization is
invalid structural input, not a policy question.

I-2a. The root node can never be re-parented. A root node is not a valid move target and is not
a valid move subject. An operation that would give the root a parent, or would move another node
above it, fails closed as invalid input.

I-3. A node's parent must belong to the same organization. Cross-organization parenting is
invalid input, not a policy question.

I-4. The graph of nodes within an organization is acyclic; a node is never its own ancestor.

I-5. `HierarchyPathRef` is derived from parent relationships by the control plane. It is
never accepted from a client, a request actor, an LLM, a document, or a display name.

I-6 (bounded depth, revised in R1). Authorization semantics are independent of a fixed
hierarchy depth: no rule may depend on a specific level number, level name, or display label,
and no rule may assume a node is "the second level". Independently of that, the control plane
enforces a platform-owned hard maximum depth and a bounded `HierarchyPathRef` size. See
"Bounded depth" below.

I-7. Sibling relationships convey nothing. Two nodes sharing a parent have no relationship
beyond that shared ancestor.

I-8. Moving a node re-derives its `HierarchyPathRef` and therefore changes the outcome of
`subtree-member` predicates. Structural change is an authorization-relevant event and must be
auditable. Move mechanics are a control-plane concern, not decided here.

I-9. Anonymous readability is never a property of a node or of the hierarchy. It exists only
as an active visibility policy on a specific resource. A node is never "a public node" in a
way that makes its future resources readable by guests.

## Node lifecycle and structural change

This section fixes the minimum authorization-relevant node lifecycle. It deliberately does not
invent a complete persistence model, an admin surface, or an archival workflow.

L-1. A node is either `ACTIVE` or `NON_ACTIVE`. These are the only two states that authorization
semantics depend on. Any richer state set a future package introduces must map onto these two for
authorization purposes.

L-2. Only an `ACTIVE` node may create new authorization scope. Membership, scoped-role
assignment, and `subtree-member` breadth are evaluated against active nodes.

L-3. A `NON_ACTIVE` node grants **no new access**. Making a node non-active is a narrowing
operation, never a widening one. A non-active node is not a wildcard and not a bypass.

L-4. Deactivating a node does not retroactively create implicit access anywhere else. The
forbidden implications in "Default-deny hierarchy semantics" continue to hold in every node
state: no parent, child, or sibling access appears because a node became non-active.

L-5. Moving or re-parenting a node is an authorization-relevant operation, because it re-derives
`HierarchyPathRef` and therefore changes `subtree-member` outcomes (I-8).

L-6. A move or re-parent requires explicit authorization and produces an audit record. It is
never a silent structural edit and never a side effect of renaming or of a type change.

L-7. After a move, every derived `HierarchyPathRef`, scope cache, and pre-filter cache affected
by the moved subtree must be invalidated. A stale cached path is a silent authorization defect:
until invalidation completes, the safe behavior is to fail closed rather than serve a stale path.

L-8. Historical audit records retain the **historical** node and path reference that was in force
when the recorded decision was made. Audit history is never rewritten to match the current
structure, because that would destroy the ability to explain a past decision.

L-9. Root deletion and archive mechanics remain deferred. This package fixes only that the root
exists, is unique, and cannot be re-parented.

## Node metadata publication

P-1. Node metadata is **default deny**. There is no public node directory in this baseline.

P-2. An End User's access to node-directory information requires an explicit publication or
directory policy. Authenticated membership somewhere in the organization does not by itself
entitle a principal to enumerate the organization's structure.

P-3. Guest (`AnonymousGuest`) node metadata is denied. A future explicit publication contract may
allow specific published node metadata; until that contract exists, the answer is deny.

P-4. Publication of node metadata, if it is ever allowed, is an explicit versioned policy
decision on specific metadata, exactly as resource publication is (I-9). It is never a structural
property of a node and never inherited by the node's resources.

## Bounded depth

B-1. The platform owns a hard maximum hierarchy depth and a hard maximum derived path size.
These are platform bounds, not tenant settings.

B-2. A deployment may configure a lower effective limit within those hard bounds.
Administrators cannot raise, disable, or otherwise weaken the platform bound.

B-3. Structural operations that would exceed the effective limit fail closed as invalid
input. There is no truncation of a derived path, because a truncated path would silently
change `subtree-member` outcomes.

B-4. The exact initial limit is an open decision, to be selected later from operational
evidence. No authorization rule may become dependent on whatever value is chosen.

## Organization and node identity rules

R-1. Organization and node identity are opaque and stable. Renaming a node never changes its
identity and never changes an access outcome by itself.

R-2. Display names, administrator-typed labels, and free-text unit names are presentation
data, never authorization inputs.

R-3. Node references used in an authorization input must be qualified by organization. An
unqualified node reference is rejected rather than resolved by best effort.

R-4. Node identity is independent of `NodeType`. Changing a node's type does not create a new
node and does not, by itself, change access.

R-5. Node identity is distinct from every scope code and policy reference. A security scope
reference is a policy artifact (ADR-CP-002), not a node identifier reused as a scope.

## Node type extensibility

- `NodeType` values come from a dynamic, versioned vocabulary owned by the control plane.
- Adding a value is a vocabulary change, not a model change: no new entity, no new membership
  kind, no new authorization branch, no new Core code.
- No authorization rule in this baseline is written against a specific `NodeType` value.
  Rules are written against the safe visibility primitives of ADR-CP-002. A future package
  needing type-conditional policy must express it as an explicit versioned policy rule rather
  than a hard-coded type name.
- Unknown or retired type values fail closed at ingestion of structural data rather than
  being coerced to a default type.

## Default-deny hierarchy semantics

The hierarchy is a structural fact, not a permission graph. These implications are forbidden:

| Forbidden implication | Baseline behavior |
|---|---|
| Membership in a parent node grants access to descendants | Denied unless an active policy contains an explicit `subtree-member` predicate that matches |
| Membership in a child node grants access to ancestor resources | Denied. No upward inheritance exists in any form |
| Membership in one sibling grants access to another sibling | Denied. Siblings are unrelated for authorization purposes |
| A node's `NodeType` (for example "faculty") grants breadth | Denied. Type is vocabulary, not authority |
| Organization-root membership grants everything in the organization | Denied. Breadth comes only from an active policy predicate evaluated per resource |
| A node being "public-facing" makes its resources guest-readable | Denied. Only a resource's own active `anonymous-public` policy does that (I-9) |

Subtree access exists only when an active, versioned visibility policy contains a matching
`subtree-member` predicate and the principal's trusted `HierarchyPathRef` satisfies it. The
decision path is in ADR-CP-002; this ADR fixes only that hierarchy alone grants nothing.

## Deployment examples

All three use the same entity, the same membership relation, and the same decision path. Only
vocabulary and shape differ.

```text
University (layered example used throughout this package)
organization: University
└── node "Faculty of Computer Engineering"      (NodeType faculty)
    ├── node "Education Office"                 (NodeType office)
    ├── node "Computer Engineering Department"   (NodeType department)
    └── node "Robotics Laboratory"              (NodeType laboratory)

Company                                  Hospital
organization: Company                    organization: Hospital
├── node "HR"        (department)         ├── node "Ward A"     (ward)
├── node "Finance"   (department)         ├── node "Cardiology" (clinical-unit)
├── node "Engineering" (department)       │   └── node "ICU"    (clinical-unit)
└── node "Project Atlas" (project)        └── node "Administration" (office)
```

Worked consequences of the invariants:

- University: an Education Office member has no access to Faculty-level material, and a
  Faculty-level member has no access to Education Office material, unless an active policy
  predicate matches. The policy `computer-education-staff` in ADR-CP-002 is exactly how the
  Education Office case is expressed.
- University publication: `university-public-information` (`anonymous-public` AND
  `classification(public)`) makes specific published material readable with no account at all,
  while changing nothing about who can read Faculty or Education Office internal material.
- Company: "only central HR may manage HR knowledge" is expressed by assigning the steward
  role at the `HR` node with node-only breadth. No other node gains it.
- Hospital: centrally controlled knowledge management is expressed by management assignments
  at the organization root, while `Ward A` and `ICU` members read only what an active policy
  exposes to them, and patient records are outside this model entirely (ADR-CP-002 boundary).

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| `Department` as the universal structural entity | Cannot express faculty/office/laboratory/ward/project without renaming semantics per deployment or adding parallel entities; forces deployment-specific authorization code |
| A distinct entity per organizational concept (Faculty, Ward, Team, ...) | Multiplies authorization paths; every vocabulary term becomes a schema and policy change |
| Flat list of nodes with no parent relationship | Cannot express subtree predicates or delegated management; pushes structure into display names, which are untrusted |
| Materialized name path as the identifier | Renaming or moving a unit would silently change identity and access; conflicts with R-1 and R-2 |
| Implicit top-down inheritance of access | Contradicts default-deny; makes every reorganization a silent privilege grant |
| Unbounded operational depth | Unbounded derived paths are a denial-of-service and correctness hazard for path evaluation; replaced by bounded depth with depth-independent semantics |
| Marking nodes as public and inheriting that to their resources | Makes publication a structural side effect; conflicts with I-9 and with explicit publication under ADR-CP-002 |
| Per-organization authorization system selected by deployment type | Rejected by package scope: one model must serve all three deployment examples |
| One index/collection per node, role, or principal | Unbounded physical fan-out; moves authorization into topology where it cannot be versioned or audited |

## Consequences

- One structural entity and one decision path serve all deployment types; deployment
  differences are configuration and vocabulary, not code.
- Every access decision must consult an active policy. Nothing is derivable from structure
  alone, so no "cheap" hierarchy shortcut is available to implementers.
- `HierarchyPathRef` must be derived, trusted, and bounded, which makes structural change an
  authorization-relevant, auditable operation and makes path evaluation cost predictable.
- Bounded depth means some real-world reorganizations may be rejected as invalid input; that
  is preferred over silent path truncation.
- Publication for anonymous readers is possible without any node, membership, or hierarchy
  concept being weakened, because publication lives on the resource's policy, not on the node.
- Multi-organization capability is preserved at the boundary with no cross-organization code
  path for non-public resources.
- Future typed contracts will be needed for these concepts; this ADR intentionally produces no
  code, schema, or migration.

## Explicitly open decisions

| Open decision | Why it remains open | Which package should decide | Evidence required |
|---|---|---|---|
| Exact hard maximum hierarchy depth and path-size bound | No operational evidence exists yet; the invariant (bounded, platform-owned, non-weakenable) is decided, the number is not | Control-plane structural limits package | Real organizational depths across university/company/hospital deployments, and measured path-evaluation cost at candidate depths |
| Full `NodeStatus` lifecycle beyond `ACTIVE`/`NON_ACTIVE`, including archival, deletion, and root retirement | CP-000R fixes the two authorization-relevant states and their fail-closed semantics; the wider lifecycle, archival mechanics, and root retirement remain undecided | CP-001 (typed contracts), control-plane node lifecycle package | Reorganization scenarios, retention obligations, whether historical evidence stays readable after retirement |
| Exact node move and re-parenting mechanics | CP-000R fixes the obligations (explicit authorization, audit record, cache/path invalidation, historical audit retention, root immovable); the operational mechanics, bulk-move behavior, and invalidation protocol remain undecided | CP-001, control-plane node lifecycle package | Real reorganization scenarios and audit/retention requirements |
| `NodeType` vocabulary contents and versioning rules | Requires the three deployment vocabularies to be confirmed by their owners | Control-plane vocabulary package | Confirmed unit taxonomies per deployment type |
| Node metadata beyond identity, type, parent, status | Unbounded without concrete admin requirements | Control-plane admin package | Approved admin surface requirements |
| Whether any node metadata may be published to anonymous guests, and how | Guest node-metadata access is denied by default in R1; a publication path may be wanted later | Control-plane publication package | Concrete public-directory requirements per deployment |
| Membership synchronization from an external directory | Depends on the unselected identity provider | Identity/adapter package | Selected IdP and its group/unit export capability |
| Deployment topology and organization provisioning | Single-organization start is a target, not a decided topology | Platform/deployment package | Hosting and tenancy requirements |
| Typed contract shapes for these concepts | This package is design-only by mandate | A future CP contract package | Architect acceptance of ADR-CP-001 and ADR-CP-002 |
