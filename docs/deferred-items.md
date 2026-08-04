# Deferred Items Register

- **Version:** 0.7.0
- **Updated:** with the CP-000E model, integration, audit, and threat architecture package
- **Canonical source:** Git. This file is committed in the authoritative repository, so Git is
  canonical for deferred-work tracking; no external copy overrides it.
- **Repository path:** `docs/deferred-items.md`
- **Notion role:** dashboard and status mirror only

## Purpose

This register tracks work that is intentionally deferred, not yet supported, partially delivered, or completed while preserving the remaining runtime and operational obligations.

It keeps the AI Core small and provider-neutral while preventing contract-only delivery from being mistaken for a complete runtime product.

## Evidence basis and repository-state note

- Contract acceptance baseline: `CONTRACT-000` through `CONTRACT-012`, including corrective task `CONTRACT-012.1`.
- **Authoritative repository snapshot: branch `main`, HEAD `882a2ef`, clean working tree.**
- **Latest accepted architecture baseline: CP-000E (Model, Integration, Audit, and Threat Baseline),
  accepted at `882a2ef`.** CP-000A through CP-000R precede it and are accepted.
- **Architect-supplied verification evidence, captured on the canonical local machine at `6477c1c`**
  (this evidence was **not** independently reproduced while preparing this repair; it is transcribed
  exactly as provided):
  - `2442 passed in 18.37s`
  - `Required test coverage of 95% reached.`
  - `Total coverage: 95.47%`
  - `[verify] all checks passed`
  - `Successfully built: dist/ai_assistant-0.1.0.tar.gz` and `dist/ai_assistant-0.1.0-py3-none-any.whl`
- **Unresolved non-blocking build warning:** `build_system.requires = ["uv-build>=0.9.2,<0.10"]` while
  the local `uv` version was `0.12.1`. The build succeeded despite the warning. The version-range
  mismatch is **not resolved** and remains an open toolchain obligation.
- AUDIT-001 review found no code correction requirement in the Contract Foundation: all 13 committed
  JSON Schemas match their Pydantic models, public exports are controlled, schemas are closed, and no
  transport, database, cloud, observability-vendor, or model-provider SDK dependency enters the current
  AI Core package. The integrated architecture audit did **not** independently audit the test suite or
  the JSON Schemas; that residual limitation is tracked as `DEF-120`.
- **Bounded versus production split.** Several items are closed **only for the bounded, in-process,
  fake-adapter Walking Skeleton flow** and remain open as production obligations:

| Item | Bounded closure | Production obligation that remains open |
| --- | --- | --- |
| DEF-002 Idempotency | Effective-key scope, fingerprint conflict, replay, and in-flight behavior proven in-process with a test fake | No database, cache, distributed lock, TTL, or lease-expiry adapter exists; multi-replica behavior unvalidated |
| DEF-083 Finalization cross-artifact binding | Bounded binding checks proven for the fast document flow | Full binding across production authorization, retrieval, and configuration paths is unimplemented |
| DEF-087 FinalAnswer audit, telemetry, and evaluation | Audit event emitted and terminal telemetry recorded through fakes | No audit store, no telemetry backend, no evaluation plane; audit taxonomy and lineage incomplete (`DEF-114`, `DEF-115`) |
| DEF-091 Walking Skeleton | One bounded in-process turn proven end to end | No production adapter, no production retrieval, no real model, no Control Plane, no production authorization |

- **`DONE` requires all four of: implementation, local verification, independent review, and an
  accepted package.** Meeting fewer than all four is never `DONE`. `DONE` on an artifact never closes
  the separate runtime, adapter, governance, evaluation, privacy, supply-chain, or operational items
  listed below.
- **Documentation status is not implementation status.** An architecture document accepted through CP-000E
  records a decision; it never asserts that the decision is implemented in Git.

## Architectural ownership

| Layer | Responsibility |
|---|---|
| `AI Core` | Typed contracts, domain invariants, routing, planning, evidence, generation/finalization rules, evaluation contracts, and provider-neutral ports |
| `Adapter` | HTTP, identity providers, policy engines, model providers, search engines, storage, observability, and external integrations |
| `Control Plane` | Admin UI/backend, versioned configuration management, approvals, activation, rollback, and operational workflows |
| `Platform` | Secret management, deployment, networking, databases, queues, CI/CD, infrastructure, and runtime operations |
| `Governance` | Compatibility policy, release policy, documentation, review rules, privacy rules, and audit requirements |
| `Evaluation` | Datasets, model/task qualification, replay/regression suites, red-team tests, release gates, benchmark governance, and production-candidate evaluation |
| `Audit` | Business/security audit events, integrity, access, retention, and delivery controls independent of logs and traces |
| `Observability` | Trace-safe logs, metrics, traces, SLOs, diagnostics, and operational alerting without becoming the evaluation plane |

## Status values

- `OPEN`: acknowledged, but not yet assigned to a concrete implementation task.
- `PLANNED`: assigned to a concrete task or milestone.
- `VERIFYING`: implemented or delivered, but the complete local acceptance evidence has not yet been captured.
- `DONE`: implemented, locally verified, independently reviewed, and accepted.
- `DROPPED`: intentionally not supported, with rationale recorded.

## Current delivery baseline

| Delivered item | Status | Note |
|---|---|---|
| Common contract primitives | `DONE` | CONTRACT-000 |
| TurnInput and AttachmentRef | `DONE` | CONTRACT-001 |
| SecurityPrincipalContext | `DONE` | CONTRACT-002 |
| AuthorizationDecision and AuthorizationResourceRef | `DONE` | CONTRACT-002 |
| RuntimeSnapshot | `DONE` | CONTRACT-003 |
| DomainError and ErrorEnvelope | `DONE` | CONTRACT-004; HTTP mapping remains deferred |
| AuditEvent payload contract | `DONE` | CONTRACT-005; operational lifecycle remains deferred |
| QueryAnalysis | `DONE` | CONTRACT-006; runtime analyzer remains deferred |
| RouteDecision | `DONE` | CONTRACT-007; bounded deterministic routing primitives exist, while production adaptive routing and complete terminal handling remain `AI-002` work (`DEF-092`, `DEF-118`) |
| ExecutionPlan | `DONE` | CONTRACT-008; bounded deterministic builders and validation exist, while the production Planner, scheduler, bounded replan, cancellation, and policy-stability evaluation remain open (`DEF-056`..`DEF-060`, `DEF-092`) |
| StepResult | `DONE` | CONTRACT-009; bounded step-result validation exists, while production capability adapters, output registry, canonicalization, retry enforcement, and replay metrics remain open (`DEF-062`..`DEF-068`) |
| Evidence and EvidenceBundle | `DONE` | CONTRACT-010; a bounded Evidence Manager and EvidenceBundle construction path exist, while production eligibility validation, Source Registry integration, relationship handling, and content resolution remain open (`DEF-069`..`DEF-073`, `DEF-103`, `DEF-104`, `DEF-109`, `DEF-111`, `DEF-121`) |
| AnswerPlan | `DONE` | CONTRACT-011; a bounded AnswerPlanner and exact bounded-flow evidence binding exist, while the minimal `GenerationRequest`, production planning policies, replay, and semantic validation remain open (`DEF-074`..`DEF-078`, `DEF-110`, `DEF-112`) |
| FinalAnswer | `DONE` | CONTRACT-012 plus CONTRACT-012.1; bounded trusted finalization and server-side citation binding exist, while the production generator, evidence-content resolver, semantic validator, and publication-time recheck remain open (`DEF-079`..`DEF-083`, `DEF-111`..`DEF-113`) |

## Register summary

- Total tracked items: **121**
- `DONE`: **6**
- `PLANNED`: **26**
- `VERIFYING`: **2**
- `OPEN`: **87**
- `DROPPED`: **0**

Range: `DEF-001` through `DEF-121`. CP-000R added `DEF-103` through `DEF-121`. The production
Orchestrator and Planner are **not** a new identifier: they are tracked by the existing and repaired
`DEF-092`, which now separates the delivered bounded baseline from the remaining production work. No
existing identifier was deleted, renumbered, or reused. Two statuses were corrected against Git:
`DEF-091` (bounded Walking Skeleton) is now `DONE` because all four `DONE` criteria are met for its
bounded scope, and `DEF-092` remains `PLANNED` for the production components that do not exist.

## Complete register

