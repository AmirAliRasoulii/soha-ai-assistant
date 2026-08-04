# ADR-CP-002: Membership, Scoped Roles, and Authorization Scope

Status: proposed for CP-000A architect review, revision R1 (not accepted, no implementation
authorized)
Date: recorded with the CP-000A-R1 architecture package
Owner: Control Plane / Authorization Scope Baseline
Scope: authorization semantics for organizational knowledge sources. No database schema, ORM,
API, admin surface, identity-provider integration, index topology, or typed contract is decided
here.

## Repository-state note

This revision makes no claim about branch names, commit identifiers, commit counts, or the
commit status of any prior work package. Contract names are cited as design references and
must be re-confirmed against canonical HEAD before acceptance. In particular, this document
does **not** claim that `SecurityPrincipalContext` models an anonymous actor; the
`RequestActor` taxonomy below is a conceptual requirement whose realization is deferred to a
future typed-contract package.

## Context

ADR-CP-001 fixes the organizational structure and states that structure alone grants nothing.
This ADR defines who may do what, on which resources, and from which trusted inputs.

The AI Core already produces and consumes authorization *codes* -- principal identity facts,
role labels, group labels, allowed scope codes, classification allowances, resource
classification, decision effects, reason codes, obligations, constraint references, and a
policy version -- but nothing in the system currently produces those codes from organizational
facts, and no visibility concept exists. Without this ADR, each future package would invent its
own meaning for the same codes.

The baseline must additionally support two requirements that a purely membership-based model
cannot express:

1. Material intentionally published to readers who have no account at all.
2. A policy catalog that grows with deployment needs without new Core code per policy profile.

## Decision

D-A. Authorization uses a hybrid model: **scoped RBAC for administrative operations** plus
**policy/attribute-based authorization for data access**. Neither half is expressible by the
other, and both are evaluated from trusted inputs only.

D-B. Eight concepts stay distinct and are never collapsed into one role field or one ACL
column.

| Concept | What it is | What it is not |
|---|---|---|
| Identity | Trusted facts about the request actor: either an authenticated principal or an anonymous guest | Not a permission, not a role |
| Membership | Trusted association of an authenticated principal with one node in one organization | Not a role, not read access |
| Role assignment | A role label bound to a specific membership scope | Not a permission set by itself |
| Permission | A capability to perform an action in a scope, resolved by versioned policy | Not a role label, not a display name |
| Visibility policy | Versioned artifact describing which actors may see a resource | Not a role list, not an ACL on a row, not an index name |
| Security scope | Trusted filter currency emitted by an authorization decision and applied before retrieval | Not a node id, not a role, not a policy body |
| Classification | Sensitivity attribute of the resource | Not a grant, never widens access |
| Authorization decision | The versioned, auditable output that authorizes an action and emits scope references | Not a cached role lookup, not an LLM judgement |

D-C. Role labels are **inputs** to policy evaluation. A role name by itself is never a grant.

D-D. Default deny. Absence of a matching active policy is denial, never a fallback to a wider
or narrower default.

D-E. A request actor is either an `AnonymousGuest` or an `AuthenticatedPrincipal`, decided
intentionally before evaluation. Anonymous readability exists only through an active policy
allowing the `anonymous-public` primitive.

D-F. Read authorization and management authorization are separate resolutions. Neither implies
the other in either direction.

D-G. Visibility policies are administrator-defined, versioned artifacts composed only from
platform-owned safe primitives. Administrators extend the catalog; they never extend the
primitive set or author executable code.

## Request actor model

```text
RequestActor
├── AnonymousGuest
│     no principal identity, no organization, no node, no subtree,
│     no role, no group, no principal scope, no management capability
└── AuthenticatedPrincipal
      trusted identity facts + memberships + scoped role assignments + group facts
```

G-1. `anonymous-public` means exactly: readable without login, organizational membership, role,
group, or named principal.

G-2. Guest readability must be explicitly assigned by an **active versioned policy** on the
specific resource. Missing policy is deny.

G-3. Authentication failure must never downgrade or fall back to guest processing. A failed or
expired authentication is an error, not a demotion. A request is intentionally processed either
as guest or as an authenticated principal, and that determination is made once, before policy
evaluation.

