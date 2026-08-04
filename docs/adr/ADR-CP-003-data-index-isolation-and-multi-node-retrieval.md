# ADR-CP-003: Data/Index Isolation and Multi-Node Retrieval

Status: Accepted architecture baseline (originated as CP-000C; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000C architecture package
Owner: Control Plane / Data and Index Isolation Baseline
Scope: logical isolation, trusted query-time filter boundary, multi-node retrieval semantics,
IndexSnapshot eligibility, physical-isolation tiers, adapter expectations, and benchmark gating.
No vector backend, database schema, retrieval algorithm, index worker, adapter, or typed Python
contract is decided here.

## Existing contract and dependency boundary

Canonical dependencies:

- `ADR-CP-001` defines `Organization`, recursive `OrganizationalNode`, and hierarchy semantics.
- `ADR-CP-002` defines membership, scoped roles, dynamic visibility policies, `anonymous-public`,
  default deny, and the trusted authorization boundary.
- `ADR-CP-007` defines `KnowledgeSource`, immutable `SourceRevision`, source/revision lifecycle,
  immediate revocation exclusion, and purge separation.
- `CP-000A-authorization-matrix.md` and `CP-000B-source-lifecycle-matrix.md` define the approved
  administrative and lifecycle action boundaries.

Existing typed Core contracts already provide opaque authorization and runtime references:

- `SecurityPrincipalContext`, `AuthorizationResourceRef`, and `AuthorizationDecision`;
- `EvidenceSourceRef` and `EvidenceSecurityScope`;
- `RuntimeSnapshotContent` references to `index_snapshot`, `embedding_artifact`,
  `retrieval_profile`, `reranker_artifact`, `security_policy`, and `semantic_catalog`;
- `AuthorizationPort` and the provider-neutral port convention.

The organizational, source-registry, and index-isolation concepts remain conceptual until CP-001
defines typed contracts. In particular, `organization_ref`, `owning_node_ref`,
`hierarchy_path_ref`, `visibility_policy_ref`, `security_scope_ref`, `source_revision_ref`,
`IndexSnapshot`, `IndexIsolationProfile`, and `VectorStorePort` are not asserted here as existing
Python contracts.

## Context

ADR-CP-001 and ADR-CP-002 fixed the organizational, membership, and visibility-policy semantics
and established that structure alone grants nothing. ADR-CP-007 fixed the source registry:
`KnowledgeSource` as stable identity, `SourceRevision` as immutable activated snapshot, four
source states, six revision states, and an eight-condition runtime eligibility conjunction.

Neither package says where indexed content physically lives, how a query is constrained before a
backend ever ranks anything, or what happens when one principal legitimately belongs to several
nodes. Those questions decide whether the authorization model survives contact with a real search
backend. Answering them late means answering them inside a vendor adapter, which is where isolation
models are usually lost.

The AI Core already references an `index_snapshot` and an `embedding_artifact` as immutable runtime
artifacts, but nothing defines what a snapshot contains, when it is eligible, or how retrieval is
constrained by authorization. No retrieval capability, index lifecycle, or storage adapter exists.

## Problem statement

Five problems must be settled before any implementation package can proceed.

1. **Isolation topology.** If isolation is expressed physically, the topology must grow with users,
   roles, groups, or nodes, which does not scale and couples authorization to vendor objects. If
   isolation is expressed logically, the metadata must be trustworthy and the filter mandatory.
2. **Filter trust.** A retrieval filter assembled from client parameters, model output, or display
   labels is not an authorization control. The trust boundary must be explicit and one-directional.
3. **Multi-node breadth.** Multiple memberships must produce one bounded query, not fan-out,
   implicit hierarchy traversal, or silent scope widening.
4. **Index staleness.** A vector or posting entry outlives the authorization decision that justified
   it. Revocation must take effect without waiting for physical deletion or a rebuild.
5. **Provider choice.** The backend is undecided. The architecture must be decidable now and the
   backend decidable later, on measured evidence rather than documentation claims.

## Decision

Adopt this baseline:

**Shared logically partitioned index + mandatory trusted metadata pre-filter + tiered
physical-isolation promotion.**

- **D-1.** Isolation is a logical property of trusted metadata bound to every retrievable indexed
  unit, enforced by a mandatory pre-filter derived from a trusted `AuthorizationDecision`.
- **D-2.** The product contract must never require one collection per user, per role, per group, per
  ordinary organizational node, or per visibility policy. Many authorized scopes coexist in one
  shared physical backend by default.
- **D-3.** Physical isolation is an operational and defense-in-depth topology, promoted in tiers on
  measured evidence. Promotion never changes authorization semantics and never changes Core
  contracts.
- **D-4.** The pre-filter is constructed exclusively from trusted control-plane and identity output.
  Post-retrieval checks are permitted only as defense in depth, never as the primary control.
- **D-5.** Retrieval reads only explicitly active `IndexSnapshot` state, selected by trusted runtime
  state, never by the client or the model.
- **D-6.** Authorization and source status are authoritative over index presence. Physical presence
  of an entry never authorizes returning it.
- **D-7.** Every failure in identity, policy, scope, snapshot, metadata, digest, or filter
  construction resolves to zero results or a safe authorization error. There is no unfiltered
  fallback and no implicit public fallback.
- **D-8.** The backend is not selected in this package. Selection requires the benchmark in
  `CP-000C-index-isolation-blueprint.md` to pass its hard security gates.
- **D-9.** No provider object, SDK type, credential, connection handle, or vendor filter syntax
  enters Core. Backends are reached through a provider-neutral port, consistent with the existing
  port convention.

## Canonical terminology

This package uses conceptual references only. None of these is a display label, and none may be
supplied by a client or produced by a model.

### Mandatory Isolation Metadata Subset

The fourteen references in the table below are the **Mandatory Isolation Metadata Subset**. That
name is deliberate and normative:

- it is the minimum trusted metadata that every retrievable indexed unit must carry so that the
  mandatory pre-filter can be constructed and enforced;
- it is **not** the complete chunk or index metadata contract. Retrieval quality metadata, parser
  and chunker provenance, positional data, language metadata, ranking features, and display
  metadata are all outside this subset;
- the complete indexed-unit metadata contract is owned by CP-006, and CP-006 may add fields. It may
  never remove a field of this subset or make one of them optional;
- a unit missing any member of this subset is ineligible. It is never treated as "partially
  filtered" and never admitted with a default value.

| Reference | Meaning in this package |
| --- | --- |
| `organization_ref` | Stable identity of the owning organization; the outermost private boundary. |
| `owning_node_ref` | The organizational node that administratively owns the source. It is lineage and management metadata, not a read grant. |
| `hierarchy_path_ref` | Trusted reference to the node's position, used only for policy-granted subtree breadth. Never a parsed display path. |
| `visibility_policy_ref` | The active versioned visibility policy revision bound to the source revision. |
| `security_scope_ref` | A trusted scope identifier that an authorization decision may authorize and that indexed units carry. |
| `classification` | The data classification of the content, checked against the actor's allowances. |
| `source_ref` | Stable `KnowledgeSource` identity (CP-000B). |
| `source_revision_ref` | The immutable `SourceRevision` the indexed unit was derived from (CP-000B). |
| `index_snapshot_ref` | The immutable index build the unit belongs to. |
| `embedding_artifact_ref` | The immutable embedding configuration/model artifact used to produce vectors. |
| `content_digest` | Digest of the trusted content the unit was derived from, used for integrity binding. |
| `valid_from` / `valid_until` | Effective-time bounds for eligibility, produced by a trusted control-plane path only. See "Temporal metadata semantics". |
| `status` | Trusted eligibility state of the unit, derived from source and revision state. |

Explicitly **not** authorization identifiers: `department_name`, `role_name`, a `visibility = public`
string, client-submitted `allowed_group_ids`, and client-submitted organization names. These are
display or request data. They may be logged; they may never be filtered on.

`anonymous-public` carries exactly its CP-000A meaning: explicitly readable by an anonymous Guest
without login. It is a publication decision recorded as an active policy, never an absence of
policy. A missing, expired, invalid, or unresolvable policy is a deny, never public.

## Logical isolation model

Every retrievable indexed unit is bound to the trusted metadata set above. Not every field grants
read access: `owning_node_ref` is administrative lineage, while authorization is enforced through
the trusted organization, policy, scope, classification, lifecycle, time, snapshot, and integrity
conditions. Semantics per field are as defined in the terminology table; the rules that make the
set an isolation mechanism are:

- **L-1.** Authorization-relevant metadata is produced only by trusted ingestion and control-plane
  processes, from already-validated source-registry state. It is never copied verbatim from an
  upload request.
- **L-2.** Uploader-submitted labels are untrusted until validated and persisted as approved
  artifacts (CP-000B). An unvalidated label may become display metadata; it may never become filter
  metadata.
- **L-3.** Model output cannot create, alter, widen, or bypass a metadata filter. The model may only
  influence *what* is asked, never *what is permitted*.
- **L-4.** Frontend parameters cannot widen a scope. They may narrow a request within already
  authorized scopes, which is a usability feature and not an authorization input.
- **L-5.** Display names are never authorization keys. Node scope is never inferred from a rendered
  path, a title, a folder name, or a breadcrumb.
- **L-6.** Every unit is traceable to exactly one `source_revision_ref`, and through it to one
  `source_ref` and one `owning_node_ref` inside one `organization_ref`.
- **L-6A.** Changing `owning_node_ref` is an audited administrative ownership change. It does not
  change visibility, classification, active revision, or read authorization, and must not make a
  previously authorized unit readable or unreadable by itself.
- **L-7.** Every unit is traceable to exactly one `index_snapshot_ref` and one
  `embedding_artifact_ref`.
- **L-8.** A `content_digest` mismatch against trusted metadata makes the unit ineligible. An
  ineligible unit produces no evidence, not degraded evidence.
- **L-9.** `status`, `valid_from`, and `valid_until` are part of the eligibility conjunction, not
  advisory hints.
- **L-9A (temporal metadata semantics).** `valid_from` is derived from the trusted
  `SourceRevision.effective_from` recorded by the Source Registry
  (`docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`). When `effective_from` is absent,
  the trusted default is the trusted activation time. `valid_from` is never parsed from document
  text, never taken from a filename, never supplied by a client, and never inferred by a model.
- **L-9B.** `valid_until` is **nullable**. A null `valid_until` means open-ended: the unit stays
  eligible until an explicit lifecycle or security action ends its eligibility. Null is not treated
  as expired, and it is not silently replaced with a computed horizon.
- **L-9C.** Missing, malformed, or untrusted temporal metadata **never broadens access**. If
  `valid_from` cannot be trusted, the unit is ineligible; an unparseable `valid_until` is treated as
  expired rather than as open-ended.
- **L-10.** Revoked or disabled content is excluded fail-closed, immediately, regardless of physical
  presence.
- **L-11.** The unit's authorization metadata is redundant with control-plane state by design. On
  disagreement, the trusted control-plane state wins and the unit is excluded.

No ORM mapping, provider payload schema, field encoding, or index mapping is defined here. How the
set is physically represented is an adapter concern bounded by the port expectations below.

## Trusted authorization/filter boundary

Diagram 1 — query-time authorization and retrieval path:

```text
RequestActor (AnonymousGuest | AuthenticatedPrincipal)
  |
  v
Trusted identity resolution            [verified: SecurityPrincipalContext]
  |   principal facts, assurance, roles/groups/scopes as INPUTS only
  v
Membership and policy resolution       [conceptual: CP-000A control plane]
  |   memberships, scoped roles, active visibility policy revisions
  v
AuthorizationDecision                  [verified: AuthorizationDecision]
  |   effect, reason_codes, obligations, constraint_references, policy_version
  v
Authorized security_scope_refs         [conceptual allow-set, bounded]
  |
  v
Eligible active IndexSnapshot refs     [conceptual; runtime artifact ref verified]
  |
  v
MANDATORY trusted metadata pre-filter  [conceptual; enforced before candidates exist]
  |   organization + scope + classification + status + effective time
  |   + snapshot + digest binding
  v
Lexical / vector candidate retrieval   [bounded candidate limit]
  |
  v
Optional defense-in-depth re-check -> evidence construction with lineage

Denied inputs to the filter (hard):
  model-generated organization or node, frontend role label,
  client-provided department name, document display label,
  unvalidated uploader metadata, unreconciled token claims,
  model-generated visibility value.
```

Rules:

- **F-1.** Filtering after retrieval is not an acceptable primary authorization control. The
  backend must never see an unconstrained query for authorized content.
- **F-2.** Post-retrieval validation may exist only as defense in depth. Its failure is a fault to
  be reported, never a reason to widen the filter.
- **F-3.** An empty authorized scope set produces zero results. It is a valid, non-error outcome and
  must never be treated as "no constraint".
- **F-4.** Filter-construction failure produces zero results or a safe authorization error. It never
  produces a partial or absent filter.
- **F-5.** No error path, timeout, cache miss, degraded mode, or feature flag may cause unfiltered
  retrieval.
- **F-6.** No implicit private-to-public or public-to-private fallback occurs. Public retrieval is a
  distinct, explicitly requested path.
- **F-7.** No node scope is inferred from a display path.
- **F-8.** Runtime cannot broaden an `AuthorizationDecision`. It may only narrow within it, and it
  must honour `expires_at`, `obligations`, and `constraint_references`.
- **F-9.** The verified contracts carry authorization *codes*; the mapping from organizational facts
  to those codes belongs to the control plane. Nothing in this ADR assumes that mapping exists yet.

## Multi-node retrieval semantics

Multi-node retrieval is defined as **one logical authorization/retrieval envelope plus one or a
bounded number of physical backend queries**:

```text
one trusted AuthorizationDecision
    -> one bounded set of authorized security_scope_ref values
    -> one or more eligible index snapshot selections
    -> ONE logical authorization/retrieval envelope
         -> one OR a bounded number of physical backend queries
```

This document does **not** claim that every multi-node request performs exactly one physical query.
The invariant is that there is exactly one logical envelope, and that every physical query executed
under it carries the equivalent mandatory trusted constraints derived from that single envelope. A
trusted physical router may execute one backend query, or a bounded set of backend queries when
authorized scopes span promoted tiers or deployments. Physical query count is an operational and
routing property; it is never an authorization property.

- **N-1.** Scope membership is explicit. Holding a membership in one node grants nothing in any
  other node.
- **N-2.** Parent, child, and sibling access remain denied unless an active policy grants them.
  Depth and adjacency are not grants.
- **N-3.** Subtree breadth is represented by an explicit versioned policy or scope artifact, not by
  runtime path expansion.
- **N-4.** Authorized scopes are combined as one explicit logical allow-set. Multiple memberships
  never justify per-membership queries, uncontrolled fan-out, or scope widening. When physical
  routing requires more than one backend query, the router applies the same authorization envelope
  to every query and enforces a configured global fan-out bound.
- **N-5.** Hard denies, classification ceilings, source status, and revocation are evaluated outside
  the allow-set and cannot be overridden by it.
- **N-6.** Every candidate and every resulting evidence item preserves its scope, source, revision,
  and snapshot lineage. Merging candidates from several scopes must not erase authorization
  provenance.
- **N-7.** Results from different organizations are never combined for private organizational
  retrieval.
- **N-8.** `anonymous-public` results are intentionally globally readable and remain separately
  identifiable in lineage, so a public hit is never mistaken for an organizational grant.
- **N-9.** Cross-organization comparison is an explicit future query-policy concern, never implicit
  behaviour.
- **N-10.** The number of authorized scopes and the query fan-out are bounded by configuration. The
  exact bounds are open.

Final result-ranking fairness across nodes and scopes is deliberately not defined here. It is
recorded as an open retrieval-policy decision for CP-007.

## Anonymous Guest and public behavior

Guest path: `AnonymousGuest` -> public retrieval policy -> active `anonymous-public` security scopes
-> public-classification allowance -> mandatory public metadata pre-filter.

- **G-1.** Guest has no organizational membership and no role-derived scope.
- **G-2.** Guest sees only units bound to an active `anonymous-public` visibility policy revision.
- **G-3.** The unit classification must independently permit anonymous publication. Policy alone is
  insufficient; the classification ceiling also applies.
- **G-4.** Authentication failure must never silently downgrade an authenticated request into Guest
  mode. A failed authentication is an authentication error.
- **G-5.** Authenticated principals may also read `anonymous-public` units, including those owned by
  other organizations, because publication is a publication decision and not a membership grant.
- **G-6.** Public retrieval is still filtered, still bounded by candidate limits, and still snapshot
  scoped. Guest retrieval is never an unfiltered global index scan.
- **G-7.** Guest has no management, raw-inspection, or audit privilege.
- **G-8.** Administrative ownership does not affect public readability in either direction.

Whether public material lives in the same logical index or in a separately promoted physical tier is
an operational choice, not a security one. Both are permitted: the shared logical index with an
`anonymous-public` scope predicate is the Tier 1 baseline, and a promoted public tier is acceptable
when public traffic characteristics differ enough to justify it. In both cases the same mandatory
pre-filter, the same classification check, and the same snapshot eligibility rules apply. No
provider mechanism is prescribed.

## IndexSnapshot semantics

`IndexSnapshot` is a conceptual boundary here, not a typed contract. It represents an immutable,
identifiable build that contains or references at least: `index_snapshot_ref`, the corpus and source
revision set, the parser version, the chunking/contextualization version, the
`embedding_artifact_ref`, the index configuration reference, a build digest, `created_at`, an
activation status, and a superseded-snapshot reference.

- **S-1.** Indexed state is versioned. There is no unversioned "current index".
- **S-2.** Active retrieval uses explicitly active snapshots only.
- **S-3.** Re-embedding never mutates an active snapshot in place.
- **S-4.** A new parser, chunker, contextualization, embedding, or index configuration produces a
  new snapshot or an equivalent immutable revision.
- **S-5.** Activation is atomic at the product-contract level: a query observes the old snapshot or
  the new one, never a partially activated mixture.
- **S-6.** Prior snapshots remain available for rollback according to retention policy.
- **S-7.** Snapshot selection is trusted runtime state, consistent with the verified
  `RuntimeSnapshotContent.index_snapshot` artifact reference.
- **S-7A (aggregate manifest semantics).** `RuntimeSnapshotContent.index_snapshot` is a **logical
  aggregate `IndexSnapshot` manifest**, not a pointer to a single physical build. It references one
  or more eligible physical snapshots together with the routing metadata needed to select among
  them. This resolves the apparent conflict between a single `index_snapshot` reference in the
  contract and retrieval that may legitimately consult several eligible physical snapshots.
- **S-7B.** No client and no model may select an arbitrary physical snapshot from inside the
  aggregate manifest. Selection is trusted runtime routing only, and the aggregate manifest itself
  is resolved by the configuration path described in
  `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`.
- **S-8.** Neither the client nor the model may select an arbitrary snapshot.
- **S-9.** Stale or unverifiable snapshot state fails closed or abstains according to approved
  runtime policy. It never falls back to an unverified snapshot.
- **S-10.** Source revocation must not wait for a new snapshot build.

Alias switching, transaction semantics, and build orchestration are explicitly not prescribed.

## Source Registry dependencies

Index isolation is not self-contained. The eligibility conjunction depends on trusted Source
Registry state defined in `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`:

| Dependency | What retrieval consumes | Why it matters here |
| --- | --- | --- |
| Source authority | `authority_class_ref`, issuer reference, and the versioned authority profile | Authority is **not** an authorization grant. It may affect deterministic conflict precedence, ranking, and answer caveats. A model-supplied or client-supplied authority label is untrusted and must not reach ranking. |
| Source temporal metadata | `effective_from`, `valid_until`, `published_at`, `observed_at` | Produces `valid_from` / `valid_until` in the isolation subset (L-9A, L-9B). Upload time is never treated as business publication time. |
| Source lifecycle | `KnowledgeSource` and `SourceRevision` states, revocation, supersession | Drives `status` in the isolation subset and the fail-closed exclusion in L-10 and D-6. |
| Source relationships | `SUPERSEDES` within one `KnowledgeSource`, `SUPPLEMENTS` across separate sources | A superseded revision must not appear in current retrieval, while two supplemental sources may both be active and both eligible. The model never infers these relationships. |

## Benchmark fixture requirement

The benchmark that gates backend selection must include a fixture that exercises source-version and
relationship semantics together, covering at minimum:

```text
current source revision                  (active, must be retrievable)
historical superseded revision           (must be excluded from current retrieval,
                                          resolvable only through explicit historical query)
two active supplemental sources          (must coexist; neither supersedes the other)
```

This fixture is a correctness gate, not a quality metric. A backend that cannot express the
required filters over this fixture is disqualified regardless of its recall or latency results. No
vector or search backend is selected in this package: pgvector, Qdrant, OpenSearch, and any other
candidate remain open, and the comparison stays open until the benchmark in
`docs/control-plane/CP-000C-index-isolation-blueprint.md` passes its hard security gates.

## Revocation and stale-index behavior

Invariant: **authorization and source status remain authoritative over index presence.**

Sequence: source revoke or disable -> immediate retrieval exclusion -> cache and invalidation signal
-> index cleanup or rebuild later.

- **V-1.** Physical index deletion is not required for immediate exclusion.
- **V-2.** A revoked source is never returned merely because its vectors or postings are still
  physically present.
- **V-3.** Stale cache entries cannot restore revoked access. Caches are subordinate to trusted
  state.
- **V-4.** Failure to process an invalidation does not make stale results authorized. Unprocessed
  invalidation is a fault, not a permission.
- **V-5.** Runtime always checks trusted active state and authorization metadata, not index
  presence.
- **V-6.** Stale or unverifiable metadata produces no evidence.
- **V-7.** Physical purge remains a separate lifecycle and compliance action (CP-000B) and is never
  on the exclusion path.

Interaction with CP-000B and snapshots: `KnowledgeSource.source_status` gates the whole source;
`SourceRevision.revision_status` plus current-active-revision identity gates the specific version;
the active `IndexSnapshot` gates which physical build may be consulted. All three are conjunctive
with the authorization decision. A unit is returnable only when the source is `ACTIVE`, the revision
is `ACTIVE` and current, the snapshot is active and fresh enough under runtime policy, the digest
matches, effective time is satisfied, and the decision authorizes the required scope and
classification. Any single failure yields exclusion, not degradation.

## Physical isolation tiers

Diagram 2 — logical-to-physical isolation tier model:

```text
            LOGICAL (authorization)                 PHYSICAL (operations)

  organization_ref + security_scope_ref
  + classification
  + visibility_policy_ref + status
                |
                |  identical semantics at every tier
                v
  mandatory trusted metadata pre-filter
                |
  +-------------+--------------+--------------+--------------------+
  |             |              |              |                    |
  v             v              v              v                    v
Tier 1        Tier 2         Tier 3         Tier 4          (no tier grants
shared        dedicated      dedicated      dedicated        broader access)
logical       shard /        collection /   deployment
partition     partition      index
  |             |              |              |
  default     scale &        strong iso.    legal / residency /
  for all     noise iso.     lifecycle iso. customer-managed

  routing resolved by trusted configuration (IndexIsolationProfile, versioned)
  promotion / demotion is audited and never changes Core contracts
```

**Tier 1 — shared logical partition.** Default for ordinary organizations and nodes: shared physical
index or collection, trusted organization and scope metadata, mandatory filtering, bounded query
fan-out, shared operational resources.

**Tier 2 — dedicated shard or partition.** For larger or noisier scopes when the selected backend
supports it. Candidate triggers: corpus size, query volume, filter-selectivity degradation, latency
isolation, resource contention, operational maintenance windows.

**Tier 3 — dedicated collection or index.** For stronger operational isolation or backend
limitations. Candidate triggers: very large corpus, strict performance isolation, separate lifecycle
requirements, special embedding or index configuration, migration constraints.

**Tier 4 — dedicated deployment.** For legal isolation, data residency, customer-managed
infrastructure, encryption and key ownership, a compliance boundary, or extreme scale.

Rules:

- **T-1.** Promotion must not change Core contracts.
- **T-2.** Promotion must not change authorization semantics. The same filter is mandatory at every
  tier.
- **T-3.** Promotion must preserve stable references and citation lineage; `source_ref`,
  `source_revision_ref`, and citation resolvability survive relocation.
- **T-4.** Physical location is resolved through trusted configuration, never from a request.
- **T-5.** Demotion and migration are auditable, with a recorded reason and before/after topology.
- **T-6.** No tier grants broader read access. A dedicated tier is not a permission.
- **T-7.** Deployment-specific policy may prohibit lower tiers, for example a residency-bound
  deployment requiring Tier 4.

No numeric thresholds are set in this package.

## Promotion policy

Define a versioned `IndexIsolationProfile` concept (architectural artifact, no Python contract
here). Provider-neutral properties may include: `logical_tenant_key`, `physical_isolation_tier`,
`routing_profile_ref`, `capacity_class`, `residency_policy_ref`, `encryption_policy_ref`,
`index_configuration_ref`, `promotion_reason`, and an effective revision identifier.

- **P-1.** The profile is versioned and audited; a topology change is a new revision, not an edit.
- **P-2.** Promotion decisions must be evidence-based, considering: document and chunk count, vector
  count, query QPS, p95/p99 latency, filter selectivity, index build duration, memory and storage
  use, noisy-neighbour impact, backup/restore window, residency and compliance requirements, and the
  operational failure domain.
- **P-3.** Promotion is never triggered by role count, group count, membership count, or ordinary
  organizational depth.
- **P-4.** A promotion request that cites only an informal "sensitive data" label is insufficient.
  Classification controls authorization, while an explicit residency, encryption, key-ownership,
  contractual, or compliance policy may require a higher physical tier as defense in depth.
- **P-5.** Exact thresholds remain open pending benchmark and production measurement.

## Provider-neutral adapter expectations

A future `VectorStorePort` (conceptual; no typed contract here) must let any backend be used without
changing Orchestrator or Core contracts. A provider implementation must support or safely emulate:
trusted metadata filtering; organization and scope predicates; status and effective-time predicates;
snapshot selection; bounded candidate retrieval; stable result identifiers; source and version
lineage; digest and version metadata; deterministic test fixtures; timeout and cancellation; error
classification; health reporting.

Optional capabilities, which must never become mandatory Core concepts: hybrid lexical/vector
search, native tenant partitioning, dedicated shards, collection aliases, server-side reranking,
filter-aware ANN tuning.

- **A-1.** "Safely emulate" means an adapter that cannot push a required predicate down must
  guarantee the same result set with the same fail-closed behaviour, and must report the emulation
  so its cost is visible. It must never satisfy a predicate by returning unfiltered candidates for
  later trimming.
- **A-2.** Lexical and vector retrieval may be served by one backend or by separate adapters without
  changing Orchestrator contracts.
- **A-3.** No provider SDK object, credential, connection handle, or vendor query syntax may cross
  into Core, consistent with the existing provider-neutral port convention.
- **A-4.** Missing mandatory capability is a configuration error at startup, not a runtime
  degradation.

## Security invariants

- **SI-1.** Default deny.
- **SI-2.** No implicit hierarchy access (parent, child, or sibling).
- **SI-3.** No unfiltered fallback under any error, timeout, or degraded mode.
- **SI-4.** No post-retrieval-only authorization.
- **SI-5.** No client or model authority over filters, scopes, snapshots, or classification.
- **SI-6.** No stale or revoked retrieval.
- **SI-7.** No collection per role or per user as a product requirement.
- **SI-8.** No physical tier grants permission.
- **SI-9.** No cross-organization private access.
- **SI-10.** No secret or provider object in Core.

And explicitly: physical isolation is defense-in-depth and operational topology; authorization
remains a logical policy decision.

## Failure behavior

| Failure | Architectural behavior |
| --- | --- |
| Authorization unavailable | Fail closed. Safe authorization error; no retrieval attempt. Retry only inside the caller's budget with no relaxation. |
| Policy revision unavailable | Fail closed for affected scopes. No ad hoc fallback to another policy revision; any LKG behavior must come from the approved, integrity-verified RuntimeSnapshot policy defined by ADR-CP-006. |
| Authorized scope set empty | Zero results, non-error. Never interpreted as "no filter". |
| Index snapshot unavailable | Abstain with an explicit reason. No unversioned or inactive snapshot substituted. |
| Snapshot stale beyond policy | Fail closed or abstain per approved runtime policy; never silently serve stale state. |
| Metadata missing on a unit | Unit ineligible and excluded. Reported as an ingestion defect. |
| Digest mismatch | Unit ineligible; produces no evidence. Integrity incident recorded. |
| Filter rejected by backend | Fail closed. Never retried with a weaker filter. |
| Backend timeout | Bounded retry then abstain. Partial results allowed only if fully filtered and marked incomplete. |
| Backend partial failure | Abstain or return an explicitly incomplete, fully filtered result set; never widen scope to compensate. |
| Revocation invalidation delayed | Runtime state check still excludes the source. Delay is a reported fault, never a permission. |
| Public policy invalid or expired | Deny the public path. No fallback to broader public exposure; missing policy is never public. |

## Alternatives considered

Both remaining plausible options were considered seriously:

- **Fully logical isolation with no promotion path.** Simplest and safest for authorization, but it
  offers no answer to noisy neighbours, residency, or extreme scale, and would force an emergency
  architecture change under production pressure. Rejected as the sole model; retained as the Tier 1
  default.
- **Physical isolation per organization from day one.** Strong operational isolation and an easy
  compliance story, but it multiplies build, backup, and migration cost per organization, penalizes
  small tenants, and tempts teams to treat topology as permission. Rejected as the default;
  retained as Tier 3/Tier 4 for justified cases.

The adopted decision is the combination: logical isolation as the contract, physical isolation as an
evidence-driven operational tier.

## Alternatives rejected

| Alternative | Disposition |
| --- | --- |
| Collection per user | Rejected. Unbounded object count; breaks shared and public content; topology becomes an ACL. |
| Collection per role | Rejected. Roles are authorization inputs, not storage boundaries; a principal with several roles would fan out. |
| Collection per group | Rejected. Same defect as per-role, plus group churn would force reindexing. |
| Collection per organizational node | Rejected as a requirement. Node counts and depth are unbounded and subtree breadth would multiply queries. Permitted only as a justified Tier 3 promotion. |
| Single global index with no mandatory filter | Rejected. Directly violates default deny and SI-3. |
| Post-retrieval authorization only | Rejected as a primary control. Leaks through counts, latency, scoring, and any bypassed code path. Allowed only as defense in depth. |
| Client-built filters | Rejected. Client input cannot be an authorization source. |
| LLM-built filters | Rejected. Model output is untrusted and non-deterministic. |
| Display-path-derived authorization | Rejected. Display labels are mutable, localizable, and forgeable. |
| Always dedicated deployment | Rejected as default. Cost and operational burden without a security gain over logical isolation. |
| Always shared deployment | Rejected as an absolute. Cannot satisfy residency, key ownership, or legal isolation. |
| Provider-specific contracts in Core | Rejected. Destroys portability and blocks the benchmark decision. |
| Embedding ACL text into vectors | Rejected. Authorization becomes unrevocable, approximate, and prompt-visible; a similarity score is not a decision. |
| Waiting for full reindex before revocation | Rejected. Violates the CP-000B immediate-exclusion rule. |
| Silently falling back to public results | Rejected. Confuses denial with publication and misleads the user and the model. |
| Silently broadening to parent or sibling nodes | Rejected. Violates SI-2 and CP-000A default deny. |
| Deriving scope from unreconciled token claims | Rejected. Claims are inputs requiring reconciliation against control-plane state. |

## Consequences

- Authorization correctness now depends on trusted ingestion metadata, so ingestion becomes a
  security-critical component and must be tested as one.
- The benchmark gains hard security gates that can disqualify an otherwise attractive backend on
  filter semantics alone.
- Filter-selectivity behaviour becomes a first-class performance risk, because isolation is a
  predicate rather than a physical boundary; it must be measured, not assumed.
- Later packages inherit fixed boundaries: no vendor type in Core, no client or model filter
  authority, no unfiltered fallback. Some convenient adapter shortcuts are now unavailable.
- Multi-node breadth requires an explicit versioned scope artifact, so CP-000A policy authoring must
  produce subtree scopes rather than relying on runtime traversal.
- Snapshot immutability means re-embedding costs a full build; incremental-update behaviour becomes
  an explicit benchmark dimension.
- Promotion adds an audited configuration surface (`IndexIsolationProfile`) that must exist before
  any tenant is promoted.

## Non-goals

Not designed here: BM25 query construction, dense query construction, fusion algorithm, RRF
constant, reranking algorithm, parent expansion, context selection, chunk sizes, embedding model,
vector backend selection, database schema, RLS policy, index alias implementation, index worker,
crawler, Official Search implementation, General Web Search, chat attachments, application code,
Python contracts, vector adapters, APIs, migrations, Admin UI, deployment files, and provider SDK
integrations. Ranking fairness across nodes is deferred to CP-007.

## Open decisions

| Open decision | Why it remains open | Deciding package | Evidence required |
| --- | --- | --- | --- |
| Final vector/search backend | Filter semantics, Persian retrieval quality, and operational cost are not knowable from documentation | CP-012 with CP-013 | Full benchmark across pgvector, Qdrant, OpenSearch with all hard gates passed |
| Exact physical topology | Depends on backend primitives and measured tenant distribution | CP-012 | Production corpus and QPS distribution per organization |
| Exact promotion/demotion thresholds | No production measurements exist | PERF-001 with CP-012 | Latency, selectivity, and noisy-neighbour curves per tier |
| Exact index-routing implementation | Requires the chosen backend's partitioning model | CP-012 | Backend routing primitives and failover behaviour |
| Exact `IndexSnapshot` typed contract, including the aggregate-manifest representation | Depends on the ingestion pipeline's real build steps; S-7A fixes the semantics, not the shape | CP-001 with CP-006 | Parser, chunker, and embedding versioning shapes from CP-006 |
| Complete indexed-unit metadata contract beyond the Mandatory Isolation Metadata Subset | The subset is fixed here; retrieval-quality and provenance metadata are not designed | CP-006 | Chunking, parsing, and ranking feature requirements |
| Exact `VectorStorePort` shape | The minimal contract must precede production adapters but remain versionable | AI-003 with CP-012 | Provider PoCs/conformance fakes followed by production-adapter validation |
| Whether lexical and vector share one backend | Depends on hybrid quality versus operational cost | CP-012 with CP-013 | Comparative hybrid quality and operational burden |
| Filter-aware ANN tuning | Backend-specific and quality-sensitive | AI-003 with PERF-001 | Recall-versus-latency curves under realistic filters |
| RLS as defense in depth | Only meaningful if a relational backend is chosen | CP-012 | Chosen backend plus measured RLS overhead |
| Index cache design | Depends on revocation SLO and query mix | CP-006 with PERF-001 | Invalidation latency and hit-rate measurements |
| Index synchronization protocol | Depends on backend and snapshot lifecycle | CP-006 | Build, activation, and invalidation timing requirements |
| Revocation propagation SLO | Compliance and operational commitment, not a technical detail | CP-006 with the security owner | Regulatory requirement plus measured propagation time |
| Maximum authorized scope count | Bound must come from real membership distribution and filter cost | CP-007 with PERF-001 | Scope-count distribution and filter-size cost curve |
| Maximum query fan-out | Depends on tier layout and latency budget | CP-007 | Latency budget and measured fan-out cost |
| Cross-organization comparison workflow | A product and legal question, not an index question | CP-007 with the product owner | Approved use case with an authorization model |
| Ranking fairness across nodes/scopes | Requires relevance evaluation data | CP-007 with CP-013 | Labelled multi-node relevance sets |
| Benchmark corpus and hardware | Must represent real Persian and mixed-language content | CP-013 | Approved corpus snapshot and a fixed hardware class |
| Production corpus size and QPS | Not yet observed | PERF-001 | Production telemetry |
| Residency/compliance profile | Depends on customer commitments | CP-012 with the compliance owner | Signed residency and key-ownership requirements |
