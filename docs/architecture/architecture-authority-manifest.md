# Architecture Authority Manifest

Status: Accepted architecture authority baseline; CP-000E accepted at commit `882a2ef`
Implementation remains owned by the packages identified in this document.
Scope: document authority, precedence, and supersession. This manifest decides **which document is
authoritative for which decision**. It creates no architecture decision of its own, and it asserts no
implementation that Git does not contain.

Base branch: `main`
Base repository evidence commit: `8d94c6a`
Latest accepted architecture baseline: CP-000E, accepted at `882a2ef`. The CP-000E-created ADRs and
`docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md` do **not** exist at the base
repository evidence commit `8d94c6a`; they enter authority through the accepted CP-000E commit.

## Why this manifest exists

Before CP-000R there was no recorded document authority, so precedence had to be guessed. Guessing is
prohibited:

- **No model-based latest-document guessing.** A model must never decide which document wins.
- **A filename date is not authority.** Neither is a version suffix in a filename.
- **A file modification time is not authority.** Neither is upload order, nor position in a folder.
- Authority comes only from this manifest and the precedence order below.
- If a document is not listed here, it has no authority until it is added here.

## Precedence order

```text
committed implementation and typed contracts
  -> accepted CP ADRs
  -> explicit architect-approved decisions taken after the audit
  -> integrated audit repair requirements
  -> canonical delivery roadmap
  -> newer supporting architecture sources
  -> legacy documents
```

Where two documents conflict, the higher tier wins. Within one tier, the document named canonical for
that decision scope in the table below wins.

## Status values

| Status | Meaning |
| --- | --- |
| `CANONICAL_IMPLEMENTED` | Canonical **and** implemented in Git at the base repository evidence commit |
| `CANONICAL_ARCHITECTURE` | Canonical for its decision scope; the decision is accepted, the implementation is not claimed |
| `CANONICAL_ROADMAP` | Canonical for package sequencing and package status |
| `AUTHORITATIVE_SUPPORTING` | Authoritative supporting source; may inform decisions but never overrides a canonical document |
| `HISTORICAL` | Retained for history and traceability; not authoritative for any current decision |
| `SUPERSEDED` | Explicitly replaced by a named successor |
| `DRAFT` | Not accepted; carries no authority |

## Fields

Every entry records `document_ref`, `status`, `decision_scope`, `owner`, `supersedes_refs`, and
`augments_refs`. `-` means none.

## Committed implementation and typed contracts