| ID | Area | Layer | Deferred item | Why deferred | Target / trigger | Status |
|---|---|---|---|---|---|---|
| DEF-001 | TurnInput provenance | Adapter | Enforce trusted origins for `request_id`, `received_at`, `channel`, `conversation_id`, and attachment references | Pydantic validates shape, not provenance | Walking Skeleton transport adapter | OPEN |
| DEF-002 | Idempotency | AI Core + Adapter | Define scope, TTL, payload fingerprint, replay behavior, concurrent requests, and conflicting key reuse | **Delivered bounded baseline:** the Walking Skeleton implements bounded in-process idempotency acquire, replay, in-flight, and conflict handling with fail-closed terminal completion. **Remaining production obligation:** defined scope, TTL, payload fingerprint, concurrent-request and conflicting-key semantics over a durable store. Missing `DONE` criterion: a durable production idempotency adapter with those semantics; `TurnInput` still carries only the idempotency key | Runtime request handling | OPEN |
| DEF-003 | Transport limits | Adapter | Enforce HTTP request byte-size, upload-size, and transport payload limits | Character limits are not transport limits | API boundary | OPEN |
| DEF-004 | Attachments and trusted ingestion | Adapter + Platform | Resolve trusted media type, size, digest, malware status, quarantine state, classification, storage identity, retention class, parsing/OCR eligibility, and release from quarantine | `AttachmentRef` intentionally contains only opaque identity and version; trusted ingestion and quarantine are operational responsibilities | Ingestion and trusted storage milestone | OPEN |
| DEF-005 | Normalized query contract | AI Core | Finalize and accept the server-derived `normalized_query` semantics introduced by QueryAnalysis | The contract semantics are now accepted; runtime provenance and analyzer execution remain separate items | CONTRACT-006 accepted and covered by later full green suites | DONE |
| DEF-006 | Security principal | AI Core | Implement `SecurityPrincipalContext` | Identity facts must be separated from user input | CONTRACT-002 | DONE |
| DEF-007 | Authorization decision | AI Core | Implement `AuthorizationDecision` with effect, reason codes, obligations, constraints, resource binding, and policy version | Roles and groups are policy inputs, not authorization decisions | CONTRACT-002 | DONE |
| DEF-008 | Runtime reproducibility | AI Core | Implement immutable `RuntimeSnapshot` with digest-pinned artifact references | Required for replay, evaluation, debugging, and controlled hotfixes | CONTRACT-003 | DONE |
| DEF-009 | Error contract | AI Core | Implement `DomainError` and `ErrorEnvelope` without transport-specific fields | Domain errors and HTTP errors must remain separate | CONTRACT-004 | DONE |
| DEF-010 | Audit operational lifecycle | Adapter + Platform + Governance | Implement AuditEvent delivery, deduplication, append-only or tamper-evident persistence, ordering policy, retry/dead-letter handling, integrity, access, retention, and deletion | CONTRACT-005 defines the payload only | Audit adapter and audit store milestones | OPEN |
| DEF-011 | Privacy | Governance + Platform | Define persistence, retention, redaction, deletion, legal hold, and access policies for messages, analyses, evidence, and attachment references | Contracts do not authorize persistence | Runtime, conversation, evidence, and audit policy milestones | OPEN |
| DEF-012 | Correlation and tracing | Adapter + Observability | Define request/run/trace correlation, W3C Trace Context mapping, trace-safe propagation, and a pinned OpenTelemetry Semantic Conventions version/profile | Domain contracts must not depend on observability SDKs and telemetry meaning must not drift silently | Walking Skeleton observability task | OPEN |
| DEF-013 | Compatibility tests | Governance + Evaluation | Add producer/consumer compatibility tests for approved contract versions | Schema-drift tests do not prove cross-version compatibility | Contract release process | OPEN |
| DEF-014 | Locales and channels | AI Core + Adapter | Add supported locales and channels through explicit versioned contract changes | `TurnInput 1.0.0` supports only the approved initial values | First additional locale or channel | OPEN |
| DEF-015 | Validation UX | Adapter | Translate validation and domain failures into safe Persian user-facing messages | Internal validation errors must not leak directly to users | Error presentation layer | OPEN |
| DEF-016 | Compatibility governance | Governance | Reconcile and codify closed-contract compatibility rules across the contract register, specifications, release policy, and compatibility tests | FinalAnswer was corrected in CONTRACT-012.1, but repository-wide governance and automated conformance remain incomplete | DOC-001 and AUDIT-001 | PLANNED |
| DEF-017 | Versioning governance | Governance | Clarify that `schema_version` is required on top-level wire or persisted contracts, not every nested value object | Repeating versions on nested objects creates noise and inconsistent evolution | Contract Register revision | OPEN |
| DEF-018 | RuntimeSnapshot factory | AI Core port + Adapter | Implement trusted `RuntimeSnapshotFactory`, RFC 8785 canonicalization, SHA-256 computation, registry resolution, and fail-closed digest verification | RuntimeSnapshot validates metadata format only | Walking Skeleton configuration boundary | PLANNED |
| DEF-019 | Admin Control Plane | Control Plane | Build versioned administration workflows for runtime configuration artifacts | Admin frontend/backend workflows are outside AI Core | Control Plane milestone | OPEN |
| DEF-020 | RetrievalProfile | AI Core contract + Control Plane | Define candidate counts, reranker counts, evidence limits, thresholds, source caps, and context budgets | RuntimeSnapshot stores only the immutable artifact reference | Retrieval configuration task | OPEN |
| DEF-021 | ModelPolicy and provider pool | AI Core contract + Adapter + Control Plane | Define provider-neutral model policies and LLM pools with priority, weight, fallback, timeout, capability, rate-limit, residency, and health metadata | Provider selection and pool operations must remain replaceable | Model adapter milestone | OPEN |
| DEF-022 | Secret Manager | Platform + Control Plane | Store API keys only in a Secret Manager and expose credential references plus masked metadata | Secrets must never enter AI Core contracts, RuntimeSnapshot, Git, logs, traces, or the frontend | Platform security milestone | OPEN |
| DEF-023 | Safe configuration activation | Control Plane | Implement validation, approval, health checks, atomic activation, canary rollout, emergency disable, rollback, and audit | Production hotfixes require controlled lifecycle management | Control Plane milestone | OPEN |
| DEF-024 | Feature-flag port | AI Core port + Adapter | Define a vendor-neutral feature-flag evaluation port and backend adapter | Storage and evaluation backends must remain replaceable | Runtime configuration milestone | OPEN |
| DEF-025 | Authorization policy engine | Adapter | Implement deterministic policy evaluation that produces `AuthorizationDecision` | CONTRACT-002 defines only input/output contracts | Authorization adapter milestone | OPEN |
| DEF-026 | Delegation and break-glass | Governance + Adapter | Define delegation, impersonation, and break-glass workflows with approval, expiry, scope, and audit | Privileged workflows require separate governance and controls | Security hardening milestone | OPEN |
| DEF-027 | Session lifecycle | Adapter + Platform | Define session lifecycle, revocation, token introspection, and verified provider-claim mapping | Raw tokens and provider payloads are excluded from AI Core | Identity adapter milestone | OPEN |
| DEF-028 | Authorization obligations | AI Core + Adapter | Define effect-dependent obligation semantics and enforcement responsibilities | CONTRACT-002 carries obligation codes without effect-specific execution rules | Authorization enforcement milestone | OPEN |
| DEF-029 | RunContext / ChatRun | AI Core | Bind request, security context, authorization decision, RuntimeSnapshot, deadlines, cancellation, correlation, and terminal state | RuntimeSnapshot intentionally has no `run_id` | Walking Skeleton runtime-context task | PLANNED |
| DEF-030 | Runtime artifact schemas | AI Core contracts + Control Plane | Define versioned schemas for config, prompt, model policy, model artifact, structured-output backend, retrieval, embedding, reranker, index, semantic catalog, rules, security policy, and telemetry artifacts | RuntimeSnapshot references immutable artifacts but does not define their contents | Capability and configuration milestones | OPEN |
| DEF-031 | Artifact registry lifecycle | Control Plane + Platform | Define immutable revisions, digest pinning, active pointers, approvals, retention, rollback, and garbage collection | Safe hotfix and replay require stable artifact lifecycle semantics | Configuration registry milestone | OPEN |
| DEF-032 | Credential pool operations | Adapter + Platform | Implement multi-provider and multi-deployment credential pools, credential leasing, quota metadata, health checks, cooldown, rotation, revocation, provider-safe retry, and mapping of provider-neutral pool policy to the qualified LiteLLM gateway without exposing raw secrets to AI Core | Secret values, LiteLLM configuration and provider operations must stay outside AI Core; CP-000E fixes the boundary but supplies no adapter | CP-008 and CP-012 model provider operations milestone | OPEN |
| DEF-033 | Configuration permissions | Control Plane + Governance | Define who may view, draft, approve, activate, roll back, disable, or rotate each configuration and credential type | Admin capability must not imply unrestricted production access | Control Plane authorization milestone | OPEN |
| DEF-034 | Configuration auditability | Control Plane + Audit | Record before/after artifact references, actor, reason, approval, activation time, rollback target, and affected runtime snapshots | Operational changes must be attributable and replayable | Control Plane and Audit integration | OPEN |
| DEF-035 | Hard configuration bounds | AI Core contracts + Control Plane | Define safety ceilings that cannot be weakened from the admin panel | Not every configurable value should be freely editable | Configuration schema tasks | OPEN |
| DEF-036 | Model rollout | Adapter + Control Plane + Evaluation | Support staged rollout, static priority/weight, compatibility-classed bounded fallback, canary comparison, emergency disable, rollback, and exact selected-deployment audit across approved logical model pools | Direct global model replacement and unconstrained cross-model fallback are unsafe; CP-000E selects a simple bounded v1 strategy but does not implement it | CP-008, CP-009, CP-012 and CP-013 model operations milestone | OPEN |
| DEF-037 | Provider-neutral AI ports | AI Core ports + Adapter | Define and implement a provider-neutral `ModelGatewayPort` plus model invocation, streaming, cancellation, deadline, embedding, reranking, and structured-output boundaries; LiteLLM/provider SDK objects must terminate in CP-012 adapters | Existing bounded Core ports prove the pattern, but no production model gateway port or LiteLLM adapter exists; CP-000E fixes strict AI purity | CP-001 contracts with AI-008 runtime and CP-012 adapters | PLANNED |
| DEF-038 | Configuration cache | Adapter | Implement snapshot/config caching, pull-based resolution, invalidation hints, consistency and bounded last-known-good behavior; keep Backend queue state and LiteLLM coordination state outside AI Core with explicit ownership and failure policy | Runtime must remain available during control-plane or registry outages without allowing known revoke/disable to be masked by cache | CP-004 and CP-012 reliability milestone | OPEN |
| DEF-039 | Missing or invalid artifacts | AI Core + Adapter | Define fail-closed behavior for missing, unreadable, revoked, expired, or digest-mismatched artifacts | RuntimeSnapshot references alone do not prove availability or integrity | RuntimeSnapshotFactory implementation | OPEN |
| DEF-040 | Rollback safety and evaluation gates | Control Plane + Evaluation | Define compatibility checks and minimum evaluation gates for prompt, model, retrieval, rule, and policy rollbacks | A syntactically valid previous revision may be operationally incompatible | Pre-production release gate milestone | OPEN |
| DEF-041 | RFC 9457 HTTP mapping | Adapter | Map `ErrorEnvelope` to RFC 9457 Problem Details with context-aware HTTP status, media type, safe extensions, and stable product-controlled problem type URIs | HTTP semantics must remain outside AI Core | HTTP API adapter milestone | PLANNED |
| DEF-042 | Safe-message catalogs | Adapter + Governance | Define versioned Persian and English catalogs for `safe_message_key`, localization fallback, review, and compatibility | ErrorEnvelope stores a message key, not user-facing prose | Error presentation and localization milestone | OPEN |
| DEF-043 | Retry semantics | AI Core policy + Adapter | Define Backend `Retry-After`, per-request bounded backoff/retry budgets, shared deadlines, idempotency interaction, circuit breaking, provider cooldown, compatibility-classed model fallback, and code-specific retry policy | `retryable` only indicates eligibility; Backend overload retry and AI/provider retry are different boundaries and must not create retry storms | CP-010 Backend/API plus AI-009 and CP-012 reliability milestones | OPEN |
| DEF-044 | Internal error records | Platform + Governance + Adapter | Define storage, lookup authorization, retention, redaction, deletion, and incident access for records referenced by `internal_detail_ref` | ErrorEnvelope carries only an opaque reference | Error operations milestone | OPEN |
| DEF-045 | Model qualification matrix | Evaluation + Governance | Build task-specific qualification across architecture review, contract implementation, refactoring, debugging, QueryAnalysis, routing, planning, generation, and final review; compare approved candidate models; and define the validity, freshness, expiry, dependency-revocation, and reuse policy for pinned provider/model/credential/reasoning-profile probe evidence | Model quality, cost, latency, reliability, and provider-probe evidence freshness must be measured and governed rather than assumed; model availability, names, credentials, capabilities, and provider acceptance may change | Evaluation-plane milestone, before changing the default implementation model, and before relying on previously captured provider-probe evidence for activation | PLANNED |
| DEF-046 | Query analyzer implementation | AI Core + Adapter | Implement the trusted analyzer boundary, structured-output prompt, allowlist validation, and one bounded format-repair attempt | CONTRACT-006 defines only the validated payload | Walking Skeleton Query Analyzer task | PLANNED |
| DEF-047 | Query taxonomy governance | AI Core + Governance + Evaluation | Define controlled ambiguity codes, risk signals, entity types, analyzer taxonomy ownership, change policy, and benchmark coverage | Canonical codes need stable operational meaning | Query Analyzer milestone | OPEN |
| DEF-048 | ConversationContext and standalone query | AI Core | Define structured conversation state and standalone-query construction without semantic drift | QueryAnalysis intentionally contains no conversation resolver or standalone query | Context Builder milestone | OPEN |
| DEF-049 | Entity and time resolvers | AI Core ports + Adapter | Implement trusted entity catalogs, candidate resolution, time normalization, ambiguity handling, and resolver validation | Models must not mint canonical entity or time identifiers | Query Analyzer milestone | OPEN |
| DEF-050 | Deterministic routing policy | AI Core | Implement the deterministic policy that consumes validated QueryAnalysis, authorization, RuntimeSnapshot, and policy artifacts to produce RouteDecision | CONTRACT-007 defines only the immutable decision payload | Walking Skeleton deterministic routing task | PLANNED |
| DEF-051 | Route and rationale catalogs | AI Core + Governance | Define versioned Route Catalog and rationale-code catalog with lane compatibility and change governance | Route and rationale are controlled open codes rather than closed schema enums | Routing policy milestone | OPEN |
| DEF-052 | Capability policy and filter resolution | AI Core ports + Adapter | Resolve capability allowlists and approved filter references against effective policy, authorization constraints, health, and runtime state | RouteDecision carries references and literals but does not perform dynamic policy evaluation | Routing and capability-gateway milestone | OPEN |
| DEF-053 | Approved-flow registry | Control Plane + AI Core port | Define immutable approved-flow artifacts, validation, authorization, risk exceptions, activation, rollback, and reference resolution | High-risk Fast and predefined Deterministic flows require auditable approved artifacts | Predefined-flow milestone | OPEN |
| DEF-054 | Route replay and regression evaluation | Evaluation + AI Core | Build replay fixtures and model-independent routing regressions from validated QueryAnalysis and immutable policy inputs | RouteDecision must be reproducible and protected against policy drift | Routing evaluation milestone | OPEN |
| DEF-055 | Budget and deadline binding | AI Core | Bind RouteDecision count limits to ExecutionPlan, RunContext deadlines, scheduler constraints, cancellation, provider budgets, and hard safety ceilings | RouteDecision freezes count limits only; execution-time enforcement belongs to later contracts/runtime | Walking Skeleton execution-control task | PLANNED |
| DEF-056 | ExecutionPlan builders | AI Core | **Delivered bounded baseline:** `build_fast_execution_plan(...)` constructs the canonical single-step fast-document plan. **Remaining production work:** predefined-flow builders, the complex bounded Planner, and production route-to-plan composition | The typed artifact and bounded fast builder exist; broader builders and Planner behavior do not | AI-002 Adaptive Routing and Bounded Planning | PLANNED |
| DEF-057 | Plan validation and route binding | AI Core | **Delivered bounded baseline:** the fast-document builder verifies analysis, route, budget, capability, approved-flow, and canonical-plan bindings. **Remaining production work:** a general `PlanValidator` across every supported lane, approved flow, and bounded replan revision | Bounded route-to-plan validation exists, but the general validator and policy-stability checks do not | AI-002 with AI-009 | PLANNED |
| DEF-058 | Planning catalogs and typed bindings | AI Core contracts + Control Plane | Define capability-operation, goal, fact-type, source-reference, and typed producer/consumer binding catalogs | Open controlled codes need versioned ownership and resolvable semantics outside the closed ExecutionPlan schema | Capability and planning catalog milestone | OPEN |
| DEF-059 | Graph scheduler | AI Core + Adapter | **Delivered bounded baseline:** the Walking Skeleton executes the canonical single-step plan with bounded async control. **Remaining production work:** generic topological scheduling, bounded parallelism, dependency release, cancellation, deadlines, and terminal propagation for multi-step plans | A single-step executor exists; the general DAG scheduler does not | AI-002 with AI-009 | PLANNED |
| DEF-060 | Plan replay and regression | Evaluation + AI Core | Build plan replay evaluator and regression fixtures for deterministic, predefined, and composite plans | Accepted plan shape does not prove policy stability or runtime reproducibility | Planning evaluation milestone | OPEN |
| DEF-061 | CapabilityRequest boundary | AI Core contract + Adapter | Define the typed request contract and capability gateway boundary used to invoke approved operations | ExecutionPlan and StepResult reference execution concepts but no request envelope or gateway contract exists yet | Walking Skeleton capability-gateway task | PLANNED |
| DEF-062 | StepResult validator | AI Core | **Delivered bounded baseline:** `validate_step_result(...)` checks request, snapshot, plan, step, capability, operation, fact, scope, attempt, and declared-output bindings for the accepted flow. **Remaining production work:** validation across the complete capability and typed-output catalogs | Bounded cross-artifact validation exists; production catalog coverage and adapter integration do not | AI-006 with CP-012 | PLANNED |
| DEF-063 | Typed output registry | AI Core port + Adapter + Control Plane | Define typed-output schema catalog, immutable artifact registry, resolver port, versioning, and digest lookup | StepResult carries opaque typed-output references but cannot resolve or prove their schema or existence | Capability output registry milestone | OPEN |
| DEF-064 | Output canonicalization | AI Core + Adapter | Define canonical serialization, digest computation, validation, and byte-stable replay rules for capability outputs | Digest and reference fields do not by themselves prove canonical content identity | Capability output integrity milestone | OPEN |
| DEF-065 | Capability response adapters | Adapter | **Delivered bounded baseline:** in-memory test fakes exercise the capability boundary and valid `StepResult` production. **Remaining production work:** validate and map real provider, database, retrieval, selector, rule, and search responses into approved typed outputs and StepResult inputs | External responses are untrusted and provider-specific; no production adapter exists | CP-012 and the relevant AI capability packages | PLANNED |
| DEF-066 | Step retry and protected failure enforcement | AI Core + Adapter | Bind StepResult retry state to plan attempt budgets, retry policy, cancellation, and protected internal error records | StepResult records status and references but does not execute retry or incident policy | Walking Skeleton reliability task | PLANNED |
| DEF-067 | StepResult-to-Evidence materialization | AI Core | **Delivered bounded baseline:** the fast-document runtime invokes a trusted materializer boundary that produces document evidence for the accepted step. **Remaining production work:** complete provenance, subject/time/version, authorization, registry, and relationship binding across all capabilities | Bounded materialization exists; production Source Registry and multi-capability binding do not | AI-006 with AI-003 and CP-005/CP-006 | PLANNED |
| DEF-068 | Step execution replay and metrics | Evaluation + Observability + AI Core | Implement step replay evaluation plus outcome, retry, latency, and budget metrics without leaking sensitive payloads | Contract tests do not establish runtime reliability or performance | Execution evaluation milestone | OPEN |
| DEF-069 | Evidence Manager | AI Core | **Delivered bounded baseline:** `build_evidence_bundle(...)` performs deterministic candidate-integrity, acceptance-policy, fact-map, coverage, and abstention handling for the fast-document flow. **Remaining production work:** full authorization eligibility, authority/time registry binding, cross-source relationships, conflict resolution, and multi-capability sufficiency | A bounded Evidence Manager exists; the production eligibility and registry semantics do not | AI-006 with AI-003 and AI-007 | PLANNED |
| DEF-070 | EvidenceBundle factory and provenance binding | AI Core | **Delivered bounded baseline:** trusted `EvidenceBundle` construction binds the accepted fast-document artifacts to request, plan, snapshot, and bounded authorization lineage. **Remaining production work:** the complete production authorization envelope, Source Registry, relationship, and multi-step provenance bindings | Bounded bundle construction exists; complete production lineage does not | AI-006 with AI-003 | PLANNED |
| DEF-071 | Evidence policy catalogs | AI Core + Governance + Evaluation | Define versioned coverage, contradiction, freshness, subject/time compatibility, source-quality, and evidence-acceptance policies with benchmark coverage | Operational meaning must be governed independently of the closed schema | Evidence policy milestone | OPEN |
| DEF-072 | Evidence source registry and locator access | AI Core port + Adapter + Platform | Implement trusted source registry, source-version resolution, opaque locator resolution, access control, and citation-safe display metadata | Evidence and FinalCitation store references only and must not authorize dereferencing or expose raw URLs | Citation and source-registry milestone | OPEN |
| DEF-073 | Evidence lifecycle and evaluation | Platform + Governance + Evaluation | Define evidence cache, retention, redaction, deletion, replay fixtures, regression tests, and conflict/coverage metrics | Contracts do not grant storage rights or prove evidence quality over time | Evidence operations and evaluation milestones | OPEN |
| DEF-074 | AnswerPlan builder and planner | AI Core | **Delivered bounded baseline:** `build_answer_plan(...)` constructs deterministic answer or abstention plans for the accepted fast-document flow. **Remaining production work:** clarification, partial-answer, complex composite, and policy-driven production answer planning | A bounded AnswerPlanner exists; the complete product outcome planner does not | AI-007 | PLANNED |
| DEF-075 | AnswerPlan-to-Evidence binding | AI Core | **Delivered bounded baseline:** the fast-document AnswerPlanner verifies bundle lineage and mirrors accepted evidence into bounded claims, sections, caveats, and citation slots. **Remaining production work:** complete claim authorization/support, prohibited-claim, budget, and semantic binding across all answer modes | Bounded exact-flow binding exists; full production and semantic binding do not | AI-007 | PLANNED |
| DEF-076 | Answer planning policy catalogs | AI Core + Governance | Define controlled section types, claim/caveat policies, reason codes, citation-slot rules, answer-type policy, and organization-specific planning constraints | Controlled codes need stable ownership and cannot be inferred from free-form model output | Answer planning policy milestone | OPEN |
| DEF-077 | AnswerPlan semantic and numeric validation | AI Core + Evaluation | Implement deterministic and bounded semantic/numeric checks for planned claims, caveats, unsupported assertions, conflicts, and prohibited claim codes | The contract proves shape and local invariants, not truth, arithmetic correctness, or policy meaning | Answer validation milestone | OPEN |
| DEF-078 | AnswerPlan replay and regression | Evaluation + AI Core | Build replay fixtures and regression metrics for outcome selection, claim coverage, caveat use, citation-slot planning, and budget adherence | Planner behavior must remain stable across model, prompt, policy, and retrieval changes | Answer planning evaluation milestone | OPEN |
| DEF-079 | Generator and deterministic renderer | AI Core port + Adapter | **Delivered bounded baseline:** a provider-neutral `AnswerRendererPort`, bounded `RenderRequest`, rendered-draft validation, and in-memory test renderer exist. **Remaining production work:** the minimal `GenerationRequest`, real model/deterministic renderer adapters, structured-output policy, and production failure controls | Bounded rendering exists; no production generator or renderer adapter exists | AI-007 with AI-008 and CP-012 | PLANNED |
| DEF-080 | FinalAnswer factory and finalizer | AI Core | **Delivered bounded baseline:** `finalize_pending_answer(...)` is the trusted bounded factory for `FinalAnswer`, enforcing lineage, render structure, citation authorization, count, budget, timestamp, and terminal bindings. **Remaining production work:** semantic/numeric validation, publication-time revocation recheck, production content resolution, and generalized answer modes | The bounded finalization pipeline exists; production semantic assurance and adapters do not | AI-007 | PLANNED |
| DEF-081 | Claim and numeric semantic validator | AI Core + Evaluation | Validate each generated claim against only its authorized supporting evidence, including deterministic numeric checks and bounded repair/fallback policy | Pydantic proves structure, not factual or numerical support | Claim-validation milestone | OPEN |
| DEF-082 | Citation Compiler | AI Core + Adapter | **Delivered bounded baseline:** server-side citation compilation and source-binding checks create `FinalCitation` values from bounded trusted resolver output and reject fabricated or unauthorized citation data. **Remaining production work:** Source Registry-backed content/locator resolution, citation-safe metadata, historical relationship semantics, and production adapters | Bounded citation compilation exists; the production resolver and registry do not | AI-007 with CP-005/CP-006 and CP-012 | PLANNED |
| DEF-083 | Finalization cross-artifact binding | AI Core | Verify exact AnswerPlan, EvidenceBundle, RouteDecision, ExecutionPlan, AuthorizationDecision, RuntimeSnapshot, request, outcome, count, and budget bindings before FinalAnswer construction | **Delivered bounded baseline:** trusted finalization with cross-artifact binding checks exists for the bounded Walking Skeleton flow. **Remaining production obligation:** the complete binding set across AnswerPlan, EvidenceBundle, RouteDecision, ExecutionPlan, AuthorizationDecision, RuntimeSnapshot, request, outcome, count, and budget outside the bounded flow. Missing `DONE` criterion: full cross-artifact verification for production lanes; FinalAnswer still cannot inspect the referenced artifacts itself | Walking Skeleton finalization-validation task | PLANNED |
| DEF-084 | Final rendering and localization | Adapter + Governance | Render validated content, citations, freshness notes, caveats, and safe-message keys into Persian/English transport output without changing semantics | User presentation, localization, formatting, and safe fallbacks are outside the core contract | Response rendering milestone | OPEN |
| DEF-085 | Streaming semantics | AI Core + Adapter | Define whether and how draft tokens, validated sections, citations, cancellation, partial delivery, and terminal outcomes may be streamed | FinalAnswer is a terminal artifact and current contracts do not authorize partial publication | Streaming milestone after non-streaming Walking Skeleton | OPEN |
| DEF-086 | FinalAnswer lifecycle | Platform + Governance | Define persistence, cacheability, retention, redaction, deletion, access, replay, and legal-hold rules for FinalAnswer and linked artifacts | Contract validity does not authorize storage, caching, or disclosure | Response data-governance milestone | OPEN |
| DEF-087 | FinalAnswer audit, telemetry, and evaluation | Audit + Observability + Evaluation | Record trace-safe finalization events and evaluate citation validity, claim support, outcome correctness, degradation, abstention, and failure behavior | **Delivered bounded baseline:** the Walking Skeleton emits a fail-closed audit event before durable idempotency completion. **Remaining production obligation:** the trace-safe finalization event taxonomy, durable completion semantics, and evaluation of citation validity, claim support, outcome correctness, degradation, abstention, and failure behaviour. Missing `DONE` criterion: the evaluation plane and durable audit integration (`DEF-098`, `DEF-114`, `DEF-115`); structural tests do not measure runtime answer quality or operational health | Evaluation-plane and audit-integration milestones | OPEN |
| DEF-088 | FinalAnswer HTTP response adapter | Adapter | Map successful FinalAnswer outcomes to stable API response and rendering contracts while keeping RFC 9457 ErrorEnvelope handling separate | Transport status, media type, streaming, and UI payloads must remain outside AI Core | HTTP API adapter milestone | OPEN |
| DEF-089 | Architecture coverage assessment | Governance | Review the canonical repository, approved documents, contract evidence, documentation, and Deferred Register to confirm delivered work is correctly represented and every remaining approved obligation is explicitly deferred; the assessment itself creates no runtime code, architecture tests, machine-readable baseline, or repository artifact | Contract tests alone do not prove complete architecture and deferred-work coverage | AUDIT-001 review-only assessment and final delta review | VERIFYING |
| DEF-090 | Contract Foundation documentation baseline | Governance | Maintain the complete Git-traceable Persian Notion knowledge base and implemented-versus-planned inventory, synchronized to the canonical Git snapshot and Deferred Register | The accepted contracts and deferred work need a stable navigation and review layer without making Notion canonical | DOC-001.1 final delta review after committing this register | VERIFYING |
| DEF-091 | Walking Skeleton | AI Core + Adapter | Implement one bounded end-to-end flow from TurnInput through authorization, analysis, routing, planning, test capability, StepResult, EvidenceBundle, AnswerPlan, FinalAnswer, and AuditEvent | **Delivered bounded baseline.** The bounded in-process end-to-end flow is implemented in Git, locally verified, independently reviewed, and accepted, so all four `DONE` criteria are met for the bounded scope. The earlier claim that the runtime pipeline was not connected is corrected against Git. Production generalization is not part of this item and is represented by the existing production items, including the repaired `DEF-092` | Closed for the bounded scope; production generalization tracked by `DEF-092` | DONE |
| DEF-092 | Orchestrator and bounded execution loop | AI Core | **Delivered bounded baseline:** deterministic routing primitives, bounded planning primitives, the bounded execution loop, and the current Walking Skeleton behaviour. **Remaining production work:** the production Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, bounded replan, cancellation and general failure controls, and complete terminal route handling for `RouteDecision(lane="deny")` | The bounded execution loop exists in Git, so the earlier statement that no runtime orchestrator connects the accepted contracts is no longer true. The Walking Skeleton contains bounded deterministic routing, planning, and execution primitives only; it is **not** the complete production Orchestrator and Planner. Missing `DONE` criterion: implementation of the production components listed above. Production Orchestrator responsibilities are lane selection, capability limiting, bounded execution-budget assignment, conditional Planner invocation, and control of request execution and state transitions; production Planner responsibilities are decomposition, evidence-requirement identification, selection of pre-authorized capabilities only, dependency and bounded-parallelism definition, and result composition, under at most five steps, bounded parallelism, and at most one bounded replan. Fast questions use a deterministic one-step plan and require no LLM Planner | AI-002 Adaptive Routing and Bounded Planning as primary owner, with AI-009 Latency, Budget, Cache and Failure Control as supporting owner for budgets, bounded parallelism, cancellation, and failure controls | PLANNED |
| DEF-093 | Document Retrieval / Fast RAG and ingestion pipeline | AI Core capability + Adapter + Platform | Implement authorized ingestion and retrieval including quarantine release, OCR/parsing, structural chunking, embedding, immutable index builds, reindexing, alias/rollback lifecycle, authorization-filtered retrieval, reranking, evidence construction, freshness, citation metadata, revocation/physical cleanup, and Persian retrieval benchmarks | Only generic contracts exist; no ingestion, retrieval capability, index lifecycle, or storage adapter is implemented | Document Retrieval milestone | OPEN |
| DEF-094 | Semantic Analytics / secure NL2SQL | AI Core capability + Adapter | Implement typed logical-plan generation, deterministic compiler, AST/policy validation, approved views, read-only execution, evidence output, and evaluation | No model-produced SQL may execute directly and the analytics runtime is not implemented | Semantic Analytics milestone | OPEN |
| DEF-095 | Personal Selector | AI Core capability + Adapter | Implement authorized candidate selection, deterministic filters/ranking, personal-data minimization, evidence output, and evaluation | Personal-data access and selection logic require dedicated policy and adapters | Personal Selector milestone | OPEN |
| DEF-096 | Rule Evaluator | AI Core capability + Adapter | Implement versioned deterministic rules, input binding, trace-safe outcomes, evidence generation, and evaluation | Rule artifacts and runtime evaluator are not yet implemented | Rule Evaluator milestone | OPEN |
| DEF-097 | Official Search | AI Core capability + Adapter | Implement optional allowlisted official-source search with policy, freshness, evidence, citation, and failure controls | External web access is optional and deployment-profile dependent | Official Search milestone when enabled by organization profile | OPEN |
| DEF-098 | Evaluation Plane | Evaluation + Platform | Implement datasets, replay harnesses, task/model qualification, regression gates, red-team suites, release evidence, and production-candidate evaluation separate from Langfuse | Contract tests and observability are not the independent evaluation plane required by the architecture | Evaluation Plane milestone | OPEN |
| DEF-099 | Product/API/UI integration | Adapter + Control Plane | Build backend controllers, admission/job-status/cancellation and overload DTOs, Admin Website configuration workflows, product-safe presentation, masked credential/deployment read models, and the Central Source Approver pending-review read model and bounded review-surface contract around the AI Core | Frontend, HTTP controllers, Backend queue APIs, AI configuration UI and source-review read models do not exist; CP-000E fixes that UI changes provider-neutral artifacts only through Control Plane commands | CP-009, CP-010 and CP-011 product integration milestones | OPEN |
| DEF-100 | Deployment, scalability, availability, and production operations | Platform + Governance | Define an Organization Deployment Profile and NFR/SLO baseline, then implement Backend admission for the initial 300 active / 1,500 queued assumption, bounded queue and load shedding, independent LiteLLM gateway scaling, separated Backend-queue and gateway-coordination stores, secret management, networking, readiness/liveness, graceful shutdown, bulkheads, horizontal scaling, backups, RPO/RTO, game days, IaC, incident response and runbooks | The current repository is an AI Core contract package, not a deployable production product; CP-000E records capacity assumptions only, and no throughput or concurrency guarantee exists without PERF-001 evidence | CP-010, CP-012, PERF-001 and production-readiness milestones | OPEN |
| DEF-101 | Software supply-chain security | Platform + Governance | Implement SBOM generation, artifact signing, build provenance/attestation, dependency and model-artifact verification, trusted internal mirrors where required, release-integrity checks, and the exact immutable `BuildArtifact` metadata, qualification, provenance, digest, and verification rules consumed by `ConfigurationRelease` and `RuntimeSnapshotFactory` | Build success alone does not prove software, model, or release-pinned `BuildArtifact` integrity; the exact qualified metadata shape is not yet contracted | Secure build and release milestone before production deployment; CP-001 and CP-004 contract/factory design | OPEN |
| DEF-102 | Threat-model baseline | Governance + Security + Evaluation | Implement and continuously review the CP-000E threat/test baseline across prompt injection, provider output, LiteLLM/private-network exposure, credential leakage, queue flooding, retry storms, stale revoke, admin tampering, cross-scope evidence, audit leakage, event replay, supply chain, Redis boundary separation, cancellation and degraded fallback | CP-000E defines architecture threats and owners, but security controls and abuse tests are not implemented | CP-014 and CP-013 before production of each affected boundary | OPEN |

