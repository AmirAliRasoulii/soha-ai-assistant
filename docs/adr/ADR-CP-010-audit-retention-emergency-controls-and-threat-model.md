# ADR-CP-010: Audit, Retention, Emergency Controls, and Threat Model Baseline

Status: Accepted architecture baseline at commit `882a2ef` (CP-000E)
Implementation remains owned by the packages identified in this document.
Date: 2026-08-04
Owner: Security / Audit / Reliability Governance
Scope: audit versus telemetry، retention/legal hold boundary، raw-content access، emergency controls،
threat scenarios و minimum security/performance gates برای model gateway و Backend integration. این ADR
هیچ SIEM، database، retention duration، legal jurisdiction یا incident platform مشخصی را انتخاب نمی‌کند.

Companions:

- `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`
- `docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md`
- `docs/contracts/audit-event-1.0.0.md`
- `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`

## Context

AI Runtime، Control Plane، Backend و model gateway چند trust boundary دارند. Audit باید برای authorization،
configuration، provider selection، fallback، source usage و terminal outcome کافی باشد، اما نباید به
مخزن raw prompt، secret یا محتوای unrestricted تبدیل شود.

Current `AuditEvent 1.0.0` یک bounded baseline است؛ taxonomy کامل، nine-element lineage و durable
completion semantics هنوز deferred هستند. CP-000E این gap را پیاده‌سازی‌شده اعلام نمی‌کند، فقط baseline
معماری و owner را تثبیت می‌کند.

## Problem

- P-1: telemetry و audit هدف یکسان ندارند؛ fail-open telemetry نمی‌تواند جای fail-closed audit را بگیرد.
- P-2: ذخیره raw input/output در audit ممکن است داده شخصی، restricted content و secret را افشا کند.
- P-3: disable/revoke بدون precedence و propagation semantics ممکن است request جدید را با dependency
  شناخته‌شده ناامن اجرا کند.
- P-4: incident response بدون break-glass، reason، expiry و audit به privilege دائمی تبدیل می‌شود.
- P-5: retention و legal hold بدون reference model به policy hardcoded یا deletion ناقص منجر می‌شود.
- P-6: threat model باید model output، provider output، configuration و admin actions را untrusted در
  نظر بگیرد.

## Decision

### D-1 — Audit and telemetry are separate

| Property | Audit | Telemetry |
| --- | --- | --- |
| Purpose | accountability, security, governance, replay lineage | operations, metrics, tracing, performance |
| Failure policy | fail closed for mandatory security/config actions | normally fail open within policy |
| Mutability | append-only/immutable record semantics | aggregation/downsampling allowed |
| Access | tightly authorized | operational role-based access |
| Content | minimized structured facts | minimized metrics/traces |

Telemetry success هیچ audit obligation را satisfy نمی‌کند.

### D-2 — Mandatory audit classes

حداقل این actionها audit لازم دارند:

- authorization allow/deny and consulted policy refs؛
- configuration create/validate/probe/save/apply/activate/rollback/disable/revoke؛
- credential create/rotate/disable/revoke reference operations؛
- model deployment selection، retry و fallback؛
- source approve/reject/activate/revoke؛
- emergency control invocation؛
- raw-content access؛
- administrative permission changes؛
- final answer terminal outcome؛
- cancellation and overload summaries where required by policy.

### D-3 — Runtime lineage

Production audit باید نه عنصر lineage را قابل‌بازیابی کند:

1. organization؛
2. actor scope؛
3. subject؛
4. time scope؛
5. source version؛
6. policy version؛
7. `ConfigurationRelease`؛
8. `RuntimeSnapshot`؛
9. run/request identifier.

این requirement implementation آینده `DEF-115` است.

### D-4 — Outcome taxonomy

Audit outcome taxonomy حداقل:

- `answered`
- `partial`
- `clarification_required`
- `abstained`
- `policy_rejected`
- `authorization_denied`
- `failed`
- `cancelled`

`authorization_denied` و `policy_rejected` هرگز یکی نیستند. Contract versioning برای افزودن missing
values متعلق به CP-001 و `DEF-114` است.

### D-5 — Content minimization

Audit record به‌طور پیش‌فرض raw prompt، raw model output، raw source content، API key، access token،
secret header یا unrestricted attachment ندارد.

Audit می‌تواند این‌ها را حمل کند:

