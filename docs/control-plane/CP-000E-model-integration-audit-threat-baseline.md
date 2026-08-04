# CP-000E: Model, Integration, Audit, and Threat Baseline

Status: Accepted architecture package pending review and merge of the CP-000E commit
Date: 2026-08-04
Base branch: `main`
Base repository evidence commit: `8d94c6a5617c449bb38fa995f267b63256eeaf88`
Implementation status: Architecture only. No LiteLLM، Redis queue، Backend admission، Admin Website،
Secret Manager، production adapter، audit store یا threat-test implementation is claimed.

## Purpose

این package آخرین architecture closure gate پیش از `CP-001` است. هدف آن تثبیت این مرزهاست:

1. AI Core کاملاً provider-neutral و مستقل از Backend/infrastructure باقی بماند؛
2. LiteLLM به‌عنوان سرویس داخلی مستقل در adapter layer قرار گیرد؛
3. Backend مالک admission، queue و overload باشد؛
4. frontend بتواند AI configuration را فقط از مسیر Control Plane تغییر دهد؛
5. audit، retention، emergency controls و threat baseline owner و semantics روشن داشته باشند؛
6. performance assumptions بدون ادعای capacity اثبات‌نشده ثبت شوند.

## Deliverables

- `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`
- `docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md`
- `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md`
- این baseline و requirement-to-package matrix
- roadmap، authority manifest و Deferred Register updates

## Canonical decisions

### E-1 — AI Module purity

AI Core هیچ dependency به Django، Redis، LiteLLM، provider SDK، Secret Manager، HTTP یا queue framework
ندارد. تنها provider-neutral ports و immutable domain values وارد Core می‌شوند.

وضعیت فعلی:

- bounded Core separation و Protocol port pattern در Git وجود دارد؛
- production `ModelGatewayPort` و LiteLLM adapter وجود ندارد؛
- Backend queue، Admin Website و Control Plane application services وجود ندارد؛
- بنابراین independence **در bounded design/code برقرار است** ولی production integration هنوز deferred
  است و نباید implemented اعلام شود.

### E-2 — LiteLLM boundary

Production topology:

```text
AI Runtime replicas
  -> ModelGatewayPort
  -> CP-012 adapter
  -> private LiteLLM Gateway service/cluster
  -> approved provider deployments and credentials
```

LiteLLM implementation detail است؛ Core contract هیچ LiteLLM term یا type ندارد.

### E-3 — Provider pool and balancing

- چند provider، چند deployment و چند `credential_ref` برای هر logical model مجاز است؛
- load balancing v1 ساده، static و bounded است؛
- فقط candidateهای enabled، qualified، compatible و healthy/cooldown-eligible انتخاب می‌شوند؛
- retry/fallback bounded است؛
- dynamic autonomous routing در v1 وجود ندارد؛
- degraded fallback باید صریح و audited باشد.

### E-4 — Queue and Redis ownership

Backend مالک:

- global admission؛
- active/queued limits؛
- job lifecycle؛
- overload response؛
- later per-user fairness؛
- queue status/cancellation API.

AI Runtime فقط job پذیرفته‌شده را با per-request bounds اجرا می‌کند.

دو store boundary:

```text
Backend queue store
  -> CP-012 queue adapter

LiteLLM coordination store
  -> CP-012 LiteLLM deployment
```

هیچ‌کدام وارد AI Core نمی‌شوند.

### E-5 — Capacity assumptions

| Item | Initial architecture assumption | Meaning |
| --- | --- | --- |
| Registered population | up to approximately 20,000 students | sizing context only |
| Active admitted AI jobs | up to 300 | Backend global admission target |
| Waiting accepted jobs | up to 1,500 | Backend bounded queue target |
| Beyond capacity | reject before AI Runtime | product-safe busy/overload response |

این اعداد فقط پس از PERF-001 load test به production guarantee تبدیل می‌شوند.

### E-6 — Frontend configuration

System AI Administrator با `ai_configuration.manage` از Admin Website تنظیمات provider-neutral را تغییر
می‌دهد:

- model pools، deployment refs، weights/priorities؛
- model/provider refs؛
- masked credential refs؛
- enable/disable؛
- compatibility/fallback classes؛
- bounded timeouts/retries؛
- test/probe؛
- Save and Apply؛
- rollback.

Frontend raw key، LiteLLM raw config، Redis، hard bounds و Core variable را تغییر نمی‌دهد.

### E-7 — Configuration lifecycle

```text
Admin Website
  -> Backend/API
  -> Control Plane command
  -> immutable artifact revision
  -> validation
  -> conditional bounded probe
  -> ConfigurationRelease
  -> atomic activation
  -> RuntimeSnapshotFactory
  -> immutable RuntimeSnapshot
  -> AI Runtime
```

### E-8 — Audit and emergency controls

- audit و telemetry جدا هستند؛
- raw content و secrets در audit پیش‌فرض نیستند؛
- known revoke/disable از cache و LKG قوی‌تر است؛
- emergency command باید authorized، idempotent، reasoned و audited باشد؛
- LiteLLM service و internal stores public نیستند؛
- break-glass implementation آینده scope/expiry/review لازم دارد.

## Command/event/pull diagrams

### Configuration command

```text
Admin UI
  -> Backend command DTO
  -> authorize ai_configuration.manage
  -> idempotent Control Plane command
  -> optimistic concurrency
  -> validate/probe
  -> immutable revisions + ConfigurationRelease
  -> atomic pointer update
  -> audit
```

