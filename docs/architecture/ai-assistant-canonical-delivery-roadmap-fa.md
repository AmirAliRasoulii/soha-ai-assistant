# AI Assistant Canonical Delivery Roadmap

Status: Accepted canonical roadmap; CP-000E accepted at commit `882a2ef`
Authority: `CANONICAL_ROADMAP` in `docs/architecture/architecture-authority-manifest.md`
Base branch: `main`
Base repository evidence commit: `8d94c6a`

This file is the canonical delivery roadmap, committed to Git by CP-000R. Its origin is the
architect-supplied canonical source (SHA-256
`b301f6f734da999b930d14fbf237c9da5690504cc26f609286e05a99e1095e97`). CP-000R did **not** merely prepend
a precedence disclaimer to a stale body: the body itself was repaired so that this roadmap is
internally current. Stale phase statements, stale package states, and the obsolete AI configuration
precedence were rewritten in place, and the accepted CP-000D and CP-000R decisions were recorded.

Base repository evidence: `8d94c6a`. That commit contains CP-000R and predates CP-000E. CP-000E was accepted at commit `882a2ef`.

## Package status (authoritative)

| Package | Status |
| --- | --- |
| CP-000A Organization Hierarchy and Authorization Scope Baseline | `COMPLETE at 6e0d907` |
| CP-000B Source Registry and Content Lifecycle Baseline | `COMPLETE at c9416cc` |
| CP-000C Data and Index Isolation, Multi-Node Retrieval Baseline | `COMPLETE at 578f7fa` |
| CP-000D Configuration Artifacts, Activation Lifecycle and RuntimeSnapshot Baseline | `COMPLETE at 6477c1c` |
| CP-000R Complete Architecture Consistency Repair | `COMPLETE at 8d94c6a` |
| CP-000E Model Boundary, Integration, Audit and Threat Baseline | `COMPLETE at 882a2ef` |
| CP-001 Control Plane Contracts | `NEXT / UNBLOCKED` |

Delivery sequence:

```text
CP-000A -> CP-000B -> CP-000C -> CP-000D -> CP-000R -> CP-000E -> CP-001
```

Status rules:

1. `COMPLETE` records that the package was merged at the named commit. It never asserts that the
   decisions it recorded are implemented in code.
2. A package status changes only when a package is accepted; the roadmap is updated in that package.
3. Remaining implementation obligations are tracked in `docs/deferred-items.md`, not here.

## Accepted decisions in force

These decisions are accepted and supersede any earlier statement in this roadmap:

- `ConfigurationRelease` is the unit of configuration activation.
- Activation is **atomic**, through a single active release pointer.
- Rollback is **release-level**, never per-artifact.
- AI configuration is **global-only in v1**. There is no Organization or Department AI configuration
  override in v1.
- A single **System AI Administrator** holds `ai_configuration.manage`.
- The external provider capability probe is **conditional**, not unconditional.
- A single centrally assigned **Central Source Approver** holds `source.review`, `source.approve`, and
  `source.reject` in v1. There is no per-faculty or per-department approver in v1.
- Each `SourceRevision` binds a **pinned `VisibilityPolicyDefinition` revision**. There is no implicit
  follow-latest, and a missing policy revision fails closed.
- `valid_until` is **nullable** and open-ended.
- `SUPERSEDES` applies **within one `KnowledgeSource`**.
- `SUPPLEMENTS` applies **across separate `KnowledgeSource` records**.

## AI configuration precedence (v1)

```text
Platform hard bounds
  -> active global ConfigurationRelease
  -> trusted request authorization and source metadata
  -> immutable RuntimeSnapshot
```

The earlier layered chain that placed platform configuration, then organization configuration, then
node configuration beneath the hard bounds is **obsolete** and must not be used. There is no
Organization or Department AI configuration override in v1.

## Canonical package map

These package names are canonical. They must not be renamed or replaced by alternatives.

| Package | Canonical name |
| --- | --- |
| CP-001 | Control Plane Contracts |
| CP-002 | Authorization Hierarchy |
| CP-003 | Artifact Registry Core |
| CP-004 | RuntimeSnapshotFactory |
| CP-005 | Department Source Registry |
| CP-006 | Ingestion and Index Lifecycle |
| CP-007 | Retrieval and Official Search Profiles |
| CP-008 | Model/Provider/Credential Pool |
| CP-009 | Control Plane Application Services |
| CP-010 | Backend/API Integration Boundary |
| CP-011 | Admin Website Integration |
| CP-012 | Production Adapters |
| CP-013 | Evaluation and Rollout Gates |
| CP-014 | Security Closure |
| AI-001 | Conversation Context and Persian Understanding |
| AI-002 | Adaptive Routing and Bounded Planning |
| AI-003 | Retrieval Engine |
| AI-004 | Semantic Catalog and NL2SQL |
| AI-005 | Personal Selector and Rule Evaluator |
| AI-006 | Hybrid Execution and Evidence Composition |
| AI-007 | Answer Planning, Citation and Validation |
| AI-008 | Model, Prompt and Structured Output Runtime |
| AI-009 | Latency, Budget, Cache and Failure Control |
| AI-010 | Official Search, General Web Search and Attachments |

