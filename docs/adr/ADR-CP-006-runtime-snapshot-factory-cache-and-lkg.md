# ADR-CP-006: RuntimeSnapshotFactory, Cache, and Bounded Last-Known-Good

Status: Accepted architecture baseline (originated as CP-000D; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000D architecture package
Owner: Control Plane / Runtime Configuration Resolution Baseline
Scope: interpretation of `RuntimeSnapshot 1.0.0` fields, the conceptual `RuntimeSnapshotFactory`,
deterministic resolution, digest verification, canonical pull and invalidation, bounded snapshot
cache, and bounded Last-Known-Good. No Python method signature, cache implementation, message bus,
provider adapter, or numeric duration is decided here.

Companions:

- `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`
- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/control-plane/CP-000D-configuration-catalog.md`

## CP-000R cross-reference

This document was accepted as an architecture baseline by CP-000R at canonical commit `6477c1c`.
CP-000R changed no decision in this document. It repaired the surrounding conflicts that made this
document read inconsistently against its neighbours:

| Conflict repaired by CP-000R | Where it is now canonical |
| --- | --- |
| Architecture document status versus Git state (audit finding C-007) | Status lines of all seven CP ADRs and all four CP matrices/catalogs |
| Source role and approval conflict between CP-000A and CP-000B (audit finding C-001) | `docs/control-plane/CP-000B-source-lifecycle-matrix.md` is now the single canonical source-action matrix; CP-000A delegates to it |
| Visibility policy binding ambiguity (audit finding C-002) | Pinned exact immutable policy revision, in `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md` |
| Full repair ledger and remaining implementation gaps | `docs/control-plane/CP-000R-architecture-consistency-repair.md` |
| Document authority and precedence | `docs/architecture/architecture-authority-manifest.md` |

The v1 AI configuration administration model recorded here remains canonical: a **single System AI
Administrator** holding `ai_configuration.manage`, with **no mandatory second human approver**, a
**conditional** provider probe, `Save and Apply`, `ConfigurationRelease`, release-level rollback,
`BuildArtifact`-bound provenance, and bounded Last-Known-Good that a known revoke or disable defeats.
`APPROVED` does not imply approval by a second human. The superseded two-person v1 AI administration
model is **not** reintroduced by CP-000R.

## Existing contract and dependency boundary

Verified in Git at this HEAD, in `src/ai_assistant/contracts/runtime_snapshot.py` and
`schemas/runtime-snapshot/1.0.0.schema.json`:

- `RuntimeSnapshot` carries `schema_version` fixed at `1.0.0`, a version 4 `snapshot_id`,
  `captured_at`, `content`, and `integrity`.
- `RuntimeSnapshotContent` carries `application_version`, `source_revision`, `build_artifact`,
  `config_bundle`, `prompt_bundle`, `model_policy`, `model_artifacts`, `structured_output_backend`,
  `retrieval_profile`, `embedding_artifact`, `reranker_artifact`, `index_snapshot`,
  `semantic_catalog`, `rule_bundle`, `security_policy`, `telemetry_schema`, and `feature_flags`.
- `RuntimeArtifactRef` requires `artifact_id`, `revision`, and `digest`.
- `RuntimeSnapshotIntegrity` fixes `canonicalization="rfc8785"` and a `sha256:` digest, and its
  inline comment already states that the digest covers the RFC 8785 canonical JSON form of
  `snapshot.content.model_dump(mode="json")`, excluding `schema_version`, `snapshot_id`,
  `captured_at`, and `integrity`, and that computation and verification belong to a trusted factory.
- `model_artifacts` is bounded to between one and sixteen entries with unique identifiers;
  `feature_flags` is bounded to sixty-four entries with unique names.

Not typed contracts at this HEAD, therefore conceptual here: `RuntimeSnapshotFactory`,
`ConfigurationRelease`, `ActiveConfigurationReleasePointer`, the snapshot cache, and Last-Known-Good.
The Deferred Register records DEF-018 (RuntimeSnapshot factory, `PLANNED`), DEF-038 (configuration
cache, `OPEN`), and DEF-039 (missing or invalid artifacts, `OPEN`).

This ADR does not modify `RuntimeSnapshot 1.0.0` code or schema. It fixes how the existing fields are
to be read.

## Context

`ADR-CP-004` fixed the artifact taxonomy and `ADR-CP-005` fixed how a `ConfigurationRelease` becomes
active. Neither says how a running request obtains configuration. The existing contract validates the
shape of a snapshot but proves nothing about availability, integrity, or freshness of what it
references, and its field names were chosen before the control-plane vocabulary existed, so two of
them read ambiguously today.

The operational tension is between availability and safety. A runtime that fails every request when
the control plane is briefly unreachable is unusable. A runtime that serves stale configuration after
a security revocation is unsafe. Bounded Last-Known-Good exists to resolve that tension in exactly
one direction: availability may be preserved only while nothing known-bad is involved.

## Problem

- P-1: `config_bundle`, `security_policy`, `index_snapshot`, and `source_revision` are ambiguous
  against the newer control-plane vocabulary, and a wrong reading would silently misroute
  configuration or confuse source visibility with runtime security policy.
- P-2: Snapshot construction has no defined order, so two runtimes could build different snapshots
  from the same release and both look valid.
- P-3: Without digest verification at resolution time, a mutated or substituted artifact is
  indistinguishable from the reviewed one.
- P-4: Without a defined pull model, an activation event becomes a second source of truth and a lost
  event becomes a permanent divergence.
- P-5: An unbounded cache or an unbounded stale-tolerance window turns a revocation into an advisory.
- P-6: A request whose configuration changes mid-flight is not reproducible and its evidence cannot
  be explained.

## Decision

- D-1: `RuntimeSnapshotContent.config_bundle` is interpreted as the digest-pinned
  `ConfigurationRelease` manifest reference. A future contract version may rename it to
  `configuration_release`; CP-000D does not break 1.0.0.
- D-2: `RuntimeSnapshotContent.security_policy` means the global runtime `SecurityPolicy` of
  `ADR-CP-004`. It does not represent per-source `VisibilityPolicyDefinition` revisions, which remain
  resolved through authorization, source, and index metadata per `ADR-CP-002`, `ADR-CP-003`, and
  `ADR-CP-007`.
- D-3: `RuntimeSnapshotContent.index_snapshot` is a logical aggregate `IndexSnapshot` manifest. It may
  reference one or more physical index snapshots, routing metadata, embedding compatibility metadata,
  and activation state. This supports the bounded multi-scope and tiered physical retrieval of
  `ADR-CP-003` without changing the `RuntimeSnapshot` contract.
- D-4: `RuntimeSnapshotContent.source_revision` means the application or source-code revision, not a
  `KnowledgeSource` `SourceRevision`. The naming ambiguity is recorded and a possible rename is
  deferred to a future contract version.
- D-5: A conceptual `RuntimeSnapshotFactory` is the only component that constructs a
  `RuntimeSnapshot`. Its trusted inputs are the active `ConfigurationRelease` pointer, the immutable
  artifact registry, platform hard-bound policy, the schema and contract registry, revocation state,
  trusted current time, and a bounded validated cache.
- D-6: Forbidden factory inputs are frontend-composed configuration, a client-selected active
  revision, a mutable backend dictionary, LLM output, raw environment configuration injected into
  Core, a provider SDK object, and any secret value.
- D-7: Resolution follows the fixed eighteen-step algorithm below. No missing artifact is silently
  defaulted, and no artifact is pulled from outside the active release.
- D-8: A control-plane activation event is only an invalidation hint. It may carry `release_ref`,
  `release_revision`, and `release_digest`, and it must not carry the full mutable configuration as
  the source of truth. Runtime always pulls canonical state again. Missed events are handled by
  bounded polling or TTL.
- D-9: The snapshot cache is bounded by entries, by memory, and by TTL, is single-flight per release
  or digest, is cancellation-aware, and contains no secret value and no provider client. Only fully
  validated immutable snapshots may be returned from it.
- D-10: Last-Known-Good is permitted only for new requests and only when every listed condition
  holds. A known revoke or disable always defeats Last-Known-Good.
- D-11: An in-flight request remains pinned to its original `RuntimeSnapshot`. A configuration
  activation affects only later requests.
- D-12: Digest mismatch is never repaired and never defaulted. It is a fail-closed condition.
- D-13: Build provenance is bound deterministically. The active `ConfigurationRelease` must pin a
  qualified `BuildArtifact`, and the factory must resolve that exact pinned `BuildArtifact`, verify its
  revision and digest, derive or verify `application_version` and the application `source_revision`
  from its immutable metadata, reject any mismatch, and never read these values from mutable
  environment configuration or untrusted request input.

```text
RuntimeSnapshotFactory resolution (deterministic, fail-closed)

  TRUSTED INPUTS                              FORBIDDEN INPUTS
   active release pointer                      frontend-composed config
   immutable artifact registry                 client-selected active revision
   platform hard-bound policy                  mutable backend dict
   schema / contract registry                  LLM output
   revocation state                            raw environment config into Core
   trusted current time                        provider SDK object
   bounded validated cache                     secret value

   1 resolve canonical ActiveConfigurationReleasePointer
   2 resolve the immutable ConfigurationRelease
   3 verify release schema, revision, status, digest
   4 resolve every pinned artifact revision, incl. the pinned BuildArtifact
   5 verify every revision and content digest
   6 verify no referenced artifact is revoked or disabled
   7 apply platform hard-bound validation
   8 validate cross-artifact compatibility
   9 validate feature and security-policy composition
  10 verify RuntimeSnapshot named refs exactly match release refs
       incl. build_artifact == the release-pinned BuildArtifact, and
       application_version + source_revision derived / verified from
       that BuildArtifact's immutable metadata (never from env or
       request input); any mismatch is rejected
  11 resolve deterministic effective feature flags
  12 confirm no secret or provider object enters the snapshot
  13 build RuntimeSnapshotContent deterministically
  14 canonicalize via the existing RFC 8785 rule
  15 compute SHA-256
  16 create / verify RuntimeSnapshotIntegrity
  17 return an immutable RuntimeSnapshot
  18 cache only the fully validated immutable result

  ANY step fails -> no snapshot is returned for a new request
                 -> no default value is substituted
                 -> no artifact is fetched from outside the active release
                 -> no unrelated release is used as a fallback
                 -> in-flight requests keep their already-pinned snapshot
