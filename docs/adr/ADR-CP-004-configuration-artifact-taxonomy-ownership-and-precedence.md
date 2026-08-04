# ADR-CP-004: Configuration Artifact Taxonomy, Ownership, and Precedence

Status: Accepted architecture baseline (originated as CP-000D; CP-000R consistency repair applied, and CP-000R was accepted at commit `8d94c6a`)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000D architecture package
Owner: Control Plane / Configuration Ownership Baseline
Scope: which configuration exists, who owns each part, what the Admin Website may change, and
which precedence rules resolve conflicts. No typed Python contract, database schema, HTTP API,
Admin Website layout, provider adapter, or secret manager is decided here.

Companions:

- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
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

Verified in Git at this HEAD:

- `RuntimeSnapshotContent` (`src/ai_assistant/contracts/runtime_snapshot.py`) already fixes sixteen
  named artifact reference fields plus `feature_flags`, and `RuntimeArtifactRef` already requires
  `artifact_id`, `revision`, and `digest`. This ADR must fit that shape, not replace it.
- `RuntimeSnapshotIntegrity` already fixes `canonicalization="rfc8785"` and a `sha256:` digest.
- `SecurityPrincipalContext`, `AuthorizationResourceRef`, and `AuthorizationDecision`
  (`src/ai_assistant/contracts/security.py`) already carry identity inputs and the trusted decision.
- `ADR-CP-001` fixes `Organization` and recursive `OrganizationalNode` semantics.
- `ADR-CP-002` fixes membership, scoped roles, visibility policies, `anonymous-public`, default deny.
- `ADR-CP-003` fixes data/index isolation, `IndexSnapshot` eligibility, and isolation tiers.
- `ADR-CP-007` fixes `KnowledgeSource`, `SourceRevision`, and the source lifecycle.

Not represented as typed contracts anywhere in `src` or `schemas` at this HEAD, and therefore
conceptual in this ADR: `ConversationPolicy`, `RetrievalProfile`, `EvidenceAnswerPolicy`,
`ModelPolicy`, `IngestionPolicy`, `ReliabilityPolicy`, `FeaturePolicy`, `SecurityPolicy`,
`ConfigurationRelease`, `ActiveConfigurationReleasePointer`, `RuntimeSnapshotFactory`,
`credential_ref`, reasoning profiles, and every artifact lifecycle state named below.

## Context

`RuntimeSnapshot 1.0.0` proves the shape of a configuration manifest but says nothing about what the
referenced artifacts contain, who may change them, or what a change costs. The Deferred Register
records this gap as DEF-019 (Admin Control Plane), DEF-030 (runtime artifact schemas), DEF-031
(artifact registry lifecycle), DEF-033 (configuration permissions), DEF-034 (configuration
auditability), and DEF-035 (hard configuration bounds), all `OPEN`.

Without a taxonomy and an ownership rule, three failures are likely. A single large `AIConfig` blob
makes every edit a full-surface change with no meaningful validation or review granularity. One
artifact per field makes activation a distributed transaction across dozens of pointers. And an
unbounded Admin Website turns safety ceilings into editable fields, which silently converts a
governance decision into a form input.

## Problem

- P-1: The granularity of a configuration artifact is undefined, so validation scope, revision
  scope, and rollback scope are all undefined.
- P-2: It is undefined which values are product configuration and which are platform governance,
  so nothing prevents a safety ceiling from becoming an admin field.
- P-3: It is undefined who may change AI behavior, so organization and department administrators
  might acquire runtime authority that `ADR-CP-002` never granted them.
- P-4: Editable policy artifacts and technical build artifacts have different validation and
  qualification lifecycles, but no boundary separates them.
- P-5: Conflicts between artifacts (a feature flag against a security prohibition, a configured
  timeout against a platform ceiling) have no stated precedence, so resolution would be incidental.
- P-6: Content approval (`ADR-CP-007`) and AI configuration approval are different authorities that
  are easily conflated into one "admin" role.

## Decision

- D-1: Configuration is decomposed into domain-level policy artifacts, not one `AIConfig` blob and
  not one artifact per field. The v1 set is exactly: `ConversationPolicy`, `RetrievalProfile`,
  `EvidenceAnswerPolicy`, `ModelPolicy`, `IngestionPolicy`, `ReliabilityPolicy`, `FeaturePolicy`,
  `SecurityPolicy`.