## Canonical AI Module path

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

**AI-002 Adaptive Routing and Bounded Planning** owns Orchestrator, Fast Plan, Planner, Plan Validator,
Approved Flows, Bounded Replan, and route-to-plan composition. These are never owned by the Django
backend, by the Control Plane, by CP-009, by AI-006 alone, by AI-007, or by AI-010.

The **Orchestrator** selects the fast, clarification, or complex lane; limits the available
capabilities; assigns a bounded execution budget; invokes the Planner only when required; and controls
request execution and state transitions. It is **not** an unconstrained agent: it cannot invent tools,
invent capabilities, expand authorization, ignore the `RuntimeSnapshot`, start unbounded tasks, or run
arbitrary subagents.

The **Planner** decomposes complex questions, identifies evidence requirements, selects only
pre-authorized available capabilities, defines dependencies, defines sequential or bounded parallel
execution, and defines result-composition requirements. Its constraints are a maximum of five steps,
bounded parallelism, at most one bounded replan, no free agent or subagent, no invented tool, no
invented capability, no authorization decision, and no arbitrary personal NL2SQL. Fast questions use a
deterministic one-step plan and do not require an LLM Planner.

The current Walking Skeleton contains bounded deterministic routing, planning, and execution
primitives. It is **not** the complete production Orchestrator and Planner.

---

## Canonical integrated roadmap

# AI Assistant — Canonical Delivery Roadmap

## وضعیت سند

- نوع: Roadmap اجرایی canonical برای ادامه پروژه
- زبان: فارسی، با identifierهای فنی انگلیسی
- مبنا:
  1. Git و قراردادهای committed
  2. ADRهای approved و committed
  3. `ai-assistant-master-handoff-fa`
  4. `ai-module-architecture v0.4`
  5. `evaluation-plane-implementation-blueprint`
- اصل: Git از همه اسناد جدیدتر و authoritativeتر است.
- این فایل جایگزین اسناد معماری اصلی نیست؛ مسیر اجرایی و پوشش requirementها را یکپارچه می‌کند.
- قبل از آغاز هر package، تصمیم‌های همان package با معمار بررسی و تصویب می‌شوند.
- هیچ packageای صرفاً به‌دلیل تولید patch یا گزارش Agent تکمیل‌شده محسوب نمی‌شود.

---

# 1. قواعد تقدم و رفع تعارض

## 1.1 ترتیب تقدم

```text
Committed Git contracts and behavior
→ Approved committed ADRs
→ Master Handoff product roadmap
→ AI Module Architecture runtime detail
→ Evaluation Plane acceptance detail
→ Agent reports and generated patches
```

## 1.2 قواعد رفع تعارض

1. اگر نام یا schema سند AI با ADR جدید تضاد داشت، ADR و Git مقدم‌اند.
2. انتخاب provider، model، vector backend، object storage و IdP تا benchmark یا package مربوطه قطعی نیست.
3. مقادیر عددی latency، top-k، chunk size و model choice در سند AI baseline آزمایشی‌اند، نه hard-coded product law.
4. hard safety bounds فقط در platform policy تعریف می‌شوند و از پنل قابل تضعیف نیستند.
5. Core مستقل از DB، HTTP، UI، cloud، vendor SDK و secret value باقی می‌ماند.
6. هر request با `Immutable RuntimeSnapshot` ثابت اجرا می‌شود.
7. authorization فقط از trusted identity، membership، policy artifact و `AuthorizationDecision` ساخته می‌شود.
8. هیچ role label، department display name، LLM output یا client metadata مجوز ایجاد نمی‌کند.

---

# 2. اصلاحات اعمال‌شده نسبت به AI Module Architecture v0.4

## 2.1 موارد پذیرفته‌شده

موارد زیر از سند AI به roadmap نهایی اضافه و مالک‌دار شدند:

- `ConversationState` و context کوتاه بدون LLM summary در hot path
- Persian normalization، entity/time/reference resolution
- Adaptive Orchestrator با fast path و bounded planning
- حداکثر یک replan
- Retrieval کامل: lexical + dense + fusion + dedup + rerank + parent expansion
- structure-aware chunking و versioned `IndexSnapshot`
- Semantic Catalog و NL2SQL مبتنی بر Logical Plan
- Self Selector و Rule Evaluator مستقل از NL2SQL
- Typed Hybrid composition و fact/evidence table
- Evidence sufficiency، missing facts و conflict detection
- server-side citation compilation
- deterministic و semantic answer validation
- model/prompt routing و structured output
- deadline، budget، cache، retry و circuit breaker
- prompt injection، exfiltration، privacy و cross-user controls
- Official Web Search روی domain allowlist
- Modular Monolith برای AI Runtime با indexing worker مستقل
- replayable state machine و idempotent step execution