### Runtime snapshot pull

```text
Activation event/hint
  -> Runtime adapter invalidates cache
  -> RuntimeSnapshotFactory resolves active release
  -> verify exact refs and digests
  -> immutable snapshot cached
  -> request pins snapshot
```

Notification is a hint; pull and digest verification remain authoritative.

### Model execution

```text
Admitted request
  -> AI Runtime bounded execution
  -> ModelGatewayPort
  -> LiteLLM adapter/service
  -> eligible deployment
  -> provider-neutral stream/result
  -> validation and finalization
```

### Backend admission

```text
Incoming product request
  -> auth/product validation
  -> active slot available? RUNNING
  -> queue slot available? QUEUED
  -> otherwise OVERLOADED
```

## Emergency-control matrix

| Action | Required authority | Immediate effect | Cache/LKG behavior | Audit |
| --- | --- | --- | --- | --- |
| Disable deployment | model operations permission | no new selection | dependency becomes ineligible | mandatory |
| Revoke credential | credential operations permission | all dependent deployments stop | defeats cache/LKG | mandatory |
| Disable logical pool | AI configuration/emergency permission | typed model unavailable | no fallback outside policy | mandatory |
| Roll back release | AI configuration permission | atomic previous release activation | new snapshot resolved | mandatory |
| Stop Backend admission | operations/emergency permission | no new jobs accepted | existing policy decides running jobs | mandatory |
| Revoke source/policy | source/security permission | evidence ineligible | publication recheck | mandatory |

## Threat baseline

| Threat area | Baseline control |
| --- | --- |
| Prompt/model output authority expansion | model output never authorizes |
| Provider/vendor coupling | provider-neutral Core port |
| Secret leakage | Secret Manager, masked refs, redaction |
| Queue flooding | Backend bounded admission/load shedding |
| Retry storm | shared deadline, bounded retry, cooldown |
| Stale revoke | revoke defeats cache/LKG |
| Admin tampering | authorization, immutable revisions, audit |
| Cross-scope evidence leak | mandatory trusted filter and recheck |
| Raw-content audit leak | minimization and separate permission |
| Supply-chain compromise | exact version/digest/provenance |
| Public gateway exposure | private network and service auth |
| Redis boundary confusion | distinct ownership/credentials/namespaces |

## Requirement-to-package coverage matrix

| Requirement | Architecture owner | Implementation owner | Gate/evidence |
| --- | --- | --- | --- |
| Provider-neutral `ModelGatewayPort` | CP-001, ADR-CP-008 | AI-008, CP-012 | contract and adapter tests |
| Model/provider/credential pool | CP-008 | CP-003, CP-009, CP-012 | activation/probe tests |
| Simple load balancing/fallback | ADR-CP-008 | CP-012, AI-009 | deterministic and failure tests |
| Backend admission/queue | ADR-CP-009 | CP-010, CP-012 | PERF-001 load tests |
| Admin configuration UI | CP-000D, ADR-CP-009 | CP-009, CP-011 | authorization/E2E tests |
| Immutable release/snapshot path | CP-000D | CP-003, CP-004, CP-009 | digest/replay tests |
| Audit taxonomy/lineage | ADR-CP-010 | CP-001, CP-009, CP-012, AI-002, AI-007 | contract/persistence tests |
| Emergency disable/revoke | ADR-CP-010 | CP-009, CP-012, CP-014 | propagation/game-day tests |
| Threat model/security tests | ADR-CP-010 | CP-014, CP-013 | reviewed threat/test plan |
| 300 active / 1,500 queued target | CP-000E assumption | CP-010, CP-012 | PERF-001 sustained load evidence |
| LiteLLM version/image qualification | ADR-CP-008 | CP-012, CP-013, CP-014 | exact pin, SBOM, regression |

## Deferred implementation mapping

CP-000E closes architecture decisions but keeps implementation open in existing items:

- `DEF-032` credential pool operations؛
- `DEF-034` configuration auditability؛
- `DEF-036` model rollout؛
- `DEF-037` provider-neutral AI ports؛
- `DEF-038` configuration cache؛
- `DEF-043` retry semantics؛
- `DEF-045` model/probe qualification؛
- `DEF-099` product/API/UI integration؛
- `DEF-100` deployment/scalability/operations؛
- `DEF-101` supply-chain security؛
- `DEF-102` threat-model and abuse tests؛
- `DEF-114` audit outcome taxonomy؛
- `DEF-115` runtime lineage and durable completion.

No new DEF ID is necessary because the obligations map cleanly to existing entries.

## CP-000E exit criteria

- ADR-CP-008، ADR-CP-009 و ADR-CP-010 reviewed and accepted؛
- AI purity boundary explicit؛
- Backend versus AI queue ownership explicit؛
- LiteLLM service boundary explicit؛
- frontend configuration path explicit؛
- emergency/audit/threat matrix explicit؛
- existing deferred items updated without duplicate IDs؛
- roadmap and authority manifest updated؛
- all changes documentation-only؛
- `git diff --check` and Markdown table checks pass؛
- repository verification/build executed on canonical machine before merge.

## After acceptance

```text
CP-000A COMPLETE
CP-000B COMPLETE
CP-000C COMPLETE
CP-000D COMPLETE
CP-000R COMPLETE
CP-000E COMPLETE
CP-001 UNBLOCKED
```

شروع implementation از `CP-001 Control Plane Contracts` است، نه از LiteLLM deployment یا Backend queue.