- D-2: Every policy artifact conceptually carries `artifact_ref`, `artifact_type`, `schema_version`,
  an immutable revision, `content_digest`, `created_at`, `created_by`, validation status, lifecycle
  status, and compatibility metadata. Field-level Python schemas are not decided here.
- D-3: A platform-only control set exists and is not an Admin Website surface. It changes only
  through a software or platform governance change, never through a form field.
- D-4: In v1 the AI Runtime configuration is global. Only a globally authorized system
  administrator holding `ai_configuration.manage` may change it.
- D-5: No Organization-, Faculty-, Department-, or Node-level AI override exists in v1. Local
  administrators retain only the authority `ADR-CP-001`, `ADR-CP-002`, and `ADR-CP-007` grant them
  over structure, membership, delegated data roles, sources, and source visibility.
- D-6: The v1 administrative interaction is `Edit` then `Test Configuration` where required then
  `Save and Apply`. No user-visible draft workspace, review queue, staged editing workflow, or
  second AI configuration approver is a v1 product requirement. This supersedes the earlier
  proposed two-person AI configuration workflow. Validation, immutable revisions, audit, atomic
  activation, previous release retention, and rollback remain mandatory behind that simple flow.
- D-7: Technical and runtime artifacts are a separate class from editable policy artifacts:
  `PromptBundle`, `ModelArtifact`, `EmbeddingArtifact`, `RerankerArtifact`, `IndexSnapshot`,
  `SemanticCatalog`, `RuleBundle`, `StructuredOutputBackendManifest`, `TelemetrySchema`,
  `BuildArtifact`. A release may pin them, but their validation and qualification lifecycles differ.
- D-8: Precedence is fixed and total. From strongest to weakest: platform hard bounds and mandatory
  security invariants; `SecurityPolicy` prohibitions and classification ceilings; `FeaturePolicy`
  enablement; the remaining policy artifacts within their own domain; artifact-declared defaults.
  A weaker layer may only narrow, never widen, a stronger one.
- D-9: The client, the frontend, and the model hold no rank in that ordering at all. They are not a
  weak input; they are not an input.
- D-10: No secret value appears in any configuration artifact. `ModelPolicy` references
  `credential_ref` and masked metadata only.
- D-11: Content approval authority (`source.review`, `source.approve`, `source.reject`) is distinct
  from `ai_configuration.manage`. Neither implies the other.
- D-12: The path `Backend` then mutable dictionary then direct Core variable mutation is forbidden.
  Configuration reaches Core only as an immutable digest-pinned manifest.

```text
Ownership boundary (who may change what)

  PLATFORM / GOVERNANCE  (software change only; no Admin Website field)
  +------------------------------------------------------------------+
  | contract and schema versions      hard safety bounds              |
  | mandatory security invariants     canonicalization algorithm      |
  | digest algorithm                  safe visibility primitives      |
  | classification lattice primitives secret-handling invariants      |
  | mandatory audit fields            forbidden capabilities          |
  | absolute concurrency ceilings     hierarchy/path safety limits    |
  +---------------------------------+--------------------------------+
                                    | bounds and prohibitions only
                                    v inside envelope may validate,
                                      outside envelope is rejected
  SYSTEM AI ADMINISTRATOR  (ai_configuration.manage, global scope, v1)
  +------------------------------------------------------------------+
  | ConversationPolicy   RetrievalProfile   EvidenceAnswerPolicy      |
  | ModelPolicy          IngestionPolicy    ReliabilityPolicy        |
  | FeaturePolicy        SecurityPolicy                              |
  |                                                                  |
  | UI: Edit -> Test Configuration (when required) -> Save and Apply |
  +---------------------------------+--------------------------------+
                                    | no AI authority downward
                                    v
  ORGANIZATION / DEPARTMENT ADMINISTRATOR
  +------------------------------------------------------------------+
  | organization and node structure      membership and scoped roles |
  | delegated data roles                 sources and source          |
  |                                      visibility policy selection |
  |                                                                  |
  | DENIED: model, provider, prompt, reasoning level, retrieval      |
  | counts, ranking weights, chunking, embedding, reranker,          |
  | timeouts, retries, concurrency, cache, feature enablement,       |
  | web search, security policy, classification ceiling, hard bounds |
  +------------------------------------------------------------------+

  SOURCE APPROVER  (source.review / source.approve / source.reject)
  +------------------------------------------------------------------+
  | approves content eligibility only; no AI configuration authority |
  +------------------------------------------------------------------+

  FORBIDDEN EDGE:  Backend -> mutable dict -> Core variable mutation
```