## 2.2 موارد اصلاح‌شده

### Authorization metadata

نام‌های نمونه زیر canonical نیستند:

```text
organization_id
visibility
allowed_group_ids
public
```

در implementation باید با artifactهای مصوب هماهنگ شوند:

```text
organization_ref
owning_node_ref
hierarchy_path_ref
visibility_policy_ref
security_scope_ref
classification
anonymous-public
authorized security_scope_refs
```

### Search capabilityها

این capabilityها مستقل‌اند:

```text
Persistent Document Upload
Official Source/URL Registration
Chat Attachment
General Web Search
```

`Official Web Search` جایگزین `General Web Search` نیست.

Baseline نسخه اول می‌تواند فقط Official Search را فعال کند و General Web Search را خاموش نگه دارد، اما contract و feature flag آن مستقل می‌ماند.

### Technology stack

موارد زیر candidate baseline هستند، نه تصمیم نهایی:

```text
OpenSearch
PostgreSQL + pgvector
Qdrant
vLLM
Qwen
BGE-M3
BGE Reranker
Redis
MinIO
Docling
Tesseract
Celery/RabbitMQ
Langfuse
```

انتخاب نهایی براساس benchmark، residency، corpus size، latency، quality، operations و cost انجام می‌شود.

### Production topology

عبارت «سه process کافی است» فقط درباره AI Module runtime profile است:

```text
Chat Runtime
Indexing Worker
Evaluation Runner
```

کل محصول علاوه بر آن ممکن است Control Plane API، Admin Website، persistence، queue، observability و adapter processes داشته باشد.

### Evaluation

مرحله ۱۸ سند AI ناقص است. `Evaluation Plane Blueprint` مرجع کامل evaluation، release gates، security/load/chaos و thesis experiment است.

### Memory

مرحله ۱ و ۸ سند AI در یک package واحد ادغام می‌شوند. در v1:

- no personal long-term memory
- no history embedding
- no LLM compaction in normal hot path
- state scoped to conversation
- persistence behind a port

---

# 3. وضعیت فعلی پروژه

## 3.1 تکمیل‌شده

```text
WS-001
WS-002
WS-003A
WS-003B
WS-004A
WS-004B
Walking Skeleton 1.0.0
```

Walking Skeleton canonical:

```text
TurnInput
→ Authorization
→ Analysis
→ Routing
→ Planning
→ Capability
→ StepResult
→ EvidenceBundle
→ AnswerPlan
→ FinalAnswer/ErrorEnvelope
→ AuditEvent
→ Idempotency completion
→ Telemetry
→ Replay
```

## 3.2 وضعیت authoritative packageها

```text
CP-000A  COMPLETE at 6e0d907
CP-000B  COMPLETE at c9416cc
CP-000C  COMPLETE at 578f7fa
CP-000D  COMPLETE at 6477c1c
CP-000R  COMPLETE at 8d94c6a
CP-000E  COMPLETE at 882a2ef
CP-001   NEXT / UNBLOCKED
```

`CP-000A` تا `CP-000D` همه merge شده‌اند. هیچ commit یا merge معلقی برای آن‌ها باقی نیست، و
هیچ verification یا canonicalization معلقی در Phase 0 باز نیست.

`CP-000R` در commit `8d94c6a` و `CP-000E` در commit `882a2ef` بسته شده‌اند. `CP-001` اکنون
unblocked و package بعدی است.

---

# 4. مدل کلی delivery

```text
Walking Skeleton
→ CP-000 Architecture Baseline
→ Control Plane and Runtime Foundations
→ AI Runtime Completion
→ Product Integration and Production Adapters
→ Evaluation and Rollout Gates
→ Security Closure
→ Performance Qualification
```

`CP-000` فقط پل معماری پیش از implementation است.

`CP-001` تا `CP-012` و packageهای `AI-*` پیاده‌سازی اصلی محصول هستند.

---

# 5. Phase 0 — بستن وضعیت جاری

## P0-01 — Canonicalize CP-000A — `COMPLETE at 6e0d907`

Merged to `main`. Phase 0 canonicalization is closed; it is no longer pending.

## P0-02 — Canonicalize CP-000B — `COMPLETE at c9416cc`

Merged to `main`, including `ADR-CP-007-source-registry-and-content-lifecycle.md` and
`CP-000B-source-lifecycle-matrix.md`. Verification and merge are both closed for this package.