### CP-000R additions (architecture-gap obligations)

These nineteen items record implementation gaps confirmed by the integrated architecture audit, the
accepted CP ADRs, and the final cross-document review. Each is documentation-complete and
implementation-absent.

| ID | Area | Layer | Deferred item | Why deferred | Target / trigger | Status |
|---|---|---|---|---|---|---|
| DEF-103 | Source authority binding | AI Core contracts + Control Plane | Bind the existing controlled `authority` code to trusted Source Registry authority metadata (`authority_class_ref`, `issuer_ref` / `authority_ref`, `authority_assignment_policy_ref`), and add the versioned authority catalog and the deterministic conflict-precedence function | Evidence 1.0.0 **already carries** `authority` as a controlled canonical code; what is missing is the binding to trusted registry metadata, the catalog, and the ranking function (audit finding G-001, re-scoped by CP-000R against the committed contract) | CP-001 Control Plane Contracts with CP-005 Department Source Registry | OPEN |
| DEF-104 | Source temporal derivation and revalidation | AI Core contracts + Control Plane | Deterministically derive and revalidate evidence temporal values against `SourceRevision.effective_from`, nullable `SourceRevision.valid_until`, and current Source Registry lifecycle state, and derive index `valid_from` / `valid_until` from them | Evidence 1.0.0 **already carries** `EvidenceValidityWindow` (`as_of`, `valid_from`, `valid_to`) and `EvidenceSourceTime` (`observed_at`, `published_at`); what is missing is trusted derivation and revalidation, and upload time must never be treated as business publication time (audit finding G-002, re-scoped by CP-000R against the committed contract) | CP-001 Control Plane Contracts with CP-005 Department Source Registry and CP-006 Ingestion and Index Lifecycle | OPEN |
| DEF-105 | Node lifecycle and node metadata publication | Control Plane | Implement node create, rename, move/re-parent with authorization plus audit plus path/scope cache invalidation, `ACTIVE` / `NON_ACTIVE` transitions, and the explicit node-metadata publication policy including default-deny and Guest denial | ADR-CP-001 fixes the rules; no typed lifecycle/publication contracts, application service, or directory read-model/API boundary exist (audit findings G-003, G-020) | CP-001 Control Plane Contracts with CP-002 Authorization Hierarchy, CP-009 Control Plane Application Services, and CP-010 Backend/API Integration Boundary | OPEN |
| DEF-106 | Typed AuthorizationRequest and decision binding | AI Core contracts | Define a typed `AuthorizationRequest`, the exact request-to-decision binding, decision expiry enforcement, the consulted policy revision reference, and the authorized scope reference | `AuthorizationDecision 1.0.0` carries `policy_version` only; the binding is not contractually expressible (audit finding G-004) | CP-001 with CP-002 | OPEN |
| DEF-107 | RetrievalAuthorizationEnvelope | AI Core contracts + Adapter | Define the envelope that separates the authorization decision from the trusted, non-bypassable retrieval filter inputs, including the Mandatory Isolation Metadata Subset | ADR-CP-003 mandates a mandatory pre-filter but no typed envelope carries its inputs (audit finding G-005) | CP-002 with AI-003 | OPEN |
| DEF-108 | First-class typed Guest principal | AI Core contracts | Introduce `AnonymousGuest` as a first-class typed principal alongside `AuthenticatedPrincipal`, with the invariant that authentication failure never downgrades into Guest | Guest is an accepted architecture actor but has no typed representation (audit finding G-006) | CP-001 with CP-002 | OPEN |
| DEF-109 | Evidence eligibility validator | AI Core | Implement deterministic per-unit eligibility validation covering authorized scope membership, organization, classification ceiling, source active state, source revision eligibility, source digest, effective time, authority, the `SUPERSEDES` / `SUPPLEMENTS` relation, and current revocation state | Post-retrieval checks are defense in depth only and no validator exists (audit finding G-007) | AI-003 Retrieval Engine with AI-006 Hybrid Execution and Evidence Composition | OPEN |
| DEF-110 | Minimal GenerationRequest boundary | AI Core contracts | Define the minimal typed generation request boundary carrying only the sanitized question, approved claims, approved caveats, bounded authorized evidence content, answer constraints, and response locale, and never the full `RuntimeContext`, the full principal, roles or groups, the `AuthorizationDecision`, raw source-management metadata, or provider credentials | No typed boundary exists between `AnswerPlan` and the generator (audit finding G-008) | AI-007 Answer Planning, Citation and Validation | OPEN |
| DEF-111 | Bounded evidence content resolution | AI Core port + Adapter | Implement bounded trusted resolution of evidence content and opaque locators with authorization, citation-safe display metadata, and historical-revision resolvability | Evidence carries references only and cannot resolve them (audit finding G-009) | AI-007 Answer Planning, Citation and Validation as primary owner, with CP-006 Ingestion and Index Lifecycle and CP-012 Production Adapters as dependencies | OPEN |
| DEF-112 | Numeric and semantic claim validation | AI Core + Evaluation | Implement deterministic numeric checks, semantic faithfulness and entailment checking, unsupported-claim rejection, bounded repair, and safe abstention or fallback | Current validation proves structure, not semantic support (audit finding G-010) | AI-007 Answer Planning, Citation and Validation with CP-013 Evaluation and Rollout Gates | OPEN |
| DEF-113 | Publication-time eligibility and revocation recheck | Control Plane + AI Core | Implement a deterministic current-eligibility and revocation recheck **before final answer publication**, covering the exact race in which retrieval succeeds and the source or its visibility policy is then revoked before finalization and publication, including the invalidation propagation budget and fail-closed behaviour | Revocation is architecturally immediate, but no recheck runs between successful retrieval and publication (audit finding G-011). This is not a difference between authorization-decision time and retrieval time, and it is not implemented today | AI-007 Answer Planning, Citation and Validation with CP-006 Ingestion and Index Lifecycle | OPEN |
| DEF-114 | Audit outcome taxonomy | AI Core contracts + Audit | Type the full outcome taxonomy `answered`, `partial`, `clarification_required`, `abstained`, `policy_rejected`, `authorization_denied`, `failed`, keeping `authorization_denied` distinct from `policy_rejected` | `AuditEvent 1.0.0` does not carry the required taxonomy (audit finding G-012) | CP-001 for typed contract/versioning, CP-009 for application-service semantics and emission, CP-012 for durable persistence/delivery consumption where applicable, AI-002 for terminal lifecycle, and AI-007 for finalization/publication hooks | OPEN |
| DEF-115 | Runtime lineage in audit and durable completion semantics | AI Core + Audit | Carry the complete runtime lineage in audit records: organization, actor scope, subject, time scope, source version, policy version, `ConfigurationRelease`, `RuntimeSnapshot`, and run or request identifier; and resolve the pre-completion versus durable-completion meaning of `runtime.turn.completed` | No current contract carries the complete nine-element lineage, and the completion event is currently emitted before durable idempotency completion (audit findings G-013, C-006) | CP-001 for typed contracts, CP-009 for application-service semantics and emission, CP-012 for durable persistence and delivery, AI-002 for request/run lifecycle, and AI-007 for finalization/publication hooks | OPEN |
| DEF-116 | RuntimeSnapshot naming and namespace vNext | AI Core contracts | Rename `source_revision` to `application_source_revision`, add a namespace to `RuntimeArtifactRef`, and disambiguate `security_policy` as the global configuration artifact rather than a per-source visibility policy | The 1.0.0 field names are ambiguous and collision-prone; no version bump is authorized in this baseline (audit findings G-014, G-015, G-016, NEW-006) | CP-001 with CP-004 | OPEN |
| DEF-117 | Aggregate IndexSnapshot manifest and factory equivalence | AI Core contracts + Control Plane | Define the logical aggregate `IndexSnapshot` manifest with routing metadata, and enforce exact equivalence between the `ConfigurationRelease` manifest and the denormalized `RuntimeSnapshot` references | `index_snapshot` is a single named reference while retrieval may consult several eligible physical snapshots, and release/snapshot duplication is unchecked (audit findings G-017, G-018, NEW-005, NEW-007) | CP-006 with CP-004 | OPEN |
| DEF-118 | Terminal handling for `RouteDecision(lane="deny")` | AI Core runtime | Implement complete terminal handling for `RouteDecision(lane="deny")` in the Runtime, and move clarification and abstention out of the error envelope into answer outcomes. An authorization deny occurs before routing and yields `UNAUTHORIZED` with no `RouteDecision`; a route or policy deny is `RouteDecision(lane="deny")` and yields `POLICY_REJECTED` with a zero execution budget and no capability execution | **The contract already contains the `deny` terminal lane**, so nothing must be added to `RouteDecision 1.0.0`. The gap is that the bounded Runtime and Walking Skeleton do not yet handle that lane terminally, and clarification and abstention still travel the error path (audit findings C-004 re-scoped by CP-000R, and C-005) | AI-002 Adaptive Routing and Bounded Planning | OPEN |
| DEF-119 | Source metadata class split implementation | Control Plane + AI Core | Implement `CitationSafePublishedSourceMetadata`, `ManagementSourceMetadata`, `LifecycleAuditMetadata`, and `RawSourceContent` as separately permissioned resources, and name the Mandatory Isolation Metadata Subset distinctly from the complete CP-006 chunk metadata contract | A single "view source metadata" permission would leak management and lifecycle data to ordinary readers and Guests, while the complete chunk/index metadata contract remains undefined (audit findings C-003, G-019) | CP-001 Control Plane Contracts with CP-006 Ingestion and Index Lifecycle and CP-009 Control Plane Application Services | OPEN |
| DEF-120 | Independent verification of tests and schemas | Governance + Evaluation | Perform an independent review of the committed test suite and JSON Schemas against the accepted architecture, rather than relying on documentation and reported totals | The integrated audit did not independently audit tests or schemas; this is a recorded residual audit limitation (audit finding G-022) | CP-013 with Governance | OPEN |
| DEF-121 | SourceRelationship and partial-amendment contracts | AI Core contracts + Control Plane | Define and implement the versioned `SourceRelationship` contract and trusted registry behavior for `SUPERSEDES` between revisions of one `KnowledgeSource`, `SUPPLEMENTS` between separate `KnowledgeSource` instances, relationship provenance and authorization, deterministic lifecycle effects, conflict and citation behavior, and future `AMENDS` / `PARTIALLY_SUPERSEDES` semantics | Architecture documents define `SUPERSEDES` and `SUPPLEMENTS`, but no typed relationship contract, registry record, resolver, persistence rule, or validator exists. Partial amendment remains explicitly deferred and must never be guessed (integration finding NEW-001) | CP-001 Control Plane Contracts with CP-005 Department Source Registry and CP-006 Ingestion and Index Lifecycle | OPEN |