## Detailed semantics

### Common artifact semantics

An artifact is a named domain of configuration whose content is validated as a unit and revisioned
as a unit. `artifact_ref` identifies the logical artifact across revisions; the revision identifies
one immutable content state; `content_digest` binds that state to a verifiable value. Validation
status records the outcome of the layered validation in `ADR-CP-005`; lifecycle status records
`VALIDATED`, `APPROVED`, `REVOKED`, or `ARCHIVED`. Compatibility metadata records which schema
versions and which peer artifact revisions the content was validated against, so a later release
cannot assume compatibility it never proved.

Representative fields below are semantic ownership statements, not final schemas. Their purpose is
to make later typed-contract packages deterministic about which artifact owns which value.

### ConversationPolicy

Owns how much prior conversation and ambient context may enter a turn: `history_max_messages`,
`history_token_budget`, `history_time_window`, `system_context_budget`,
`attachment_context_budget`, `conversation_summary_policy_ref`. It bounds input volume only. It
grants no read authority over any message it did not already have, and it never widens retrieval.

### RetrievalProfile

Owns retrieval shape and budget: `candidate_count`, `lexical_candidate_count`,
`vector_candidate_count`, `rerank_count`, `final_evidence_count`, `per_source_cap`, `per_scope_cap`,
`minimum_score`, `hybrid_weights`, `freshness_window`, `max_context_tokens`. `per_scope_cap` is the
provider-neutral concept; no provider partition name appears here. Authorization never derives from
these values. Per `ADR-CP-003`, the authorized scope set comes from trusted authorization
resolution, and a larger `candidate_count` cannot reach an unauthorized unit.

### EvidenceAnswerPolicy

Owns answer construction constraints: `required_fact_coverage`, citation limits, answer-length
budget, abstention thresholds, freshness-note policy, allowed answer types, claim-validation policy
refs, caveat policy refs. These constrain what may be asserted from evidence that already exists.
They never create evidence authority and never lower an authorization requirement.

### ModelPolicy

Owns model selection and provider-neutral operational behavior: model entry refs, declared
provider-neutral capabilities, priority, fallback order, timeout profile, max output, rate-limit
profile, health and cooldown profile, residency policy refs, `credential_ref`, and the active
reasoning profile ref. No secret value and no provider SDK object may appear. Provider-specific
strings stay behind the adapter boundary; Core sees stable provider-neutral refs.

### IngestionPolicy

Owns the technical ingestion contract: allowed MIME and file types, max upload size, chunk strategy
and bounds, OCR enablement, embedding artifact ref, index-build policy, deduplication policy,
malware and content-validation refs, retention policy refs. Department users cannot override any of
these; their authority per `ADR-CP-007` covers submitting content, not deciding how it is processed.

### ReliabilityPolicy

Owns bounded resource behavior: request deadline, capability timeout, retry budget, maximum parallel
steps, queue limits, concurrency limits, rate limits, circuit-breaker profile, load-shedding policy,
cache limits, and Last-Known-Good policy. No retry, queue, task, or cache may be unbounded. Every
value here must remain within its platform hard bound; a violation is rejected.

### FeaturePolicy

Owns enablement: capability enablement, chat attachment enablement, Official Search enablement,
General Web Search enablement, emergency capability disable, rollout flags. A feature flag can only
turn something off or on within what is already permitted. It can never override a `SecurityPolicy`
prohibition or a platform-forbidden capability.

### SecurityPolicy

Owns the global runtime security posture: classification ceilings, capability prohibitions,
cross-scope behavior, model data-classification allowance, residency constraints, audit policy
refs, retention policy refs, emergency controls. This is not a per-source visibility policy. The
per-source `VisibilityPolicyDefinition` remains owned by `ADR-CP-002` and `ADR-CP-007` and is
resolved through authorization and source or index metadata, never through this artifact.

### Precedence resolution

Precedence is evaluated as narrowing only *between policy layers within one candidate release*. A
candidate value inside the platform envelope may validate; a candidate value outside the platform
envelope rejects `Save and Apply` and the active release remains unchanged. If `ReliabilityPolicy`
sets a request deadline above the platform ceiling, the release fails validation; the value is never
clamped silently, because a silently adjusted value would make the active configuration differ from
the reviewed one. If `FeaturePolicy` enables a capability that `SecurityPolicy` prohibits, the release
fails validation. If two policy artifacts constrain the same quantity within one candidate release,
the more restrictive value applies and the combination must be recorded as validated in the release.
No precedence rule ever resolves a conflict by widening.

