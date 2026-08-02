# Deferred Items Register

**Version:** 0.5.0  
**Updated:** 2026-08-02  
**Canonical source:** Git after this file is committed to the authoritative repository  
**Recommended repository path:** `docs/deferred-items.md`  
**Notion role:** dashboard and status mirror only

## Purpose

This register tracks work that is intentionally deferred, not yet supported, partially delivered, or completed while preserving the remaining runtime and operational obligations.

It keeps the AI Core small and provider-neutral while preventing contract-only delivery from being mistaken for a complete runtime product.

## Evidence basis and repository-state note

- Contract acceptance baseline: `CONTRACT-000` through `CONTRACT-012`, including corrective task `CONTRACT-012.1`.
- Authoritative reviewed repository snapshot: branch `main`, HEAD `5d9775c024141fc9f261882fd9476df6d88dd13d`, tree `74b31b7ff325f8d86167fd34148086dfa738faa8`, clean working tree.
- Genuine local acceptance evidence: full suite `1536 passed`, total coverage `97.31%`, Ruff/mypy/syntax/import gates green, `verify-exit=0`, and successful wheel/source-distribution builds.
- AUDIT-001 review found no code correction requirement in the Contract Foundation: all 13 committed JSON Schemas match their Pydantic models, public exports are controlled, schemas are closed, and no transport, database, cloud, observability-vendor, or model-provider SDK dependency enters the current AI Core package.
- The repository copy of the Deferred Register was stale and must be replaced by this version before Git can be treated as canonical for deferred-work tracking.
- `DONE` means the accepted artifact itself is complete; it does not close the separate runtime, adapter, governance, evaluation, privacy, supply-chain, or operational items listed below.

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
| RouteDecision | `DONE` | CONTRACT-007; routing policy remains deferred |
| ExecutionPlan | `DONE` | CONTRACT-008; builders, validation, and scheduling remain deferred |
| StepResult | `DONE` | CONTRACT-009; runtime validator and output registry remain deferred |
| Evidence and EvidenceBundle | `DONE` | CONTRACT-010; Evidence Manager and source lifecycle remain deferred |
| AnswerPlan | `DONE` | CONTRACT-011; planner and exact evidence binding remain deferred |
| FinalAnswer | `DONE` | CONTRACT-012 plus CONTRACT-012.1; finalizer, generator, validators, and Citation Compiler remain deferred |

## Register summary

- Total tracked items: **102**
- `DONE`: **5**
- `PLANNED`: **27**
- `VERIFYING`: **2**
- `OPEN`: **68**
- `DROPPED`: **0**

## Complete register