## Exit criteria — met

```text
main contains CP-000A, CP-000B, CP-000C and CP-000D
working tree clean at 6477c1c
validation outputs recorded on the canonical machine
```

---

# 6. Phase 1 — تکمیل CP-000 Architecture Baseline

## CP-000C — Index Isolation and Multi-Node Retrieval — `COMPLETE at 578f7fa`

This package is complete and merged. It is **not** the next package; the next package is CP-000E.

### Deliverables

```text
ADR-CP-003
Index Isolation Blueprint
VectorStorePort behavior
logical partition contract
tiered isolation profiles
multi-node retrieval semantics
promotion policy
PoC/benchmark plan
```

### Decisions

- shared partition baseline
- mandatory trusted metadata pre-filter
- no collection per role/user/node
- dedicated shard/collection/deployment promotion
- active index snapshot selection
- public and private scope behavior
- fail-closed empty scope
- index metadata contract
- benchmark dimensions for pgvector/Qdrant/OpenSearch candidates

### Non-goals

- final provider selection
- actual vector adapter
- production index build

---

## CP-000D — Configuration, Artifact Lifecycle and RuntimeSnapshot — `COMPLETE at 6477c1c`

### Deliverables

```text
ADR-CP-004
ADR-CP-005
ADR-CP-006
Configuration Catalog
configuration precedence matrix
artifact state machines
RuntimeSnapshot composition diagram
```

### Decisions

- artifact taxonomy
- ownership/delegation
- platform hard bounds
- precedence (accepted, v1):
  `Platform hard bounds → active global ConfigurationRelease → trusted request authorization and
  source metadata → immutable RuntimeSnapshot`
- AI configuration is global-only in v1; there is no organization or node configuration override
- immutable revisions
- validate/review/approve/stage/activate
- rollback/revoke/disable/archive
- atomic active pointer
- canonical serialization and digest
- deterministic resolution
- bounded cache and LKG
- request snapshot pinning
- failure and stale behavior

---

## CP-000E — Model Boundary, Integration, Audit and Threat Baseline — `COMPLETE at 882a2ef`

### Deliverables

```text
docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md
docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md
docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md
docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md
command/event/pull diagrams
audit taxonomy
emergency-control matrix
threat scenarios
performance assumptions
Requirement-to-Package Coverage Matrix
```

### Decisions

- AI Core remains pure: no Django, Redis, LiteLLM, provider SDK, Secret Manager, HTTP, or queue framework
- production model calls cross a provider-neutral `ModelGatewayPort` into a private independent LiteLLM gateway service
- multi-provider, multi-deployment, multi-credential logical model pools with simple static bounded v1 balancing
- credential references and Secret Manager boundary; raw secrets never enter artifacts, snapshots, audit, logs, prompts, or frontend payloads
- Backend owns global admission, queue, overload, job status, and later per-user fairness; AI Runtime owns only per-request bounds
- initial sizing assumptions: approximately 20,000 registered students, 300 active admitted AI jobs, 1,500 accepted queued jobs, then overload rejection
- Backend queue store and LiteLLM coordination store have separate ownership, credentials/namespaces, and failure policy
- Admin Website changes provider-neutral AI settings only through authorized Control Plane commands, immutable revisions, validation/probe, `ConfigurationRelease`, and `RuntimeSnapshot`
- commands/events/snapshot pull/cache invalidation with optimistic concurrency and idempotency
- audit metadata versus raw-content access, retention references and legal-hold boundary
- emergency disable/revoke; known revoke or disable defeats cache and LKG
- threat model baseline and supply-chain pinning
- performance assumptions remain unproven until PERF-001 evidence
- exact CP-001 and AI work package boundaries

## CP-000 exit criteria

```text
ADR-CP-001...010 approved
Configuration Catalog approved
Authorization and lifecycle matrices approved
Index Isolation Blueprint approved
Control Plane Roadmap approved
all AI architecture components mapped to packages
no provider or backend object crosses Core
open decisions explicitly preserved
```

---

# 7. Phase 2 — Typed Control Plane Foundations

## CP-001 — Control Plane Contracts

### Scope

```text
Organization
OrganizationalNode
NodeType
Membership
ScopedRoleAssignment
VisibilityPolicyDefinition
KnowledgeSource
SourceRevision
ConfigurationArtifact
ArtifactRevision
ActivationRecord
IndexIsolationProfile
ModelPolicy
CredentialRef
Audit metadata contracts
```

### Requirements

- Pydantic v2 or current project contract convention
- immutable/closed schemas
- schema versioning
- canonical serialization
- digest stability
- no DB/HTTP/vendor types

---

## CP-002 — Authorization Hierarchy

### Scope