| document_ref | status | decision_scope | owner | supersedes_refs | augments_refs | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `src/ai_assistant/contracts/` | `CANONICAL_IMPLEMENTED` | The actual typed shapes, field names, and validation rules in force | AI Core | - | - | Committed typed contracts; highest authority. Where a document disagrees with a committed contract, the contract wins |
| `schemas/` | `CANONICAL_IMPLEMENTED` | The published schema surface of the committed contracts | AI Core | - | - | Committed JSON Schemas; not independently audited (`DEF-120`) |
| `src/ai_assistant/core/` | `CANONICAL_IMPLEMENTED` | The bounded in-process runtime that actually exists | AI Core | - | - | Ports and bounded runtime; fake-adapter only |
| `docs/contracts/turn-input-1.0.0.md` | `CANONICAL_IMPLEMENTED` | `TurnInput` boundary | AI Core | - | - | Bounded baseline. `TurnInput` carries no identity and no authorization, and no `SecurityPrincipalContext` |
| `docs/contracts/query-analysis-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Query understanding boundary | AI Core | - | - | Bounded baseline |
| `docs/contracts/route-decision-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Deterministic routing boundary | AI Core | - | - | `RouteLane` already contains the terminal `deny` lane; bounded runtime terminal handling for it is incomplete (`DEF-118`) |
| `docs/contracts/execution-plan-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Plan construction and validation boundary | AI Core | - | - | Bounded baseline |
| `docs/contracts/step-result-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Capability execution boundary | AI Core | - | - | Bounded baseline |
| `docs/contracts/evidence-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Evidence normalization and sufficiency boundary | AI Core | - | - | Already carries the `authority` controlled code, `EvidenceValidityWindow`, and `EvidenceSourceTime`; not yet bound to or revalidated against the Source Registry, and `SourceRelationship` is absent (`DEF-103`, `DEF-104`, `DEF-121`) |
| `docs/contracts/answer-plan-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Answer planning boundary | AI Core | - | - | Bounded baseline |
| `docs/contracts/final-answer-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Terminal answer artifact | AI Core | - | - | Status line added by CP-000R |
| `docs/contracts/security-authorization-1.0.0.md` | `CANONICAL_IMPLEMENTED` | `SecurityPrincipalContext` and `AuthorizationDecision` | AI Core | - | - | No typed `AuthorizationRequest` or Guest principal (`DEF-106`, `DEF-108`) |
| `docs/contracts/runtime-snapshot-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Runtime configuration boundary | AI Core | - | - | Naming and aggregate-manifest limitations (`DEF-116`, `DEF-117`). The RuntimeSnapshotFactory is owned by CP-004 and was **not** delivered in the Walking Skeleton task |
| `docs/contracts/audit-event-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Audit payload boundary | AI Core | - | - | Incomplete outcome taxonomy and lineage (`DEF-114`, `DEF-115`) |
| `docs/contracts/error-envelope-1.0.0.md` | `CANONICAL_IMPLEMENTED` | Domain error boundary | AI Core | - | - | Carries transitional clarification/abstention (`DEF-118`) |
| `docs/walking-skeleton-1.0.0.md` | `CANONICAL_IMPLEMENTED` | The bounded in-process turn lifecycle that exists | AI Core | - | - | Bounded, not production-ready; department isolation is **not** fully enforced; contains bounded deterministic routing, planning, and execution primitives only, **not** the production Orchestrator and Planner, which are owned by AI-002 with AI-009 and tracked as the repaired `DEF-092` |

## Accepted CP architecture documents

| document_ref | status | decision_scope | owner | supersedes_refs | augments_refs | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md` | `CANONICAL_ARCHITECTURE` | Organization and node hierarchy, node lifecycle, node metadata publication | Control Plane | `legacy-docs/00-master-architecture-roadmap-fa.md` | `docs/control-plane/CP-000A-authorization-matrix.md` | Not implemented (`DEF-105`) |
| `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md` | `CANONICAL_ARCHITECTURE` | Membership, scoped roles, visibility policy semantics, pinned policy binding | Control Plane | `legacy-docs/02-scope-and-decision-framework-fa.md` | `docs/control-plane/CP-000A-authorization-matrix.md`, `docs/contracts/security-authorization-1.0.0.md` | Not implemented (`DEF-106`, `DEF-107`, `DEF-108`) |
| `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md` | `CANONICAL_ARCHITECTURE` | Data and index isolation, mandatory pre-filter, multi-node retrieval, aggregate snapshot | Control Plane | - | `docs/control-plane/CP-000C-index-isolation-blueprint.md`, `docs/contracts/runtime-snapshot-1.0.0.md` | Not implemented; no provider selected |
| `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md` | `CANONICAL_ARCHITECTURE` | Configuration artifact taxonomy, ownership, precedence | Control Plane | - | `docs/control-plane/CP-000D-configuration-catalog.md` | Single System AI Administrator model |
| `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md` | `CANONICAL_ARCHITECTURE` | Artifact revisions, validation layers, `ConfigurationRelease`, activation, rollback | Control Plane | - | `docs/control-plane/CP-000D-configuration-catalog.md` | `APPROVED` does not imply a second human approver |
| `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md` | `CANONICAL_ARCHITECTURE` | `RuntimeSnapshotFactory`, cache, bounded Last-Known-Good | Control Plane | - | `docs/control-plane/CP-000D-configuration-catalog.md`, `docs/contracts/runtime-snapshot-1.0.0.md` | Bounded LKG; a known revoke or disable defeats LKG |
| `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md` | `CANONICAL_ARCHITECTURE` | Source registry, revisions, authority, temporal metadata, relationships, metadata classes, approval workflow | Control Plane | - | `docs/control-plane/CP-000B-source-lifecycle-matrix.md` | Not implemented (`DEF-103`, `DEF-104`, `DEF-119`, `DEF-121`) |
| `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md` | `CANONICAL_ARCHITECTURE` | Pure AI model gateway boundary, provider/deployment/credential pool, LiteLLM adapter placement, bounded load balancing and fallback | CP-008 / AI Runtime Boundary | - | `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`, `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md` | Architecture only; implementation remains in `DEF-032`, `DEF-036`, `DEF-037`, `DEF-045`, `DEF-100` |
| `docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md` | `CANONICAL_ARCHITECTURE` | Backend admission/queue ownership, commands/events/snapshot pull, cancellation, idempotency and Admin Website configuration path | CP-009 / CP-010 | - | `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md` | AI Core owns no global queue or Redis; implementation remains in `DEF-038`, `DEF-043`, `DEF-099`, `DEF-100` |
| `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md` | `CANONICAL_ARCHITECTURE` | Audit/telemetry split, retention/legal hold boundary, emergency controls and threat baseline | Security / Audit Governance | - | `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`, `docs/contracts/audit-event-1.0.0.md` | Architecture only; implementation remains in `DEF-101`, `DEF-102`, `DEF-113`, `DEF-114`, `DEF-115` |
| `docs/control-plane/CP-000A-authorization-matrix.md` | `CANONICAL_ARCHITECTURE` | Organization and authorization actions per actor | Control Plane | - | `docs/adr/ADR-CP-001-organization-and-department-hierarchy.md`, `docs/adr/ADR-CP-002-membership-role-and-authorization-scope.md` | **Delegates all source actions to `CP-000B`** |
| `docs/control-plane/CP-000B-source-lifecycle-matrix.md` | `CANONICAL_ARCHITECTURE` | **Single canonical source lifecycle and source-action matrix** | Control Plane | `docs/control-plane/CP-000A-authorization-matrix.md` | `docs/adr/ADR-CP-007-source-registry-and-content-lifecycle.md` | Supersedes the former source-action rows in CP-000A and wins over any other document on source actions |
| `docs/control-plane/CP-000C-index-isolation-blueprint.md` | `CANONICAL_ARCHITECTURE` | Isolation metadata subset, tiers, query-path invariants, benchmark plan | Control Plane | - | `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md` | No provider selected; no benchmark result asserted |
| `docs/control-plane/CP-000D-configuration-catalog.md` | `CANONICAL_ARCHITECTURE` | Configuration artifact and control catalog | Control Plane | - | `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`, `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`, `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md` | - |
| `docs/control-plane/CP-000R-architecture-consistency-repair.md` | `CANONICAL_ARCHITECTURE` | The consistency repair itself: repair ledger, dispositions, residual limitations | Governance | - | - | Documentation only. Created by CP-000R and not present at `6477c1c` |
| `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md` | `CANONICAL_ARCHITECTURE` | CP-000E decision summary, diagrams, emergency matrix, performance assumptions and requirement-to-package coverage | Governance / Control Plane | - | `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`, `docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md`, `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md` | Documentation only; does not claim LiteLLM, Backend queue, Redis, UI or audit implementation |
| `docs/deferred-items.md` | `CANONICAL_ARCHITECTURE` | Deferred obligations, ownership, and `DONE` criteria | Governance | `legacy-docs/deferred-items-register.md` | - | Version `0.7.0` is updated by CP-000E; implementation obligations remain open |
| `docs/architecture/architecture-authority-manifest.md` | `CANONICAL_ARCHITECTURE` | Document authority, precedence, and supersession | Governance | - | - | This document; before it, precedence was undocumented |