| ID | Area | Layer | Deferred item | Why deferred | Target / trigger | Status |
|---|---|---|---|---|---|---|
| DEF-001 | TurnInput provenance | Adapter | Enforce trusted origins for `request_id`, `received_at`, `channel`, `conversation_id`, and attachment references | Pydantic validates shape, not provenance | Walking Skeleton transport adapter | OPEN |
| DEF-002 | Idempotency | AI Core + Adapter | Define scope, TTL, payload fingerprint, replay behavior, concurrent requests, and conflicting key reuse | `TurnInput` currently carries only the idempotency key | Runtime request handling | OPEN |
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
| DEF-032 | Credential pool operations | Adapter + Platform | Define credential leasing, quotas, health checks, cooldown, rotation, revocation, and provider-safe retry behavior | Secret values and provider operations must stay outside AI Core | Model provider operations milestone | OPEN |
| DEF-033 | Configuration permissions | Control Plane + Governance | Define who may view, draft, approve, activate, roll back, disable, or rotate each configuration and credential type | Admin capability must not imply unrestricted production access | Control Plane authorization milestone | OPEN |
| DEF-034 | Configuration auditability | Control Plane + Audit | Record before/after artifact references, actor, reason, approval, activation time, rollback target, and affected runtime snapshots | Operational changes must be attributable and replayable | Control Plane and Audit integration | OPEN |
| DEF-035 | Hard configuration bounds | AI Core contracts + Control Plane | Define safety ceilings that cannot be weakened from the admin panel | Not every configurable value should be freely editable | Configuration schema tasks | OPEN |
| DEF-036 | Model rollout | Adapter + Control Plane + Evaluation | Support staged rollout, traffic weighting, canary comparison, automatic fallback, emergency disable, and rollback | Direct global model replacement is unsafe | Model operations milestone | OPEN |
| DEF-037 | Provider-neutral AI ports | AI Core ports + Adapter | Define provider-neutral model invocation, embedding, reranking, and structured-output ports | Provider SDK objects must never enter domain contracts | Walking Skeleton provider-neutral port task | PLANNED |
| DEF-038 | Configuration cache | Adapter | Define snapshot/config caching, invalidation, consistency, and last-known-good behavior | Runtime must remain available during control-plane or registry outages | Walking Skeleton reliability milestone | OPEN |
| DEF-039 | Missing or invalid artifacts | AI Core + Adapter | Define fail-closed behavior for missing, unreadable, revoked, expired, or digest-mismatched artifacts | RuntimeSnapshot references alone do not prove availability or integrity | RuntimeSnapshotFactory implementation | OPEN |
| DEF-040 | Rollback safety and evaluation gates | Control Plane + Evaluation | Define compatibility checks and minimum evaluation gates for prompt, model, retrieval, rule, and policy rollbacks | A syntactically valid previous revision may be operationally incompatible | Pre-production release gate milestone | OPEN |
| DEF-041 | RFC 9457 HTTP mapping | Adapter | Map `ErrorEnvelope` to RFC 9457 Problem Details with context-aware HTTP status, media type, safe extensions, and stable product-controlled problem type URIs | HTTP semantics must remain outside AI Core | HTTP API adapter milestone | PLANNED |
| DEF-042 | Safe-message catalogs | Adapter + Governance | Define versioned Persian and English catalogs for `safe_message_key`, localization fallback, review, and compatibility | ErrorEnvelope stores a message key, not user-facing prose | Error presentation and localization milestone | OPEN |
| DEF-043 | Retry semantics | AI Core policy + Adapter | Define `Retry-After`, bounded backoff, retry budgets, idempotency interaction, circuit breaking, and code-specific retry policy | `retryable` only indicates eligibility, not execution | Runtime reliability milestone | OPEN |
| DEF-044 | Internal error records | Platform + Governance + Adapter | Define storage, lookup authorization, retention, redaction, deletion, and incident access for records referenced by `internal_detail_ref` | ErrorEnvelope carries only an opaque reference | Error operations milestone | OPEN |
| DEF-045 | Model qualification matrix | Evaluation + Governance | Build task-specific qualification across architecture review, contract implementation, refactoring, debugging, QueryAnalysis, routing, planning, generation, and final review; compare currently approved candidates such as Opus, Sonnet, Kimi, GLM, and future models | Model quality, cost, latency, and reliability must be measured rather than assumed; model availability and names may change | Evaluation-plane milestone and before changing the default implementation model | PLANNED |
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
| DEF-056 | ExecutionPlan builders | AI Core | Implement deterministic FastPlan builder, predefined-flow plan builder, and bounded composite planner | CONTRACT-008 defines the immutable plan artifact, not the trusted builders that produce it | Walking Skeleton planning task | PLANNED |
| DEF-057 | Plan validation and route binding | AI Core | Implement `PlanValidator` and exact `RouteDecision`-to-`ExecutionPlan` binding verification | Structural validation cannot prove that the plan realizes the authorized route, budgets, capabilities, or approved flow | Walking Skeleton planning-validation task | PLANNED |
| DEF-058 | Planning catalogs and typed bindings | AI Core contracts + Control Plane | Define capability-operation, goal, fact-type, source-reference, and typed producer/consumer binding catalogs | Open controlled codes need versioned ownership and resolvable semantics outside the closed ExecutionPlan schema | Capability and planning catalog milestone | OPEN |
| DEF-059 | Graph scheduler | AI Core + Adapter | Implement topological scheduling, bounded parallelism, dependency release, cancellation, deadlines, and terminal propagation | ExecutionPlan validates a bounded DAG but does not execute it | Walking Skeleton executor task | PLANNED |
| DEF-060 | Plan replay and regression | Evaluation + AI Core | Build plan replay evaluator and regression fixtures for deterministic, predefined, and composite plans | Accepted plan shape does not prove policy stability or runtime reproducibility | Planning evaluation milestone | OPEN |
| DEF-061 | CapabilityRequest boundary | AI Core contract + Adapter | Define the typed request contract and capability gateway boundary used to invoke approved operations | ExecutionPlan and StepResult reference execution concepts but no request envelope or gateway contract exists yet | Walking Skeleton capability-gateway task | PLANNED |
| DEF-062 | StepResult validator | AI Core | Implement `StepResultValidator` with exact request, snapshot, plan, step, capability, operation, fact, scope, attempt, and output-set binding checks | CONTRACT-009 proves envelope shape only and intentionally defers cross-artifact validation | Walking Skeleton execution-validation task | PLANNED |
| DEF-063 | Typed output registry | AI Core port + Adapter + Control Plane | Define typed-output schema catalog, immutable artifact registry, resolver port, versioning, and digest lookup | StepResult carries opaque typed-output references but cannot resolve or prove their schema or existence | Capability output registry milestone | OPEN |
| DEF-064 | Output canonicalization | AI Core + Adapter | Define canonical serialization, digest computation, validation, and byte-stable replay rules for capability outputs | Digest and reference fields do not by themselves prove canonical content identity | Capability output integrity milestone | OPEN |
| DEF-065 | Capability response adapters | Adapter | Validate and map provider, database, retrieval, selector, rule, and search responses into approved typed outputs and StepResult inputs | External responses are untrusted and provider-specific | Walking Skeleton test adapter, then capability adapter milestones | PLANNED |
| DEF-066 | Step retry and protected failure enforcement | AI Core + Adapter | Bind StepResult retry state to plan attempt budgets, retry policy, cancellation, and protected internal error records | StepResult records status and references but does not execute retry or incident policy | Walking Skeleton reliability task | PLANNED |
| DEF-067 | StepResult-to-Evidence materialization | AI Core | Materialize accepted StepResult facts into Evidence items with exact provenance, scope, subject, time, version, and authorization bindings | CONTRACT-009 and CONTRACT-010 remain separate structural artifacts until a trusted materializer links them | Walking Skeleton evidence-materialization task | PLANNED |
| DEF-068 | Step execution replay and metrics | Evaluation + Observability + AI Core | Implement step replay evaluation plus outcome, retry, latency, and budget metrics without leaking sensitive payloads | Contract tests do not establish runtime reliability or performance | Execution evaluation milestone | OPEN |
| DEF-069 | Evidence Manager | AI Core | Implement deterministic Evidence Manager validation for schema, acceptance, authorization, claim support, coverage, subject, time, freshness, and conflict handling | CONTRACT-010 defines Evidence and EvidenceBundle shapes, not evidence sufficiency or trusted acceptance | Walking Skeleton evidence-manager task | PLANNED |
| DEF-070 | EvidenceBundle factory and provenance binding | AI Core | Implement trusted EvidenceBundle construction from accepted capability outputs and StepResults with exact request, plan, snapshot, and authorization linkage | A valid bundle can still be unrelated to the executing run unless cross-artifact bindings are checked | Walking Skeleton evidence-bundle task | PLANNED |
| DEF-071 | Evidence policy catalogs | AI Core + Governance + Evaluation | Define versioned coverage, contradiction, freshness, subject/time compatibility, source-quality, and evidence-acceptance policies with benchmark coverage | Operational meaning must be governed independently of the closed schema | Evidence policy milestone | OPEN |
| DEF-072 | Evidence source registry and locator access | AI Core port + Adapter + Platform | Implement trusted source registry, source-version resolution, opaque locator resolution, access control, and citation-safe display metadata | Evidence and FinalCitation store references only and must not authorize dereferencing or expose raw URLs | Citation and source-registry milestone | OPEN |
| DEF-073 | Evidence lifecycle and evaluation | Platform + Governance + Evaluation | Define evidence cache, retention, redaction, deletion, replay fixtures, regression tests, and conflict/coverage metrics | Contracts do not grant storage rights or prove evidence quality over time | Evidence operations and evaluation milestones | OPEN |
| DEF-074 | AnswerPlan builder and planner | AI Core | Implement trusted `AnswerPlan` factory for deterministic, fast, clarification, partial-answer, abstention, and bounded composite outcomes | CONTRACT-011 validates a plan artifact but does not decide or construct one | Walking Skeleton answer-planning task | PLANNED |
| DEF-075 | AnswerPlan-to-Evidence binding | AI Core | Implement exact binding from AnswerPlan claims, caveats, sections, citation slots, prohibited claims, budgets, and outcome to the accepted EvidenceBundle | Structural validity cannot prove that every planned claim is authorized and supportable by accepted evidence | Walking Skeleton answer-plan validation task | PLANNED |
| DEF-076 | Answer planning policy catalogs | AI Core + Governance | Define controlled section types, claim/caveat policies, reason codes, citation-slot rules, answer-type policy, and organization-specific planning constraints | Controlled codes need stable ownership and cannot be inferred from free-form model output | Answer planning policy milestone | OPEN |
| DEF-077 | AnswerPlan semantic and numeric validation | AI Core + Evaluation | Implement deterministic and bounded semantic/numeric checks for planned claims, caveats, unsupported assertions, conflicts, and prohibited claim codes | The contract proves shape and local invariants, not truth, arithmetic correctness, or policy meaning | Answer validation milestone | OPEN |
| DEF-078 | AnswerPlan replay and regression | Evaluation + AI Core | Build replay fixtures and regression metrics for outcome selection, claim coverage, caveat use, citation-slot planning, and budget adherence | Planner behavior must remain stable across model, prompt, policy, and retrieval changes | Answer planning evaluation milestone | OPEN |
| DEF-079 | Generator and deterministic renderer | AI Core port + Adapter | Implement provider-neutral generation and deterministic rendering paths with no tool access and strictly bounded structured output | Final answer text is not produced by any runtime component yet | Walking Skeleton generation task | PLANNED |
| DEF-080 | FinalAnswer factory and finalizer | AI Core | Implement the only trusted factory allowed to construct FinalAnswer after generation/rendering, claim validation, citation compilation, and final validation | CONTRACT-012 validates the terminal artifact but does not implement the finalization pipeline | Walking Skeleton finalization task | PLANNED |
| DEF-081 | Claim and numeric semantic validator | AI Core + Evaluation | Validate each generated claim against only its authorized supporting evidence, including deterministic numeric checks and bounded repair/fallback policy | Pydantic proves structure, not factual or numerical support | Claim-validation milestone | OPEN |
| DEF-082 | Citation Compiler | AI Core + Adapter | Compile citation slots into server-generated citations using trusted source metadata and resolvable opaque locators; reject fabricated or unauthorized citations | The Generator must not create URLs, pages, labels, versions, or locator values | Walking Skeleton citation-compiler task | PLANNED |
| DEF-083 | Finalization cross-artifact binding | AI Core | Verify exact AnswerPlan, EvidenceBundle, RouteDecision, ExecutionPlan, AuthorizationDecision, RuntimeSnapshot, request, outcome, count, and budget bindings before FinalAnswer construction | FinalAnswer contains identifiers but cannot inspect the referenced artifacts itself | Walking Skeleton finalization-validation task | PLANNED |
| DEF-084 | Final rendering and localization | Adapter + Governance | Render validated content, citations, freshness notes, caveats, and safe-message keys into Persian/English transport output without changing semantics | User presentation, localization, formatting, and safe fallbacks are outside the core contract | Response rendering milestone | OPEN |
| DEF-085 | Streaming semantics | AI Core + Adapter | Define whether and how draft tokens, validated sections, citations, cancellation, partial delivery, and terminal outcomes may be streamed | FinalAnswer is a terminal artifact and current contracts do not authorize partial publication | Streaming milestone after non-streaming Walking Skeleton | OPEN |
| DEF-086 | FinalAnswer lifecycle | Platform + Governance | Define persistence, cacheability, retention, redaction, deletion, access, replay, and legal-hold rules for FinalAnswer and linked artifacts | Contract validity does not authorize storage, caching, or disclosure | Response data-governance milestone | OPEN |
| DEF-087 | FinalAnswer audit, telemetry, and evaluation | Audit + Observability + Evaluation | Record trace-safe finalization events and evaluate citation validity, claim support, outcome correctness, degradation, abstention, and failure behavior | Structural tests do not measure runtime answer quality or operational health | Evaluation-plane and audit-integration milestones | OPEN |
| DEF-088 | FinalAnswer HTTP response adapter | Adapter | Map successful FinalAnswer outcomes to stable API response and rendering contracts while keeping RFC 9457 ErrorEnvelope handling separate | Transport status, media type, streaming, and UI payloads must remain outside AI Core | HTTP API adapter milestone | OPEN |
| DEF-089 | Architecture coverage assessment | Governance | Review the canonical repository, approved documents, contract evidence, documentation, and Deferred Register to confirm delivered work is correctly represented and every remaining approved obligation is explicitly deferred; the assessment itself creates no runtime code, architecture tests, machine-readable baseline, or repository artifact | Contract tests alone do not prove complete architecture and deferred-work coverage | AUDIT-001 review-only assessment and final delta review | VERIFYING |
| DEF-090 | Contract Foundation documentation baseline | Governance | Maintain the complete Git-traceable Persian Notion knowledge base and implemented-versus-planned inventory, synchronized to the canonical Git snapshot and Deferred Register | The accepted contracts and deferred work need a stable navigation and review layer without making Notion canonical | DOC-001.1 final delta review after committing this register | VERIFYING |
| DEF-091 | Walking Skeleton | AI Core + Adapter | Implement one bounded end-to-end flow from TurnInput through authorization, analysis, routing, planning, test capability, StepResult, EvidenceBundle, AnswerPlan, FinalAnswer, and AuditEvent | Contracts are complete but the runtime pipeline is not connected | Milestone 5 after DOC-001 and AUDIT-001 | PLANNED |
| DEF-092 | Orchestrator and bounded execution loop | AI Core | Implement deterministic state transitions, lane execution, bounded retry/replan, cancellation, terminal outcomes, and no-unbounded-agent guarantees | No runtime orchestrator currently connects the accepted contracts | Walking Skeleton and orchestration milestones | PLANNED |
| DEF-093 | Document Retrieval / Fast RAG and ingestion pipeline | AI Core capability + Adapter + Platform | Implement authorized ingestion and retrieval including quarantine release, OCR/parsing, structural chunking, embedding, immutable index builds, reindexing, alias/rollback lifecycle, authorization-filtered retrieval, reranking, evidence construction, freshness, citation metadata, revocation/physical cleanup, and Persian retrieval benchmarks | Only generic contracts exist; no ingestion, retrieval capability, index lifecycle, or storage adapter is implemented | Document Retrieval milestone | OPEN |
| DEF-094 | Semantic Analytics / secure NL2SQL | AI Core capability + Adapter | Implement typed logical-plan generation, deterministic compiler, AST/policy validation, approved views, read-only execution, evidence output, and evaluation | No model-produced SQL may execute directly and the analytics runtime is not implemented | Semantic Analytics milestone | OPEN |
| DEF-095 | Personal Selector | AI Core capability + Adapter | Implement authorized candidate selection, deterministic filters/ranking, personal-data minimization, evidence output, and evaluation | Personal-data access and selection logic require dedicated policy and adapters | Personal Selector milestone | OPEN |
| DEF-096 | Rule Evaluator | AI Core capability + Adapter | Implement versioned deterministic rules, input binding, trace-safe outcomes, evidence generation, and evaluation | Rule artifacts and runtime evaluator are not yet implemented | Rule Evaluator milestone | OPEN |
| DEF-097 | Official Search | AI Core capability + Adapter | Implement optional allowlisted official-source search with policy, freshness, evidence, citation, and failure controls | External web access is optional and deployment-profile dependent | Official Search milestone when enabled by organization profile | OPEN |
| DEF-098 | Evaluation Plane | Evaluation + Platform | Implement datasets, replay harnesses, task/model qualification, regression gates, red-team suites, release evidence, and production-candidate evaluation separate from Langfuse | Contract tests and observability are not the independent evaluation plane required by the architecture | Evaluation Plane milestone | OPEN |
| DEF-099 | Product/API/UI integration | Adapter + Control Plane | Build backend controllers, transport DTOs, user interface, administration workflows, and product-safe presentation around the AI Core | Frontend, HTTP controllers, admin product, and business integration are outside the contract package | Product integration milestones | OPEN |
| DEF-100 | Deployment, scalability, availability, and production operations | Platform + Governance | Define an Organization Deployment Profile and NFR/SLO baseline, then implement isolated organization deployment, databases, queues, secret management, networking, CI/CD, readiness/liveness, graceful shutdown, bounded concurrency, bulkheads, backpressure/load shedding, horizontal scaling, backups, RPO/RTO profiles, restore drills, high availability, game days, fleet inventory, IaC, incident response, and operational runbooks | The current repository is an AI Core contract package, not a deployable production product; production characteristics must be explicit per organization profile | Deployment and production-readiness milestones | OPEN |
| DEF-101 | Software supply-chain security | Platform + Governance | Implement SBOM generation, artifact signing, build provenance/attestation, dependency and model-artifact verification, trusted internal mirrors where required, release-integrity checks, and verification procedures for consumed artifacts | Build success alone does not prove software or model supply-chain integrity | Secure build and release milestone before production deployment | OPEN |
| DEF-102 | Threat-model baseline | Governance + Security + Evaluation | Create and review a threat model and abuse/security test plan for every approved trust boundary, including user input, identity, authorization, model output, tool/provider output, attachments, evidence, SQL planning, citations, configuration, audit, and administration | Contract validation describes shape but does not enumerate threats, abuse paths, mitigations, or security-test coverage | Before implementing each affected runtime boundary; Walking Skeleton receives the minimum applicable baseline | OPEN |

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

1. Replace the stale repository copy with this register at `docs/deferred-items.md`, commit it on authoritative `main`, and run the complete local verification/build gate.
2. Perform a limited DOC-001.1/Notion delta update so the documented register version becomes `0.5.0`, the range becomes `DEF-001` through `DEF-102`, and AUDIT-001 is described as a review-only assessment.
3. Complete the final delta review for `DEF-089` and `DEF-090`; mark them `DONE` only after Git, the exported documentation, and the accepted audit conclusion agree.
4. Resolve `DEF-016` before approving any new public wire contract such as `CapabilityRequest` or a future top-level `RunContext` contract.
5. Start Walking Skeleton discovery and technical design only after the previous gates are accepted; do not begin implementation before `DESIGN_APPROVED`.
6. Acceptance of the contract artifacts must not mark their separate runtime, adapter, security, evaluation, governance, or operational items complete.

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