## Package ownership map

Canonical package names. These names are authoritative and must not be renamed or replaced by
alternatives in any document.

| Package | Canonical name | Deferred obligations owned |
| --- | --- | --- |
| CP-000E | Model Boundary, Integration, Audit and Threat Baseline | Accepted architecture closure package; does not mark LiteLLM, Backend queue, Redis, UI, audit or security implementation complete |
| CP-001 | Control Plane Contracts | `DEF-103`, `DEF-104`, `DEF-105`, `DEF-106`, `DEF-108`, `DEF-114`, `DEF-115`, `DEF-116`, `DEF-119`, `DEF-121` |
| CP-002 | Authorization Hierarchy | `DEF-105`, `DEF-106`, `DEF-107`, `DEF-108` |
| CP-003 | Artifact Registry Core | Artifact revision registry and validation layers |
| CP-004 | RuntimeSnapshotFactory | `DEF-101`, `DEF-116`, `DEF-117` |
| CP-005 | Department Source Registry | `DEF-103`, `DEF-104`, `DEF-121` |
| CP-006 | Ingestion and Index Lifecycle | `DEF-104`, `DEF-111`, `DEF-113`, `DEF-117`, `DEF-119`, `DEF-121` |
| CP-007 | Retrieval and Official Search Profiles | Retrieval-profile and official-search policy obligations; does **not** own node-directory publication |
| CP-008 | Model/Provider/Credential Pool | `DEF-032`, `DEF-036`, `DEF-045`; provider, deployment, credential pool and qualification obligations |
| CP-009 | Control Plane Application Services | `DEF-099`, `DEF-105`, `DEF-114`, `DEF-115`, `DEF-119`; owns source-activation application-service semantics |
| CP-010 | Backend/API Integration Boundary | `DEF-043`, `DEF-099`, `DEF-100`, `DEF-105`; Backend admission, queue/overload, Django integration and read-model/API boundaries |
| CP-011 | Admin Website Integration | `DEF-099`; admin surface obligations |
| CP-012 | Production Adapters | `DEF-032`, `DEF-037`, `DEF-038`, `DEF-043`, `DEF-100`, `DEF-101`, `DEF-111`, `DEF-115`; LiteLLM, Redis/queue, Secret Manager, storage, delivery and physical topology |
| CP-013 | Evaluation and Rollout Gates | `DEF-045`, `DEF-112`, `DEF-120` |
| CP-014 | Security Closure | Production hardening and compliance closure |
| AI-001 | Conversation Context and Persian Understanding | Context building, Persian understanding, query analysis |
| AI-002 | Adaptive Routing and Bounded Planning | **Orchestrator, Fast Plan, Planner, Plan Validator, Approved Flows, Bounded Replan, route-to-plan composition**; `DEF-092`, `DEF-114`, `DEF-115`, `DEF-118` |
| AI-003 | Retrieval Engine | `DEF-107`, `DEF-109` |
| AI-004 | Semantic Catalog and NL2SQL | Semantic catalog and NL2SQL obligations |
| AI-005 | Personal Selector and Rule Evaluator | Selector and rule evaluation obligations |
| AI-006 | Hybrid Execution and Evidence Composition | `DEF-109`; capability execution and evidence composition |
| AI-007 | Answer Planning, Citation and Validation | `DEF-110`, `DEF-111`, `DEF-112`, `DEF-113`, `DEF-114`, `DEF-115` |
| AI-008 | Model, Prompt and Structured Output Runtime | Model, prompt, and structured-output runtime obligations |
| AI-009 | Latency, Budget, Cache and Failure Control | Latency, budgets, bounded parallelism, and failure controls; supporting owner of `DEF-092` |
| AI-010 | Official Search, General Web Search and Attachments | Official search, general web search, and attachment obligations |
| PERF-001 | Performance and load qualification | Performance, latency, selectivity, capacity, and load qualification |