### Precedence versus historical revisions

Narrowing-only precedence is a rule about how layers combine inside a single candidate release. It is
not a rule about revision history, and it does not require every new revision to be monotonically
more restrictive than the revision before it. The System AI Administrator may change a
`SecurityPolicy` anywhere within the platform security envelope, including restoring a capability
that a previous revision had turned off, provided that platform invariants are not weakened, the
complete release validates, the change is explicit and audited, and an emergency disable is never
implicitly reversed. Re-enabling something previously disabled by an emergency action requires a
deliberate, separately audited re-enable, never a side effect of an ordinary edit.

### Source approval boundary carried forward

Approved v1 behavior, recorded here only so configuration authority and content authority are not
conflated: authorized department users upload or register a source and submit it for review; one
centrally assigned Source Approver holding `source.review`, `source.approve`, and `source.reject`
reviews submissions from all departments; only approved content becomes eligible for activation and
indexing. Department users may hold `source.create`, `source.upload`, `source.edit_own_draft`, and
`source.submit`. The same principal must not approve a submission they created, authored, uploaded,
or submitted; holding `source.approve` does not override that v1 prohibition. This ADR does
not redesign `ADR-CP-007` or `CP-000B`; reconciliation is owned by `CP-000R`.

```text
Artifact taxonomy and release composition

  EDITABLE POLICY ARTIFACTS (System AI Administrator, revisioned, validated as a set)
    ConversationPolicy   RetrievalProfile   EvidenceAnswerPolicy   ModelPolicy
    IngestionPolicy      ReliabilityPolicy  FeaturePolicy          SecurityPolicy
         |                    |                   |                    |
         +--------------------+---------+---------+--------------------+
                                        |
  TECHNICAL / RUNTIME ARTIFACTS (separate qualification lifecycle, pinned not "edited")
    PromptBundle   ModelArtifact   EmbeddingArtifact   RerankerArtifact   IndexSnapshot
    SemanticCatalog  RuleBundle  StructuredOutputBackendManifest  TelemetrySchema
    BuildArtifact
         |                                  |
         +----------------+-----------------+
                          v
              ConfigurationRelease  (pins every ref + revision + digest)
                          |
                          v
              ActiveConfigurationReleasePointer  (exactly one, global, v1)
                          |
                          v
              RuntimeSnapshotFactory -> immutable RuntimeSnapshot
                          |
                          v
              stateless AI Runtime  (reads nothing else)

  NOT an artifact: platform hard bounds, mandatory security invariants, digest and
  canonicalization algorithms. Those are governed, not configured.
```

## Ownership

- Platform and Governance own the platform-only control set in D-3. An Admin Website field may never
  weaken any of them, and a request that attempts it is a validation failure, not a negotiation.
- The System AI Administrator owns the eight policy artifacts globally in v1 under
  `ai_configuration.manage`, and may invoke `Save and Apply`, rollback, and emergency disable.
- Organization and Department administrators own structure, membership, delegated data roles,
  sources, and source visibility selection. They own no AI behavior in v1.
- The Source Approver owns content eligibility only. This is a dependency of configuration
  correctness, not a part of it: an approved source is what `IngestionPolicy` and `RetrievalProfile`
  operate on, not something they authorize.
- In v1, `source.review` includes permission to read pending source submissions from all departments
  for the purpose of review. It does not independently grant access to unrelated active or restricted
  content outside the reviewer's required review surface. The exact scoping of that review surface
  remains a `CP-000R` and `CP-001` contract dependency, and `ADR-CP-007` and `CP-000B` are not edited
  by this package.
- Technical and runtime artifacts are owned by the packages that produce them, and are qualified by
  `CP-013` where evaluation is required.

## Security invariants

- SI-1: Default deny is preserved. No configuration artifact grants read access to any resource.
- SI-2: No configuration value is an authorization input. Authorization comes only from the trusted
  path in `ADR-CP-002` and `ADR-CP-003`.
- SI-3: Platform hard bounds and mandatory security invariants cannot be weakened from any Admin
  Website field, any API input, or any artifact revision.
- SI-4: A `FeaturePolicy` flag cannot override a `SecurityPolicy` prohibition or a platform-forbidden
  capability.