G-4. A guest receives no organization, node, subtree, role, group, or principal scope. Any
policy clause requiring such a predicate cannot match a guest.

G-5. A guest may retrieve only resources whose active policy allows `anonymous-public` **and**
whose classification is the platform-approved public classification. Both conditions are
required; neither substitutes for the other.

G-6. A guest receives no management, audit, raw-content inspection, upload, update, approval,
activation, revoke, or deletion permission, under any policy. These are not policy-expressible
for guests.

G-7. Authenticated principals may also read `anonymous-public` resources, including resources
owned by an organization they are not a member of (see cross-organization semantics).

G-8. Guest retrieval is still filtered retrieval: the decision emits a trusted, non-bypassable
public security-scope filter that is applied before retrieval. There is no unfiltered
retrieval path for guests or anyone else.

G-9. No claim is made here that any existing typed contract represents an anonymous actor. A
future contract package must decide whether guest requests carry a distinct context type or a
restricted principal context. Until then, guest handling is a conceptual requirement only.

## Cross-organization semantics

X-1. Cross-organization access to **non-public organizational resources** is always denied.
Organization isolation is evaluated outside allow clauses and cannot be overridden by one.

X-2. `anonymous-public` is an intentional publication decision by the owning organization. It
is not an organizational membership grant and confers nothing beyond reading that resource.

X-3. Consequently an authenticated principal of Organization A may read an `anonymous-public`
source owned by Organization B, because that source is available to every actor including
guests. The principal gains no membership, no scope, and no visibility into any other resource
of Organization B.

X-4. No other cross-organization mechanism is introduced by this baseline. Any future
controlled federation must arrive as an explicit versioned policy capability in its own
package.

## Membership model

M-1. Membership is many-to-many between an authenticated principal and `OrganizationalNode`.
A principal may hold many memberships; a node may have many members.

M-2. Each membership is scoped to exactly one node in exactly one organization. There is no
"organization-wide membership" shortcut distinct from membership at the organization root node.

M-3. Membership is a trusted fact resolved by the control plane. Client-supplied, LLM-derived,
or document-derived membership claims are rejected inputs, not lower-confidence inputs.

M-4. Membership by itself conveys no read access and no management capability. It is a
predicate input only.

M-5. Memberships are independent. Holding several does not compose into a broader implicit
scope; each is evaluated on its own against the resource's active policy.

M-6. Membership breadth is exactly one node. Any breadth beyond that node comes only from a
`subtree-member` predicate in the resource's active policy, evaluated against the principal's
trusted `HierarchyPathRef`.

M-7. Membership state changes (grant, revoke, suspend) are authorization-relevant and must be
auditable. Revocation and disabled status are evaluated outside allow clauses.

Worked example (unchanged decision, layered example):

```text
Principal A
├── membership: node "Computer Engineering Department" | role: member
├── membership: node "Research Office"                | role: reviewer
└── membership: node "Project X"                      | role: manager
```

Principal A is a reviewer only within Research Office scope, a manager only within Project X
scope, and an ordinary member in the department. No role leaks across memberships.

## Scoped role assignment model

S-1. A role assignment binds a role label to a specific membership scope. A role label without
a scope is invalid input.

S-2. Role labels are opaque codes from a versioned catalog. Display names, free text, and
frontend-supplied labels are never role labels.

S-3. A role assignment grants nothing by itself. It becomes effective only where a versioned
policy references that role in a matching clause.

S-4. Role assignments do not propagate to parent, child, or sibling nodes.

S-5. The same principal may hold different roles in different scopes simultaneously, with no
interaction between them.

S-6. Administrative roles are resolved through scoped RBAC; data-read entitlement is resolved
through visibility policy. An administrative role never appears as an implicit read grant
(see "Administrative permission separation").

## Trusted authorization inputs

```text
trusted request-actor determination (guest or authenticated principal)
+ trusted principal identity facts        (authenticated case only)
+ trusted memberships
+ scoped role assignments
+ trusted group facts
+ resource visibility policy              (active revision)
+ resource classification
+ versioned authorization policy
= AuthorizationDecision
```

Forbidden inputs. These are rejected, not down-weighted:

