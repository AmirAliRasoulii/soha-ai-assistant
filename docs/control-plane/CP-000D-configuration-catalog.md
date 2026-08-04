# CP-000D Configuration Catalog

Status: Accepted architecture baseline (originated as CP-000D; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Scope: operational companion to `ADR-CP-004`, `ADR-CP-005`, and `ADR-CP-006`. Tables only. No
provider is selected, no numeric threshold is fixed, no typed contract is defined, and no benchmark
or test result is asserted.

Companions:

- `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`
- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
- `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`
- `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`
- `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`

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

## Legend

| Symbol | Meaning |
| --- | --- |
| `PLATFORM` | Platform and Governance owned; changeable only by a software or governance change |
| `SYS-AI-ADMIN` | System AI Administrator holding `ai_configuration.manage`, global scope in v1 |
| `ORG-ADMIN` | Organization or Department administrator; holds no AI configuration authority in v1 |
| `CONTROL-PLANE` | Produced by trusted control-plane processes, never by client input |
| `FAIL-CLOSED` | No snapshot, no release, or no result; never a default and never a weaker policy |
| `BOUNDS` | Must remain within platform bounds; a violation is rejected, never clamped silently |
| `REJECT` | Command refused before any revision or release is persisted as canonical |
| `AUDIT` | Requires recorded actor, safe reason, and before/after references |
| `OPEN` | Deliberately undecided in this package |

## 25.1 Ownership table

| Artifact / Field Group | Representative Fields | Owner | Editable from Backend | Department Override | Hard-Bound Interaction | Approval/Activation Rule | Implementation Package |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Platform-only controls | contract/schema versions, hard safety bounds, mandatory security invariants, canonicalization algorithm, digest algorithm, safe visibility primitives, classification lattice primitives, secret-handling invariants, mandatory audit fields, forbidden capabilities, absolute concurrency ceilings, hierarchy/path safety limits | `PLATFORM` | No | Denied | Defines the ceiling; cannot be weakened by any field | Software or platform governance change only | CP-001 with Governance |
| ConversationPolicy | `history_max_messages`, `history_token_budget`, `history_time_window`, `system_context_budget`, `attachment_context_budget`, `conversation_summary_policy_ref` | `SYS-AI-ADMIN` | Yes | Denied | Must remain within platform bounds; violation is rejected. `BOUNDS` | `Save and Apply`, full release, `AUDIT` | CP-001, CP-009 |
| RetrievalProfile | `candidate_count`, `lexical_candidate_count`, `vector_candidate_count`, `rerank_count`, `final_evidence_count`, `per_source_cap`, `per_scope_cap`, `minimum_score`, `hybrid_weights`, `freshness_window`, `max_context_tokens` | `SYS-AI-ADMIN` | Yes | Denied | Must remain within platform bounds; violation is rejected. `BOUNDS` | `Save and Apply`, full release, `AUDIT`; never an authorization input | CP-001, CP-007 |
| EvidenceAnswerPolicy | `required_fact_coverage`, citation limits, answer-length budget, abstention thresholds, freshness-note policy, allowed answer types, claim-validation policy refs, caveat policy refs | `SYS-AI-ADMIN` | Yes | Denied | Bounded by platform output ceilings | `Save and Apply`, full release, `AUDIT`; creates no evidence authority | CP-001, CP-009 |
| ModelPolicy | model entry refs, provider-neutral capabilities, priority, fallback order, timeout profile, max output, rate-limit profile, health/cooldown profile, residency policy refs, `credential_ref`, active reasoning profile ref | `SYS-AI-ADMIN` | Yes | Denied | Must remain within platform bounds; violation is rejected. `BOUNDS` | `Save and Apply` plus a controlled probe when the intended active combination changes, `AUDIT`; no secret value | CP-001, CP-008 |
| IngestionPolicy | allowed MIME/file types, max upload size, chunk strategy, chunk bounds, OCR enablement, embedding artifact ref, index-build policy, deduplication policy, malware/content-validation refs, retention policy refs | `SYS-AI-ADMIN` | Yes | Denied | Must remain within platform bounds; violation is rejected. `BOUNDS` | `Save and Apply`, full release, `AUDIT` | CP-001, CP-006 |
| ReliabilityPolicy | request deadline, capability timeout, retry budget, maximum parallel steps, queue limits, concurrency limits, rate limits, circuit-breaker profile, load-shedding policy, cache limits, LKG policy | `SYS-AI-ADMIN` | Yes | Denied | Must remain within platform bounds; violation is rejected. Nothing may be unbounded. `BOUNDS` | `Save and Apply`, full release, `AUDIT` | CP-001, CP-012 |
| FeaturePolicy | capability enablement, chat attachment enablement, Official Search enablement, General Web Search enablement, emergency capability disable, rollout flags | `SYS-AI-ADMIN` | Yes | Denied | Cannot enable a platform-forbidden capability | `Save and Apply`, full release, `AUDIT`; cannot override a `SecurityPolicy` prohibition | CP-001, CP-009 |
| SecurityPolicy (global runtime) | classification ceilings, capability prohibitions, cross-scope behavior, model data-classification allowance, residency constraints, audit policy refs, retention policy refs, emergency controls | `SYS-AI-ADMIN` | Yes, editable only within platform hard bounds | Denied | Cannot weaken a mandatory security invariant; a violation is rejected | `Save and Apply`, full release, `AUDIT`; a new revision need not be more restrictive than the previous one, and an emergency disable is never implicitly reversed; distinct from per-source visibility policy | CP-001, CP-009 |
| Per-source VisibilityPolicyDefinition | visibility primitives per source revision | `ORG-ADMIN` within source authority | Yes, via source management | Not an AI override | Restricted to safe platform primitives | Source lifecycle per `ADR-CP-007` and `CP-000B` | CP-006, CP-009 |
| Source approval authority | `source.review`, `source.approve`, `source.reject` | Central Source Approver | Yes, via source workflow | The same principal cannot approve a submission they created, authored, uploaded, or submitted | None | Business approval precedes `ACTIVE` eligibility; it is not an AI configuration action and does not replace technical gates. In v1 `source.review` includes reading pending submissions from all departments for review, and does not independently grant access to unrelated active or restricted content outside the required review surface | CP-006, CP-009, reconciled in CP-000R |
| Credential material | secret value | `PLATFORM` Secret Manager | No, masked operations only | Denied | Secret-handling invariant | Create, rotate, revoke, masked read, bounded health probe; original value never returned | CP-008, CP-012 |

## 25.2 Artifact taxonomy table

| Artifact Type | Purpose | Revisioned | Pinned by ConfigurationRelease | RuntimeSnapshot Mapping | Validation Owner | Future Typed Contract Package |
| --- | --- | --- | --- | --- | --- | --- |
| ConfigurationRelease | Atomic unit of activation and rollback | Yes | It is the pinning unit | `config_bundle` (interpreted per `ADR-CP-006` D-1) | Control Plane, Layer 6 | CP-001 |
| ConversationPolicy | Conversation and ambient context budgets | Yes | Yes | No dedicated field in 1.0.0; carried within the release manifest | Control Plane, Layers 1 to 4 | CP-001 |
| RetrievalProfile | Retrieval shape and budgets | Yes | Yes | `retrieval_profile` | Control Plane, Layers 1 to 4 | CP-001 |
| EvidenceAnswerPolicy | Answer construction constraints | Yes | Yes | No dedicated field in 1.0.0; carried within the release manifest | Control Plane, Layers 1 to 4 | CP-001 |
| ModelPolicy | Model selection and operational behavior | Yes | Yes | `model_policy` | Control Plane, Layers 1 to 5 including probe | CP-001, CP-008 |
| IngestionPolicy | Ingestion and index-build contract | Yes | Yes | No dedicated field in 1.0.0; carried within the release manifest | Control Plane, Layers 1 to 4 | CP-001 |
| ReliabilityPolicy | Bounded resource behavior and LKG policy | Yes | Yes | No dedicated field in 1.0.0; carried within the release manifest | Control Plane, Layers 1 to 4 | CP-001 |
| FeaturePolicy | Capability enablement and rollout flags | Yes | Yes | `feature_flags` effective resolution | Control Plane, Layers 1 to 4 | CP-001 |
| SecurityPolicy | Global runtime security posture | Yes | Yes | `security_policy` (global, not per-source) | Control Plane, Layers 1 to 4 | CP-001 |
| PromptBundle | Prompt set for a qualified behavior | Yes | Yes | `prompt_bundle` | Qualification per `CP-013` | CP-001, CP-013 |
| ModelArtifact | Qualified model artifact identity | Yes | Yes | `model_artifacts`; `RuntimeSnapshot 1.0.0` exposes at most sixteen such refs, which does not bound other artifact refs inside the release | Qualification per `CP-013` | CP-001, CP-008 |
| EmbeddingArtifact | Embedding identity and compatibility | Yes | Yes | `embedding_artifact` | Compatibility with `IndexSnapshot` | CP-001, CP-006 |
| RerankerArtifact | Reranker identity and compatibility | Yes | Yes | `reranker_artifact` | Compatibility with retrieval output | CP-001, CP-006 |
| IndexSnapshot | Logical aggregate indexed-state manifest | Yes | Yes | `index_snapshot` (aggregate per `ADR-CP-006` D-3) | Ingestion and index lifecycle | CP-001, CP-006 |
| SemanticCatalog | Semantic mapping artifact | Yes | Yes | `semantic_catalog` | Catalog validation | CP-001 |
| RuleBundle | Deterministic rule artifact | Yes | Yes | `rule_bundle` | Rule-bundle validation | CP-001 |
| StructuredOutputBackendManifest | Structured-output capability manifest | Yes | Yes | `structured_output_backend` | Compatibility with `ModelPolicy` | CP-001, CP-008 |
| TelemetrySchema | Telemetry contract for a run | Yes | Yes | `telemetry_schema` | Schema registry | CP-001 |
| BuildArtifact | Application build identity and provenance producer | Yes | Yes, a qualified `BuildArtifact` must be pinned | `build_artifact`; `application_version` and `source_revision` are derived or verified from its immutable metadata, never from environment configuration | Build and supply chain | CP-012, DEF-101 |

## 25.3 Validation matrix

| Validation Layer | Input | Required Checks | Failure Outcome | External Dependency | Owning Package |
| --- | --- | --- | --- | --- | --- |
| Layer 1 contract/schema | Submitted intended configuration | Required fields, types, closed schemas, bounded collections, canonical identifiers, known artifact types, valid references | `REJECT`; no canonical revision persisted | None | CP-001, CP-009 |
| Layer 2 platform hard bounds | Candidate artifact content plus platform policy | A candidate value inside the platform envelope may validate: configured `max_parallel_steps` within platform maximum, configured timeouts within platform maximum, minimum security constraints not weakened, no platform-forbidden feature enabled | A candidate value outside the platform envelope rejects `Save and Apply`; never clamped silently; active release remains unchanged | Platform hard-bound policy | CP-001, Governance |
| Layer 3 artifact semantic | One candidate artifact | `minimum_score` valid, `rerank_count` within `candidate_count`, `final_evidence_count` within `rerank_count` where required, default reasoning profile exists, selected reasoning profile enabled, fallback list model refs unique, `credential_ref` present where required | `REJECT` with safe field-level error | None | CP-001, CP-009 |
| Layer 4 cross-artifact | Complete candidate artifact set | RetrievalProfile with EvidenceAnswerPolicy, ModelPolicy with PromptBundle, ModelPolicy with structured-output requirement, EmbeddingArtifact with IndexSnapshot, RerankerArtifact with retrieval output, FeaturePolicy with SecurityPolicy, ReliabilityPolicy with platform resource bounds | `REJECT` the combination even when each artifact is individually valid | Artifact registry | CP-001, CP-009 |
| Layer 5 external capability (CONDITIONAL) | Exact intended active model combination, only when it changes in a way requiring provider validation: provider ref, provider model identifier, `credential_ref`, selected reasoning profile or provider value, required response mode, required structured-output or tool capability | When it runs: credential resolution works, model identifier accepted, selected reasoning configuration accepted, request format accepted, required response shape returnable; future types may add index compatibility, semantic catalog, rule bundle, storage readiness. When the model configuration is unchanged: reuse the still-valid pinned validation and probe evidence and contact no provider, unless that evidence or a dependency is revoked, expired under an approved policy, or otherwise invalid | `REJECT` `Save and Apply`; current release remains active; sanitized `AUDIT` event. An unrelated change such as a `RetrievalProfile` count never contacts the provider merely because the release also pins an unchanged `ModelPolicy` | Provider adapter or application service; never Core | CP-008, CP-012 |
| Layer 6 release | Intended `ConfigurationRelease` with all pinned revisions | No referenced artifact missing, invalid, revoked, disabled, digest-mismatched, schema-incompatible, unapproved where approval is required, or cross-artifact incompatible | `REJECT`; active pointer unchanged; a green probe never bypasses this layer | Artifact registry and revocation state | CP-003, CP-009 |
| Resolution-time revalidation | Active release at request time | Steps 3, 5, 6, 7, 8, 9, and 10 of the factory algorithm | `FAIL-CLOSED`; no snapshot for new requests; in-flight requests keep their pinned snapshot | Registry, revocation state, trusted time | CP-004 |

## 25.4 Model reasoning-profile table

| Field | Meaning | Entered by Administrator | Provider-specific | Visible to Core | Validation Rule |
| --- | --- | --- | --- | --- | --- |
| `model_entry_ref` | Stable provider-neutral identity of a configured model entry | Yes | No | Yes | Canonical identifier, unique within `ModelPolicy` |
| `display_name` | Human label for the Admin Website | Yes | No | Never as an authorization or routing key | Non-empty; never used as a key |
| `provider_ref` | Provider identity behind the adapter boundary | Yes | Reference only | Yes, as an opaque ref | Must resolve to a known adapter-supported provider |
| `provider_model_identifier` | Exact provider model string | Yes | Yes | No; stays behind the adapter | Accepted by the controlled probe |
| declared capabilities | Provider-neutral capability claims | Yes | No | Yes | Must be compatible with `FeaturePolicy` and the structured-output requirement |
| `reasoning_profile_ref` | Stable ref for one declared reasoning profile | Yes | No | Yes | Unique within the model entry; not assumed to be low, medium, or high |
| `display_name` (profile) | Human label for a profile, such as `Standard` | Yes | No | Never as a key | Non-empty |
| `provider_value` | Exact value sent to the provider, such as `standard` | Yes | Yes | No; stays behind the adapter | Accepted by the controlled probe for the selected profile |
| `description` (profile) | Operator explanation of the profile | Yes | No | No | Optional free text; carries no behavior |
| `enabled` (profile) | Whether the profile may be selected | Yes | No | Yes | The selected active profile must be enabled |
| selected active reasoning profile | The one profile in effect in v1 | Yes | No | Yes, as a ref | Exactly one per active model configuration; changing it revalidates and reprobes |
| max output constraints | Upper bound on generated output | Yes | No | Yes | Within the platform output ceiling |
| context constraints | Model context limits | Yes | No | Yes | Consistent with `ConversationPolicy` and `RetrievalProfile` budgets |
| timeout profile | Bounded provider timeout behavior | Yes | No | Yes | Within the platform timeout maximum |
| structured-output support | Whether structured responses are supported | Yes | No | Yes | Must satisfy the structured-output requirement when required |
| tool support | Whether provider tool calling is available | Yes | No | Yes | Optional capability; never a mandatory Core concept |
| `credential_ref` | Reference to secret material held by the Secret Manager | Yes, as a reference | No | Yes, as a ref only | Must resolve during the probe; the value never enters an artifact, release, snapshot, log, telemetry, or audit |

## 25.5 RuntimeSnapshotFactory invariant table

| Invariant | Required Behavior | Forbidden Fallback | Failure Mode | Owner |
| --- | --- | --- | --- | --- |
| Determinism | Same release plus same registry state yields the same content digest, including provenance derived from the pinned `BuildArtifact` | Ambient values, wall-clock in `content`, nondeterministic ordering, environment-read provenance | `FAIL-CLOSED` on any nondeterministic input | CP-004 |
| No partial snapshot | All eighteen steps complete or nothing is returned | Returning a snapshot with unresolved refs | `FAIL-CLOSED` | CP-004 |
| No mixed revisions | Every ref comes from the one active release | Pulling a newer artifact revision outside the release | `FAIL-CLOSED` | CP-004 |
| No stale revoked artifact | Revocation state is checked at resolution | Serving because vectors or caches still exist | `FAIL-CLOSED`; LKG forbidden | CP-004, CP-009 |
| No client-defined active refs | Snapshot selection is trusted runtime state | Client- or LLM-selected release, revision, or snapshot | `REJECT` the request input; `FAIL-CLOSED` | CP-004, CP-010 |
| No secret in snapshot | Only `credential_ref` and masked metadata | Resolved secret cached or embedded | `FAIL-CLOSED` plus sanitized `AUDIT` | CP-004, CP-012 |
| No provider object in snapshot | Provider-neutral refs only | Provider client, SDK object, or raw response | `FAIL-CLOSED` | CP-004, CP-012 |
| Immutable during a request | In-flight requests stay pinned to their original snapshot | Re-reading mutable config mid-request | Activation affects later requests only | CP-004 |
| No default on digest mismatch | Mismatch is terminal | Re-fetching until it matches, or substituting a default | `FAIL-CLOSED` plus `AUDIT` | CP-004, CP-003 |
| No unrelated-release fallback | Only the canonical active release, or valid bounded LKG of it | Falling back to a previous unrelated release | `FAIL-CLOSED` | CP-004 |
| Reference identity (step 10) | Named snapshot refs equal release-pinned refs, revisions, and digests exactly | Accepting a near-match | `FAIL-CLOSED` | CP-004 |
| Build provenance binding | Release pins a qualified `BuildArtifact`; the factory resolves it, verifies revision and digest, and derives or verifies `application_version` and application `source_revision` from its immutable metadata | Reading these from mutable environment configuration or request input; trusting the running process's own version claim | `FAIL-CLOSED` on any mismatch; never defaulted | CP-004, CP-012 |
| Cache returns validated results only | Only fully validated immutable snapshots are cacheable or returnable | Caching unvalidated or partially built snapshots | Discard entry; canonical pull; LKG forbidden if corrupted | CP-004, CP-012 |
| Single-flight resolution | One build per release or digest, shared result | Thundering-herd rebuilds | Bounded contention; cancellation-aware abort | CP-004, CP-012 |
| No authority from resolution | A resolved snapshot grants no read access | Treating snapshot presence as authorization | Authorization remains independent per `ADR-CP-002` and `ADR-CP-003` | CP-004, CP-009 |

## 25.6 LKG failure table

| Condition | LKG Allowed | Required Action | Security Rationale | Future Evidence Needed |
| --- | --- | --- | --- | --- |
| Previously fully validated, all digests known, age within policy maximum, enabled by `ReliabilityPolicy`, no known revoke or disable, cache intact, compatibility valid | Yes | Serve new requests from the bounded LKG snapshot and record degraded mode | Availability concession applies only to unknown control-plane state, never to known-bad state | Approved maximum stale age, `OPEN` |
| Control plane unreachable, all LKG conditions hold | Yes | Bounded LKG plus canonical pull retry and alerting | A brief control-plane outage should not deny all service | Control-plane availability data, `OPEN` |
| Snapshot missing | No | `FAIL-CLOSED` | Nothing validated exists to reuse | None; rule is absolute |
| Digest mismatch exists | No | `FAIL-CLOSED` plus `AUDIT` | A mismatch may indicate substitution or mutation | None; rule is absolute |
| Release revoked | No | `FAIL-CLOSED` | Known revoke outranks cache, LKG, and prior validation | None; rule is absolute |
| Any pinned artifact revoked | No | `FAIL-CLOSED` | A release is only as valid as every artifact it pins | None; rule is absolute |
| `SecurityPolicy` revoked | No | `FAIL-CLOSED` | Serving without a valid security posture is unbounded risk | None; rule is absolute |
| Emergency disable known | No | `FAIL-CLOSED`; never implicitly re-enable | The disable represents a deliberate human decision | None; rule is absolute |
| Maximum stale age exceeded | No | `FAIL-CLOSED` | Unbounded staleness turns revocation into an advisory | Approved revocation propagation budget, `OPEN` |
| Cache corrupted | No | Discard, attempt canonical pull, then `FAIL-CLOSED` | Corrupted state cannot be proven validated | None; rule is absolute |
| Compatibility no longer valid | No | `FAIL-CLOSED` | A once-valid combination may be incompatible after a governance change | Compatibility policy, DEF-016 |
| `ReliabilityPolicy` disables LKG | No | `FAIL-CLOSED` | A deployment or compliance profile may forbid any staleness | Residency and compliance commitments, `OPEN` |
| Invalidation event lost, otherwise healthy | Yes, until TTL or poll converges | Bounded polling or TTL, then canonical pull | Freshness degrades boundedly; authorization correctness is independent | Event delivery reliability data, `OPEN` |

## 25.7 Backend action table

| Action | Required Permission | Validation | Creates Revision | Creates Release | Changes Active Pointer | Audit Required |
| --- | --- | --- | --- | --- | --- | --- |
| View configuration | Read grant for AI configuration | None beyond authorization | No | No | No | Access logging per audit policy |
| Test model configuration | `ai_configuration.manage` | Layers 1 to 3 plus the bounded controlled probe against the intended active combination | No | No | No | Yes, sanitized probe outcome |
| Save and apply | `ai_configuration.manage` | Layers 1 to 6; Layer 5 probe only when the intended active model combination changes, otherwise reuse still-valid pinned evidence | Yes, for changed artifacts only; a successful authorized command may mark that revision `APPROVED`, which in v1 implies no second human | Yes, pinning the complete set | Yes, atomically | Yes, actor, reason, before/after refs, validation report |
| Rollback | `ai_configuration.manage` | Re-verify target eligibility against current revocation and compatibility state | No | No | Yes, atomically | Yes, including the rollback target and reason |
| Revert one artifact to a previous revision | `ai_configuration.manage` | Layers 1 to 6 on the full recomposed combination | No, reuses the previous revision | Yes, a new release | Yes, atomically | Yes |
| Emergency disable | `ai_configuration.manage` | Authorization plus safe reason; no probe required | No | No | Yes, prevents new resolution; never implicitly re-enables | Yes, mandatory actor and safe reason |
| Rotate credential | Credential management grant plus `ai_configuration.manage` where `ModelPolicy` is affected | Bounded health or probe operation; masked metadata only | No, secret material lives in the Secret Manager | Only if `credential_ref` changes | Only if a new release activates | Yes, without any secret value |
| Revoke credential | Credential management grant | Immediate ineligibility of dependent releases for new snapshots | No | No | Indirectly, by making releases ineligible | Yes |
| Inspect active release | Read grant for AI configuration | None beyond authorization | No | No | No | Access logging per audit policy |
| Compare releases | Read grant for AI configuration | None beyond authorization; digest comparison only | No | No | No | Access logging per audit policy |

## Explicit statements

- AI Runtime configuration is global in v1; only `ai_configuration.manage` may change it.
- The administrative flow is `Edit` then `Test Configuration` where required then `Save and Apply`.
- No persistent or user-visible `DraftWorkspace` is a v1 product requirement.
- `ConfigurationRelease` is the atomic unit of activation and rollback, and there is exactly one
  `ActiveConfigurationReleasePointer` in v1.
- Changing one field still produces a complete release that pins every artifact revision and digest.
- A candidate value inside the platform envelope may validate; a candidate value outside it rejects
  `Save and Apply` and leaves the active release unchanged. Values are never clamped silently.
- Narrowing-only precedence applies between policy layers within one candidate release. It does not
  require each new revision to be more restrictive than the previous one, so a `SecurityPolicy` change
  within the platform envelope, including restoring an allowed capability, is permitted when platform
  invariants hold, the complete release validates, and the change is explicit and audited. An emergency
  disable is never implicitly reversed.
- The Layer 5 provider probe is conditional and runs only when the intended active model combination
  changes; unchanged model configuration reuses its still-valid pinned evidence.
- In v1 a successful authorized `SaveAndApplyAIConfiguration` may mark the artifact revision
  `APPROVED`, and `APPROVED` does not imply approval by a second human. Changing that semantic is a
  versioned contract decision.
- `application_version`, `source_revision`, and `build_artifact` are produced from the release-pinned
  qualified `BuildArtifact`, never from mutable environment configuration or request input.
- A new policy artifact carried only inside `ConfigurationRelease` and `config_bundle` may be
  introduced through a versioned `ConfigurationRelease` schema; adding a new dedicated
  `RuntimeSnapshotContent` field requires a `RuntimeSnapshot` contract version event.
- `RuntimeSnapshot 1.0.0` exposes at most sixteen model artifact refs and sixty-four effective feature
  flags. Those limits do not define the total number of other artifact refs inside a
  `ConfigurationRelease`.
- In v1 `source.review` includes permission to read pending source submissions from all departments
  for review, and does not independently grant access to unrelated active or restricted content
  outside the reviewer's required review surface. This remains a `CP-000R` and `CP-001` contract
  dependency, and `ADR-CP-007` and `CP-000B` are not edited here.
- Rollback is release-level; reverting one artifact is expressed as a new validated release.
- Reasoning profiles are administrator-declared, not assumed to be low, medium, or high, and exactly
  one selected active profile is validated before activation.
- The controlled probe proves connectivity and acceptance only; it proves nothing about answer,
  Persian, reasoning, citation, retrieval, or capacity quality, which belong to `CP-013`.
- Probe or validation failure leaves the current active release unchanged and persists no canonical
  revision.
- A known revoke or disable always defeats cache, LKG, previous validation, and current release
  selection.
- `config_bundle` is interpreted as the digest-pinned `ConfigurationRelease` manifest reference;
  `security_policy` is the global runtime policy, not per-source visibility; `index_snapshot` is a
  logical aggregate manifest; `source_revision` is the application revision.
- No secret value and no provider object crosses into Core, a release, a snapshot, a cache, a log,
  telemetry, or an audit record.
- No configuration value is ever an authorization input; authorization remains the trusted decision of
  `ADR-CP-002` and `ADR-CP-003`.
- No numeric TTL, cache size, polling interval, retry value, timeout, rate limit, rollout percentage,
  canary duration, provider, model name, prompt text, or evaluation threshold is fixed in this package.

## Open decisions

| Open decision | Why open | Owning package | Evidence required |
| --- | --- | --- | --- |
| Exact database or storage backend for artifacts and releases | Access patterns and retention volume unknown | CP-003 with CP-012 | Revision volume, query patterns, retention obligations |
| Exact typed contract fields for each artifact | Must follow real capability implementations | CP-001 | Implemented capability inputs and validation needs |
| Exact HTTP/API shape for configuration commands | Depends on typed contracts | CP-010 | Approved contracts |
| Exact Admin Website layout | Product design, not an architecture decision | CP-011 | Usability review with the System AI Administrator |
| Exact LKG maximum stale age | Balances revocation risk against outage tolerance | PERF-001 with CP-012 | Control-plane availability data and an approved propagation budget |
| Exact cache size in entries and memory | Depends on snapshot size and traffic | PERF-001 | Measured snapshot size and concurrency |
| Exact polling interval and TTL | Depends on invalidation reliability | CP-012 | Event delivery reliability measurements |
| Exact retry values | No measured failure distribution | PERF-001 with CP-008 | Provider and control-plane failure rates |
| Exact timeout values | No measured latency distribution | PERF-001 with CP-008 | Latency percentiles under load |
| Exact rate limits | No traffic baseline | PERF-001 | Production QPS and burst profiles |
| Exact rollout percentage | No traffic baseline for canary sensitivity | CP-013 | Regression-detection sensitivity analysis |
| Exact canary duration | Depends on traffic volume and metric stability | CP-013 | Time-to-signal measurements |
| Exact provider | Not selected; selecting one now would be unevidenced | CP-008 with CP-013 | Probe plus evaluation results per candidate |
| Exact model names | Depends on provider selection and qualification | CP-008 with CP-013 | Qualification evidence per model |
| Exact prompt content | Prompt text is a qualified artifact, not an ADR decision | CP-013 | Approved qualification results |
| Exact evaluation thresholds | Requires labelled datasets that do not yet exist | CP-013 | Approved datasets and baseline metrics |
| Exact secret manager provider | Platform and residency choice | CP-012 | Residency requirements and operational review, DEF-022 |
| Exact distributed invalidation mechanism | Depends on deployment topology | CP-012 | Chosen transport and delivery guarantees, DEF-038 |
| Whether per-organization AI overrides are ever introduced | Deferred v1 decision with real demand uncertainty | CP-009 with CP-007 | Documented need plus an enforceable safety model |
| Configuration permission decomposition beyond `ai_configuration.manage` | v1 has one role | CP-009 | Approved separation-of-duties model, DEF-033 |
| Which changes require a `CP-013` evaluation gate before activation | Quality risk differs per artifact type | CP-013 | Regression evidence per artifact class |
| Whether a future contract version renames `config_bundle` and `source_revision` | 1.0.0 must not break | CP-001 | Compatibility policy and consumer inventory |
| Exact probe-evidence freshness and expiry policy | Reusing pinned probe evidence needs a defined validity horizon | CP-008 with CP-013 | Provider credential and model stability data |
| Exact `BuildArtifact` metadata fields and qualification rules | Build provenance format is not yet defined | CP-012 with CP-001 | Approved build provenance format, DEF-101 |
| Exact scoping of the Source Approver review surface | v1 grants cross-department review reading without a defined boundary contract | CP-000R with CP-001 | Approved review-surface definition reconciled with `ADR-CP-007` |

## CP-000R repair dependencies

Recorded, not applied in CP-000D: source management matrix reconciliation; single central Source
Approver for v1; source relationship semantics; `SUPERSEDES` within one `KnowledgeSource`;
`SUPPLEMENTS` across independent `KnowledgeSource` instances; `valid_until` may be null; source
authority metadata; source temporal metadata; minimal Node lifecycle; Guest contract gap; authorized
retrieval scope envelope; isolation metadata subset naming; architecture document status updates;
roadmap status synchronization; deferred-register synchronization.
