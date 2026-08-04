# CP-000R Architecture Consistency Repair

Status: Accepted architecture baseline (originated as CP-000R; CP-000R consistency repair applied, and CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Scope: documentation consistency repair only. This package reconciles confirmed contradictions across
the accepted architecture documents, records every confirmed implementation gap under its correct
future package, and repairs governance and status metadata. **No Python code, typed contract, JSON
Schema, database model, HTTP API, Django integration, adapter, migration, or test is created or
changed by this package, and no contract version is bumped.**

Base branch: `main`
Base commit: `6477c1c`
Sequence: `CP-000R -> CP-000E -> CP-001`

Companions:

- `docs/architecture/architecture-authority-manifest.md`
- `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md`
- `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`
- `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md`
- `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`
- `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`
- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
- `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md`
- `docs/control-plane/CP-000A-authorization-matrix.md`
- `docs/control-plane/CP-000B-source-lifecycle-matrix.md`
- `docs/control-plane/CP-000C-index-isolation-blueprint.md`
- `docs/control-plane/CP-000D-configuration-catalog.md`
- `docs/deferred-items.md`
- `docs/walking-skeleton-1.0.0.md`

## Precedence used by this repair

```text
committed implementation and typed contracts
  -> accepted CP ADRs
  -> explicit architect-approved decisions taken after the audit
  -> integrated audit repair requirements
  -> canonical delivery roadmap
  -> newer supporting architecture sources
  -> legacy documents
```

No document was altered to claim implementation that Git does not contain. Where documentation and Git
disagreed about whether something exists, Git won and the documentation was corrected downward.

## Post-audit overriding decisions applied

| Decision | Applied as |
| --- | --- |
| A single **System AI Administrator** holds `ai_configuration.manage`; there is no second human approver in v1, and `APPROVED` does not imply approval by a second person | CP-000D documents left intact and cross-referenced; the superseded `Technical Admin drafts / Global System Admin approves / drafter != approver` model is **not** restored |
| One centrally assigned **Central Source Approver** holds `source.review`, `source.approve`, `source.reject`; contributors hold `source.create`, `source.upload`, `source.edit_own_draft`, `source.submit`; `source.review` includes reading pending submissions from all departments. The same principal must not approve a submission they created, authored, uploaded, or submitted | `ADR-CP-007` "Source approval workflow (v1)"; `CP-000B` canonical matrix. No per-faculty or per-department approver is introduced in v1, and the mandatory same-principal self-approval prohibition remains in force |
| **Activation is not a human approver permission in v1.** `source.approve` records business approval; once all validation, ingestion and index gates pass, the Control Plane application service may transition the revision to `ACTIVE`; activating a newer same-source revision automatically marks the previous active revision `SUPERSEDED`. The `ACTIVE` transition and the `SUPERSEDED` effect are lifecycle and application-service operations, not additional human-facing v1 permissions, and neither Department Contributor nor Central Source Approver receives `disable`, `revoke`, `archive`, or purge capability automatically | `ADR-CP-007` `AP-7`, `AP-8`, `V-5` and the corrected failure-condition rows; `CP-000B` matrix rows for activation and supersession plus statements 23, 25 and 26. Whether the transition occurs in the same command or in a separate application-service step remains CP-009 work |
| `PINNED_VISIBILITY_POLICY_REVISION`: no implicit follow-latest, no model-selected revision, no client-selected revision; missing revision fails closed; inactive or revoked revision makes the source ineligible; audit records carry the exact consulted revision; rebinding never mutates an active `SourceRevision` in place | `ADR-CP-002` "Pinned visibility policy binding" (`B-1`..`B-9`); `ADR-CP-007` `R-5A`; `CP-000B` statement 13 |

## Dispositions used in the ledger

| Disposition | Meaning |
| --- | --- |
| `REPAIRED_IN_DOCUMENTATION` | The contradiction or omission is fixed in the authorized documents by this package |
| `DECISION_CLOSED` | An open architectural question is now closed by an explicit accepted decision |
| `DOCUMENTED_IMPLEMENTATION_GAP` | The decision is recorded; the implementation does not exist and is now tracked with an owner |
| `DEFERRED_WITH_OWNER` | Deliberately not decided here; assigned to a named future package with the evidence it needs |
| `RESIDUAL_AUDIT_LIMITATION` | A limitation of the audit itself that documentation cannot remove |

## Repair ledger

### Confirmed contradictions (C-001 .. C-008)

| Finding ID | Finding | Disposition | Files Changed | Future Package Owner | Remaining Implementation Work | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| C-001 | CP-000A and CP-000B state conflicting source-action permissions (HIGH) | `REPAIRED_IN_DOCUMENTATION` | `CP-000A-authorization-matrix.md`, `CP-000B-source-lifecycle-matrix.md`, `ADR-CP-007` | CP-001 with CP-009 | Implement the permission checks behind the canonical matrix | CP-000A now contains "Scope of this matrix" plus a "Delegated source actions" list and a single `DELEGATED` row; CP-000B declares "Canonical scope" and carries the 7-actor matrix |
| C-002 | Visibility policy binding was ambiguous between `PINNED_REVISION` and `FOLLOW_ACTIVE_POLICY` (HIGH, previously OPEN) | `DECISION_CLOSED` | `ADR-CP-002`, `ADR-CP-007`, `CP-000B` | CP-002 with CP-005 | Typed pinned-revision reference and the versioned audited rebinding migration | `ADR-CP-002` "Pinned visibility policy binding" `B-1`..`B-9`; `ADR-CP-007` `R-5A`; `CP-000B` statement 13 |
| C-003 | "View source metadata" conflated citation metadata with internal management metadata (HIGH privacy and data minimization) | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-007`, `CP-000B`, `CP-000A`, `evidence-1.0.0.md`, `final-answer-1.0.0.md` | CP-001 with CP-009 | Implement the four separately permissioned resources (`DEF-119`) | `ADR-CP-007` "Source metadata classes" table with the four classes; CP-000B rows for the four read actions; CP-000B statements 9 and 10 |
| C-004 | Deny handling. **Re-scoped by CP-000R against the committed contract (`CONTRACT_FACT`):** `RouteLane` already contains `deny`, and `_TERMINAL_LANES` already contains `deny` alongside `clarify` and `abstain`. The audit statement that the contract lacks a deny lane is not correct. The real gap is that the bounded Runtime and Walking Skeleton do not yet provide complete terminal handling for `RouteDecision(lane="deny")` | `DOCUMENTED_IMPLEMENTATION_GAP` | `route-decision-1.0.0.md`, `error-envelope-1.0.0.md`, `walking-skeleton-1.0.0.md`, `deferred-items.md`, `architecture-authority-manifest.md` | AI-002 (Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, Bounded Replan) | Implement complete terminal handling for `RouteDecision(lane="deny")`; keep `UNAUTHORIZED` (authorization deny, before routing) distinct from `POLICY_REJECTED` (route or policy deny, zero budget, no capability execution) (`DEF-118`) | Contract fact verified in `src/ai_assistant/contracts/route_decision.py`; corrected notes in `route-decision-1.0.0.md`, `error-envelope-1.0.0.md`, and the Walking Skeleton; rewritten `DEF-118` |
| C-005 | Clarification and abstention are surfaced as errors (MEDIUM, intentional transition) | `REPAIRED_IN_DOCUMENTATION` | `error-envelope-1.0.0.md`, `route-decision-1.0.0.md`, `walking-skeleton-1.0.0.md` | AI-002 with AI-006 | Move clarification and abstention out of the error envelope (`DEF-118`) | "transitional" wording present in all three documents |
| C-006 | `runtime.turn.completed` is emitted before durable idempotency completion (HIGH audit semantics) | `DOCUMENTED_IMPLEMENTATION_GAP` | `audit-event-1.0.0.md`, `walking-skeleton-1.0.0.md`, `deferred-items.md` | CP-001 for typed audit contracts and future versioning, CP-009 for application-service audit semantics and emission, CP-012 for durable persistence and delivery adapters, AI-002 for request and run lifecycle and terminal transitions, AI-007 for answer-finalization and publication hooks | Resolve ordering or rename the event (`DEF-115`). Durable completion is not implemented today | "pre-completion" wording in both documents; split audit ownership; `DEF-115` |
| C-007 | Document status lines contradicted actual Git state (HIGH governance) | `REPAIRED_IN_DOCUMENTATION` | All 7 CP ADRs, all 4 CP matrices/catalogs, all 12 contract docs, `walking-skeleton-1.0.0.md` | Governance | None; status accuracy is now a governance rule | Every CP ADR and matrix carries an `Accepted architecture baseline` status line recording that the CP-000R consistency repair was applied and that CP-000R acceptance becomes effective when the CP-000R commit is reviewed and merged; every contract reads `Accepted and implemented as a bounded baseline` with base repository evidence `6477c1c`; the Walking Skeleton reads `Accepted and implemented bounded in-process baseline` |
| C-008 | The canonical delivery roadmap drifted after the CP-000A/B/C/D merges (`ROADMAP_MAPPING`, MEDIUM-HIGH governance) | `REPAIRED_IN_DOCUMENTATION` | `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` (new) | Governance | Keep the roadmap updated at each package acceptance | The roadmap **body itself** was repaired, not merely prefixed: stale `CP-000A`/`CP-000B`/`CP-000C` phase statements rewritten, obsolete `hard bounds -> platform -> organization -> node` precedence replaced by `Platform hard bounds -> active global ConfigurationRelease -> trusted request authorization and source metadata -> immutable RuntimeSnapshot`, accepted CP-000D decisions recorded, canonical CP-001..CP-014 and AI-001..AI-010 maps retained, and AI-002 explicitly carries Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, and Bounded Replan. Re-verified in R3: the false `(verbatim)` heading was removed, the stale active-work section was replaced by the authoritative package-status block, the `Effective baseline commit` wording became `Base repository evidence commit`, and the two-person open decision became future configurable separation-of-duties rules beyond the accepted v1 single System AI Administrator and Central Source Approver models. No contradictory current status remains |

### Confirmed gaps (G-001 .. G-022)

| Finding ID | Finding | Disposition | Files Changed | Future Package Owner | Remaining Implementation Work | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| G-001 | Source authority binding. **Re-scoped by CP-000R against the committed contract (`CONTRACT_FACT`):** `_EvidenceBase` already carries `authority` as a controlled canonical code, so Evidence is not authority-blind. The real gap is that this code is not bound to trusted Source Registry authority metadata: `authority_class_ref`, `issuer_ref` / `authority_ref`, `authority_assignment_policy_ref` | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-007`, `CP-000B`, `CP-000C`, `evidence-1.0.0.md`, `answer-plan-1.0.0.md`, `deferred-items.md`, `architecture-authority-manifest.md` | CP-001 with CP-005 (Department Source Registry) | Bind the controlled `authority` code to trusted registry authority metadata, add the versioned authority catalog and the deterministic conflict-precedence function (`DEF-103`) | Contract fact verified in `src/ai_assistant/contracts/evidence.py`; `ADR-CP-007` `AU-1`..`AU-7`; `CP-000C` 18.5 dependency row; rewritten `DEF-103` |
| G-002 | Source temporal derivation. **Re-scoped by CP-000R against the committed contract (`CONTRACT_FACT`):** typed temporal metadata already exists as `EvidenceValidityWindow` (`as_of`, `valid_from`, `valid_to`) and `EvidenceSourceTime` (`observed_at`, `published_at`), with ordering validation. The real gap is that these values are not deterministically derived from, or revalidated against, `SourceRevision.effective_from`, `SourceRevision.valid_until`, and current Source Registry lifecycle state | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-007`, `ADR-CP-003`, `CP-000C`, `CP-000B`, `evidence-1.0.0.md`, `query-analysis-1.0.0.md`, `deferred-items.md`, `architecture-authority-manifest.md` | CP-001 with CP-005 and CP-006 (Ingestion and Index Lifecycle) | Derive and revalidate evidence temporal values from trusted `SourceRevision` state; `valid_until` remains nullable (`DEF-104`) | Contract fact verified in `src/ai_assistant/contracts/evidence.py`; `ADR-CP-007` `T-1`..`T-7`; `ADR-CP-003` `L-9A`..`L-9C`; rewritten `DEF-104` |
| G-003 | No node lifecycle or structural-change model | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-001`, `CP-000A`, `deferred-items.md` | CP-001 / CP-002 with CP-009 / CP-010 | Implement typed lifecycle contracts, create/rename/move application services, audit and cache invalidation, and the API/read-model boundary (`DEF-105`) | `ADR-CP-001` "Node lifecycle and structural change" `L-1`..`L-9`; `I-2a`; CP-000A "move or re-parent node" row |
| G-004 | No authorization request/decision binding | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-002`, `security-authorization-1.0.0.md`, `turn-input-1.0.0.md`, `deferred-items.md` | CP-001 with CP-002 | Typed `AuthorizationRequest`, expiry enforcement, consulted-policy and scope refs (`DEF-106`) | `ADR-CP-002` "Future authorization contract obligations" `O-1`..`O-10`; `DEF-106` |
| G-005 | No retrieval authorization envelope | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-002`, `ADR-CP-003`, `execution-plan-1.0.0.md`, `security-authorization-1.0.0.md`, `deferred-items.md` | CP-002 with AI-003 | Typed `RetrievalAuthorizationEnvelope` carrying the pre-filter inputs (`DEF-107`) | `ADR-CP-002` `O-4`; `DEF-107` |
| G-006 | Guest has no typed contract representation | `DOCUMENTED_IMPLEMENTATION_GAP` | `ADR-CP-002`, `security-authorization-1.0.0.md`, `turn-input-1.0.0.md`, `deferred-items.md` | CP-001 with CP-002 | First-class typed `AnonymousGuest` principal (`DEF-108`) | `ADR-CP-002` `O-5` and `O-6`; `DEF-108` |
| G-007 | No evidence eligibility validator (`AUDIT_FINDING`) | `DOCUMENTED_IMPLEMENTATION_GAP` | `step-result-1.0.0.md`, `evidence-1.0.0.md`, `deferred-items.md` | AI-003 (Retrieval Engine) with AI-006 (Hybrid Execution and Evidence Composition) | Deterministic per-unit validation covering authorized scope membership, organization, classification ceiling, source active state, source revision eligibility, source digest, effective time, authority, the `SUPERSEDES` / `SUPPLEMENTS` relation, and current revocation state (`DEF-109`) | Expanded limitation note in `step-result-1.0.0.md`; rewritten `DEF-109` |
| G-008 | No minimal `GenerationRequest` boundary (`AUDIT_FINDING`) | `DOCUMENTED_IMPLEMENTATION_GAP` | `answer-plan-1.0.0.md`, `deferred-items.md` | AI-007 (Answer Planning, Citation and Validation) | Define the minimal typed generation boundary carrying only the sanitized question, approved claims, approved caveats, bounded authorized evidence content, answer constraints, and response locale, and never the full `RuntimeContext`, the full principal, roles or groups, the `AuthorizationDecision`, raw source-management metadata, or provider credentials (`DEF-110`) | Expanded limitation note in `answer-plan-1.0.0.md`; rewritten `DEF-110` |
| G-009 | No evidence content resolver (`AUDIT_FINDING`) | `DOCUMENTED_IMPLEMENTATION_GAP` | `evidence-1.0.0.md`, `deferred-items.md` | AI-007 Answer Planning, Citation and Validation as primary owner, with CP-006 Ingestion and Index Lifecycle as the source and index lifecycle dependency and CP-012 Production Adapters as the production adapter dependency, matching `DEF-111` | Bounded trusted resolution of evidence content and opaque locators with authorization, citation-safe display metadata, and historical-revision resolvability (`DEF-111`) | Split owner row in `evidence-1.0.0.md`; `DEF-111` ownership aligned to AI-007 with CP-006 |
| G-010 | No semantic claim validation (`AUDIT_FINDING`) | `DOCUMENTED_IMPLEMENTATION_GAP` | `evidence-1.0.0.md`, `answer-plan-1.0.0.md`, `final-answer-1.0.0.md`, `deferred-items.md` | AI-007 (Answer Planning, Citation and Validation) with CP-013 (Evaluation and Rollout Gates) | Deterministic numeric checks, semantic faithfulness and entailment checking, unsupported-claim rejection, bounded repair, and safe abstention or fallback (`DEF-112`) | Limitation notes in `answer-plan-1.0.0.md` and `final-answer-1.0.0.md`; rewritten `DEF-112` |
| G-011 | Revocation race. The exact finding is that **retrieval succeeds, then the source or policy is revoked, before finalization and publication**. It is not a difference between authorization-decision time and retrieval time | `DOCUMENTED_IMPLEMENTATION_GAP` | `security-authorization-1.0.0.md`, `evidence-1.0.0.md`, `final-answer-1.0.0.md`, `ADR-CP-002`, `deferred-items.md` | AI-007 (Answer Planning, Citation and Validation) with CP-006 (Ingestion and Index Lifecycle) | Deterministic current-eligibility and revocation recheck **before final answer publication**, plus the invalidation propagation budget and fail-closed behaviour (`DEF-113`). Not implemented today | `ADR-CP-002` `B-9`; limitation notes in `security-authorization-1.0.0.md`, `evidence-1.0.0.md`, and `final-answer-1.0.0.md`; rewritten `DEF-113` |
| G-012 | Audit outcome taxonomy incomplete | `DOCUMENTED_IMPLEMENTATION_GAP` | `audit-event-1.0.0.md`, `walking-skeleton-1.0.0.md`, `deferred-items.md` | CP-001 for the typed contract, CP-009 for emission semantics, AI-002 for terminal lifecycle transitions, AI-007 for finalization hooks | Type `answered`, `partial`, `clarification_required`, `abstained`, `policy_rejected`, `authorization_denied`, `failed` (`DEF-114`) | Taxonomy listed in `audit-event-1.0.0.md` and the Walking Skeleton limitations; `DEF-114` |
| G-013 | Runtime lineage not carried in audit (`AUDIT_FINDING`). The complete future lineage requirement is organization, actor scope, subject, time scope, source version, policy version, `ConfigurationRelease`, `RuntimeSnapshot`, and run or request identifier | `DOCUMENTED_IMPLEMENTATION_GAP` | `audit-event-1.0.0.md`, `walking-skeleton-1.0.0.md`, `deferred-items.md` | CP-001 for the typed lineage contract, CP-009 for application-service emission, CP-012 for durable persistence and delivery, AI-002 for request and run lifecycle, AI-007 for answer-finalization and publication hooks | Carry the complete nine-element runtime lineage in audit records (`DEF-115`). No current contract carries the complete lineage, and no document claims it does | Corrected limitation notes in `audit-event-1.0.0.md` and the Walking Skeleton; rewritten `DEF-115` |
| G-014 | `RuntimeSnapshot.source_revision` is misleading | `DEFERRED_WITH_OWNER` | `runtime-snapshot-1.0.0.md`, `deferred-items.md` | CP-001 | vNext rename to `application_source_revision`; no version bump is authorized here (`DEF-116`) | Limitation note naming the intended vNext rename; `DEF-116` |
| G-015 | `RuntimeArtifactRef` has no namespace | `DEFERRED_WITH_OWNER` | `runtime-snapshot-1.0.0.md`, `deferred-items.md` | CP-001 with CP-004 | Add a namespace to prevent cross-family artifact-id collisions (`DEF-116`) | Limitation note in `runtime-snapshot-1.0.0.md`; `DEF-116` |
| G-016 | `security_policy` meaning ambiguous | `REPAIRED_IN_DOCUMENTATION` | `runtime-snapshot-1.0.0.md`, `ADR-CP-002`, `deferred-items.md` | CP-004 with CP-002 | Disambiguate in the vNext contract (`DEF-116`) | `runtime-snapshot-1.0.0.md` states it is the global `SecurityPolicy` artifact, not a per-source `VisibilityPolicyDefinition`; `ADR-CP-002` `O-8` |
| G-017 | `index_snapshot` aggregate semantics undefined | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-003`, `CP-000C`, `runtime-snapshot-1.0.0.md`, `deferred-items.md` | CP-006 | Typed aggregate manifest with routing metadata (`DEF-117`) | `ADR-CP-003` `S-7A` and `S-7B`; `CP-000C` 18.6; limitation note in `runtime-snapshot-1.0.0.md` |
| G-018 | `config_bundle` duplicates the release manifest | `DOCUMENTED_IMPLEMENTATION_GAP` | `runtime-snapshot-1.0.0.md`, `deferred-items.md` | CP-004 with CP-006 | Enforce exact factory equivalence between release manifest and snapshot refs (`DEF-117`) | Limitation note in `runtime-snapshot-1.0.0.md`; `DEF-117` |
| G-019 | Metadata subset naming was ambiguous against the complete chunk metadata contract | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-003`, `CP-000C`, `deferred-items.md` | CP-006 | Own the complete indexed-unit metadata contract; may add fields, never remove one (`DEF-119`) | `ADR-CP-003` "Mandatory Isolation Metadata Subset"; `CP-000C` heading 18.1 and its CP-006 boundary paragraph |
| G-020 | Public node metadata exposure undecided | `DECISION_CLOSED` | `ADR-CP-001`, `CP-000A`, `deferred-items.md` | CP-001 / CP-002 with CP-009 / CP-010 | Implement the explicit publication/directory policy, application service, and API/read-model boundary (`DEF-105`); this is not CP-007 work | `ADR-CP-001` "Node metadata publication" `P-1`..`P-4` (default deny, Guest denied); CP-000A statement 10 |
| G-021 | Deferred register drifted from repository state | `REPAIRED_IN_DOCUMENTATION` | `deferred-items.md` | Governance | Keep the register synchronized at each package acceptance | Register version `0.6.0`, introduced by CP-000R and not present at `6477c1c`; base repository evidence `main` / `6477c1c`; latest accepted baseline CP-000D; recalculated counts |
| G-022 | Tests and JSON Schemas were not independently audited | `RESIDUAL_AUDIT_LIMITATION` | `deferred-items.md` | CP-013 with Governance | Independent review of the committed test suite and schemas (`DEF-120`) | Evidence-basis note states the audit did not independently audit tests or schemas; `DEF-120` |

### New findings raised during integration (NEW-001 .. NEW-007)

| Finding ID | Finding | Disposition | Files Changed | Future Package Owner | Remaining Implementation Work | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| NEW-001 | `SUPPLEMENTS` cannot be modeled as two active revisions of one `KnowledgeSource` | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-007`, `CP-000B`, `CP-000C`, `deferred-items.md` | CP-001 with CP-005 and CP-006 | Typed `SourceRelationship`, trusted registry behavior, and partial-amendment semantics (`DEF-121`) | `ADR-CP-007` "Source relationships" `SR-1`..`SR-7`; `CP-000B` statement 14; `CP-000C` 18.7 fixture row |
| NEW-002 | Architecture documents need an authority and supersession manifest, and the model must not guess the latest document | `REPAIRED_IN_DOCUMENTATION` | `docs/architecture/architecture-authority-manifest.md` (new) | Governance | Maintain the manifest at each package acceptance | Manifest exists with `document_ref`, `status`, `decision_scope`, `owner`, `supersedes_refs`, `augments_refs`, and an explicit no-guessing rule |
| NEW-003 | Source metadata read must split citation-safe from management metadata | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-007`, `CP-000B`, `CP-000A`, `evidence-1.0.0.md`, `final-answer-1.0.0.md` | CP-001 with CP-009 | Implement the four resources (`DEF-119`) | Same verification as C-003 |
| NEW-004 | Roadmap stale after the CP-000A/B/C merges (`ROADMAP_MAPPING`) | `REPAIRED_IN_DOCUMENTATION` | `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` (new) | Governance | Update at each acceptance | Same verification as C-008, re-verified in R3: the roadmap body is internally current, contains no stale active-work section, and no longer claims to be verbatim |
| NEW-005 | `RuntimeSnapshot.index_snapshot` must be a logical aggregate manifest | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-003`, `CP-000C`, `runtime-snapshot-1.0.0.md` | CP-006 | Typed aggregate manifest (`DEF-117`) | Same verification as G-017 |
| NEW-006 | `RuntimeArtifactRef` namespace and `security_policy` meaning are ambiguous | `DEFERRED_WITH_OWNER` | `runtime-snapshot-1.0.0.md`, `ADR-CP-002` | CP-001 with CP-004 | Namespace field and disambiguation in vNext (`DEF-116`) | Same verification as G-015 and G-016 |
| NEW-007 | `ConfigurationRelease` refs and denormalized `RuntimeSnapshot` refs need an exact factory cross-check | `DOCUMENTED_IMPLEMENTATION_GAP` | `runtime-snapshot-1.0.0.md`, `ADR-CP-006` cross-reference | CP-004 with CP-006 | Enforce exact equivalence in the factory (`DEF-117`) | Same verification as G-018 |

### Per-document repair backlog (R-001 .. R-012)

| Finding ID | Finding | Disposition | Files Changed | Future Package Owner | Remaining Implementation Work | Verification |
| --- | --- | --- | --- | --- | --- | --- |
| R-001 | ADR-CP-001 needed one-root, re-parenting, node status, move authorization, and node metadata rules | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-001` | CP-002 | Implement the hierarchy service (`DEF-105`) | `I-2`, new `I-2a`, `ACTIVE` / `NON_ACTIVE`, `L-1`..`L-9`, `P-1`..`P-4` |
| R-002 | ADR-CP-002 needed pinned policy binding, the future authorization contract obligations, Guest as a first-class principal, and the "labels never authorize" rule | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-002` | CP-001 with CP-002 | `DEF-106`, `DEF-107`, `DEF-108` | `V-4`, `V-5`, `B-1`..`B-9`, `O-1`..`O-10` |
| R-003 | ADR-CP-003 needed the isolation metadata subset name, trusted temporal producers, the envelope-versus-physical-query distinction, and the aggregate snapshot | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-003` | CP-006 | `DEF-104`, `DEF-107`, `DEF-117` | "Mandatory Isolation Metadata Subset", `L-9A`..`L-9C`, `S-7A`, `S-7B`, "Source Registry dependencies", "Benchmark fixture requirement" |
| R-004 | ADR-CP-007 needed authority, temporal, relationship, metadata-class, approval-workflow, and workflow-boundary sections | `REPAIRED_IN_DOCUMENTATION` | `ADR-CP-007` | CP-001 with CP-005 and CP-006 | `DEF-103`, `DEF-104`, `DEF-119`, `DEF-121` | `AU-1`..`AU-7`, `T-1`..`T-7`, `SR-1`..`SR-7`, `M-1`..`M-4`, `AP-1`..`AP-10`, `WB-1`..`WB-4`, `R-5A` |
| R-005 | CP-000A duplicated and contradicted source lifecycle rows | `REPAIRED_IN_DOCUMENTATION` | `CP-000A` | CP-001 | Implement the permission model | "Scope of this matrix", "Delegated source actions", statements 6..10 |
| R-006 | CP-000B was not declared canonical and lacked the split actions and the accepted actor set | `REPAIRED_IN_DOCUMENTATION` | `CP-000B` | CP-001 with CP-009 | `DEF-119`, `DEF-121` | "Canonical scope", 7-actor matrix, split read/authority/temporal/relationship/lifecycle actions, 26 explicit statements, and the same-principal self-approval prohibition |
| R-007 | CP-000C did not mirror the ADR-CP-003 corrections | `REPAIRED_IN_DOCUMENTATION` | `CP-000C` | CP-006 | `DEF-104`, `DEF-117` | Sections 18.1, 18.5, 18.6, 18.7 and the added explicit statements |
| R-008 | Contract documents lacked truthful status and limitation notes | `REPAIRED_IN_DOCUMENTATION` | All 12 contract docs | Per-contract owners in each note | Per-contract `DEF` items | Each contract has a status line and a "Bounded baseline status and known limitations (CP-000R)" section; `final-answer-1.0.0.md` gained its missing status line. Re-verified in R3: `turn-input-1.0.0.md` no longer claims a `SecurityPrincipalContext`, `security-authorization-1.0.0.md` carries only the exact revocation race plus the explicit Django and AI Core trust boundary, `evidence-1.0.0.md` has split owner rows and the full ten-item eligibility check, `runtime-snapshot-1.0.0.md` attributes the factory to CP-004 rather than the Walking Skeleton task, and `query-analysis-1.0.0.md`, `execution-plan-1.0.0.md` and `audit-event-1.0.0.md` carry their completed limitation notes |
| R-009 | The Walking Skeleton overstated department isolation and understated transitional behavior | `REPAIRED_IN_DOCUMENTATION` | `walking-skeleton-1.0.0.md` | AI-002, AI-003, AI-007 with the audit-contract/application/adapter owners recorded under C-006, G-012, and G-013 | `DEF-114`, `DEF-115`, `DEF-118` | "Scope-lineage integrity (not production department isolation)", "Department isolation is not fully enforced", pre-completion and `deny`-route notes. The STOPPED clarification and abstention paragraph is complete and in place before the deny limitation, the bounded Orchestrator and Planner section tracks the repaired `DEF-092`, the full nine-element runtime lineage is used, and the five-way audit ownership split is recorded in C-006, G-012, and G-013 |
| R-010 | The deferred register recorded a stale repository state and stale gates | `REPAIRED_IN_DOCUMENTATION` | `deferred-items.md` | Governance | Keep synchronized | Version `0.6.0` introduced by CP-000R; base repository evidence `main` / `6477c1c`; bounded-versus-production reconciliation across the implemented planning, validation, evidence, answer, finalization, idempotency, audit/telemetry, and Walking Skeleton rows; `DEF-103`..`DEF-121`; CP-000D open-decision mappings; corrected canonical CP, AI, CP-000E, and adapter ownership map |
| R-011 | The canonical delivery roadmap was not in the repository and was stale | `REPAIRED_IN_DOCUMENTATION` | `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` (new) | Governance | Update at each acceptance | Roadmap file present with the CP-000R status block; re-verified in R3 against the authoritative package-status block and the repaired body |
| R-012 | No authority manifest existed, so document precedence was guessable | `REPAIRED_IN_DOCUMENTATION` | `docs/architecture/architecture-authority-manifest.md` (new) | Governance | Maintain at each acceptance | Manifest present with the seven statuses and the six required fields; re-verified in R3: every `document_ref`, `supersedes_refs` and `augments_refs` entry is an exact repository path, an exact external source identifier, or `-`, with no wildcard and no vague prose reference |

## Requirement-to-document-and-package matrix

| Repair requirement | Canonical document after CP-000R | Implementation owner |
| --- | --- | --- |
| Organization hierarchy, node lifecycle, node metadata publication | `ADR-CP-001` with `CP-000A` | CP-001 with CP-002, and CP-009 / CP-010 for the application-service and read-model boundaries. Node-directory publication is **not** assigned to CP-007 |
| Membership, scoped roles, pinned visibility policy binding, authorization contract obligations | `ADR-CP-002` with `CP-000A` | CP-001 with CP-002 |
| Index isolation, mandatory pre-filter, multi-node retrieval, aggregate snapshot | `ADR-CP-003` with `CP-000C` | CP-006 with AI-003 |
| Configuration artifacts and activation | `ADR-CP-004`, `ADR-CP-005` with `CP-000D` | CP-003 Artifact Registry Core, CP-008 Model/Provider/Credential Pool, CP-009 Control Plane Application Services |
| RuntimeSnapshot resolution | `ADR-CP-006` with `CP-000D` | CP-004 RuntimeSnapshotFactory, with CP-005 / CP-006 for source and index dependencies where applicable |
| Source registry, authority, temporal metadata, relationships, metadata classes, approval workflow | `ADR-CP-007` | CP-001 and CP-005, with CP-006 for lifecycle/index effects, CP-009 for application services, and `DEF-121` for typed `SourceRelationship` / partial-amendment work |
| Source lifecycle actions per actor | `CP-000B` (single canonical matrix) | CP-001 with CP-009 |
| Typed contract boundaries and their known limitations | The twelve `docs/contracts/*-1.0.0.md` documents | CP-001, AI-002, AI-003, AI-006, AI-007 |
| Bounded runtime proof and its limits | `docs/walking-skeleton-1.0.0.md` | AI-002 for orchestration and planning, AI-006 for execution and evidence composition, AI-007 for answer and finalization. AI-001 is a context and understanding dependency, not the primary bounded-runtime owner |
| Deferred obligations and ownership | `docs/deferred-items.md` | Governance |
| Document authority and precedence | `docs/architecture/architecture-authority-manifest.md` | Governance |
| Package sequencing and status | `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` | Governance |
| This repair, its ledger, and its residual limitations | This document | Governance |

## Audit event outcome semantics recorded by this repair

| Outcome | Meaning |
| --- | --- |
| `answered` | A complete answer was produced and finalized |
| `partial` | An answer was produced but did not cover the full request |
| `clarification_required` | The runtime deliberately asked for clarification instead of answering |
| `abstained` | The runtime deliberately declined to answer, with a reason |
| `policy_rejected` | A policy other than authorization rejected the request or the answer |
| `authorization_denied` | Authorization denied the request; this must remain distinct from `policy_rejected` |
| `failed` | An unexpected failure prevented a terminal answer |

`UNAUTHORIZED` and `POLICY_REJECTED` must never be collapsed into one generic failure, and no error
message may disclose the existence or metadata of unauthorized content. Audit remains fail-closed;
telemetry and evaluation export remain fail-open. The two are never conflated. This taxonomy is
recorded here as an architecture requirement; it is **not** implemented in `AuditEvent 1.0.0`
(`DEF-114`).

## Django and backend boundary

```text
Admin Website / Backend (Django)
  -> Control Plane commands
  -> immutable versioned configuration artifacts
  -> validation
  -> ConfigurationRelease
  -> atomic activation
  -> RuntimeSnapshotFactory
  -> immutable RuntimeSnapshot
  -> stateless AI Runtime
```

The Django backend owns accounts, permission assignment, source submission and review surfaces, and
configuration commands. It never mutates an approved artifact revision, never authorizes retrieval by
role label, and never injects configuration directly into the AI Runtime. The AI Runtime consumes an
already-resolved immutable `RuntimeSnapshot` and has no opinion on how it was assembled. No Django
integration is implemented by this package.

## Corrected contract facts (`CONTRACT_FACT`)

R1 asserted claims that the committed code contradicts. R2 corrected them against the code, not from
memory.

| Subject of the R1 error | Committed reality (authoritative) | Evidence |
| --- | --- | --- |
| Routing deny lane | `RouteLane` contains `deterministic`, `fast`, `composite`, `clarify`, `abstain`, `deny`; `_TERMINAL_LANES` contains `clarify`, `abstain`, `deny`. R1 wrongly denied this | `src/ai_assistant/contracts/route_decision.py` |
| Evidence authority metadata | `_EvidenceBase.authority` is a controlled canonical code, so authority metadata is typed and present. R1 wrongly denied this | `src/ai_assistant/contracts/evidence.py` |
| Evidence temporal metadata | `EvidenceValidityWindow` carries `as_of`, `valid_from`, `valid_to`, and `EvidenceSourceTime` carries `observed_at`, `published_at`, so temporal metadata is typed and present. R1 wrongly denied this | `src/ai_assistant/contracts/evidence.py` |
| RuntimeSnapshot limits | At most sixteen entries in `model_artifacts` and at most sixty-four effective `feature_flags`. These are collection bounds, not a fixed set of named artifact reference fields, and they do not bound `ConfigurationRelease`. R1 described them incorrectly | `src/ai_assistant/contracts/runtime_snapshot.py` |

Deny semantics as recorded across the repaired documents:

```text
authorization deny
  -> occurs before routing
  -> UNAUTHORIZED
  -> no RouteDecision required

route or policy deny
  -> RouteDecision(lane="deny")
  -> POLICY_REJECTED
  -> zero execution budget
  -> no capability execution
```

The remaining gap is runtime, not contractual: the bounded Runtime and Walking Skeleton do not yet
provide complete terminal handling for `RouteDecision(lane="deny")` (`DEF-118`, AI-002).

## Orchestrator and Planner

The canonical AI Module path is unchanged by this repair:

```text
TurnInput
  -> Context Builder
  -> Query Analyzer
  -> Orchestrator
  -> Fast Plan or Planner
  -> Capability Executor
  -> Evidence Manager
  -> Answer Builder
  -> Citation and Validation
  -> FinalAnswer
```

**Orchestrator responsibility.** Selects the fast, clarification, or complex lane; limits the available
capabilities; assigns a bounded execution budget; invokes the Planner only when required; and controls
request execution and state transitions. The Orchestrator is **not** an unconstrained agent. It cannot
invent tools, invent capabilities, expand authorization, ignore the `RuntimeSnapshot`, start unbounded
tasks, or run arbitrary subagents.

**Planner responsibility.** Decomposes complex questions; identifies evidence requirements; selects
only pre-authorized available capabilities; defines dependencies; defines sequential or bounded
parallel execution; and defines result-composition requirements. Planner constraints: maximum five
steps, bounded parallelism, at most one bounded replan, no free agent or subagent, no invented tool, no
invented capability, no authorization decision, and no arbitrary personal NL2SQL. Fast questions use a
deterministic one-step plan and do not require an LLM Planner.

**Ownership.** `AI-002 Adaptive Routing and Bounded Planning` is the primary implementation owner of
Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, Bounded Replan, and route-to-plan
composition. Related ownership: `AI-001` for context, Persian understanding, and query analysis;
`AI-006` for capability execution and evidence composition; `AI-007` for answer planning, citation, and
semantic validation; `AI-009` for latency, budgets, bounded parallelism, and failure controls.
Orchestrator and Planner are never placed under the Django backend, the Control Plane, CP-009, AI-006
alone, AI-007, or AI-010.

**Current implementation truth.** The current Walking Skeleton contains bounded deterministic routing,
planning, and execution primitives. It is **not** the complete production Orchestrator and Planner, and
no document in this repair claims that it is. The production components are tracked as the repaired `DEF-092` under
AI-002, with AI-009 as supporting owner. A temporary draft use of `DEF-121` for the same work was removed
as a duplicate before acceptance. The final register assigns `DEF-121` only to the distinct
`SourceRelationship` and partial-amendment obligation, and its range is `DEF-001` through `DEF-121`.

## R3 and R4 cross-document consistency corrections

R3 superseded R1 and R2 and repaired the main cross-document defects. R4 preserves those corrections,
changes no code, schema, test, or configuration file, and closes the final deferred-ownership, source-
governance, ledger-traceability, and authority-reference gaps. The corrections were:

| Area | Correction | Classification |
| --- | --- | --- |
| Roadmap | Removed the false `(verbatim)` heading and the stale active-work section; made the package statuses authoritative and internally consistent; qualified the two-person wording; corrected the commit terminology to base repository evidence | `ROADMAP_MAPPING`, `STRUCTURAL_DOCUMENT_REFINEMENT` |
| Deferred register | Removed the temporary duplicate Orchestrator/Planner use of `DEF-121` and folded that work into the repaired `DEF-092` (AI-002 primary, AI-009 supporting); then assigned final `DEF-121` only to the distinct `SourceRelationship` and partial-amendment obligation; reconciled bounded-versus-production facts, CP-000D open decisions, package ownership, counts, and the change log | `AUDIT_FINDING`, `STRUCTURAL_DOCUMENT_REFINEMENT` |
| Source lifecycle | Removed activation and supersession as human-facing v1 permissions; made `disable`, `revoke`, `archive`, and purge deny-by-default pending a separately delegated lifecycle permission; renumbered `AP-1`..`AP-10`; distinguished missing business approval, missing technical gates, and an unauthorized Control Plane lifecycle transition | `ACCEPTED_DECISION` |
| Temporal eligibility | Added the two temporal gates to the runtime eligibility conjunction with fail-closed and untrusted-draft rules | `ACCEPTED_DECISION` |
| Contract documents | Corrected TurnInput identity, the security trust boundary and the duplicate revocation-race row, the Evidence owner split and eligibility list, the RuntimeSnapshot factory ownership and reference interpretations, and the QueryAnalysis, ExecutionPlan and AuditEvent limitation notes | `CONTRACT_FACT`, `AUDIT_FINDING` |
| Walking Skeleton | Restored the misplaced STOPPED-mapping paragraph, tracked the production components as the repaired `DEF-092`, and used the full nine-element runtime lineage | `STRUCTURAL_DOCUMENT_REFINEMENT` |
| Ownership | Split audit ownership across CP-001, CP-009, CP-012, AI-002, and AI-007; corrected the requirement-to-package mapping so node-directory publication is not assigned to CP-007 and AI-001 is a dependency rather than the bounded-runtime owner | `ACCEPTED_DECISION` |
| Manifest | Replaced the ADR-001 and ADR-002 wildcard references with exact paths, corrected the commit terminology, and stated that the CP-000R-created files and ledger do not exist at `6477c1c` | `STRUCTURAL_DOCUMENT_REFINEMENT` |
| Source governance | Made the same-principal self-approval prohibition explicit; separated the Central Source Approver business decision from the Control Plane `ACTIVE` transition; corrected the contributor review-surface cell | `ACCEPTED_DECISION` |
| Final ownership closure | Added the independent `SourceRelationship` obligation, mapped provider-probe freshness, `BuildArtifact` qualification, and the approver review surface to existing deferred items, and aligned CP/AI/adapter ownership | `AUDIT_FINDING`, `STRUCTURAL_DOCUMENT_REFINEMENT` |

## Residual limitations of this repair

1. This package changes documentation only. Every repaired contradiction that requires code remains
   unimplemented and is tracked with an owner in `docs/deferred-items.md`.
2. The integrated audit did not independently audit the committed test suite or the JSON Schemas
   (`G-022`, `DEF-120`).
3. Verification evidence for the base commit was supplied by the architect from the canonical local
   machine. It was not independently reproduced while preparing this repair.
4. The `uv` version-range build warning (`uv-build>=0.9.2,<0.10` versus local `uv 0.12.1`) remains
   unresolved.
5. Several open decisions remain deliberately open: hard-bound representation, partial-amendment
   relations (`DEF-121`), the Last-Known-Good maximum, the canary model, provider-probe evidence
   freshness (`DEF-045`), exact `BuildArtifact` qualification (`DEF-101`), the approver review surface
   (`DEF-099`), and the configurable separation-of-duties model.

## Explicit statements

1. Documentation status is never implementation status.
2. `CP-000B` is the single canonical source lifecycle and source-action matrix.
3. `ADR-CP-002` and `ADR-CP-007` jointly fix the pinned visibility policy revision rule.
4. Source authority affects ranking, conflict precedence, and caveats. It never affects authorization.
5. Role labels, frontend labels, display names, and model output never authorize.
6. A single System AI Administrator model, with no mandatory second human approver, remains canonical
   for v1 AI configuration administration.
7. A single Central Source Approver model remains canonical for v1 source approval. The same principal
   must not approve a submission they created, authored, uploaded, or submitted.
8. No contract version was bumped, no schema was changed, and no code or test was touched.
9. `CP-001` is blocked until `CP-000R` and `CP-000E` are accepted.
