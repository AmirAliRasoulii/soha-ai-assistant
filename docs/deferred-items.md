# Deferred Items Register

**Version:** 0.2.0  
**Updated:** 2026-08-01  
**Canonical source:** Git  
**Recommended path:** `docs/deferred-items.md`  
**Notion role:** dashboard and status mirror only

## Purpose

This register tracks work that is intentionally deferred, not yet supported, or only partially implemented.

It prevents architectural decisions from being lost while keeping each delivery task small and focused.

## Architectural ownership

| Layer | Responsibility |
|---|---|
| `AI Core` | Typed contracts, domain rules, routing, planning, evidence, generation rules, evaluation, and vendor-neutral ports |
| `Adapter` | HTTP, identity providers, policy engines, model providers, search engines, storage, observability, and other external integrations |
| `Control Plane` | Admin UI/backend, versioned configuration management, approvals, activation, rollback, and operational workflows |
| `Platform` | Secret management, deployment, networking, databases, queues, CI/CD, infrastructure, and runtime operations |
| `Governance` | Compatibility policy, release policy, documentation, review rules, and audit requirements |

## Status values

- `OPEN`: acknowledged, not yet assigned to a concrete task
- `PLANNED`: assigned to a concrete task or milestone
- `VERIFYING`: implemented or delivered, but the full local acceptance gate has not passed
- `DONE`: implemented, locally verified, independently reviewed, and accepted
- `DROPPED`: intentionally not supported, with rationale recorded

## Current delivered baseline

| Item | Status |
|---|---|
| Common contract primitives | `DONE` |
| TurnInput and AttachmentRef | `DONE` |
| SecurityPrincipalContext | `DONE` |
| AuthorizationDecision and AuthorizationResourceRef | `DONE` |
| RuntimeSnapshot | `VERIFYING` |

## Register