- anonymous Guest
- trusted principal
- many-to-many memberships
- scoped roles
- dynamic versioned visibility policy
- OR-of-AND policy composition
- classification conditions
- no implicit parent/child/sibling access
- explicit subtree semantics
- management permission separation
- retrieval authorization output

---

## CP-003 — Artifact Registry Core

### Scope

- stable artifact identity
- immutable revisions
- validation state
- active pointer
- atomic activation
- rollback
- revoke
- optimistic concurrency
- audit-safe history
- idempotent commands

---

## CP-004 — RuntimeSnapshotFactory

### Scope

- artifact resolution
- precedence application
- completeness validation
- canonical digest verification
- deterministic snapshot
- fail-closed behavior
- bounded in-memory LKG
- canonical pull
- invalidation hint handling
- no mutable runtime config

---

# 8. Phase 3 — AI Runtime Foundation

## AI-001 — Conversation Context and Persian Understanding

Maps AI Architecture stages 1 and 8 plus stage 13 supplements.

### Scope

```text
ConversationState
ContextBuilder
StateBrief renderer
ReferenceResolver
StateUpdater
PersianNormalizer
EntityResolver
TimeResolver
AmbiguityDetector
QueryAnalyzer
```

### Required behavior

- raw and normalized query preserved
- Persian/Arabic character normalization
- half-space handling
- Persian/Arabic/English number handling
- Jalali/Gregorian time resolution through trusted calendar artifacts
- exact identifiers preserved
- bounded recent/related message selection
- no LLM summary in hot path
- no authorization facts created from state
- evidence-linked organizational facts
- conversation-scoped persistence
- state update only after valid terminal answer

---

## AI-002 — Adaptive Routing and Bounded Planning

Maps AI Architecture stages 2 and 15. **This package owns the Orchestrator and the Planner.**

### Owned components

```text
Orchestrator
Fast Plan
Planner
Plan Validator
Approved Flows
Bounded Replan
route-to-plan composition
```

### Scope

```text
Orchestrator lane selection: fast, clarification or complex
Orchestrator capability limiting and bounded execution budget assignment
Orchestrator invokes the Planner only when required
Orchestrator controls request execution and state transitions
Planner decomposition of complex questions
Planner evidence-requirement identification
Planner selection of pre-authorized available capabilities only
Planner dependency, sequencing and bounded-parallelism definition
Planner result-composition requirements
deterministic pre-routing
lightweight structured analysis
fast one-step plans
bounded complex planner
approved flows
PlanValidator
typed dependency graph
parallel groups
typed output binding
one bounded replan
clarification lifecycle
replay events
```

### Invariants

- Planner output is proposal, never authority
- the Orchestrator is not an unconstrained agent: it cannot invent tools, invent capabilities, expand
  authorization, ignore the `RuntimeSnapshot`, start unbounded tasks, or run arbitrary subagents
- Planner bounds: maximum five steps, bounded parallelism, at most one bounded replan
- the Planner makes no authorization decision
- fast questions use a deterministic one-step plan and do not require an LLM Planner
- the bounded Walking Skeleton is not the complete production Orchestrator and Planner
- max step and parallel-step bounds
- no arbitrary tools
- no free agent loop
- no personal NL2SQL
- no unbounded retry/replanning
- capability allowlist resolved before planning
- deterministic route where possible
- common deadline and cancellation

---

# 9. Phase 4 — Source, Ingestion and Retrieval

## CP-005 — Department Source Registry

Implements ADR-CP-007.

### Scope

- source identity
- uploaded document
- official URL
- immutable revisions
- administrative ownership
- visibility/classification binding
- approval/activation
- disable/revoke/archive
- citation-safe locators
- source audit history

---

## CP-006 — Ingestion and Index Lifecycle

Maps AI Architecture stage 4.

### Scope

```text
content validation
quarantine boundary
parser ports
structure extraction
structure-aware chunking
parent/child chunks
table/list handling
multi-column reading order
deterministic contextualization
embedding port
deduplication
IndexSnapshot build
evaluation before activation
alias/active-pointer switch
rollback
revoke/delete propagation
```

### Baseline values are benchmark inputs

```text
child chunk 250–450 tokens
parent chunk 800–1500 tokens
forced overlap 40–80 tokens
```

They are not permanent constants.

---

## CP-007 — Retrieval and Official Search Profiles

Defines configurable policy:

- candidate counts
- lexical/vector counts
- fusion policy
- rerank count
- final evidence count
- source/node caps
- minimum scores
- freshness
- authority weighting
- context budget
- domain allowlist
- fallback rules
- abstention thresholds
- hard bounds

---

## AI-003 — Retrieval Engine

Maps AI Architecture stage 3.

### Scope