| Forbidden input | Reason |
|---|---|
| LLM output of any kind | Non-deterministic and injectable; authorization must be reproducible |
| Frontend-provided role labels | Client-controlled privilege escalation |
| Node or department display names | Presentation data; renaming would change access |
| Client-provided organization metadata | Client-controlled organization spoofing |
| Untrusted document metadata | Documents can assert their own visibility if trusted |
| Retrieval results or their scores | Circular: retrieval must already be constrained by the decision |
| Absence of a policy interpreted as permissive | Contradicts default deny |
| A failed authentication interpreted as guest | Contradicts G-3 |

## AuthorizationDecision responsibilities

D-1. The decision authorizes a specific action on a specific resource reference for a specific
request actor. It is not a general capability dump.

D-2. It records the effect together with reason codes, so both allow and deny are explainable
without re-running evaluation.

D-3. It carries the policy version and the identity of the policy revisions consulted. A
decision that cannot name its policy version is invalid.

D-4. It emits the authorized security scope references that the retrieval pre-filter must use,
including the public scope filter for guest and `anonymous-public` reads.

D-5. It may attach obligations and constraint references, for example audit obligations for
raw-content inspection. Obligations are mandatory, not advisory.

D-6. It is time-bounded: evaluation time and expiry are part of the decision, and an expired
decision may not authorize retrieval.

D-7. It never widens itself. A decision cannot be re-interpreted, merged with another decision,
or extended by a downstream component.

## VisibilityPolicy semantics

Two layers, per R1-03:

```text
Layer 1: platform-owned safe primitives          (fixed, only Core may extend)
    anonymous-public
    organization-member
    exact-node-member
    subtree-member
    scoped-role
    trusted-group
    explicit-principal
    classification-condition

Layer 2: admin-defined versioned VisibilityPolicyDefinition artifacts
    composed only from Layer 1 primitives
```

V-1. A `VisibilityPolicyDefinition` is: named; versioned; validated; approved according to
delegated authority; immutable after activation; identified by a stable ref plus
revision/digest; composed only from supported safe primitives; and subject to hard platform
bounds that administrators cannot weaken.

V-2. The catalog grows dynamically. Adding a policy profile must never require new Core code,
new primitives, a new index, or a new collection.

V-3. Ordinary administrators may not author arbitrary executable predicates, scripts, or
expression-language fragments. Composition is declarative and closed over Layer 1.

V-4. Every protected source references exactly **one** active `VisibilityPolicyDefinition`
revision at a time, plus a trusted security-scope reference used by the pre-filter.

V-5. Changing a source's policy means binding a new approved revision. That rebinding is
authorization-relevant and audited. Activated revisions are never edited in place.

V-6. Policies are never realized as one collection, index, partition, or namespace per role,
group, principal, or node. Physical topology is not an authorization mechanism.

V-7. Missing or unresolvable policy reference is deny, and for an unpublished source it means
draft-only.

Example policy definitions (definitions, not hard-coded role names or index collections):

```text
all-public-guests                     anonymous-public AND classification(public)
university-public-information         anonymous-public AND classification(public)
all-authenticated-university-members  organization-member(University)
computer-faculty-members              subtree-member(Faculty of Computer Engineering)
computer-education-staff              exact-node-member(Education Office)
                                          AND scoped-role(education-staff)
hr-compensation-managers              exact-node-member(HR) AND scoped-role(compensation-manager)
icu-clinical-staff                    exact-node-member(ICU) AND scoped-role(clinical-staff)
```

### Composition (R1-04)

```text
VisibilityPolicyDefinition
├── one or more allow clauses
├── every predicate inside one clause is AND
└── clauses are combined with OR

allow =
    clause_1_matches
    OR clause_2_matches
    OR ...

within a clause:
    node match
    AND role match
    AND classification condition
```

C-1. A clause matches only if every predicate in it matches. A definition allows only if at
least one clause matches.

C-2. Evaluated **outside** allow clauses, and not overridable by any clause: hard platform
denies, organization isolation for non-public data, revocation, disabled membership or node
status, and classification ceilings.

C-3. No administrator-authored explicit deny language, scripting, or arbitrary expression
language exists in this baseline. Restriction is achieved by writing narrower clauses.

C-4. An empty clause set is deny. A clause that cannot be validated makes the whole revision
invalid and non-activatable.

## Classification interaction

K-1. Classification is a property of the resource and describes sensitivity only.

