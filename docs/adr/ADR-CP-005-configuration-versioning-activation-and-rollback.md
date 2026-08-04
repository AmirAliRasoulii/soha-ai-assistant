# ADR-CP-005: Configuration Versioning, Activation, and Rollback

Status: Accepted architecture baseline (originated as CP-000D; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Date: recorded with the CP-000D architecture package
Owner: Control Plane / Configuration Lifecycle Baseline
Scope: immutable artifact revisions, layered validation, the controlled provider probe,
`ConfigurationRelease`, atomic activation, rollback, revocation, and emergency disable. No typed
Python contract, database schema, HTTP API, approval engine, or provider adapter is decided here.

Companions:

- `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`
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

Verified in Git at this HEAD: `RuntimeArtifactRef` already requires `artifact_id`, `revision`, and
`digest`, so digest pinning is already contractually possible without any change. `RuntimeSnapshot`
already carries `captured_at` and an integrity block with `canonicalization="rfc8785"`.
`AuthorizationDecision` already carries `effect`, `reason_codes`, `policy_version`, and `evaluated_at`,
which is the shape an activation authorization check will consume.

Not typed contracts at this HEAD, therefore conceptual here: `ConfigurationRelease`,
`ActiveConfigurationReleasePointer`, artifact revision lifecycle states, validation report
references, reasoning profiles, `credential_ref`, and the provider probe. `ADR-CP-007` supplies the
precedent for immutable revisions and supersession; this ADR mirrors those semantics for
configuration rather than inventing new ones.

## Context

`ADR-CP-004` fixed what configuration exists and who owns it. It did not say how a change becomes
effective. The Deferred Register records the gap as DEF-023 (safe configuration activation), DEF-031
(artifact registry lifecycle), DEF-034 (configuration auditability), DEF-039 (missing or invalid
artifacts), and DEF-040 (rollback safety and evaluation gates), all `OPEN`.

The operational requirement is asymmetric. The System AI Administrator wants one button. The system
requires reproducibility, meaning every past run must be explainable by an immutable configuration
state, and requires that a bad change be reversible without reconstructing what the previous state
was. Those are compatible only if the simple action generates a complete, immutable, validated unit
rather than a partial edit.

## Problem

- P-1: If a change mutates an artifact in place, no past run can be reproduced and no rollback target
  exists.
- P-2: If each artifact has its own active pointer, a multi-artifact change is observable in a torn
  intermediate state where, for example, a new `RetrievalProfile` is active against an old
  `EvidenceAnswerPolicy` that was never validated with it.
- P-3: If validation happens only per artifact, incompatible-but-individually-valid combinations
  activate.
- P-4: If a model or credential change activates without contacting the provider, the first real user
  request becomes the test, and the failure surface is production.
- P-5: If a failed attempt leaves a persisted artifact revision, the registry accumulates states that
  look legitimate but were never valid.
- P-6: If revocation does not outrank cached and previously validated state, a known-bad artifact
  keeps serving traffic.
- P-7: If rollback can select any earlier state, a revoked or security-invalid release becomes
  reachable again.

## Decision

- D-1: Persisted artifact content is immutable. An active or referenced revision is never edited in
  place. A change creates a new revision.
- D-2: `ConfigurationRelease` is the atomic unit of activation and rollback. It pins every artifact
  ref, every artifact revision, and every content digest for the complete set, not only the changed
  ones.
- D-3: There is exactly one canonical `ActiveConfigurationReleasePointer` for the global AI Runtime
  configuration in v1. Per-artifact active pointers are not the runtime composition source, because
  independent pointers cause configuration tearing.
- D-4: The v1 backend command is conceptually `SaveAndApplyAIConfiguration`. It performs
  authorization, schema validation, hard-bound validation, semantic validation, cross-artifact
  validation, an external model probe only when the intended active model combination changes in a
  way that requires provider validation, canonicalization, digest generation,
  immutable artifact revision creation, `ConfigurationRelease` creation, atomic release activation,
  and audit.
- D-5: Six mandatory validation layers apply, defined below. No artifact is validated only in
  isolation, and Layer 6 validates the exact pinned combination.
- D-6: The bounded controlled probe is conditional. It runs before activation only when the intended
  active combination changes in a way requiring provider validation: provider reference, provider
  model identifier, `credential_ref`, selected reasoning profile or provider value, required response
  mode, or a required structured-output or tool capability. When it runs, it uses the exact intended
  active combination. For an unchanged model configuration, the still-valid pinned validation and
  probe evidence of that exact pinned revision is reused, unless that evidence or a dependency is
  revoked, expired under an approved policy, or otherwise invalid. An unrelated change such as a
  `RetrievalProfile` count must not contact the provider merely because the release also pins an
  unchanged `ModelPolicy`.
- D-7: The probe verifies only credential resolution, model identifier acceptance, reasoning
  configuration acceptance, request format acceptance, and required response shape. It proves nothing
  about answer quality, Persian quality, reasoning correctness, citation faithfulness, retrieval
  quality, or production capacity; those belong to `CP-013`.
- D-8: On any validation or probe failure, no new release becomes active, the current release remains
  unchanged, the failure is returned to the Admin Website, and a safe audit event is recorded. Failed
  attempts do not become active artifact revisions.
- D-9: No user-visible or persistent `DraftWorkspace` is a v1 product requirement. Internal command
  or job records may exist, but a complex draft lifecycle is not exposed.
- D-10: Reasoning profiles are administrator-declared, not assumed to be `low`, `medium`, `high`.
  Each profile carries `reasoning_profile_ref`, `display_name`, `provider_value`, `description`,
  `enabled`. Exactly one active profile is selected per active model configuration in v1, and
  changing it is a configuration change requiring validation again.
- D-11: Rollback is release-level. Reverting a single artifact is expressed as a new release pinning
  that artifact's previous revision together with the current revisions of the others, validated as a
  full combination and activated atomically. An active artifact pointer is never mutated directly.
- D-12: A known revoke or disable always overrides cache, Last-Known-Good, previous validation, and
  current release selection. Revoked and security-invalid releases can never be rollback targets.
- D-13: The System AI Administrator is authorized to invoke `Save and Apply`, rollback, and emergency
  disable in v1. No second AI configuration approver is required. Every action is authenticated,
  authorized, and audited.
- D-14: In v1 a successful authorized `SaveAndApplyAIConfiguration` by the System AI Administrator may
  mark the canonical artifact revision `APPROVED`. In v1, `APPROVED` does not imply approval by a
  second human. A future separation-of-duties workflow may change this semantic through a versioned
  contract decision.

```text
Save and Apply -> ConfigurationRelease

  Admin Website
    Edit  ->  Test Configuration (when required)  ->  Save and Apply
      |
      v  intended new configuration or changed fields (UNTRUSTED input)
  +-------------------------------------------------------------------+
  | Backend / Control Plane: SaveAndApplyAIConfiguration              |
  |                                                                   |
  |  1 authorize ai_configuration.manage        -> deny = stop        |
  |  2 Layer 1 contract/schema validation       -> fail = stop        |
  |  3 Layer 2 platform hard bounds             -> fail = stop        |
  |  4 Layer 3 artifact semantic validation     -> fail = stop        |
  |  5 Layer 4 cross-artifact compatibility     -> fail = stop        |
  |  6 Layer 5 external capability probe        -> fail = stop        |
  |       CONDITIONAL: runs only if the intended active model         |
  |       combination changed (provider ref, model identifier,        |
  |       credential_ref, reasoning profile / provider value,         |
  |       response mode, structured-output or tool capability)        |
  |       otherwise: reuse still-valid pinned probe evidence          |
  |       of the UNCHANGED pinned ModelPolicy revision                |
  |       (bounded, fixed non-sensitive prompt, no user data)         |
  |  7 canonicalize + digest                                          |
  |  8 create immutable revision for CHANGED artifacts only           |
  |       reuse exact existing revisions for UNCHANGED artifacts      |
  |  9 create ConfigurationRelease pinning the COMPLETE set           |
  | 10 Layer 6 release validation of the exact combination            |
  | 11 atomically switch ActiveConfigurationReleasePointer            |
  | 12 audit: actor, reason, before/after refs, validation report     |
  +-------------------------------------------------------------------+
      |                                        |
      | stop at any step:                      | success:
      v   no revision persisted as canonical   v  R(n) ACTIVE
        current release remains ACTIVE            R(n-1) SUPERSEDED, retained
        safe error to Admin Website               invalidation event emitted
        sanitized audit event recorded            (release_ref, revision, digest)
```

## Detailed semantics

### Layered validation

Layer 1, contract and schema validation, checks required fields, types, closed schemas, bounded
collections, canonical identifiers, known artifact types, and valid references. A value that is not
representable is rejected before anything else runs.

Layer 2, platform hard bounds, checks that a configured maximum parallel step count does not exceed
the platform hard maximum, that a configured timeout does not exceed the platform hard maximum, that
minimum security constraints are not weakened, and that no platform-forbidden feature is enabled.
Hard bounds cannot be overridden by Admin Website input. A candidate value inside the platform
envelope may validate; a candidate value outside the platform envelope rejects `Save and Apply` and
the active release remains unchanged. The value is never clamped silently, so that the active
configuration always equals the reviewed configuration.

Layer 3, artifact semantic validation, checks internal coherence: that `minimum_score` is valid, that
`rerank_count` does not exceed `candidate_count`, that `final_evidence_count` does not exceed
`rerank_count` where required, that a default reasoning profile exists, that the selected reasoning
profile is enabled, that a fallback list contains unique model refs, and that `credential_ref` is
present where required. No final numeric production threshold is invented here.

Layer 4, cross-artifact compatibility, checks the pairings that only make sense together:
`RetrievalProfile` against `EvidenceAnswerPolicy`, `ModelPolicy` against `PromptBundle`, `ModelPolicy`
against the structured-output requirement, `EmbeddingArtifact` against `IndexSnapshot`,
`RerankerArtifact` against retrieval output, `FeaturePolicy` against `SecurityPolicy`, and
`ReliabilityPolicy` against platform resource bounds.

Layer 5, external capability validation, is conditional. It runs the controlled probe only when the
intended active combination changes in a way that requires provider validation: a changed provider
reference, a changed provider model identifier, a changed `credential_ref`, a changed selected
reasoning profile or provider value, a changed required response mode, or a changed required
structured-output or tool capability. When the model configuration is unchanged, the layer is
satisfied by reusing the still-valid pinned validation and probe evidence attached to that exact
pinned revision, and no provider contact occurs. That reuse is invalid, and the probe must run again,
if the evidence or any dependency it rests on is revoked, has expired under an approved evidence
freshness policy, or is otherwise invalid. Consequently a change confined to a `RetrievalProfile`
count, a `ConversationPolicy` budget, or any other artifact that does not alter the intended active
model combination never contacts the provider. For future artifact types this layer may include index
compatibility checks, semantic catalog validation, rule-bundle validation, and storage readiness
checks. Every such check stays provider-neutral at the architecture boundary, and the exact evidence
freshness policy is an open decision recorded below.

Layer 6, release validation, validates the exact combination of all pinned revisions in the intended
`ConfigurationRelease`. A release cannot activate if any referenced artifact is missing, invalid,
revoked, disabled, digest-mismatched, schema-incompatible, unapproved where approval is required, or
cross-artifact incompatible.

### Model entries and reasoning profiles

The System AI Administrator manually defines model metadata. A model entry conceptually carries
`model_entry_ref`, `display_name`, `provider_ref`, `provider_model_identifier`, declared
capabilities, reasoning profile definitions, the selected active reasoning profile, max output
constraints, context constraints, a timeout profile, structured-output support, tool support, and
`credential_ref`.

Reasoning profiles are declared by the administrator because providers do not share a vocabulary. A
profile is `reasoning_profile_ref`, `display_name`, `provider_value`, `description`, `enabled`; for
example `reasoning-standard` with display name `Standard` and provider value `standard`. The
provider-specific value stays behind the provider adapter boundary, and Core and `RuntimeSnapshot`
see only the stable provider-neutral ref. Multiple profiles may be declared, but Runtime does not
dynamically choose an unqualified arbitrary provider value; exactly one selected active profile is in
effect, and changing the selection is a configuration change that revalidates and reprobes.

### Controlled provider probe

The probe uses a fixed non-sensitive prompt, carries no user or organization data, requests a very
small output, applies a strict timeout and a bounded request size, performs no retry loop unless
explicitly bounded, returns a sanitized error, records no secret in logs or audit, and lets no
provider response object enter Core. It is implemented through a provider adapter or application
service, never inside Core. On success the immutable revision, the release, and the atomic activation
proceed. On failure `Save and Apply` is rejected, the current release stays active, a safe validation
error is shown, and a sanitized audit event is recorded.

The probe is a connectivity and acceptance check. Treating a green probe as evidence of answer
quality is a category error that this ADR names explicitly so later packages cannot rely on it.

### ConfigurationRelease

A release conceptually contains `release_ref`, `release_revision`, `schema_version`, exact artifact
refs, exact artifact revisions, exact content digests, a compatibility profile or version, validation
report refs, `created_at`, `created_by`, a change reason, `supersedes_release_ref`, a release digest,
and a lifecycle status. The release digest lets a runtime prove it resolved the same release the
control plane activated.

When one field or one artifact changes, the exact existing revisions of unchanged artifacts are
reused, a new immutable revision is created only for the changed artifact, a new release pins the
complete set, the complete set is validated, and the active pointer switches atomically. The
administrator sees a simple operation; the backend preserves reproducibility.

### Lifecycle states

Artifact revision lifecycle is minimal: `VALIDATED`, `APPROVED`, `REVOKED`, `ARCHIVED`. Because v1
requires no user-visible AI draft or review workflow, no complex visible state machine is forced. A
change request may be transient until validation succeeds; once persisted as a canonical revision its
content is immutable.

`APPROVED` has a deliberately narrow meaning in the single-administrator v1 model. v1 has no second AI
configuration approver, so a successful authorized `SaveAndApplyAIConfiguration` performed by the
System AI Administrator may itself mark the canonical artifact revision `APPROVED`. In v1, `APPROVED`
does not imply approval by a second human; it records that the revision passed the mandatory
validation layers and was activated by an authenticated, authorized, audited action. A future
separation-of-duties workflow may change this semantic, and doing so is a versioned contract decision
owned by `CP-001` and `CP-009`, not a configuration change.

Release lifecycle is `VALIDATED` then `ACTIVE` then `SUPERSEDED`, with side states `REJECTED`,
`DISABLED`, `REVOKED`, `ROLLED_BACK`, and `ARCHIVED`.

### Rollback

Baseline rollback selects a previously valid release, verifies it is still eligible against current
revocation state and current compatibility rules, atomically switches the active pointer, and marks
the outgoing release rolled back or superseded as appropriate. Eligibility is re-verified rather than
assumed, because a syntactically valid previous release may reference an artifact revoked since it
was active. This is DEF-040 and it is why rollback is not a pointer assignment.

### Revocation and emergency disable

Revoking an artifact revision makes every release containing it ineligible for new snapshots.
Revoking or disabling a release prevents new requests from resolving it. Emergency disable must be
authenticated, authorized, carry actor and safe reason, be audited, and must never implicitly
re-enable; re-enabling requires an explicit valid `Save and Apply` or activation action. A known
revoke or disable defeats cache and Last-Known-Good, which `ADR-CP-006` restates as a runtime rule.

```text
Atomic activation, rollback, and revocation

  RELEASES (immutable, retained)
    R10 SUPERSEDED    R11 SUPERSEDED    R12 ACTIVE        R13 VALIDATED
     |                 |                 |                 |
     |                 |                 |                 +-- not yet active
     |                 |                 |
     |                 |                 +-- ActiveConfigurationReleasePointer -> R12
     |                 |
     |                 +-- eligible rollback target IF re-verified now
     |                       (all pinned revisions still non-revoked,
     |                        still schema-compatible, still cross-compatible)
     |
     +-- INELIGIBLE if it pins a revoked revision, even though it once worked

  ACTIVATION (forward)               ROLLBACK (backward)
    validate R13 fully                 select R11
    pointer: R12 -> R13 (atomic)       re-verify eligibility  -> fail = stop
    R12 -> SUPERSEDED                  pointer: R12 -> R11 (atomic)
    emit invalidation event            R12 -> ROLLED_BACK / SUPERSEDED
                                       emit invalidation event

  SINGLE-ARTIFACT REVERT is not a pointer edit:
    new R14 = { previous revision of artifact X } + { current revisions of others }
    -> validate full combination -> activate atomically

  REVOCATION / EMERGENCY DISABLE (outranks everything)
    revoke artifact revision  -> every release pinning it becomes ineligible
    revoke or disable release -> new requests cannot resolve it
    known revoke or disable   -> defeats cache, defeats LKG, defeats prior validation
    re-enable                 -> only via explicit Save and Apply or activation
    never                     -> implicit re-enable, silent downgrade, partial apply
```

## Ownership

The System AI Administrator holding `ai_configuration.manage` owns `Save and Apply`, rollback, and
emergency disable in v1. Platform and Governance own the hard bounds enforced at Layer 2 and the
canonicalization and digest algorithms. The Control Plane owns revision creation, release creation,
activation, retention, and audit. Provider adapters own probe execution; Core owns none of it. The
Source Approver's authority over content eligibility is a precondition for indexing, not a step in
configuration activation.

## Security invariants

- SI-1: A persisted canonical revision is immutable; in-place edit of an active or referenced
  revision is impossible by construction.
- SI-2: Activation is atomic at the product-contract level; no partially applied configuration is
  observable.
- SI-3: Exactly one active release pointer composes runtime configuration in v1; no torn combination
  can be resolved.
- SI-4: A release activates only if the exact pinned combination validated.
- SI-5: Failed validation or a failed probe never mutates the active pointer and never persists an
  active revision.
- SI-6: A known revoke or disable overrides cache, Last-Known-Good, prior validation, and current
  release selection.
- SI-7: Revoked or security-invalid releases are never rollback targets.
- SI-8: Emergency disable never implicitly re-enables.
- SI-9: The probe carries no user or organization data and no secret, and no provider object crosses
  into Core.
- SI-10: Every activation, rollback, revocation, and disable action is authenticated, authorized, and
  audited with actor and safe reason.

## Failure behavior

| Failure | Architectural behavior |
| --- | --- |
| Authorization denied for `Save and Apply` | Fail closed; no revision, no release; audit the denied attempt |
| Layer 1 schema failure | Reject; no revision persisted as canonical |
| Layer 2 hard-bound violation | Reject; never clamp silently; current release remains active |
| Layer 3 semantic failure | Reject with a safe field-level error; no release created |
| Layer 4 incompatibility | Reject the combination even if each artifact is individually valid |
| Probe timeout or rejection | Reject `Save and Apply`; current release stays active; sanitized audit event |
| Probe succeeds but release validation fails | Reject; a green probe never bypasses Layer 6 |
| Digest mismatch on a pinned revision | Reject the release; treat the artifact as untrusted |
| Referenced artifact revoked mid-activation | Abort activation; pointer unchanged |
| Activation write fails after validation | Pointer remains on the previous release; retry is permitted because validation is idempotent |
| Rollback target no longer eligible | Refuse the rollback; report which pinned revision is ineligible |
| Invalidation event not delivered | Runtime bounded polling or TTL converges; stale state is never treated as authorized |
| Audit sink unavailable | Treat as an activation failure; an unauditable production change is not permitted |

## Alternatives considered

Per-artifact active pointers were considered because they make a one-field change appear cheap. They
were weighed against the tearing risk in P-2 and rejected: with eight artifacts and no combination
validation, the number of reachable unvalidated combinations grows faster than any test suite. A
full evaluation gate before every activation was also weighed, since it would catch quality
regressions that a probe cannot. It was deferred rather than adopted because an evaluation run is
slow and dataset-dependent, and requiring it for every retrieval-count tweak would push
administrators toward out-of-band changes; `CP-013` owns the question of which changes require an
evaluation gate.

## Alternatives rejected

| Alternative | Why rejected |
| --- | --- |
| Mutable artifact edited in place | Destroys reproducibility and leaves no rollback target |
| Independent per-artifact active pointers | Configuration tearing; unvalidated combinations become reachable |
| Per-artifact validation only | Individually valid, jointly broken configurations activate |
| Activating a model change without a probe | Makes the first production request the test |
| Treating the probe as a quality gate | Confuses connectivity with answer, Persian, and citation quality |
| Persisting failed attempts as revisions | Registry accumulates states that were never valid |
| Persistent user-visible `DraftWorkspace` in v1 | Product surface without a real second reviewer |
| Requiring a second AI configuration approver in v1 | No second qualified reviewer exists; the workflow would be bypassed or block all changes |
| Silently clamping an out-of-bound value | Active configuration would differ from the reviewed configuration |
| Rollback by direct pointer assignment without re-verification | Can reactivate a release pinning a revoked revision |
| Reverting one artifact by editing its pointer | Produces a combination that was never validated |
| Allowing revoked releases as rollback targets | Reintroduces known-bad state through a legitimate-looking action |
| Implicit re-enable after emergency disable | Removes the deliberate human decision the disable represented |
| Shipping full configuration inside the activation event | Makes the event a second source of truth |

## Consequences

Every activation produces a complete, immutable, validated, digest-pinned description of runtime
behavior, so any past run is explainable and any bad change is reversible by selecting a retained
release. The administrator experience stays a single button.

The costs are real. Every change writes a full release, so release volume grows with edit frequency
and retention becomes a storage and garbage-collection concern owned by `CP-003`. Rollback requires
re-verification, so it can legitimately fail, and operators must be told why rather than being given
a retry. Layer 4 means an artifact cannot be changed in isolation, so an incompatible pair blocks a
change that looks locally valid. And because Layer 5 is conditional, a provider outage blocks only
those changes that actually alter the intended active model combination; a change confined to another
artifact still activates by reusing the unchanged model configuration's still-valid pinned evidence.
The residual coupling is therefore narrow but real: a genuine model, credential, reasoning-profile, or
response-mode change cannot activate while the provider is unreachable, and bounding the probe limits,
but does not remove, that coupling.

## Contract implications

- The release manifest must be expressible as one `RuntimeArtifactRef`, so `release_ref`,
  `release_revision`, and the release digest map onto `artifact_id`, `revision`, and `digest`.
  `ADR-CP-006` fixes that this is `RuntimeSnapshotContent.config_bundle`. Version 1.0.0 is unchanged.
- Digests must be `sha256:` with sixty-four lowercase hexadecimal characters to satisfy the existing
  contract pattern; an uppercase or padded digest is a rejection, not a repair.
- `AuthorizationDecision` is the expected shape for the activation authorization check;
  `ai_configuration.manage` becomes an action code consumed there.
- Typed contracts for `ConfigurationRelease`, artifact revisions, and validation reports are owned by
  `CP-001` and are not defined here, per DEF-030 and DEF-031.

## Package ownership

| Concern | Owning package |
| --- | --- |
| Typed release and artifact contracts | CP-001 |
| Artifact registry, immutable revisions, retention, garbage collection | CP-003 |
| Snapshot resolution consuming the active pointer | CP-004 |
| Model entries, reasoning profiles, credential pool, probe execution | CP-008 |
| `SaveAndApplyAIConfiguration`, rollback, disable, audit | CP-009 |
| API surface for configuration commands | CP-010 |
| Admin Website `Edit` then `Test` then `Save and Apply` flow | CP-011 |
| Provider adapters and secret manager integration | CP-012 |
| Which changes require an evaluation gate | CP-013 |
| Cross-document consistency repairs | CP-000R |

## Open decisions

| Open decision | Why open | Owning package | Evidence required |
| --- | --- | --- | --- |
| Exact probe timeout and bounded retry values | No measured provider latency distribution exists | CP-008 with PERF-001 | Provider response-time percentiles under load |
| Exact release retention depth and garbage-collection policy | Depends on real edit frequency and audit requirements | CP-003 | Edit-rate telemetry and retention obligations |
| Which changes require a `CP-013` evaluation gate before activation | Quality risk differs per artifact type | CP-013 | Regression evidence per artifact class |
| Exact rollout percentage and canary duration | No production traffic baseline | CP-013 with PERF-001 | Traffic volume and regression-detection sensitivity |
| Exact distributed invalidation mechanism | Depends on deployment topology | CP-012 | Chosen queue or bus and delivery guarantees |
| Exact storage backend for releases and revisions | Access patterns not yet known | CP-003 with CP-012 | Revision volume and query patterns |
| Exact HTTP/API shape of configuration commands | Depends on typed contracts | CP-010 | Approved contracts |
| Whether artifact `APPROVED` ever requires a distinct approver | v1 deliberately has one role and `APPROVED` implies no second human | CP-009 with CP-001 | Documented separation-of-duties requirement, DEF-033 |
| Exact probe-evidence freshness and expiry policy | Reuse of pinned probe evidence needs a defined validity horizon | CP-008 with CP-013 | Provider credential and model stability data |
| Exact secret manager provider and rotation cadence | Platform and residency choice | CP-012 | Residency requirements and operational review, DEF-022 |
| Exact provider and model names | Not selected; selecting one here would be unevidenced | CP-008 with CP-013 | Probe plus evaluation results per candidate |
| Exact prompt content of the probe | Must be non-sensitive and stable; wording is an implementation detail | CP-008 | Reviewed fixed prompt with no user data |

## Migration and evolution notes

Nothing is migrated at this HEAD because no code exists. Forward rules: adding a validation layer is
a backwards-compatible strengthening and does not require a contract version bump, but it may make
previously eligible rollback targets ineligible, which must be reported rather than hidden. Adding a
release lifecycle side state is a contract change owned by `CP-001`. Introducing scoped configuration
later would require a second pointer dimension and must not be retrofitted by adding per-artifact
pointers, since that reintroduces P-2.

If this ADR is found inconsistent with an already committed ADR, the committed ADR is preserved and
the conflict is recorded for architect review in `CP-000R`.

## Traceability

- Depends on: `ADR-CP-004`, `ADR-CP-001`, `ADR-CP-002`, `ADR-CP-003`, `ADR-CP-007`, `CP-000A`,
  `CP-000B`, `CP-000C`, RuntimeSnapshot 1.0.0.
- Consumed by: `ADR-CP-006` (the factory resolves the pointer and release defined here).
- Deferred Register: DEF-022, DEF-023, DEF-031, DEF-032, DEF-033, DEF-034, DEF-039, DEF-040.
- Repairs recorded for `CP-000R`, not applied here: the fifteen items listed in the traceability
  section of `ADR-CP-004`.