```text
lexical query builder
dense query builder
mandatory authorization/time/version filters
parallel BM25 and dense retrieval
RRF or approved fusion
deduplication
reranking
authority/current-version adjustments
parent expansion
fact-aware context selection
structured DocumentEvidence
```

### Invariants

- no post-retrieval authorization as primary control
- no unfiltered fallback
- no display-label-derived filters
- Orchestrator does not know search engine internals
- citation remains bound to original source locator
- historical version retrieval only when explicitly requested and authorized

---

# 10. Phase 5 — Structured Data and Deterministic Capabilities

## AI-004 — Semantic Catalog and NL2SQL

Maps AI Architecture stage 5.

### Scope

```text
Metric
Dimension
Approved Entity/View
JoinPath
CatalogProjection
LogicalPlan
LogicalPlanValidator
SQL Compiler
SQL AST/Policy Validator
Read-only Executor Port
ResultValidator
SqlEvidence
privacy suppression
bounded repair
```

### Invariants

- model never produces executable free-form SQL
- model never sees raw DB schema
- backend injects organization/security filters
- only approved views
- parameterized values
- SELECT-only
- read-only role/transaction
- timeout, row and cost limits
- minimum group size and sensitive metric policy
- no personal query
- no raw rows in v1 unless a future explicit policy exists

---

## AI-005 — Personal Selector and Rule Evaluator

### Personal Selector

- self-only or explicitly authorized subject
- minimal-field typed result
- no full-record exposure
- no model-selected recipient
- no semantic cache across subjects/scopes

### Rule Evaluator

- versioned deterministic rules
- typed policy facts and user facts
- deterministic decision
- matched/failed conditions
- evidence lineage
- LLM does not calculate eligibility

---

# 11. Phase 6 — Hybrid Evidence and Answer Integrity

## AI-006 — Hybrid Execution and Evidence Composition

Maps AI Architecture stage 6.

### Scope

- required facts
- parallel and sequential steps
- typed binding
- fact table
- subject/time/organization/version compatibility
- sectioned/comparison/rule/temporal/aggregate compositions
- missing evidence
- conflict detection
- bounded replan
- trajectory validation

---

## AI-007 — Answer Planning, Citation and Validation

Maps AI Architecture stage 7.

### Scope

```text
AnswerDecision
AnswerPlan
atomic claims
structured DraftAnswer
server-side CitationCompiler
deterministic claim/evidence validation
semantic faithfulness/completeness check
conflict and freshness notes
bounded repair
deterministic answers for simple cases
validated streaming policy
FinalAnswer
```

### Invariants

- Generator receives selected evidence, not raw tool output
- Generator cannot call tools/retrieval
- model cannot invent URL/page/source
- every material claim has evidence
- unsupported claims removed or blocked
- no raw token streaming before validation
- no fabricated confidence score

---

# 12. Phase 7 — Model Routing, Reliability and Search Capabilities

## CP-008 — Model/Provider/Credential Pool

### Scope

- provider-neutral model entries
- capabilities
- priority/weight
- timeout
- fallback
- quota
- residency
- health/cooldown
- staged rollout
- canary
- emergency disable
- `credential_ref`
- no secret values outside Secret Manager adapter

---

## AI-008 — Model, Prompt and Structured Output Runtime

Maps AI Architecture stage 9.

### Scope

- model gateway port
- model selector
- prompt registry
- prompt version/digest
- structured output
- schema validation
- bounded retry
- repair policy
- deterministic fallback
- model/prompt/index/policy version tracing

Provider/model candidates are benchmarked here but production selection lands in CP-012.

---

## AI-009 — Latency, Budget, Cache and Failure Control

Maps AI Architecture stage 10.

### Scope

- route budgets
- shared deadline
- cancellation propagation
- bounded parallel execution
- early exit
- token/context budgets
- cache taxonomy
- authorization-aware cache keys
- invalidation
- retry taxonomy
- circuit breakers
- load shedding
- cost controller
- degraded/abstain behavior

### Invariants

- no unbounded queue/task
- no blocking event loop
- no personal answer cache
- no retrieval cache without permission/policy hash
- failures never produce fabricated evidence

---

## AI-010 — Official Search, General Web Search and Attachments

Maps AI Architecture stage 12 and Master capability separation.

### AI-010A Official Search

- registered URL/domain
- allowlist
- privacy-preserving query builder
- SSRF-safe fetch boundary
- content parsing and evidence materialization
- injection handling
- freshness
- reranking
- conflict with internal RAG
- citation resolvability

### AI-010B General Web Search

- separate feature flag
- separate permission and policy
- no implicit trust
- evidence materialization
- legal/safety/provider decision later
- disabled by default for university baseline

### AI-010C Chat Attachments

- request-scoped capability
- ephemeral by default
- separate upload/scan/size policy
- no automatic promotion to persistent knowledge
- promotion only through explicit future source workflow