Orchestrator and Planner are owned by **AI-002 Adaptive Routing and Bounded Planning**. They are never
owned by the Django backend, by the Control Plane, by CP-009, by AI-006 alone, by AI-007, or by AI-010.

## Model-qualification acceptance dimensions

`DEF-045` must evaluate models per task rather than using one global quality score.

Minimum dimensions:

1. contract and architectural compliance;
2. unauthorized-scope change rate;
3. compile, Ruff, mypy, test, and schema-drift success rate;
4. security-invariant violation rate;
5. patch applicability and Git hygiene;
6. Persian requirement comprehension;
7. retry count and human correction effort;
8. latency and token/cost consumption;
9. regression consistency across repeated runs;
10. escalation policy for tasks that require the strongest approved model.

## Control-plane invariants

1. AI Core consumes an immutable, fully resolved `RuntimeSnapshot`.
2. Admin UI and backend never mutate an approved artifact revision.
3. Every change creates a new versioned artifact.
4. Activation changes an audited pointer, not historical content.
5. Sensitive changes require explicit authorization and, where configured, approval.
6. Activation must be atomic and rollbackable.
7. Unsafe values must be blocked by contract-level hard limits.
8. API keys and credentials are stored only in a Secret Manager.
9. Frontend receives masked credential metadata, never secret values.
10. Every run records the effective configuration references used.
11. Provider SDK objects, URLs, credentials, and mutable config dictionaries never enter AI Core domain contracts.
12. Control-plane or registry failure must use a validated last-known-good snapshot or fail closed according to policy.