K-2. Classification never widens access. A permissive classification cannot make a resource
readable to an actor whose policy evaluation did not allow it.

K-3. Classification can only narrow: the actor's classification allowance is a ceiling applied
after the allow evaluation. Guests are limited to the platform-approved public classification.

K-4. `classification-condition` inside a clause may only further restrict that clause; it
cannot raise an actor's ceiling.

K-5. Unknown or missing classification fails closed and is treated as not readable, never as
public.

## Administrative permission separation

A-1. Read entitlement and management capability are resolved separately. Being allowed to read
a source implies no capability to upload, edit, submit, review, approve, activate, revoke, or
delete it.

A-2. The reverse also holds and is the correction introduced in R1: an administrative role
confers **no** automatic read privilege. An administrator reads a normal source only when an
ordinary visibility policy entitles them, exactly as any other principal would be entitled.
When so entitled, no special raw-content permission is involved.

A-3. Conceptual node-scoped administrative concepts for the baseline: Node Manager, Data
Steward, Reviewer, Activator or authorized approver, Auditor, End User. The final catalog is
versioned later.

A-4. Administrative capability is bounded by assigned scope. A Node Manager does not
automatically manage sibling or descendant nodes; descendant management requires an explicit
assignment or an explicit versioned delegation policy.

A-5. Approval and activation are distinct capabilities. Reviewer approval does not imply
activation.

A-6. Raw-content inspection is a separate, explicitly named administrative action requiring its
own permission, a recorded reason, and an audit obligation. It is never implied by metadata
access, by any administrative role, or by ordinary read entitlement.

A-7. Delegated management is supported but not required. A deployment may keep all management
at the organization root (hospital case), delegate per unit (university faculty stewards), or
centralize by function (company HR).

## Source metadata at draft time (R1-05)

U-1. When a persistent document or official URL is drafted, the authorized uploader must
provide or select: `administrative_owner_node_ref`, `visibility_policy_ref`, `classification`,
`source_type`, `title`.

U-2. Administrative ownership does not grant read access, and membership in the owner node does
not grant read access. Ownership answers "who administers this", not "who may read it".

U-3. The uploader may select only already-approved policy revisions within their delegated
scope. Selecting metadata is not authoring policy.

U-4. The uploader cannot create a wider policy merely by submitting metadata. Widening requires
the separate policy-authoring, approval, and activation permissions.

U-5. Creating, approving, and activating visibility policy definitions are three separate
permissions and may be held by different actors.

U-6. Missing `visibility_policy_ref` means draft-only and deny. A draft is never readable
through the ordinary read path.

U-7. Ownership changes and visibility changes are independent operations, each
authorization-relevant and each audited.

U-8. The complete source lifecycle -- revision, update, revoke, deletion, and the persistent
document and official URL lifecycles -- is **not** designed here. It belongs to the next
source-registry package.

## Query-time authorization path

```text
(1) trusted request-actor determination      guest or authenticated principal, decided once
         |
(2) trusted identity facts                  principal identity, assurance, groups
         |
(3) membership and policy resolution        trusted memberships, scoped roles,
         |                                  resource active VisibilityPolicyDefinition revision
(4) outside-clause gates                    platform denies, organization isolation for
         |                                  non-public data, revocation, disabled status
(5) allow evaluation                        OR of clauses, AND within a clause
         |
(6) classification ceiling                  actor allowance applied; guests limited to
         |                                  the platform-approved public classification
(7) AuthorizationDecision                   effect, reason codes, obligations,
         |                                  policy version, expiry
(8) authorized security_scope_refs          trusted filter currency, including the
         |                                  non-bypassable public scope filter
(9) mandatory retrieval pre-filter          applied before retrieval, not after
         |
(10) retrieval                              constrained by construction
```

E-1. Filtering after retrieval is insufficient and is not an accepted implementation. The
pre-filter is mandatory for every actor, including guests.

E-2. Query filters are built only from the trusted decision output and versioned artifacts.
No filter may be derived from an LLM, a client hint, a display name, or document metadata.

E-3. A missing, expired, or unparsable decision means no retrieval, not unfiltered retrieval.

E-4. The decision's policy version and consulted revisions must be recoverable for audit, so
that any past retrieval can be re-explained.

## Examples