---

# 13. Phase 8 — Application Services and Backend Boundary

## CP-009 — Control Plane Application Services

### Scope

- commands
- validation
- optimistic concurrency
- idempotency
- approval workflow
- activation
- rollback
- revoke
- delegation
- audit records
- emergency commands
- no transport-specific types

---

## CP-010 — Backend/API Integration Boundary

### Scope

- command API contract
- query/read model contract
- domain events
- snapshot pull
- cache invalidation
- error mapping
- transport adapters
- no ORM/HTTP objects in Core
- no direct DB/env/UI reads from Core

---

# 14. Phase 9 — Admin Website and Production Adapters

## CP-011 — Admin Website Integration

### Workflows

- organization tree
- node type and hierarchy management
- membership and scoped role management
- visibility policy catalog
- source/document/URL lifecycle
- review/approval/activation
- configuration catalog
- model pool metadata
- credential rotate/revoke operations
- audit views
- emergency disable

UI only issues Control Plane commands.

---

## CP-012 — Production Adapters

### Adapter groups

#### Persistence

- PostgreSQL metadata/config/audit/jobs
- object storage
- migrations
- transactions
- locking/optimistic concurrency
- backup/restore

#### Search and indexing

- vector/lexical backend adapter
- embedding/reranker adapter
- parser/OCR adapter
- indexing queue/worker

#### Identity and security

- IdP adapter
- membership sync
- Secret Manager
- authorization data source
- audit sink

#### Runtime

- model serving adapter
- official search adapter
- cache/invalidation
- idempotency
- telemetry/tracing

### Selection rule

Candidates are selected by PoC and benchmark, not architecture preference alone.

---

# 15. Phase 10 — Evaluation and Rollout Gates

## CP-013 / EVAL-A — Contracts, Trace, Registry and Deterministic Graders

Maps Evaluation PR-01 to PR-04.

- `EvaluationCase`
- `ExperimentManifest`
- `CaseTrialResult`
- `MetricResult`
- `ReleaseGateDecision`
- JSON Schema
- manifest hashing
- OpenTelemetry trace contract
- redaction
- canonical dataset/run/score registry
- deterministic router/retrieval/evidence/citation/auth graders
- baseline dataset

---

## CP-013 / EVAL-B — NL2SQL, Distributed and Semantic/Human Evaluation

Maps Evaluation PR-05 to PR-08.

- real PostgreSQL controlled snapshots
- SQLGlot and result equivalence
- unauthorized/timeout suites
- distributed runner
- shard/aggregate
- idempotent trials
- cost/time budgets
- Langfuse optional UI integration
- calibrated judge
- human review/adjudication
- agreement report

---

## CP-013 / EVAL-C — Security, Load, Chaos and Thesis

Maps Evaluation PR-09 and PR-10.

- Promptfoo
- deterministic ACL/security assertions
- k6 HTTP/WebSocket
- Toxiproxy
- restore/rollback
- frozen thesis dataset
- S0...S5 variants
- repeated paired trials
- confidence intervals
- effect size
- failure analysis
- reproducibility package

---

# 16. Phase 11 — Security Closure

## CP-014

### Required threat closure

- cross-user leakage
- cross-organization/node leakage
- visibility policy escalation
- stale/revoked retrieval
- malicious upload/index poisoning
- direct/indirect prompt injection
- SSRF
- data exfiltration
- secret leakage
- raw tool output injection
- NL2SQL policy bypass
- privacy inference through small groups
- cache scope leakage
- event recipient confusion
- replay/idempotency abuse
- audit bypass
- emergency-control abuse

Security hard gates use deterministic assertions, not LLM judgment.

---

# 17. Phase 12 — Performance Qualification

## PERF-001

Target definition:

```text
500 concurrent active in-flight requests
```

### Workloads

- steady
- spike
- soak
- mixed fast/complex traffic
- HTTP and WebSocket
- slow clients
- reconnect storm
- dependency latency/failure
- worker crash
- stale index
- duplicate delivery
- cache/control-plane outage

### Metrics

- TTFT
- time-to-validated-answer
- p50/p95/p99
- queue wait
- stage latency
- throughput
- error rate
- token/cost per success
- worker utilization
- queue depth
- backpressure/load shedding behavior

No production-ready claim before this package passes.

---

# 18. Production-Grade Delivery Contract for Every Package

هر package باید این ترتیب را طی کند.

## 18.1 Architecture consultation

قبل از Claude prompt:

1. مسئله و boundary
2. گزینه‌های واقعی
3. پیشنهاد معماری
4. تصمیم مشترک
5. non-goals
6. acceptance criteria
7. open decisions

بدون این مرحله Agent شروع نمی‌کند.

## 18.2 Agent scope

هر prompt باید:

