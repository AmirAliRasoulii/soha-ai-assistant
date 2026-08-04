# ADR-CP-001: Organization and OrganizationalNode Hierarchy

Status: proposed for CP-000A architect review, revision R1 (not accepted, no implementation
authorized)
Date: recorded with the CP-000A-R1 architecture package
Owner: Control Plane / Authorization Scope Baseline
Scope: conceptual domain model only. No database schema, ORM, API, admin surface, or
identity-provider integration is decided here.

## Repository-state note

This revision makes no claim about branch names, commit identifiers, commit counts, or the
commit status of any prior work package. Contract names referenced below are cited as design
references and must be re-confirmed against canonical HEAD before acceptance. No statement
in this document depends on a particular Git history.

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
| `NodeStatus` | value object (open) | Lifecycle state of a node | Minimally proposed; not finalized in this package |
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

I-2. A node has at most one parent. The organization root node has no parent.

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
| `NodeStatus` lifecycle states | No canonical source approves a state set. Minimal proposal: an active state plus a non-active state that fails closed for new access; archival/deletion unresolved | Control-plane node lifecycle package | Reorganization scenarios, retention obligations, whether historical evidence stays readable after retirement |
| Node move and re-parenting semantics | Interacts with `subtree-member` predicates, audit history, and previously granted access | Same lifecycle package | Real reorganization scenarios and audit/retention requirements |
| `NodeType` vocabulary contents and versioning rules | Requires the three deployment vocabularies to be confirmed by their owners | Control-plane vocabulary package | Confirmed unit taxonomies per deployment type |
| Node metadata beyond identity, type, parent, status | Unbounded without concrete admin requirements | Control-plane admin package | Approved admin surface requirements |
| Whether any node metadata may be published to anonymous guests, and how | Guest node-metadata access is denied by default in R1; a publication path may be wanted later | Control-plane publication package | Concrete public-directory requirements per deployment |
| Membership synchronization from an external directory | Depends on the unselected identity provider | Identity/adapter package | Selected IdP and its group/unit export capability |
| Deployment topology and organization provisioning | Single-organization start is a target, not a decided topology | Platform/deployment package | Hosting and tenancy requirements |
| Typed contract shapes for these concepts | This package is design-only by mandate | A future CP contract package | Architect acceptance of ADR-CP-001 and ADR-CP-002 |