- SI-5: No secret value exists in an artifact, a release, a snapshot, a frontend read response, a
  log, telemetry, or an audit record. Only `credential_ref` and masked metadata cross that boundary.
- SI-6: No provider SDK object, client, or raw provider response enters Core.
- SI-7: Core never reads database configuration, frontend state, secrets, or environment
  configuration directly.
- SI-8: LLM output cannot change configuration, and client-supplied metadata cannot authorize a
  configuration change.
- SI-9: Organization and department scope cannot produce an AI configuration override in v1.
- SI-10: Physical or deployment topology grants no configuration authority, consistent with
  `ADR-CP-003`: isolation is defense in depth, authorization remains a logical policy decision.

## Failure behavior

| Failure | Architectural behavior |
| --- | --- |
| Artifact type unknown | Reject at Layer 1; no revision is created |
| Value exceeds a platform hard bound | Reject the change; do not clamp silently; current release stays active |
| `FeaturePolicy` conflicts with `SecurityPolicy` | Reject the release; record a safe validation error |
| Secret value detected in an artifact payload | Reject and record a sanitized audit event; never persist the value |
| Department-scoped AI override attempted | Deny as unauthorized; audit the attempt |
| `credential_ref` missing where required | Reject at Layer 3; no release is created |
| Compatibility metadata absent for a referenced peer artifact | Treat as incompatible; reject at Layer 4 |
| Precedence conflict between two policy artifacts | Apply the narrower value only if validated; otherwise reject |

No failure in this ADR results in a partially applied configuration, and none falls back to a
weaker policy. Detailed activation-time and runtime failure behavior is in `ADR-CP-005` and
`ADR-CP-006`.

## Alternatives considered

Two options were weighed seriously. A per-organization AI configuration override model would let
faculties tune retrieval and models to their own corpora, which is genuinely useful, but in v1 it
multiplies the validation surface by the number of nodes, makes a global safety change unenforceable
without touching every override, and creates a scope-widening path that `ADR-CP-002` deliberately
closes. It is deferred, not dismissed. A two-person AI configuration workflow with a separate
approver would raise the bar on production changes, but v1 has one system administrator role and no
second qualified reviewer, so the workflow would either be bypassed or would block all changes; the
underlying safety properties are preserved instead by mandatory validation, immutability, audit, and
rollback behind the simple flow.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| One large `AIConfig` artifact | No validation or rollback granularity; every edit is a full-surface change |
| One artifact per field | Activation becomes a multi-pointer transaction; tearing becomes the normal case |
| Admin-editable hard bounds | Converts a governance decision into a form field; SI-3 violation |
| Per-department AI overrides in v1 | Unenforceable global safety changes and a scope-widening path |
| Feature flag able to override `SecurityPolicy` | Makes a prohibition advisory; SI-4 violation |
| Secrets stored in `ModelPolicy` | Puts key material in artifacts, releases, snapshots, and audit; SI-5 violation |
| Provider SDK objects or provider enums in Core | Breaks provider neutrality and leaks vendor lifecycle into contracts |
| Backend mutating Core variables directly | Removes reproducibility and makes a request non-replayable; D-12 violation |
| Treating every immutable artifact as editable configuration | Confuses qualification lifecycles for prompts, models, indexes, and builds |
| Conflating `ai_configuration.manage` with `source.approve` | Lets a content approver change model and retrieval behavior |
| Persistent user-visible `DraftWorkspace` in v1 | Adds product surface without adding a real second reviewer |
| Resolving precedence by widening | Any widening rule eventually grants unintended access |

## Consequences

The Admin Website surface becomes finite and reviewable: eight artifacts, one permission, one flow.
Validation and rollback gain a natural unit. A change to one retrieval number no longer requires
reasoning about prompt or security state, because the release pins everything else unchanged.

The cost is that the eight artifact boundaries are now a commitment. Moving a field between
artifacts later is a schema-compatibility event, not a refactor. A second cost is that v1 offers no
local tuning at all, so any faculty-specific need must wait for a deliberate override design rather
than being solved informally. A third cost is that platform-only controls require a software release
to change, which is intentional friction and will occasionally be experienced as an obstacle.

## Contract implications

- `RuntimeSnapshotContent.config_bundle` is interpreted as the digest-pinned `ConfigurationRelease`
  manifest reference. `ADR-CP-006` states this interpretation normatively. Version 1.0.0 is not
  modified.
- The eight policy artifacts must be expressible as `RuntimeArtifactRef` values, so each needs a
  stable `artifact_id`, a revision string, and a `sha256:` digest. Nothing in this taxonomy requires
  a change to `RuntimeArtifactRef`.