```text
(1) Layered university read
Principal: member of "Education Office", scoped role education-staff
Source:    owner node "Education Office", policy computer-education-staff,
           classification internal
Evaluation: clause exact-node-member(Education Office) AND scoped-role(education-staff)
            matches -> allow, ceiling satisfied
Outcome:    allowed. A Faculty-level member without that node membership is denied,
            and an Education Office member lacking the role is denied.

(2) Guest read of published material
Actor:     AnonymousGuest
Source:    policy university-public-information (anonymous-public AND classification(public))
Outcome:   allowed, retrieval still constrained by the trusted public scope filter.
           The same guest is denied every other source, all metadata management,
           audit metadata, and raw-content inspection.

(3) Cross-organization authenticated read
Actor:     authenticated principal of Company (Organization A)
Source:    owned by University (Organization B), policy university-public-information
Outcome:   allowed for that source only. No membership, no scope, no other
           University resource becomes visible.

(4) Administrator with no ordinary entitlement
Actor:     Global System Admin, no membership matching the source policy
Source:    policy hr-compensation-managers
Outcome:   ordinary read denied -- administrative role grants no read privilege.
           Raw-content inspection is possible only through the separate named
           inspection action, with reason and audit obligation.

(5) Uploader cannot self-grant
Actor:     Data Steward of "HR", drafting a compensation document
Attempt:   select a broader policy such as all-authenticated-university-members
Outcome:   rejected unless that revision is approved and within the steward's delegated
           scope. Submitting metadata never authors or widens policy.

(6) Hospital clinical scope
Actor:     member of "ICU", scoped role clinical-staff
Source:    ICU clinical guideline, policy icu-clinical-staff
Outcome:   allowed. A Ward A member is denied (sibling conveys nothing).
           Patient records are outside this model entirely (see boundaries).
```

## Default-deny behavior

Denied by default, with no fallback: no matching clause; missing or unresolvable policy
reference; expired or missing decision; unknown or missing classification; revoked, suspended,
or disabled membership or node status; cross-organization request for a non-public resource;
guest request for anything not `anonymous-public` with public classification; guest request for
any management, audit, or inspection action; authentication failure (an error, never a
downgrade to guest); any input that is client-, LLM-, or document-derived.

## Boundaries and non-goals

B-1. Personal, transactional, and clinical records -- patient records above all -- must not be
modeled as ordinary knowledge documents. They require separate capabilities and inputs such as
self-only access, care-team assignment, purpose of use, record ownership, and transactional
policy. This baseline explicitly declares that out of scope; no clinical record authorization
system is designed here.

B-2. Not designed or implemented by this package, and referenced only as downstream
dependencies or open decisions: database schema, ORM and Django models, REST/GraphQL APIs,
admin pages, identity-provider integration, vector database selection, physical index topology,
source ingestion pipeline and source-registry lifecycle, configuration artifact precedence,
runtime snapshot factory behavior, model/provider pool, secret management, and
retention/compliance policy.

B-3. No typed contract, schema, or Python code is added by this package. Contract realization,
including how a guest request is represented, is a future package.

## Alternatives rejected

| Alternative | Why rejected |
|---|---|
| Single global role field per user | Cannot express different roles per node; forces one privilege level across the whole deployment |
| Role names as direct grants | A rename or a client-supplied label would become privilege; conflicts with S-2 and S-3 |
| Pure RBAC for data access | Cannot express classification ceilings, subtree conditions, or per-resource publication |
| Pure ABAC for administration | Loses simple, auditable scoped administrative assignment and delegation |
| Implicit hierarchy inheritance | Contradicts ADR-CP-001 default-deny; reorganization would silently grant access |
| Fixed closed list of visibility profiles | Every new deployment need would require Core code; replaced by dynamic definitions over safe primitives |
| Administrator-authored expression language or scripts | Unbounded, unvalidatable, and unauditable; injection and escalation surface |
| Administrator-authored explicit deny rules | Deny/allow interaction becomes unreviewable; restriction is expressed by narrower clauses instead |
| Multiple active policy revisions per source | Ambiguous evaluation and unexplainable decisions; exactly one active revision is required |
| Mutable activated policy revisions | Past decisions would become unexplainable; activation is immutable |
| Treating absent policy as public | Catastrophic default; absence is deny |
| Falling back to guest access on authentication failure | Turns an outage or token bug into silent data exposure; conflicts with G-3 |
| Treating `anonymous-public` as a cross-organization membership grant | Would leak non-public resources of the owning organization; publication is per-resource only |
| Administrative roles carrying implicit read privilege | Makes administration a shadow read path; corrected in R1 by A-2 |
| Requiring raw-content permission for ordinary administrator reads | Wrongly conflates ordinary policy entitlement with privileged inspection; corrected in R1 by A-2 and A-6 |
| Post-retrieval filtering | Content has already left the trust boundary; conflicts with E-1 |
| One index or collection per role, group, principal, or node | Unbounded physical fan-out; authorization becomes untestable topology |
| Storing visibility as an ACL list on each source | Unversioned, unreviewable, and unmaintainable at scale; loses policy identity and audit |
| Deriving any authorization input from LLM output | Non-deterministic and injectable |