## Update rule

Every task review must:

1. add newly deferred work;
2. assign the correct architectural layer;
3. link every `PLANNED` item to a concrete task or milestone;
4. use `VERIFYING` after implementation but before the complete local acceptance gate;
5. mark an item `DONE` only after local verification and independent review;
6. record a short rationale before marking an item `DROPPED`;
7. avoid deleting completed history;
8. split a delivered contract from its still-deferred runtime, adapter, evaluation, governance, or operational implementation;
9. avoid duplicate items by referencing an existing ID when a later contract depends on the same work;
10. keep Notion synchronized as a mirror, never as a competing source of truth.

## Immediate next gates

Delivery sequence:

```text
CP-000R  (accepted at 8d94c6a)  ->  CP-000E  (accepted at 882a2ef)  ->  CP-001  (next)
```

1. Begin CP-001 Control Plane Contracts. CP-001 is no longer blocked by an architecture gate.
2. Keep all LiteLLM, Backend queue, Redis, Admin Website, audit and security implementation items open until their package evidence passes.
3. Resolve the `uv` version-range warning (`uv-build>=0.9.2,<0.10` versus local `uv 0.12.1`) as a
   toolchain obligation; it is currently unresolved.
4. Complete the final delta review for `DEF-089` and `DEF-090`; mark them `DONE` only after all four
   `DONE` criteria are met and Git, the exported documentation, and the accepted audit conclusion agree.