## Roadmap

| document_ref | status | decision_scope | owner | supersedes_refs | augments_refs | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` | `CANONICAL_ROADMAP` | Package sequencing, package status, and delivery gates | Governance | `legacy-docs/00-master-architecture-roadmap-fa.md` | - | `CP-000R COMPLETE at 8d94c6a -> CP-000E COMPLETE at 882a2ef -> CP-001 NEXT` |

## Authoritative supporting sources

These are authoritative as supporting input. They never override a canonical document, and they are
not committed to this repository by CP-000R.

| document_ref | status | decision_scope | owner | supersedes_refs | augments_refs | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `ai-assistant-master-handoff-fa(1).md` | `AUTHORITATIVE_SUPPORTING` | Overall product and delivery handoff context | Governance | - | `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` | Where it conflicts with a CP ADR, the ADR wins |
| `ai-module-architecture(3)(2).md` | `AUTHORITATIVE_SUPPORTING` | AI runtime module decomposition | AI Core | - | `docs/adr/ADR-CP-003-data-index-isolation-and-multi-node-retrieval.md`, `docs/contracts/route-decision-1.0.0.md`, `docs/contracts/execution-plan-1.0.0.md` | AI Module Architecture v0.4; canonical supporting source of the AI Module path, including Orchestrator and Planner. Where it conflicts with a committed contract, the contract wins |
| `evaluation-plane-implementation-blueprint-fa(2)(1).md` | `AUTHORITATIVE_SUPPORTING` | Evaluation plane design | Evaluation | - | - | Not implemented; informs `DEF-098`, `DEF-112`, and `DEF-120` |
| `architecture-audit-integrated-pre-cp000d-fa.md` | `AUTHORITATIVE_SUPPORTING` | The integrated audit findings that this repair consumed | Governance | - | `docs/control-plane/CP-000R-architecture-consistency-repair.md` | **A repair input, not a repository contract.** Not committed to Git by CP-000R |

## Historical and superseded documents

| document_ref | status | decision_scope | owner | supersedes_refs | augments_refs | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `docs/adr/ADR-001-error-envelope-and-http-problem-details.md` | `HISTORICAL` | Early error-envelope and HTTP problem-details decision | Governance | - | - | Retained; outside the CP series and not modified by CP-000R |
| `docs/adr/ADR-002-audit-event-and-cloudevents-boundary.md` | `HISTORICAL` | Early audit-event and CloudEvents boundary decision | Governance | - | - | Retained; not modified by CP-000R |
| `legacy-docs/00-master-architecture-roadmap-fa.md` | `SUPERSEDED` | Early master roadmap | Governance | - | - | Superseded by `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` |
| `legacy-docs/01-source-synthesis-fa.md` | `HISTORICAL` | Early source synthesis | Governance | - | - | Traceability only |
| `legacy-docs/02-scope-and-decision-framework-fa.md` | `HISTORICAL` | Early scope and decision framework | Governance | - | - | Traceability only |
| `legacy-docs/03-test-and-evaluation-blueprint-fa.md` | `SUPERSEDED` | Early test and evaluation plan | Evaluation | - | - | Superseded by the evaluation plane blueprint and `CP-000C` 18.4 |
| `legacy-docs/04-deep-research-traceability-fa.md` | `HISTORICAL` | Research traceability | Governance | - | - | Traceability only |
| `legacy-docs/decisions/ADR-001-product-boundary.md` | `HISTORICAL` | Early product boundary | Governance | - | - | Traceability only |
| `legacy-docs/deferred-items-register.md` | `SUPERSEDED` | Early deferred register | Governance | - | - | Superseded by `docs/deferred-items.md` |
| `legacy-docs/stages/00-foundation-workbook-fa.md` | `HISTORICAL` | Early foundation workbook | Governance | - | - | Traceability only |

## Maintenance rules

1. Every accepted package must add or update its own entries here as part of that package.
2. A document gains authority only by being listed here with a status other than `DRAFT`.
3. `supersedes_refs` must name the superseded document explicitly. Implicit supersession is prohibited.
4. A `CANONICAL_IMPLEMENTED` claim requires that the artifact actually exists in Git at the base
   repository evidence commit. Documentation acceptance alone never justifies `CANONICAL_IMPLEMENTED`.
5. This manifest records authority only. It never asserts that a decision is implemented.
6. Every `supersedes_refs` and `augments_refs` value must be an exact repository path, an exact
   external source identifier, or `-`. Vague descriptive phrases are prohibited as reference values.
7. This manifest must never claim that a file created by CP-000E existed at `8d94c6a`. The three
   `ADR-CP-008`..`ADR-CP-010` files and
   `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md` are introduced by CP-000E and
   are absent at `8d94c6a`.

## Canonical AI Module path

The canonical AI Module path, authoritative in AI Module Architecture v0.4 and unchanged by CP-000R:

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

Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, Bounded Replan, and route-to-plan
composition are owned by **AI-002 Adaptive Routing and Bounded Planning**. They are never owned by the
Django backend, by the Control Plane, by AI-006 alone, by AI-007, or by AI-010. The bounded Walking
Skeleton contains deterministic routing, planning, and execution primitives only; it is not the
complete production Orchestrator and Planner.