- Git canonical state را inspect کند
- scope دقیق فایل‌ها را محدود کند
- unrelated files را تغییر ندهد
- contract-first باشد
- provider-neutrality را حفظ کند
- bounded behavior داشته باشد
- patch cumulative بسازد
- commit/merge نکند
- validation واقعی را گزارش کند
- failureها را pass اعلام نکند

## 18.3 Required test layers

با توجه به نوع package:

### همیشه

- unit tests
- negative tests
- schema/contract tests
- immutability tests
- serialization round-trip
- `git diff --check`
- Ruff format/check
- mypy
- focused pytest
- full `verify.sh`
- coverage gate
- `uv build`

### Contract/domain packages

- property tests
- invariant/state-machine tests
- digest stability
- version compatibility
- unknown-field rejection
- mutation rejection

### Async/runtime packages

- cancellation
- deadline
- bounded concurrency
- task cleanup
- retry budget
- idempotency
- replay determinism
- telemetry/audit failure behavior
- no event-loop blocking

### Authorization/security packages

- default deny
- cross-user/cross-org/node escape
- guest/public behavior
- stale/revoked policy
- malicious/untrusted metadata
- role label spoofing
- raw-content separation
- cache-scope isolation

### Persistence/adapter packages

- Testcontainers or equivalent
- migrations
- transaction rollback
- optimistic concurrency
- crash/retry behavior
- connection limits
- timeout
- duplicate delivery
- backup/restore where relevant

### Retrieval/AI behavior packages

- deterministic fixture suite
- golden cases
- retrieval Recall@k/MRR/nDCG where applicable
- citation correctness
- no-evidence/abstention
- conflict/stale/version cases
- Persian normalization cases
- route/trajectory correctness
- semantic eval only as supplementary evidence

## 18.4 Merge gates

```text
all required focused tests pass
full verify.sh passes
coverage threshold passes
build passes
reviewed staged diff contains only authorized files
fast-forward merge
post-merge clean status
```

---

# 19. Claude Batch Strategy

برای کاهش هزینه Agent، packageهای مرتبط می‌توانند در یک prompt باشند، اما:

- فایل‌ها و work packageها جدا باقی می‌مانند.
- هر logical package commit مستقل دارد.
- Agent commit نمی‌کند؛ commitها پس از review محلی ساخته می‌شوند.
- failure یک package نباید package دیگر را pass جلوه دهد.

## Batchهای پیشنهادی

```text
Batch A: CP-000C
Batch B: CP-000D
Batch C: CP-000E

Batch D: CP-001 + CP-002
Batch E: CP-003 + CP-004

Batch F: AI-001 + AI-002
Batch G: CP-005
Batch H: CP-006 + CP-007 policy docs/contracts
Batch I: AI-003

Batch J: AI-004 + AI-005
Batch K: AI-006 + AI-007

Batch L: CP-008 + AI-008
Batch M: AI-009
Batch N: AI-010

Batch O: CP-009 + CP-010
Batch P: CP-011
Batch Q1..Qn: CP-012 by adapter group

Batch R: EVAL-A
Batch S: EVAL-B
Batch T: EVAL-C
Batch U: CP-014
Batch V: PERF-001
```

هر Batch قبل از prompt نهایی با معمار بررسی می‌شود.

---

# 20. Open Decision Register

تا package مربوطه باز می‌مانند:

- Identity Provider
- PostgreSQL/pgvector versus Qdrant/OpenSearch profile
- object storage provider
- model serving runtime
- exact fast/strong models
- embedding and reranker models
- parser/OCR stack
- distributed queue stack
- deployment topology
- data residency and compliance profile
- exact SLOs
- actual corpus size/QPS
- retention/legal hold
- General Web Search provider and legal policy
- attachment promotion policy
- future configurable separation-of-duties rules beyond the accepted v1 single System AI
  Administrator model and the accepted v1 Central Source Approver model
- final evaluation thresholds
- final cache/LKG TTLs
- exact chunk/candidate/rerank sizes

این موارد با evidence، benchmark و operational constraints بسته می‌شوند.

---

# 21. Final Release Definition

محصول فقط وقتی production-ready نامیده می‌شود که:

```text
CP-000...CP-012 complete
AI-001...AI-010 complete
production adapters verified
evaluation release gates operational
security closure passed
PERF-001 passed
rollback artifacts exist
backup/restore tested
no critical authorization/privacy regression
```

---

# 22. Immediate Next Step

1. `CP-001 — Control Plane Contracts` را آغاز کن.
2. `CP-000A`، `CP-000B`، `CP-000C`، `CP-000D`، `CP-000R` و `CP-000E` بسته شده‌اند.
3. هیچ LiteLLM، Backend queue، Redis یا Admin Website implementation پیش از package owner مربوطه complete محسوب نمی‌شود.