```

## Detailed semantics

### Determinism

The same active release plus the same registry state must produce the same content digest. Every
input that would break that property is excluded: wall-clock values do not enter `content`, ordering
of `model_artifacts` and `feature_flags` is deterministic, effective feature flags are resolved
from the release rather than from ambient state, and `application_version`, `source_revision`, and
`build_artifact` are derived from the release-pinned `BuildArtifact`'s immutable metadata rather than
from mutable environment configuration, deployment labels, or request input. Because build provenance
is pinned rather than ambient, the same release resolved on two different hosts, containers, or
environments produces the same content digest. `captured_at` and `snapshot_id` vary per snapshot and
are deliberately excluded from the digest by the existing contract, so two snapshots of the same
release compare equal on `integrity.digest` while remaining distinguishable records.

### Step 10, reference identity

Step 10 exists because a snapshot could otherwise be internally consistent yet reference an artifact
the release never pinned. Each named `RuntimeSnapshotContent` field must equal the corresponding
release-pinned ref, revision, and digest exactly. A near-match is a rejection.

Reference identity extends to build provenance. `build_artifact` must equal the exact `BuildArtifact`
ref, revision, and digest pinned by the active release, and `application_version` and the application
`source_revision` must equal the values derived from that same `BuildArtifact`'s immutable metadata. If
the pinned `BuildArtifact` metadata says one application version and the resolving process believes
another, that disagreement is a mismatch and is rejected; it is never resolved in favor of the running
process, because doing so would let a redeployment silently change what a snapshot claims to describe.

### Build provenance binding

`application_version`, `source_revision`, and `build_artifact` are required by the existing contract
but have no defined producer until now. Their producer is the release-pinned `BuildArtifact`, which
must be a qualified artifact. The factory resolves that exact pinned `BuildArtifact`, verifies its
revision and digest, derives or verifies `application_version` and the application `source_revision`
from its immutable metadata, and rejects any mismatch. These three values are never read from mutable
environment configuration, container labels, build-time environment variables observed at runtime, or
untrusted request input. `source_revision` here is the application revision per D-4, and the existing
contract already constrains it to a forty- or sixty-four-character lowercase hexadecimal value, which a
qualified `BuildArtifact`'s metadata must satisfy. A release that pins no qualified `BuildArtifact`
cannot produce a snapshot, and that is a fail-closed condition rather than a defaulted one.

### Canonical pull and invalidation

Activation emits a small event; the runtime discards or marks the cache entry stale; the runtime pulls
the canonical active release; the factory rebuilds or resolves a validated cache entry. Because the
event is a hint, a lost event degrades freshness bounded by polling or TTL, never correctness of
authorization, which per `ADR-CP-003` and `ADR-CP-005` is enforced independently of index or cache
presence.

### Cache keys

Valid cache keys are the `ConfigurationRelease` ref, the release revision, the release digest, and the
`RuntimeSnapshot` content digest. Forbidden keys are display labels, role names, a client-provided
version, and mutable dictionary identity. A forbidden key would let a caller select which
configuration it is served, which is a client authority this architecture denies everywhere else.

### Bounded Last-Known-Good

Last-Known-Good is permitted for new requests only when the snapshot was previously fully validated,
all digests are known, snapshot age is inside a policy-owned maximum, Last-Known-Good is enabled by
`ReliabilityPolicy`, no known revoke or disable invalidates it, and the cache is intact and
compatibility remains valid. It is forbidden when the snapshot is missing, a digest mismatch exists,
the release is revoked, an artifact is revoked, the `SecurityPolicy` is revoked, an emergency disable
is known, the maximum stale age is exceeded, or the cache is corrupted.

The governing rule is that a known revoke or disable always defeats Last-Known-Good. Last-Known-Good
is an availability concession about *unknown* control-plane state, never a tolerance for *known-bad*
state. No final numeric TTL is chosen here; the exact duration is an open operational decision owned
by later reliability, security, and performance qualification.

### Request pinning

A request binds its snapshot once and keeps it for its lifetime, so its evidence, plan, and answer are
all explainable by one immutable configuration. Activation therefore never produces a request that was
half-old and half-new, and replay of a past run needs only the recorded snapshot digest.

```text
Canonical pull, cache, and LKG failure behavior

  Control Plane                          AI Runtime (stateless)
    activate release R(n)
       |
       | invalidation hint: release_ref, release_revision, release_digest
       |   (never the full configuration)
       v
    -------------------------->  mark cache entry stale
                                        |
                                        v
                                 pull canonical active release  ----+
                                        |                           |
                            success     |            unavailable    |
                                        v                           v
                             factory resolves (18 steps)     evaluate LKG
                                        |                           |
                                        v                  +--------+--------+
                              cache validated snapshot      |                 |
                                        |             ALL conditions      ANY forbidden
                                        v             hold:              condition:
                              serve new requests      serve bounded LKG   FAIL CLOSED
                                                      + record degraded   no snapshot,
                                                        mode              safe error

  LKG ALLOWED only if: previously fully validated, all digests known,
    age inside policy maximum, enabled by ReliabilityPolicy, no known
    revoke or disable, cache intact, compatibility still valid.

  LKG FORBIDDEN if: snapshot missing, digest mismatch, release revoked,
    artifact revoked, SecurityPolicy revoked, emergency disable known,
    maximum stale age exceeded, cache corrupted.

  RULE: known revoke or disable always defeats LKG.
  RULE: in-flight requests keep their original pinned snapshot.
  NEVER: default value, unrelated release, partial snapshot, secret in cache.