- `RuntimeSnapshotContent.security_policy` maps to the global runtime `SecurityPolicy` here, not to
  per-source visibility policy revisions.
- `RuntimeSnapshot 1.0.0` exposes at most sixteen model artifact refs and sixty-four effective
  feature flags. Those limits do not define the total number of other artifact refs inside a
  `ConfigurationRelease`.
- Typed contracts for the eight artifacts are owned by `CP-001` and remain undefined here, per
  DEF-030.

## Package ownership

| Concern | Owning package |
| --- | --- |
| Typed artifact contracts and schema versions | CP-001 |
| Artifact registry, revisions, digests, retention | CP-003 |
| RuntimeSnapshotFactory implementation | CP-004 |
| Model, provider, and credential pool | CP-008 |
| Control Plane application services and permissions | CP-009 |
| Backend and API integration boundary | CP-010 |
| Admin Website integration | CP-011 |
| Production adapters and secret manager integration | CP-012 |
| Evaluation and rollout gates | CP-013 |
| Cross-document consistency repairs | CP-000R |

## Open decisions

| Open decision | Why open | Owning package | Evidence required |
| --- | --- | --- | --- |
| Exact typed fields of each policy artifact | Field sets must follow real capability implementations | CP-001 | Implemented capability inputs and validation needs |
| Exact platform hard-bound values | No production measurement exists | PERF-001 with CP-001 | Latency, concurrency, and resource curves |
| Exact database or storage backend for artifacts | Registry access patterns not yet known | CP-003 with CP-012 | Revision volume, query patterns, retention needs |
| Exact HTTP/API shape for configuration commands | Depends on typed contracts | CP-010 | Approved contracts and Admin Website flows |
| Exact Admin Website layout | Product design not in scope of an ADR | CP-011 | Usability review with the System AI Administrator |
| Whether per-organization AI overrides are ever introduced | Deferred v1 decision with real demand uncertainty | CP-009 with CP-007 | Documented faculty need plus an enforceable safety model |
| Configuration permission decomposition beyond `ai_configuration.manage` | v1 has one role; finer grants need real separation of duties | CP-009 | Approved role model, DEF-033 |
| Exact secret manager provider | Platform choice with residency implications | CP-012 | Residency requirements and operational review, DEF-022 |
| Qualification requirements per technical artifact type | Prompt, model, and index qualification differ | CP-013 | Approved evaluation gates per artifact type |

## Migration and evolution notes

This package introduces no code, so there is nothing to migrate at this HEAD. Forward evolution
rules: a new policy artifact carried only inside the `ConfigurationRelease` and reachable through
`config_bundle` may be introduced through a versioned `ConfigurationRelease` schema, without a
`RuntimeSnapshot` contract version event; adding a new dedicated `RuntimeSnapshotContent` field does
require a `RuntimeSnapshot` contract version event. Moving a field between existing artifacts
requires a compatibility profile bump and a re-validation of every retained release that is still a rollback
target; renaming `config_bundle` to `configuration_release` is a candidate for a future contract
version and must not be attempted against 1.0.0.

If a later package finds an inconsistency between this ADR and an already committed ADR, the
committed ADR is preserved and the conflict is recorded for architect review in `CP-000R` rather
than resolved by editing history.

## Traceability

- Depends on: `ADR-CP-001`, `ADR-CP-002`, `ADR-CP-003`, `ADR-CP-007`, `CP-000A`, `CP-000B`,
  `CP-000C`, Walking Skeleton 1.0.0, RuntimeSnapshot 1.0.0.
- Companion documents: `ADR-CP-005`, `ADR-CP-006`, `CP-000D-configuration-catalog.md`.
- Deferred Register: DEF-019, DEF-022, DEF-030, DEF-031, DEF-032, DEF-033, DEF-034, DEF-035.
- Repairs recorded for `CP-000R`, not applied here: source management matrix reconciliation, single
  central Source Approver for v1, source relationship semantics, `SUPERSEDES` within one
  `KnowledgeSource`, `SUPPLEMENTS` across independent `KnowledgeSource` instances, `valid_until` may
  be null, source authority metadata, source temporal metadata, minimal Node lifecycle, Guest
  contract gap, authorized retrieval scope envelope, isolation metadata subset naming, architecture
  document status updates, roadmap status synchronization, deferred-register synchronization.