- opaque content/evidence refs؛
- digests؛
- citation-safe metadata؛
- controlled reason/outcome codes؛
- lengths/counts؛
- masked deployment/credential refs؛
- policy/snapshot/release refs.

### D-6 — Raw-content access

Raw-content inspection یک permission جدا با reason و audit obligation است. AI administration، source
approval، support یا audit role به‌تنهایی raw content access نمی‌دهد.

Emergency content access باید time-bounded، scope-bounded و reviewable باشد.

### D-7 — Retention references

Contractها retention duration را hardcode نمی‌کنند. Artifact/audit records یک versioned retention
policy reference و legal-hold state/reference دارند.

Deletion semantics باید میان این‌ها فرق بگذارد:

- active operational record؛
- archived record؛
- legal hold؛
- user-facing deletion؛
- cryptographic/pointer removal؛
- physical purge.

Exact periods و jurisdiction به governance/compliance واگذار می‌شود.

### D-8 — Emergency control classes

| Control | Effect | Owner | Default behavior |
| --- | --- | --- | --- |
| `disable_deployment` | deployment برای request جدید ineligible | CP-009/CP-012 | immediate fail closed |
| `revoke_credential` | تمام deploymentهای وابسته ineligible | CP-009/CP-012 | immediate fail closed |
| `disable_model_pool` | logical pool unavailable | CP-009 | typed model unavailable |
| `rollback_release` | active pointer به release قبلی qualified | CP-003/CP-009 | atomic |
| `disable_feature` | feature/capability جدید متوقف | CP-009 | according to SecurityPolicy |
| `revoke_source_or_policy` | evidence eligibility فوراً شکست می‌خورد | CP-005/CP-006 | publication recheck |
| `stop_admission` | Backend job جدید نمی‌پذیرد | CP-010 | overload/maintenance response |

### D-9 — Emergency precedence

Known revoke/disable از cache و LKG قوی‌تر است. هیچ cached health، snapshot یا provider state حق استفاده
از dependency شناخته‌شده revoked را ندارد.

Emergency command باید:

- strongly authorized؛
- idempotent؛
- reason-required؛
- time-stamped؛
- audit-required؛
- propagation-observable؛
- قابل rollback فقط با command مجاز جدید باشد.

### D-10 — Break-glass

Break-glass در v1 به‌عنوان workflow production implementation نشده است، اما هر implementation آینده
باید:

- principal جدا یا elevated grant صریح داشته باشد؛
- scope و expiry داشته باشد؛
- reason و incident reference لازم داشته باشد؛
- raw-content access را خودکار grant نکند؛
- real-time alert و post-incident review ایجاد کند؛
- قابل delegation خام یا permanent نباشد.

### D-11 — Threat actors and trust assumptions

Untrusted inputs شامل:

- user prompt and attachments؛
- frontend fields and labels؛
- identity token claims تا زمان verification؛
- model output؛
- provider errors/output metadata؛
- tool/search/retrieval output؛
- source metadata تا زمان trusted ingestion؛
- event delivery duplicates/out-of-order؛
- mutable external configuration؛
- admin browser/session compromise.

Trusted status فقط از adapter/control-plane verification و immutable references می‌آید.

### D-12 — Minimum threat scenarios

| ID | Threat | Required baseline mitigation |
| --- | --- | --- |
| T-01 | prompt injection expands authority | model output never authorizes; pre-authorized capability allowlist |
| T-02 | provider compromise or malformed output | schema validation, bounded parsing, no provider object in Core |
| T-03 | API key disclosure | Secret Manager, masked refs, redaction, rotation/revoke |
| T-04 | queue flooding | Backend admission, bounded queue, load shedding, auth/rate controls |
| T-05 | retry storm | bounded retries, cooldown, circuit breaker, shared deadline |
| T-06 | stale config after revoke | revoke defeats cache/LKG; pull/digest verification |
| T-07 | admin config tampering | strong authorization, optimistic concurrency, immutable revisions, audit |
| T-08 | cross-user or cross-node data leak | trusted authorization, mandatory pre-filter, evidence recheck |
| T-09 | audit data leakage | minimization, separate raw-content permission, retention policy |
| T-10 | event replay/duplication | idempotent consumers and causation/correlation refs |
| T-11 | dependency/supply-chain compromise | exact version/digest pinning, SBOM/signature/provenance |
| T-12 | direct LiteLLM exposure | private network, service authentication, no public endpoint |
| T-13 | Redis cross-boundary confusion | separated credentials/namespaces/owners and fail policies |
| T-14 | cancellation ignored | propagated cancellation, safe points, terminal audit |
| T-15 | model fallback changes capability silently | compatibility class and audited degraded fallback |