```

## Ownership

The factory is trusted runtime infrastructure owned by `CP-004`. The active pointer and revocation
state are owned by the Control Plane per `ADR-CP-005`. Platform hard bounds and the canonicalization
and digest algorithms are owned by Platform and Governance and are not configurable. `ReliabilityPolicy`
owns whether Last-Known-Good is enabled and its maximum stale age, but cannot enable it past a
platform ceiling. Cache implementation and the invalidation transport are owned by `CP-012`. Core owns
none of the resolution mechanics; it receives an immutable snapshot.

## Security invariants

- SI-1: The same release plus the same registry state yields the same content digest.
- SI-2: No partially resolved snapshot is ever returned.
- SI-3: No snapshot mixes artifact revisions from different releases.
- SI-4: No stale revoked artifact is resolvable.
- SI-5: No client-defined active refs are honored; snapshot selection is trusted runtime state.
- SI-6: No secret value appears in a snapshot or in the cache.
- SI-7: No provider object appears in a snapshot or in the cache.
- SI-8: Configuration is immutable after request start; no mutable config is read mid-request.
- SI-9: A digest mismatch never produces a default; it fails closed.
- SI-10: No fallback to an unrelated release occurs under any failure.
- SI-11: A known revoke or disable defeats cache and Last-Known-Good.
- SI-12: Snapshot resolution grants no read authority; authorization remains the independent decision
  of `ADR-CP-002` and `ADR-CP-003`.
- SI-13: Build provenance is never ambient. `application_version`, `source_revision`, and
  `build_artifact` come only from the release-pinned qualified `BuildArtifact`, and a mismatch is
  rejected rather than reconciled.

## Failure behavior

| Failure | Architectural behavior |
| --- | --- |
| Active pointer unreadable | Evaluate bounded Last-Known-Good; otherwise fail closed with a safe error |
| Release missing from the registry | Fail closed; never substitute a nearby release |
| Release digest mismatch | Fail closed; treat the release as untrusted; audit |
| Pinned artifact missing | Fail closed; never default the artifact |
| Artifact digest mismatch | Fail closed; Last-Known-Good is forbidden |
| Referenced artifact revoked or disabled | Fail closed for new requests; in-flight requests keep their pinned snapshot |
| Hard-bound validation fails at resolution | Fail closed; a release that violates a ceiling cannot serve traffic even if it once activated |
| Cross-artifact incompatibility detected at resolution | Fail closed; abstain rather than guess a compatible pairing |
| Step 10 reference mismatch | Fail closed; the snapshot is rejected as unrelated to the release |
| Release pins no qualified `BuildArtifact` | Fail closed; no snapshot is produced; never default `application_version` or `source_revision` |
| Pinned `BuildArtifact` digest or revision mismatch | Fail closed; audit; never accept the running process's own version claim instead |
| `application_version` or `source_revision` disagrees with pinned `BuildArtifact` metadata | Fail closed; the disagreement is a mismatch, not a reconciliation |
| Canonicalization or digest computation failure | Fail closed; no snapshot is returned |
| Cache corrupted | Discard the entry, attempt a canonical pull, forbid Last-Known-Good |
| Cache miss under control-plane outage | Bounded Last-Known-Good if all conditions hold; otherwise fail closed |
| Maximum stale age exceeded | Last-Known-Good forbidden; fail closed |
| Invalidation event lost | Bounded polling or TTL converges; stale state is never authorized |
| Emergency disable known | Refuse to serve the disabled release; Last-Known-Good forbidden; never implicitly re-enable |
| Concurrent resolution for the same release | Single-flight; one build, shared validated result |
| Request cancelled during resolution | Cancellation-aware abort; no partial entry is cached |

The distinction between fail-closed and abstain in this ADR is deliberate: a resolution failure is
fail-closed at the configuration boundary, meaning no snapshot exists and therefore no run starts,
whereas abstain is the runtime answer behavior defined by `ADR-CP-003` for cases where a run exists but
cannot be safely grounded.

## Alternatives considered

Pushing full configuration in the activation event was weighed because it removes a pull and makes
activation appear instantaneous. It was rejected against P-4: the event would become a second source of
truth, and any divergence between event content and registry content would be unresolvable. Unbounded
Last-Known-Good was also weighed, since it maximizes availability during a control-plane outage. It was
rejected against P-5, but the underlying availability concern was accepted, which is why bounded
Last-Known-Good exists at all rather than being removed. A stricter variant that forbids
Last-Known-Good entirely remains available to a deployment through `ReliabilityPolicy`.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Runtime reads database configuration directly | Removes the trusted boundary and makes runs unreproducible |
| Activation event carries full configuration as truth | Creates a second source of truth; lost or reordered events diverge permanently |
| Unbounded Last-Known-Good | Turns a revocation into an advisory |
| Last-Known-Good despite known revoke or disable | Directly contradicts the strongest control-plane signal |
| Defaulting a missing artifact | Produces a configuration nobody reviewed |
| Repairing a digest mismatch by re-fetching until it matches | Masks substitution and mutation |
| Falling back to a previous unrelated release on failure | Serves a combination that was not selected |
| Client- or LLM-selected snapshot or revision | Grants configuration authority to untrusted input |
| Caching by display label or role name | Lets a caller choose which configuration it is served |
| Caching unvalidated snapshots | Makes the cache a bypass around the eighteen-step algorithm |
| Rebuilding configuration mid-request | Makes a single run unexplainable and unreplayable |
| Interpreting `security_policy` as per-source visibility | Conflates global runtime posture with source authorization |
| Interpreting `source_revision` as a `KnowledgeSource` revision | Confuses application provenance with content provenance |
| Reading `application_version`, `source_revision`, or `build_artifact` from environment configuration | Makes provenance ambient and mutable, so the same release could yield different digests per host |
| Trusting the running process's own version claim over pinned `BuildArtifact` metadata | Lets a redeployment silently change what a snapshot claims to describe |
| Renaming `config_bundle` now | Breaks contract version 1.0.0 |
| Secrets or provider clients in the cache | Puts key material and vendor objects inside runtime state |

## Consequences

Configuration resolution becomes a single trusted, deterministic, auditable path, and a recorded
snapshot digest is sufficient to reconstruct what a past run used. Bounded Last-Known-Good keeps the
runtime usable during short control-plane outages without weakening revocation.

The costs are explicit. Every request depends on a resolvable active pointer or a valid cache entry,
so the control plane becomes an availability dependency whose failure modes must be operated, not
assumed away. Full digest verification at resolution adds work on cache misses, which is why
single-flight caching is mandatory rather than optional. Fail-closed behavior means a
misconfiguration produces refused requests rather than degraded answers, which is the intended
trade-off but will be experienced as a hard outage. And the four field interpretations in D-1 through
D-4 are now load-bearing for the contract without being enforced by it, so a future contract version
should encode them in names.

## Contract implications

- No change to `RuntimeSnapshot 1.0.0` code or schema is proposed or permitted by this package.
- `config_bundle`, `security_policy`, `index_snapshot`, and `source_revision` acquire normative
  interpretations that later packages must honor.
- The release manifest occupies exactly one `RuntimeArtifactRef` slot, so `release_ref`,
  `release_revision`, and the release digest must satisfy the existing `artifact_id`, `revision`, and
  `sha256:` digest constraints.
- `RuntimeSnapshot 1.0.0` exposes at most sixteen model artifact refs and sixty-four effective feature
  flags. Those limits do not define the total number of other artifact refs inside a
  `ConfigurationRelease`.
- A new policy artifact carried only inside the `ConfigurationRelease`, reachable through
  `config_bundle`, may be introduced through a versioned `ConfigurationRelease` schema. Adding a new
  dedicated `RuntimeSnapshotContent` field requires a `RuntimeSnapshot` contract version event.
- `application_version`, `source_revision`, and `build_artifact` acquire a defined producer: the
  release-pinned qualified `BuildArtifact`. No contract change is needed to adopt this.
- A future 1.1.0 or 2.0.0 candidate list is recorded but not scheduled: rename `config_bundle` to
  `configuration_release`, rename `source_revision` to `application_revision`, and consider an
  explicit aggregate marker on `index_snapshot`. Owned by `CP-001`.
- Typed contracts for the factory, the cache, and Last-Known-Good policy are owned by `CP-004` and
  `CP-001`, per DEF-018 and DEF-038.

## Package ownership

| Concern | Owning package |
| --- | --- |
| Typed factory, cache, and policy contracts | CP-001 |
| Artifact registry resolution and digest storage | CP-003 |
| RuntimeSnapshotFactory implementation and determinism tests | CP-004 |
| Model, provider, and credential resolution behind the adapter boundary | CP-008 |
| Active pointer, revocation state, invalidation emission | CP-009 |
| API exposure of active release inspection | CP-010 |
| Admin visibility of active release and degraded mode | CP-011 |
| Cache implementation, invalidation transport, secret manager | CP-012 |
| Degraded-mode and rollout gates | CP-013 |
| Exact durations, sizes, and intervals | PERF-001 with CP-012 |
| Cross-document consistency repairs | CP-000R |

## Open decisions

| Open decision | Why open | Owning package | Evidence required |
| --- | --- | --- | --- |
| Exact Last-Known-Good maximum stale age | Must balance revocation propagation risk against outage tolerance | PERF-001 with CP-012 | Control-plane availability data and an approved revocation propagation budget |
| Exact cache size in entries and memory | Depends on snapshot size and traffic | PERF-001 | Measured snapshot size and request concurrency |
| Exact polling interval and TTL | Depends on invalidation reliability | CP-012 | Event delivery reliability measurements |
| Exact distributed invalidation mechanism | Depends on deployment topology | CP-012 | Chosen transport and delivery guarantees, DEF-038 |
| Exact `RuntimeSnapshotFactory` Python signatures | Depends on typed artifact contracts | CP-004 with CP-001 | Approved artifact contracts, DEF-018 |
| Whether a future contract version renames `config_bundle` and `source_revision` | 1.0.0 must not break; rename needs a version event | CP-001 | Compatibility policy and consumer inventory |
| Whether `index_snapshot` aggregation needs an explicit typed manifest | Depends on real multi-tier routing from `ADR-CP-003` | CP-006 with CP-001 | Chosen backend and routing needs |
| Exact retry and timeout values for canonical pull | No measured control-plane latency exists | PERF-001 | Latency percentiles under load |
| Exact rate limits protecting the registry from resolution storms | No traffic baseline | PERF-001 | Concurrency and cache-miss rates |
| Exact degraded-mode observability and alerting thresholds | Requires production signal | CP-013 with CP-012 | Incident review and SLO definitions |
| Whether Last-Known-Good is permitted at all per deployment profile | Compliance profiles may forbid any staleness | CP-012 | Residency and compliance commitments |
| Exact storage backend for cached snapshots if shared | Single-process versus shared cache is undecided | CP-012 | Deployment topology and consistency needs |
| Exact `BuildArtifact` metadata fields and qualification rules | Build and supply-chain provenance format is not yet defined | CP-012 with CP-001 | Approved build provenance format, DEF-101 |
| Whether `application_version` is derived from or independently verified against `BuildArtifact` metadata | Both satisfy the invariant; the choice depends on the build pipeline | CP-012 | Chosen build pipeline and provenance guarantees |

## Migration and evolution notes

Nothing is migrated at this HEAD. The four field interpretations are documentation-only and require no
code change. When a future contract version renames a field, the rename must be accompanied by a
consumer inventory and a compatibility test per DEF-013 and DEF-016, and both names must not coexist as
independent sources of truth. Introducing a shared distributed cache later must preserve SI-6 and SI-7
by storing only validated snapshot content, never resolved secrets or provider clients. If
Last-Known-Good is later disabled for a deployment profile, the change is a `ReliabilityPolicy` edit
and therefore an ordinary `Save and Apply`, not a code change.

If this ADR is found inconsistent with an already committed ADR, the committed ADR is preserved and the
conflict is recorded for architect review in `CP-000R`.

## Traceability

- Depends on: `ADR-CP-004`, `ADR-CP-005`, `ADR-CP-002`, `ADR-CP-003`, `ADR-CP-007`, RuntimeSnapshot
  1.0.0, Walking Skeleton 1.0.0.
- Interprets, without modifying: `src/ai_assistant/contracts/runtime_snapshot.py`,
  `schemas/runtime-snapshot/1.0.0.schema.json`, `docs/contracts/runtime-snapshot-1.0.0.md`.
- Deferred Register: DEF-008, DEF-013, DEF-016, DEF-018, DEF-024, DEF-029, DEF-030, DEF-038, DEF-039.
- Repairs recorded for `CP-000R`, not applied here: the fifteen items listed in the traceability
  section of `ADR-CP-004`.