## Consequences

- Every read requires an active policy revision on the resource; there is no permissive default
  and no structural shortcut.
- Publication to anonymous readers is possible, explicit, per-resource, and still filtered,
  which keeps organizational isolation intact for everything else.
- The policy catalog can grow with deployment needs without Core changes, at the cost of
  requiring policy authoring, approval, and activation workflows.
- OR-of-AND composition is intentionally weak. Some real requirements will not be expressible
  and must wait for an explicitly versioned extension of the primitive set rather than being
  worked around.
- Administrators are ordinary readers unless entitled, which means administrative work may be
  possible on resources whose content the administrator cannot read.
- Raw-content inspection carries permission, reason, and audit costs by design.
- Structural, membership, ownership, and policy-binding changes are all
  authorization-relevant events requiring audit.
- Retrieval components must accept authorized scope references as mandatory input; no component
  may retrieve first and filter later.
- Personal and clinical record handling remains unbuilt until a dedicated package defines it.

## Explicitly open decisions

| Open decision | Why it remains open | Which package should decide | Evidence required |
|---|---|---|---|
| Identity provider selection | No approved integration decision; affects trusted identity facts and assurance semantics | Identity/adapter package | Deployment IdP inventory, supported protocols, assurance and session requirements |
| Exact role catalog | Baseline defines conceptual roles only; the catalog must be versioned with concrete actions | Control-plane role catalog package | Confirmed operating models per deployment type |
| Exact action catalog | Matrix actions are conceptual and must be reconciled with real control-plane operations | Same catalog package | Approved control-plane operation list |
| Exact classification taxonomy, including the platform-approved public classification code | Guests depend on a single approved public code; the wider taxonomy is not approved | Classification package | Regulatory and organizational sensitivity requirements per deployment |
| Exact policy authoring, approval, and activation workflow | Delegated authority model is not approved; two-person approval requirements are unresolved | Control-plane policy governance package | Risk assessment, audit requirements, staffing reality |
| Two-person approval and self-review requirements | Whether an author may review or approve their own submission depends on governance and regulatory obligations | Same governance package | Regulatory obligations, staffing reality, and incident/risk analysis |
| Hard platform bounds on policy size and clause count | Bounds must exist and must not be weakenable, but the numbers need evidence | Control-plane limits package | Measured evaluation cost and realistic policy shapes |
| Membership synchronization mechanism | Depends on the unselected IdP; manual versus synchronized changes the trust model | Identity/adapter package | Selected IdP export capability, expected churn |
| Node lifecycle and status states | Owned by ADR-CP-001 and unresolved there | Control-plane node lifecycle package | Reorganization and retention scenarios |
| Physical index backend and topology | Explicitly out of scope; must not become an authorization mechanism | Retrieval/index package | Scale, latency, and cost requirements |
| Legal retention requirements for decisions and audit records | Jurisdiction and deployment dependent | Compliance package | Legal review per deployment type |
| Deployment topology and organization provisioning | Single-organization start is a target, not a decided topology | Platform/deployment package | Hosting and tenancy requirements |
| Guest request representation in typed contracts | This package adds no contract, and no claim is made about existing contract shapes | Future CP contract package | Architect acceptance of this ADR |
| Personal/transactional/clinical record authorization | Declared a non-goal here; requires its own inputs and capabilities | Clinical/transactional records package | Clinical governance requirements, purpose-of-use rules, legal review |
