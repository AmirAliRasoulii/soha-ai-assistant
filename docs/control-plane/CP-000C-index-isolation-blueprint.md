# CP-000C Index Isolation Blueprint

Status: Accepted architecture baseline (originated as CP-000C; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Scope: operational companion to ADR-CP-003 (data/index isolation and multi-node retrieval). Tables
only; no provider is selected, no threshold is fixed, no benchmark result is asserted.

Companions:

- `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`
- `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`
- `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`
- `docs/control-plane/CP-000A-authorization-matrix.md`
- `docs/control-plane/CP-000B-source-lifecycle-matrix.md`
- `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
- `docs/control-plane/CP-000R-architecture-consistency-repair.md`

## Legend

| Symbol | Meaning |
| --- | --- |
| `TRUSTED` | Produced by identity or control-plane processes; usable as an authorization input |
| `UNTRUSTED` | Request, uploader, or model supplied; never usable in a filter |
| `FILTER` | Enforced in the mandatory pre-filter before any candidate exists |
| `GATE` | Hard pass/fail condition; failure excludes the unit |
| `FAIL-CLOSED` | Failure yields zero results or a safe authorization error |
| `ABSTAIN` | Runtime declines to answer with an explicit reason rather than guessing |
| `AUDIT` | Requires a recorded reason and actor |
| `OPEN` | Deliberately undecided in this package |

## 18.1 Mandatory Isolation Metadata Subset matrix

The fourteen fields below are the **Mandatory Isolation Metadata Subset**, mirroring ADR-CP-003. They
are the minimum trusted metadata required to construct and enforce the mandatory pre-filter. They are
**not** the complete chunk or index metadata contract: retrieval-quality metadata, parser and chunker
provenance, positional data, language metadata, and ranking features are outside this subset and are
owned by CP-006. CP-006 may add fields; it may never remove a field of this subset or make one
optional. A unit missing any member of this subset is ineligible, never partially filtered.

| Field | Trusted producer | Purpose | Authorization-relevant | Mutable | Failure behavior |
| --- | --- | --- | --- | --- | --- |
| `organization_ref` | Control plane, from source registry | Outermost private boundary | Yes, `FILTER` `GATE` | No, for the life of the unit | Missing or mismatched: unit ineligible, `FAIL-CLOSED`, ingestion defect raised |
| `owning_node_ref` | Control plane, from ADR-CP-007 administrative ownership | Administrative lineage and management routing; not a read grant | No | Only via audited ownership change | Missing/stale: management-lineage defect; read authorization is unchanged and remains governed by policy/scope/classification |
| `hierarchy_path_ref` | Control plane, trusted hierarchy service | Supports policy-granted subtree breadth and lineage | Yes, only when a versioned subtree scope grants it | On node move, re-derived under `AUDIT` | Missing or stale: unit ineligible for subtree-derived retrieval; no runtime path expansion or implicit breadth |
| `visibility_policy_ref` | Control plane, active policy revision (CP-000A) | Who may read, including `anonymous-public` | Yes, `FILTER` `GATE` | Only by an audited versioned rebinding | Missing, expired, or invalid: deny; never interpreted as public |
| `security_scope_ref` | Control plane, derived from policy plus membership model | Matched against the authorized allow-set | Yes, `FILTER` `GATE` | Re-derived when policy binding changes | Missing: ineligible; unrecognized: no match, so excluded |
| `classification` | Control plane, from the source revision | Checked against actor allowances and ceilings | Yes, `FILTER` `GATE` | Only via audited classification change (CP-000B) | Missing: treated as most restrictive, excluded |
| `source_ref` | Source registry (CP-000B) | Stable identity and lineage | Indirectly, via source status `GATE` | No | Missing: ineligible, no citation possible |
| `source_revision_ref` | Source registry (CP-000B) | Exact immutable version the unit derives from | Yes, `GATE` on current-active-revision | No, immutable | Missing or not current active: excluded |
| `index_snapshot_ref` | Ingestion/index build | Binds the unit to an immutable build | Yes, `GATE` on active snapshot | No, immutable | Not active or unavailable: `ABSTAIN` per runtime policy |
| `embedding_artifact_ref` | Ingestion/index build | Ensures query and unit vectors are comparable | No, but correctness `GATE` | No, immutable | Mismatch with the query artifact: unit not comparable, excluded |
| `content_digest` | Ingestion, over trusted content | Integrity binding to approved content | Yes, `GATE` | No, immutable | Mismatch: ineligible, produces no evidence, integrity incident recorded |
| `valid_from` | Control plane, derived from trusted `SourceRevision.effective_from`; trusted activation time when `effective_from` is absent | Start of eligibility | Yes, `FILTER` | Only by an audited revision change | Missing, malformed, or untrusted: treated as not yet valid, excluded. Never parsed from document text, a filename, a client value, or model output |
| `valid_until` | Control plane, from trusted `SourceRevision` temporal metadata | End of eligibility; **nullable** | Yes, `FILTER` | Only by an audited revision change | Null means open-ended and stays eligible until an explicit lifecycle or security action; passed or unparseable: excluded. Missing temporal metadata never broadens access |
| `status` | Control plane, derived from source and revision state | Trusted eligibility state | Yes, `FILTER` `GATE` | Yes, on lifecycle actions | Not active, unknown, or unresolvable: excluded `FAIL-CLOSED` |

All uploader-supplied equivalents of these fields are `UNTRUSTED` until validated and persisted as
approved artifacts. `department_name`, `role_name`, a `visibility = public` string, client-supplied
`allowed_group_ids`, and client-supplied organization names are `UNTRUSTED` in all cases and are never
promoted into filter metadata.

## 18.2 Isolation tier matrix

| Tier | Logical model | Physical model | Candidate trigger | Security effect | Operational effect | Open implementation concerns |
| --- | --- | --- | --- | --- | --- | --- |
| Tier 1 shared logical partition | Trusted metadata plus mandatory pre-filter; many scopes coexist | One shared index or collection | Default for all organizations and nodes | None beyond the logical model; filter is the control | Shared resources, one build and backup path, lowest cost | Filter selectivity at scale; noisy-neighbour latency; per-scope observability |
| Tier 2 dedicated shard or partition | Identical logical model | Backend-native shard or partition per promoted scope | Corpus size, query volume, selectivity degradation, latency isolation, resource contention, maintenance windows | None; `no tier grants broader read access` | Latency isolation, independent maintenance, more routing state | Backend support varies; rebalancing cost; routing failover |
| Tier 3 dedicated collection or index | Identical logical model | Separate collection or index | Very large corpus, strict performance isolation, separate lifecycle, special embedding or index configuration, migration constraints | None | Independent build, snapshot, and rollback; higher operational surface | Cross-collection query bounding; snapshot activation across collections; config drift |
| Tier 4 dedicated deployment | Identical logical model | Separate deployment or infrastructure | Legal isolation, residency, customer-managed infrastructure, encryption or key ownership, compliance boundary, extreme scale | None; compliance and blast-radius benefit only | Separate lifecycle, upgrades, monitoring, and cost centre | Version skew across deployments; key management; evaluation parity |

Tier rules: promotion changes no Core contract and no authorization semantics; stable references and
citation lineage survive relocation; physical location resolves from trusted configuration only;
demotion and migration require `AUDIT`; deployment policy may prohibit lower tiers. Thresholds are
`OPEN`.

## 18.3 Query-path invariant matrix

| Case | Scope resolution | Filter requirement | Expected outcome |
| --- | --- | --- | --- |
| Authenticated single-node | One authorized `security_scope_ref` from the decision | `FILTER` on organization, scope, classification, status, effective time, snapshot | Only that node's authorized units; no parent, child, or sibling content |
| Authenticated multi-node | Bounded logical allow-set of authorized scopes | **One logical authorization/retrieval envelope plus one or a bounded number of physical backend queries**, each carrying the equivalent mandatory constraints derived from that single envelope. This blueprint does not claim that every multi-node request performs exactly one physical query | Union of authorized scopes only; per-result lineage preserved; no per-membership or unbounded fan-out |
| Explicit subtree | Versioned subtree scope artifact grants breadth | `FILTER` includes the granted subtree scope, not a parsed path | Subtree units within the grant; unrelated branches denied |
| Anonymous Guest | No membership; active `anonymous-public` scopes only | Mandatory public `FILTER` plus classification allowance | Only explicitly published units; never a global scan; no management or raw access |
| Authenticated access to `anonymous-public` | Public scopes plus the principal's own scopes | Single combined `FILTER`; public hits remain separately identifiable | Both sets returned; public origin visible in lineage; no membership implied |
| Empty authorized scope | Allow-set is empty | Filter is not constructed against "any" | Zero results, non-error; never interpreted as unconstrained |
| Revoked source | Source status not `ACTIVE` | `GATE` before and independent of index contents | Excluded immediately regardless of physical presence; `AUDIT` trail retained |
| Disabled source | Source status `DISABLED` | Same `GATE` | Excluded from new retrieval; re-enablement is an explicit authorized action |
| Stale index snapshot | Snapshot beyond freshness policy | Snapshot `GATE` | `FAIL-CLOSED` or `ABSTAIN` per approved runtime policy; never serve unverified state |
| Digest mismatch | Unit digest differs from trusted metadata | Integrity `GATE` | Unit ineligible; produces no evidence; integrity incident recorded |
| Cross-organization private access | Requested organization is not authorized | Organization `GATE` | Deny; no partial results; no mixing with authorized organizational results |
| Filter construction failure | Identity, policy, or scope resolution incomplete | Filter cannot be completed | Zero results or safe authorization error; never retried with a weaker filter |

## 18.4 Provider benchmark matrix

Candidates to evaluate: PostgreSQL with pgvector, Qdrant, OpenSearch. All candidates must run against
the same corpus snapshot, metadata fields, authorization fixtures, queries, expected-relevant sets,
embedding artifact, candidate limits, and hardware class where practical. No provider may be approved
on documentation claims. No result is asserted in this document.

| Criterion | Test method | Required fixture | Metric | Hard gate or comparative | Deciding package |
| --- | --- | --- | --- | --- | --- |
| Restricted-result leakage | Query as principals with known-limited scopes across the full corpus | Authorization fixture set with expected-visible sets | Leaked units | Hard gate, must be 0 | CP-013 |
| Revoked-result retrieval | Revoke sources, then query within the approved propagation budget | Revocation fixtures plus invalidation harness | Revoked hits | Hard gate, must be 0 after the budget | CP-013 |
| Cross-organization leakage | Multi-organization corpus, single-organization principals | At least three organizations with overlapping content | Foreign-organization hits | Hard gate, must be 0 | CP-013 |
| Cross-node leakage | Sibling, parent, and child nodes without grants | Hierarchy fixture with and without subtree grants | Unauthorized node hits | Hard gate, must be 0 unless explicitly authorized | CP-013 |
| Anonymous-public behavior | Guest queries plus authenticated queries over public units | Active and expired public policy fixtures | Correct visible set; expired policy denies | Hard gate | CP-013 |
| Filter semantics correctness | Conjunctive, disjunctive, effective-time, and status predicates, including empty allow-set | Predicate conformance suite | Exact expected set match | Hard gate | CP-012 |
| Snapshot and version selection | Query pinned to an active snapshot while another builds and activates | Two snapshots with overlapping corpus | No cross-snapshot bleed; atomic switch observed | Hard gate | CP-012 |
| No unfiltered fallback under fault | Inject backend errors, timeouts, and rejected filters | Fault-injection harness | Unfiltered result count | Hard gate, must be 0 | CP-013 |
| Recall@k | Fixed queries against labelled relevant sets | Labelled relevance judgements | Recall@k | Comparative | CP-013 |
| MRR and nDCG | Same query set | Graded relevance judgements | MRR, nDCG | Comparative | CP-013 |
| Filter-aware recall | Recall measured under realistic authorization filters | Scope-varied query set | Recall delta versus unfiltered | Comparative with a minimum floor | CP-013 |
| Exact identifier/code retrieval | Queries for codes, article numbers, and identifiers | Corpus with identifier-bearing documents | Exact-hit rate at rank 1 | Comparative with a minimum floor | CP-013 |
| Persian semantic retrieval | Persian query set including morphology and mixed script | Persian and mixed-language corpus | Recall@k, nDCG | Comparative with a minimum floor | CP-013 |
| Similar-policy disambiguation | Near-duplicate policy documents across nodes | Near-duplicate fixture set | Correct-document rate | Comparative | CP-013 |
| Query latency | Fixed query mix at fixed concurrency | Same corpus and hardware class | p50, p95, p99 | Comparative with a latency budget gate | PERF-001 |
| Filter selectivity impact | Sweep authorized scope counts and selectivity | Scope-count sweep fixture | Latency and recall versus selectivity | Comparative | PERF-001 |
| Concurrent query behavior | Ramped concurrency to saturation | Load profile | Throughput, error rate, tail latency | Comparative | PERF-001 |
| Index build time | Full build of the same corpus | Fixed corpus and embedding artifact | Wall-clock build duration | Comparative | PERF-001 |
| Incremental update behavior | Add, update, and revoke units on an existing index | Incremental fixture | Time to visibility, correctness | Comparative with a correctness gate | CP-006 |
| Memory, storage, CPU | Measured at steady state and during build | Same corpus and hardware class | Peak and steady resource use | Comparative | PERF-001 |
| Backup and restore | Full backup then restore, verify correctness | Backup harness | Window duration, post-restore correctness | Comparative with a correctness gate | CP-012 |
| Migration | Move a scope between tiers | Tier-promotion fixture | Downtime, correctness, lineage preservation | Comparative with a lineage gate | CP-012 |
| Snapshot activation and rollback | Activate then roll back to a prior snapshot | Two-snapshot fixture | Atomicity, time to switch, correctness | Hard gate on atomicity | CP-006 |
| Reindex and re-embedding | Rebuild with a new embedding artifact | Second embedding artifact | Duration, quality delta, cutover behavior | Comparative | CP-006 |
| Tenant promotion | Promote a scope through the supported tiers | Isolation profile fixtures | Effort, downtime, semantics unchanged | Hard gate on unchanged semantics | CP-012 |
| Observability | Inspect per-scope query and error telemetry | Telemetry fixture | Available signals, cardinality cost | Comparative | CP-012 |
| Failure recovery | Kill and restart nodes, partition the network | Chaos harness | Recovery time, data loss, fail-closed behavior | Hard gate on fail-closed | CP-012 |
| Operational complexity | Structured operator review of the runbook | Documented runbook | Reviewer scoring with rationale | Comparative | CP-012 |
| Infrastructure footprint and cost | Size the production profile per candidate | Production sizing assumptions | Cost estimate | Comparative | CP-012 |
| Licensing and lock-in | Review licences and portability of the adapter boundary | Adapter prototype per candidate | Adapter complexity, exit cost | Comparative | CP-012 |
| Residency fit | Check deployment options against residency requirements | Residency requirement list | Requirements satisfied | Hard gate where residency is committed | CP-012 |

## 18.5 Source Registry dependency matrix

Index eligibility is not self-contained. It consumes trusted Source Registry state defined in
`docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`.

| Dependency | Consumed as | Trust rule | Effect on retrieval |
| --- | --- | --- | --- |
| Source authority (`authority_class_ref`, `issuer_ref`, `authority_assignment_policy_ref`) | Deterministic conflict precedence, ranking input, answer caveats | `TRUSTED` only after the Central Source Approver confirms or assigns it from an approved versioned catalog; LLM, client, filename, and document-text labels are `UNTRUSTED` | Authority is **not** an authorization grant. It never widens visibility and never bypasses classification |
| Source temporal metadata (`effective_from`, `valid_until`, `published_at`, `observed_at`) | Produces `valid_from` / `valid_until` in 18.1 | `TRUSTED` control-plane output only; upload time is never business publication time | `FILTER` on effective time; missing or untrusted values never broaden access |
| Source lifecycle (`ACTIVE`, `DISABLED`, `REVOKED`, `ARCHIVED`, revision states) | Produces `status` in 18.1 | `TRUSTED` control-plane state; authoritative over index presence | `GATE` `FAIL-CLOSED`; revocation is immediate and independent of physical index contents |
| Source relationships (`SUPERSEDES`, `SUPPLEMENTS`) | Current-versus-historical revision selection and supplemental coexistence | `TRUSTED` control-plane facts created by an authorized actor; an LLM must never infer them | A superseded revision is excluded from current retrieval but stays resolvable for historical citation; two supplemental sources may both remain active and both eligible |

## 18.6 Aggregate IndexSnapshot manifest

| Aspect | Rule |
| --- | --- |
| Meaning of `RuntimeSnapshotContent.index_snapshot` | A **logical aggregate `IndexSnapshot` manifest**, not a pointer to a single physical build |
| Contents | References one or more eligible physical snapshots plus the routing metadata needed to select among them |
| Why | Retrieval may legitimately consult several eligible physical snapshots, especially once scopes are promoted to Tier 2 to Tier 4, while the contract carries one named reference |
| Selection authority | Trusted runtime routing only. No client and no model may select an arbitrary physical snapshot from inside the manifest |
| Resolution path | The manifest is resolved through the configuration path in `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`; named refs must match the active `ConfigurationRelease` manifest |
| Failure behavior | An unverifiable or stale manifest is `FAIL-CLOSED` or `ABSTAIN` per approved runtime policy; never a fallback to an unverified snapshot |

## 18.7 Source-version benchmark fixture

The benchmark that gates backend selection must include a fixture exercising source-version and
relationship semantics together. This is a **correctness gate**, not a quality metric: a backend that
cannot express the required filters over this fixture is disqualified regardless of its recall or
latency results.

| Fixture element | Required behavior | Gate |
| --- | --- | --- |
| Current source revision | Active revision is retrievable for authorized principals | Hard gate |
| Historical superseded revision | Excluded from current retrieval; resolvable only through an explicit historical query; citations to it remain resolvable | Hard gate |
| Two active supplemental sources | Both coexist and both remain retrievable; neither supersedes the other | Hard gate |
| Null `valid_until` | Remains eligible as open-ended | Hard gate |
| Expired `valid_until` | Excluded | Hard gate |
| Revoked source | Excluded immediately, independent of physical presence | Hard gate |

No provider is selected by this fixture or anywhere in this document. PostgreSQL with pgvector,
Qdrant, and OpenSearch remain open candidates.

## 18.8 Failure-behavior table

| Failure | Architectural behavior | Retry | Result to caller |
| --- | --- | --- | --- |
| Authorization unavailable | `FAIL-CLOSED`; no retrieval attempted | Bounded, no relaxation | Safe authorization error |
| Policy revision unavailable | `FAIL-CLOSED`; no ad hoc fallback to another revision. Integrity-verified RuntimeSnapshot LKG behavior is governed by ADR-CP-006 | Bounded | Zero results or safe error, with reason |
| Authorized scope set empty | Valid outcome, not an error | No | Zero results |
| Index snapshot unavailable | `ABSTAIN`; no substitute snapshot | Bounded | Explicit abstention with reason |
| Snapshot stale beyond policy | `FAIL-CLOSED` or `ABSTAIN` per approved runtime policy | No | Abstention or safe error; never stale content |
| Metadata missing on a unit | Unit ineligible and excluded; ingestion defect raised | No | Results without that unit |
| Digest mismatch | Unit ineligible; no evidence; integrity incident `AUDIT` | No | Results without that unit |
| Filter rejected by backend | `FAIL-CLOSED`; never retried with a weaker filter | No | Safe error |
| Backend timeout | Bounded retry, then `ABSTAIN` | Bounded | Abstention, or an explicitly incomplete fully filtered set |
| Backend partial failure | `ABSTAIN` or return an explicitly incomplete, fully filtered set; never widen scope | Bounded | Marked-incomplete results or abstention |
| Revocation invalidation delayed | Trusted state check still excludes the source; delay is a reported fault | Invalidation retried out of band | Correct results; fault recorded |
| Public policy invalid or expired | Deny the public path; missing policy is never public | No | Zero public results |

## Explicit statements

- Isolation is logical; the mandatory pre-filter is the authorization control at every tier.
- Administrative ownership is lineage/management metadata and does not grant or revoke read access.
- No tier, shard, collection, or deployment grants read access.
- The product contract never requires a collection per user, role, group, ordinary node, or
  visibility policy.
- Clients and models have no authority over filters, scopes, snapshots, or classification.
- Post-retrieval checks are defense in depth only; their absence or failure never widens a filter.
- An empty authorized scope set yields zero results and is never treated as unconstrained.
- Revocation and disablement take effect immediately, independent of physical index contents.
- Physical purge is a separate ADR-CP-007 lifecycle and compliance action and is never on the exclusion
  path.
- Guest reads only through an active `anonymous-public` policy with a permitting classification, and
  never through an unfiltered scan.
- Authentication failure never downgrades a request into Guest mode.
- Cross-organization private access is denied; cross-organization comparison is a separate future
  query-policy concern.
- No provider is selected here, and no benchmark number in this repository may be cited until it has
  actually been produced by the plan above.
- The fourteen isolation fields are the Mandatory Isolation Metadata Subset, not the complete indexed
  unit metadata contract; the complete contract is owned by CP-006.
- Multi-node retrieval is one logical authorization/retrieval envelope plus one or a bounded number of
  physical backend queries. Physical query count is an operational property, never an authorization
  property.
- `valid_until` is nullable, and null means open-ended eligibility until an explicit lifecycle or
  security action. Null is never treated as expired.
- `valid_from` has exactly one trusted producer: the control plane, from trusted
  `SourceRevision.effective_from`, defaulting to trusted activation time.
- `RuntimeSnapshotContent.index_snapshot` is a logical aggregate manifest referencing one or more
  eligible physical snapshots and their routing metadata.
- Source authority may affect ranking, conflict precedence, and caveats. It never affects
  authorization.

## Open decisions

| Open decision | Why it remains open | Deciding package | Evidence required |
| --- | --- | --- | --- |
| Final vector/search backend | Filter semantics and Persian quality are unknowable from documentation | CP-012 with CP-013 | All hard gates passed by at least one candidate |
| Exact physical topology and routing | Depends on chosen backend primitives | CP-012 | Backend partitioning and failover behavior |
| Promotion and demotion thresholds | No production measurement exists | PERF-001 | Latency, selectivity, and noisy-neighbour curves |
| `IndexSnapshot` typed contract | Depends on the real ingestion build steps | CP-001 with CP-006 | Parser, chunker, embedding versioning shapes |
| `VectorStorePort` shape | Minimal contract must precede adapters but remain versionable | AI-003 with CP-012 | Provider PoCs/conformance fakes and production-adapter validation |
| One backend for lexical and vector | Hybrid quality versus operational cost unknown | CP-012 with CP-013 | Comparative hybrid quality and burden |
| Filter-aware ANN tuning | Backend-specific | AI-003 with PERF-001 | Recall-versus-latency curves under filters |
| RLS as defense in depth | Only meaningful for a relational backend | CP-012 | Chosen backend plus measured overhead |
| Index cache design and revocation SLO | Compliance commitment plus measurement | CP-006 with PERF-001 | Regulatory requirement and propagation timings |
| Index synchronization protocol | Depends on backend and snapshot lifecycle | CP-006 | Build, activation, invalidation timing needs |
| Maximum authorized scope count and query fan-out | Bounds must come from real distributions | CP-007 with PERF-001 | Scope-count distribution and filter cost curves |
| Cross-organization comparison workflow | Product and legal question | CP-007 | Approved use case with an authorization model |
| Ranking fairness across nodes and scopes | Requires relevance data | CP-007 with CP-013 | Labelled multi-node relevance sets |
| Benchmark corpus and hardware class | Must represent real Persian and mixed content | CP-013 | Approved corpus snapshot and fixed hardware |
| Production corpus size and QPS | Not yet observed | PERF-001 | Production telemetry |
| Residency and compliance profile | Depends on customer commitments | CP-012 | Signed residency and key-ownership requirements |