5. Resolve `DEF-016` before approving any new public wire contract such as `CapabilityRequest` or a
   future top-level `RunContext` contract.
6. Resolve `DEF-118`, that is complete terminal runtime handling for `RouteDecision(lane="deny")`
   (the `deny` lane already exists in the contract), before `AI-002`, and `DEF-114` / `DEF-115` before
   relying on any audit record as durable completion evidence.
7. Acceptance of the contract artifacts, and acceptance of an architecture document, must not mark
   their separate runtime, adapter, security, evaluation, governance, or operational items complete.


## Version 0.7.0 change log

- Updated the accepted repository evidence baseline to CP-000R commit `8d94c6a`.
- Recorded CP-000E as accepted at `882a2ef` and CP-001 as the next unblocked package.
- Expanded `DEF-032`, `DEF-036`, `DEF-037`, `DEF-038`, `DEF-043`, `DEF-099`, `DEF-100`, and `DEF-102` with the accepted LiteLLM, Backend queue, Redis separation, Admin Website, capacity, audit, emergency, and threat boundaries.
- Added no new DEF identifier because CP-000E obligations map to existing implementation items without duplication.
- Recorded that 300 active and 1,500 queued are Backend/PERF assumptions, not AI Core configuration or a proven production guarantee.
- Preserved the range `DEF-001` through `DEF-121` and all existing statuses.