### D-13 — Network boundary

LiteLLM gateway، Redis، Secret Manager و internal Control Plane endpoints public internet services نیستند.
Network policy باید فقط authorized workloads را allow کند. Service-to-service authentication و TLS
به CP-012/CP-014 واگذار می‌شود.

### D-14 — Supply chain

Production artifacts باید exact version/digest، provenance و qualification evidence داشته باشند.
این شامل application build، LiteLLM image، model artifacts و critical dependencies است. اجرای کامل در
`DEF-101` باقی می‌ماند.

### D-15 — Performance and overload audit

Operations باید حداقل این metrics/events را بدون raw content ثبت کند:

- active and queued Backend jobs؛
- overload rejects؛
- model gateway active calls؛
- per-deployment success/failure/rate-limit؛
- fallback counts؛
- queue wait and execution latency؛
- end-to-first-token where streaming؛
- cancellation count؛
- Redis/gateway health؛
- credential/deployment disable state.

این metrics telemetry هستند؛ emergency/config actions و security outcomes audit جدا می‌خواهند.

### D-16 — Publication-time eligibility

قبل از انتشار پاسخ، current eligibility/revocation برای evidenceهای استفاده‌شده باید recheck شود.
Retrieval موفق پیش از revoke، اجازه انتشار پس از revoke نیست. Implementation در `DEF-113` باقی می‌ماند.

### D-17 — Durable completion

`runtime.turn.completed` تا زمانی که durable idempotency/audit semantics مشخص نشده، evidence نهایی
completion durable محسوب نمی‌شود. Implementation در `DEF-115` باقی می‌ماند.

## Emergency control flow

```text
Authorized operator
  -> Backend/API
  -> strongly authorized idempotent Control Plane command
  -> canonical registry/pointer state change
  -> mandatory audit record
  -> invalidation/notification hint
  -> adapters observe state
  -> new work fails closed
  -> propagation telemetry and incident review
```

## Rejected alternatives

- raw prompts and outputs in every audit record؛
- telemetry-only accountability؛
- permanent break-glass role؛
- cache/LKG overriding known revoke؛
- direct public LiteLLM endpoint؛
- provider error messages returned raw to user؛
- emergency changes made directly in Redis/database without command/audit.

## Package ownership

| Responsibility | Primary owner | Supporting owner |
| --- | --- | --- |
| Audit and retention contracts | CP-001 | CP-009, CP-014 |
| Audit emission semantics | CP-009, AI-002, AI-007 | AI-009 |
| Durable audit storage/delivery | CP-012 | CP-014 |
| Emergency commands | CP-009 | CP-003, CP-005, CP-008, CP-010 |
| Threat-model and security tests | CP-014, CP-013 | all affected packages |
| Supply-chain integrity | CP-014, CP-012 | CP-001, CP-004 |
| Performance/load evidence | PERF-001, CP-013 | CP-010, CP-012, AI-009 |

## Acceptance criteria

- AC-1: audit و telemetry purpose/failure policy جدا دارند.
- AC-2: raw content و secrets به‌صورت پیش‌فرض در audit نیستند.
- AC-3: emergency revoke/disable از cache/LKG قوی‌تر است.
- AC-4: emergency command authorized، idempotent، reasoned و audited است.
- AC-5: حداقل threat scenarioهای T-01..T-15 در test plan owner دارند.
- AC-6: LiteLLM و stores داخلی public نیستند.
- AC-7: retention/legal hold با reference model جدا از contract تعریف می‌شود.
- AC-8: implementation gapهای `DEF-101`, `DEF-102`, `DEF-113`, `DEF-114`, `DEF-115` باز می‌مانند.

## Open decisions preserved

- exact retention periods and legal jurisdictions؛
- exact audit store/SIEM؛
- exact break-glass approval workflow؛
- exact service identity/TLS implementation؛
- exact redaction technology؛
- exact security test tools and thresholds؛
- exact incident response and on-call platform؛
- exact RPO/RTO and propagation SLO.