| ID | Area | Layer | Deferred item | Why deferred | Target / trigger | Status |
|---|---|---|---|---|---|---|
| DEF-001 | TurnInput | Adapter | Enforce trusted origins for `request_id`, `received_at`, `channel`, `conversation_id`, and attachment references | Pydantic validates shape, not provenance | Walking Skeleton transport adapter | OPEN |
| DEF-002 | Idempotency | AI Core + Adapter | Define scope, TTL, payload fingerprint, replay behavior, concurrent requests, and conflicting key reuse | `TurnInput` currently carries only the idempotency key | Runtime request handling | OPEN |
| DEF-003 | Transport limits | Adapter | Enforce HTTP request byte-size, upload-size, and transport payload limits | Character limits are not transport limits | API boundary | OPEN |
| DEF-004 | Attachments | Adapter + Platform | Resolve trusted metadata: media type, size, digest, malware scan status, classification, and retention class | `AttachmentRef` intentionally contains only opaque identity and version | Ingestion and trusted storage milestone | OPEN |
| DEF-005 | Query processing | AI Core | Produce `NormalizedQuery` from `raw_message` | Normalized text must never be client-controlled | QueryAnalysis contract and implementation | PLANNED |
| DEF-006 | Security | AI Core | Implement `SecurityPrincipalContext` | Identity facts must be separated from user input | CONTRACT-002 | DONE |
| DEF-007 | Authorization | AI Core | Implement `AuthorizationDecision` with policy version, effect, reason codes, obligations, constraints, and resource binding | Roles and groups are policy inputs, not authorization decisions | CONTRACT-002 | DONE |
| DEF-008 | Runtime reproducibility | AI Core | Implement immutable `RuntimeSnapshot` with digest-pinned artifact references | Required for replay, evaluation, debugging, and controlled hotfixes | CONTRACT-003 local verification | VERIFYING |
| DEF-009 | Errors | AI Core + Adapter | Define `DomainError` and map it to RFC 9457 Problem Details at the HTTP boundary | Pydantic errors and transport errors must remain separate | CONTRACT-004 | PLANNED |
| DEF-010 | Audit | AI Core + Adapter + Platform | Define append-only `AuditEvent`, delivery semantics, deduplication, retention, integrity, and sensitive-data controls | Audit must be independent of logs and traces | CONTRACT-005 and audit adapter milestone | PLANNED |
| DEF-011 | Privacy | Governance + Platform | Define persistence, retention, redaction, deletion, legal hold, and access policies for messages and attachment references | Contracts do not authorize persistence | Runtime, conversation, and audit policy milestones | OPEN |
| DEF-012 | Observability | Adapter | Define request/run/trace correlation and W3C Trace Context mapping | Domain contracts must not depend on observability SDKs | Walking Skeleton observability task | OPEN |
| DEF-013 | Compatibility | Governance | Add producer/consumer compatibility tests for approved contract versions | Schema-drift tests do not prove cross-version compatibility | Contract release process | OPEN |
| DEF-014 | Localization | AI Core + Adapter | Add supported locales and channels through explicit versioned contract changes | `TurnInput 1.0.0` supports only `fa-IR` and `web` | First additional locale or channel | OPEN |
| DEF-015 | Validation UX | Adapter | Translate validation and domain failures into safe Persian user-facing messages | Internal validation errors must not leak directly to users | Error presentation layer | OPEN |
| DEF-016 | Compatibility governance | Governance | Reconcile general additive-version guidance with closed models using `extra="forbid"` | Adding even an optional field can break existing producers and consumers | Contract Register revision | OPEN |
| DEF-017 | Versioning governance | Governance | Clarify that `schema_version` is required on top-level wire or persisted contracts, not every nested value object | Repeating versions on nested objects creates noise and inconsistent evolution | Contract Register revision | OPEN |
| DEF-018 | RuntimeSnapshot factory | AI Core port + Adapter | Implement trusted `RuntimeSnapshotFactory`, RFC 8785 canonicalization, SHA-256 computation, registry resolution, and fail-closed digest verification | CONTRACT-003 validates metadata format only | Walking Skeleton configuration boundary | PLANNED |
| DEF-019 | Admin configuration | Control Plane | Build a versioned Admin Control Plane for runtime configuration artifacts | Frontend/backend configuration workflows are outside the AI Core | Control Plane milestone | OPEN |
| DEF-020 | Retrieval configuration | AI Core contract + Control Plane | Define versioned `RetrievalProfile` artifacts for candidate count, reranker count, evidence count, thresholds, source caps, and context budgets | `RuntimeSnapshot` currently stores only an immutable reference | Retrieval configuration task | OPEN |
| DEF-021 | Model policy and pool | AI Core contract + Adapter + Control Plane | Define model policy and LLM pool configuration with priorities, weights, fallbacks, timeouts, capabilities, rate limits, and health state | Provider selection and pool operation must remain replaceable | Model adapter milestone | OPEN |
| DEF-022 | Secrets | Platform + Control Plane | Integrate a Secret Manager and store only credential references plus masked metadata | API keys and credentials must never enter AI Core contracts, RuntimeSnapshot, Git, logs, or traces | Platform security milestone | OPEN |
| DEF-023 | Safe configuration activation | Control Plane | Implement schema validation, security validation, approval, health checks, atomic activation, canary rollout, emergency disable, rollback, and audit | Production hotfixes require controlled lifecycle management | Control Plane milestone | OPEN |
| DEF-024 | Feature flags | AI Core port + Adapter | Define a vendor-neutral feature-flag evaluation port and backend adapter | Feature-flag storage and evaluation backend must remain replaceable | Runtime configuration milestone | OPEN |
| DEF-025 | Policy engine | Adapter | Implement deterministic authorization policy evaluation and produce `AuthorizationDecision` | CONTRACT-002 defines only input/output contracts | Authorization adapter milestone | OPEN |
| DEF-026 | Privileged access | Governance + Adapter | Define delegation, impersonation, and break-glass workflows with approval, expiry, and audit | High-risk workflows require separate governance and controls | Security hardening milestone | OPEN |
| DEF-027 | Session lifecycle | Adapter + Platform | Define session lifecycle, revocation, token introspection, and authentication-provider claim mapping | Raw tokens and provider payloads are intentionally excluded from AI Core | Identity adapter milestone | OPEN |
| DEF-028 | Authorization obligations | AI Core + Adapter | Define effect-dependent obligation semantics and enforcement responsibilities | CONTRACT-002 intentionally allows obligation codes without effect-specific rules | Authorization enforcement milestone | OPEN |
| DEF-029 | Run context | AI Core | Define `RunContext` or `ChatRun` binding request, security context, authorization decision, runtime snapshot, deadline, cancellation, and correlation identifiers | `RuntimeSnapshot` intentionally has no `run_id` | Walking Skeleton contracts | OPEN |
| DEF-030 | Runtime artifact schemas | AI Core contracts + Control Plane | Define versioned schemas and registry semantics for config, prompt, model policy, model artifact, structured-output backend, retrieval, embedding, reranker, index, semantic catalog, rules, security policy, and telemetry artifacts | RuntimeSnapshot references immutable artifacts but does not define their contents | Capability and configuration milestones | OPEN |
| DEF-031 | Artifact registry lifecycle | Control Plane + Platform | Define immutable revisions, digest pinning, active pointers, approvals, retention, rollback, and garbage collection | Safe hotfix and replay require stable artifact lifecycle semantics | Configuration registry milestone | OPEN |
| DEF-032 | Credential pool operations | Adapter + Platform | Define API-key pool leasing, quotas, health checks, cooldown, rotation, revocation, and provider-safe retry behavior | Secret values and provider operations must stay outside AI Core | Model provider operations milestone | OPEN |
| DEF-033 | Configuration permissions | Control Plane + Governance | Define who may view, draft, approve, activate, roll back, or rotate each configuration and credential type | Admin capability must not imply unrestricted production access | Control Plane authorization milestone | OPEN |
| DEF-034 | Configuration auditability | Control Plane + Audit | Record before/after references, actor, reason, approval, activation time, rollback target, and affected runtime snapshots | Operational changes must be attributable and replayable | Control Plane and Audit integration | OPEN |
| DEF-035 | Configuration validation | AI Core contracts + Control Plane | Define hard safety bounds that cannot be weakened from the admin panel | Not every configurable value should be freely editable | Configuration schema tasks | OPEN |
| DEF-036 | Model rollout | Adapter + Control Plane | Support staged rollout, traffic weighting, canary comparison, automatic fallback, and emergency model disable | Direct global model replacement is unsafe for production | Model operations milestone | OPEN |
| DEF-037 | Provider neutrality | AI Core ports + Adapter | Define provider-neutral model invocation, embedding, reranking, and structured-output ports | Provider SDK objects must never enter domain contracts | First model adapter implementation | OPEN |
| DEF-038 | Configuration cache | Adapter | Define snapshot/config caching, invalidation, consistency, and last-known-good behavior | Runtime must remain available during control-plane or registry outages | Walking Skeleton reliability milestone | OPEN |
| DEF-039 | Missing artifact handling | AI Core + Adapter | Define fail-closed behavior for missing, unreadable, revoked, or digest-mismatched artifacts | RuntimeSnapshot references alone do not prove availability or integrity | RuntimeSnapshotFactory implementation | OPEN |
| DEF-040 | Config rollback safety | Control Plane + Evaluation | Define rollback compatibility checks and minimum evaluation gates for prompt, model, retrieval, rule, and policy changes | A syntactically valid previous version may be operationally incompatible | Pre-production release gate milestone | OPEN |

## Control-plane invariants

The future administration system must follow these rules:

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
3. link each `PLANNED` item to a concrete task or milestone;
4. use `VERIFYING` after implementation but before the full local acceptance gate;
5. mark an item `DONE` only after local verification and independent review;
6. record a short rationale before marking an item `DROPPED`;
7. avoid deleting completed history;
8. keep Notion synchronized as a mirror, never as a competing source of truth.