## Version 0.6.0 change log

- Replaced the stale repository-state evidence with the authoritative snapshot: branch `main`, HEAD
  `6477c1c`, clean working tree, latest accepted architecture baseline CP-000D.
- Recorded the architect-supplied verification evidence captured on the canonical local machine, and
  stated explicitly that it was not independently reproduced while preparing this repair.
- Recorded the unresolved `uv` version-range build warning.
- Added the bounded-versus-production split for `DEF-002`, `DEF-083`, `DEF-087`, and `DEF-091`.
- Stated the four `DONE` criteria explicitly: implementation, local verification, independent review,
  and an accepted package.
- Added nineteen architecture-gap obligations after `DEF-102`; the final item, `DEF-121`, independently tracks `SourceRelationship` and partial-amendment contracts.
- Added the package ownership map across `CP-001`..`CP-014`, `AI-001`..`AI-010`, `PERF-001`, and
  `CP-000E`.
- Replaced the stale next-gate list with the `CP-000R -> CP-000E -> CP-001` sequence.
- Recalculated the register summary from the actual table: 121 tracked items, range `DEF-001` through
  `DEF-121`, with `DONE` 6, `PLANNED` 26, `VERIFYING` 2, `OPEN` 87, `DROPPED` 0.
- Reconciled bounded delivery with production work for the implemented routing, plan construction and
  validation, step validation, materialization, Evidence Manager, AnswerPlanner, renderer, finalizer,
  citation compiler, idempotency, cross-artifact binding, audit/telemetry, and Walking Skeleton rows.
  `DEF-091` is `DONE` for its bounded scope; production Orchestrator and Planner work remains in the
  repaired `DEF-092` rather than a duplicate identifier.
- Preserved every existing `DEF-001` through `DEF-102` identifier and historical traceability. Selected
  statuses and wording were corrected against accepted Git evidence, including `DEF-091`; no identifier
  was deleted, renumbered, or reused.

## Version 0.5.0 change log

- Updated the evidence baseline to the reviewed authoritative `main` snapshot and recorded that no Contract Foundation code correction was identified by AUDIT-001.
- Reframed `DEF-089` as the approved review-only architecture coverage assessment and moved it to `VERIFYING` pending final Git/document delta acceptance.
- Moved `DEF-090` to `VERIFYING` pending synchronization of this register and the corrected Notion export.
- Expanded `DEF-004`, `DEF-012`, `DEF-093`, and `DEF-100` to cover trusted ingestion/quarantine, pinned telemetry semantics, complete ingestion/index lifecycle, and organization-specific scalability/availability/operations.
- Added `DEF-101` for software supply-chain security and `DEF-102` for threat-model and abuse/security-test baselines.
- Removed stale mainline-publication gates and replaced them with the actual next steps: commit this register, synchronize the limited documentation delta, close the audit, and begin Walking Skeleton design.
- Preserved all existing `DEF-001` through `DEF-100` identifiers and their historical meaning; no existing identifier was renumbered or deleted.

## Version 0.4.0 historical change log

- Corrected the delivery baseline from `CONTRACT-006 VERIFYING` / `CONTRACT-007 PLANNED` to accepted contracts through `CONTRACT-012.1`.
- Marked `DEF-005` complete because QueryAnalysis semantics were accepted and later full suites passed; runtime analyzer work remains in `DEF-046` through `DEF-049`.
- Kept compatibility governance open as planned work and recorded the scope of the FinalAnswer correction without treating it as repository-wide resolution.
- Added `DEF-056` through `DEF-088` for ExecutionPlan, StepResult, Evidence, AnswerPlan, and FinalAnswer runtime obligations.
- Added `DEF-089` and `DEF-090` for architecture conformance and Contract Foundation documentation.
- Added `DEF-091` through `DEF-100` for the Walking Skeleton, Orchestrator, product capabilities, Evaluation Plane, product integration, and production operations.
- Preserved all existing `DEF-001` through `DEF-055` identifiers and completed history.
