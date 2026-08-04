# ADR-CP-008: Model Gateway, Provider Pool, and Credential Boundary

Status: Accepted architecture baseline at commit `882a2ef` (CP-000E)
Implementation remains owned by the packages identified in this document.
Date: 2026-08-04
Owner: Control Plane / AI Runtime Boundary
Scope: مرز provider-neutral میان AI Core و سرویس مدل، مدل منطقی pool، credential reference، load
balancing ساده v1، retry/fallback، health/cooldown، streaming و LiteLLM deployment boundary. این ADR
هیچ provider، model name، API key، Secret Manager product، Redis topology یا deployment size مشخصی را
به‌عنوان پیاده‌سازی‌شده اعلام نمی‌کند.

Companions:

- `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`
- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
- `docs/adr/ADR-CP-009-backend-control-plane-and-runtime-integration-boundary.md`
- `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md`
- `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`

## Context

محصول ممکن است برای حدود 20,000 دانشجو سرویس ارائه کند و در اوج بار، Backend باید تا 300 درخواست
AI را وارد اجرای فعال کند، تا 1,500 درخواست پذیرفته‌شده را در صف نگه دارد، و بار بیشتر را با پاسخ
overload کنترل کند. این اعداد **Backend admission assumptions** هستند، نه state یا منطق داخل AI Core.

AI Core باید pure باقی بماند:

- هیچ import از `litellm`، Django، Redis client، provider SDK یا Secret Manager SDK ندارد؛
- هیچ API key، provider URL، mutable gateway config یا network client در domain contract ندارد؛
- فقط یک provider-neutral port و immutable request/response valueها را می‌شناسد؛
- queue position، global active count، global wait count و HTTP `Retry-After` را نمی‌شناسد؛
- برای هر request فقط deadline، cancellation، idempotency، budget و bounded execution را رعایت می‌کند.

در bounded baseline موجود، Core از Protocol portهای provider-neutral برای authorization، capability،
evidence، idempotency، audit و telemetry استفاده می‌کند. اما `ModelGatewayPort` production، LiteLLM
adapter، multi-provider pool و credential operations هنوز پیاده‌سازی نشده‌اند.

LiteLLM در v1 به‌عنوان **سرویس داخلی مستقل LLM Gateway** انتخاب می‌شود، نه library داخل AI Core.
LiteLLM Proxy یک gateway مرکزی برای دسترسی یکسان به providerهای متعدد، streaming و retry/fallback
می‌دهد؛ بااین‌حال تمام semantics معماری باید provider-neutral باقی بماند و نسخه/قابلیت واقعی LiteLLM
قبل از production توسط CP-012 و CP-013 qualify شود.

## Problem

- P-1: اتصال مستقیم AI Core به provider SDK، استقلال و testability را از بین می‌برد.
- P-2: یک provider یا یک API key availability کافی برای بار سازمانی ندارد.
- P-3: چند key و چند provider بدون مدل pool، health، cooldown و fallback می‌تواند retry storm یا
  رفتار غیرقابل‌بازسازی ایجاد کند.
- P-4: قرار دادن raw secret در `ModelPolicy`، `ConfigurationRelease` یا `RuntimeSnapshot` یک شکست trust
  boundary است.
- P-5: استفاده از LiteLLM config یا routing term در domain contract، Core را به vendor implementation
  قفل می‌کند.
- P-6: fallback میان مدل‌های متفاوت ممکن است capability، quality، cost یا structured-output behavior را
  تغییر دهد و نباید پنهان باشد.
- P-7: frontend باید بتواند تنظیمات AI را تغییر دهد، ولی نباید مستقیماً LiteLLM، secret، Redis یا Core
  variable را mutate کند.

## Decision

### D-1 — Pure AI Core boundary

AI Core فقط `ModelGatewayPort` provider-neutral را مصرف می‌کند. نام `LiteLLM` در Core contract، Core
service، planning، answer building و runtime policy ممنوع است.

```text
AI Core
  -> ModelGatewayPort
  -> CP-012 Model Gateway Adapter
  -> Internal LiteLLM Gateway Service
  -> Provider deployments and credentials
```

### D-2 — LiteLLM deployment mode

در production، LiteLLM به‌صورت سرویس داخلی مستقل و غیرقابل‌دسترسی مستقیم از اینترنت مستقر می‌شود.
قرار دادن LiteLLM Python SDK داخل process اصلی AI Runtime، topology canonical production نیست.

در development یا test می‌توان fake adapter یا single-process test double داشت، ولی هیچ‌کدام authority
تغییر معماری production را ندارند.

### D-3 — Logical model and deployment pool

`ModelPolicy` یک یا چند logical model pool را تعریف می‌کند. هر pool شامل candidate deploymentهای
صریح و pin‌شده است. هر deployment حداقل این metadata provider-neutral را دارد:

- `deployment_ref`
- `provider_ref`
- `model_ref`
- `credential_ref`
- capability profile reference
- reasoning/structured-output profile reference where applicable
- enabled/disabled state
- static priority or weight
- request timeout bound
- retry/fallback eligibility
- qualification evidence reference

Raw API key، provider SDK object و network client در این shape ممنوع است.

### D-4 — Multiple providers and multiple credentials

یک logical pool می‌تواند چند provider و چند credential مستقل داشته باشد. هر API key یا cloud
credential یک `credential_ref` جدا و هر endpoint/deployment یک `deployment_ref` جدا دارد.

چند credential فقط وقتی ظرفیت مستقل و مطابق شرایط provider دارد در capacity محاسبه می‌شود. استفاده از
چند key برای دورزدن limit یا شرایط provider ممنوع است.

### D-5 — Simple v1 load balancing

الگوریتم v1 عمداً ساده است:

1. فقط candidateهای enabled، qualified، compatible و خارج از cooldown eligible هستند.
2. انتخاب میان candidateهای هم‌رده با static priority/weight و یک strategy ساده و قابل‌تست انجام می‌شود.
3. انتخاب نباید توسط LLM، prompt، frontend label یا client metadata انجام شود.
4. adaptive cost/quality learning، dynamic bandit routing و autonomous model selection در v1 وجود ندارد.
5. mapping این policy به routing mode واقعی LiteLLM، implementation detail مربوط به CP-012 است و باید
   با نسخه دقیق qualifyشده تطبیق داده شود.

### D-6 — Compatibility classes

Fallback فقط میان candidateهایی مجاز است که compatibility آن‌ها صریحاً ثبت شده باشد:

| Class | Meaning |
| --- | --- |
| `STRICT_EQUIVALENT` | همان capability و contract behavior مورد انتظار؛ مناسب‌ترین fallback |
| `FUNCTIONALLY_COMPATIBLE` | contract-compatible با تفاوت قابل‌قبول و ثبت‌شده |
| `DEGRADED_FALLBACK` | کیفیت یا capability پایین‌تر؛ فقط با policy صریح و audit |
| `NOT_COMPATIBLE` | هرگز fallback target نیست |

### D-7 — Retry and fallback

Retry/fallback bounded است:

- هر attempt یک deadline مشترک request را مصرف می‌کند؛
- retry نامحدود ممنوع است؛
- یک deployment نمی‌تواند loop fallback ایجاد کند؛
- authentication failure، invalid request، policy rejection، authorization denial، contract violation
  و deterministic safety failure به provider بعدی fallback نمی‌شوند؛
- rate limit، timeout، transient provider failure و temporary unavailability فقط طبق active
  `ReliabilityPolicy` و candidate eligibility ممکن است fallback شوند؛
- exhaustion به typed model-unavailable/capacity outcome تبدیل می‌شود، نه exception vendor-specific.

### D-8 — Secret boundary

Secret واقعی فقط در Secret Manager یا runtime secret injection متعلق به CP-012 نگهداری می‌شود.

ممنوع است secret در این سطوح ظاهر شود:

- AI Core contracts یا logs؛
- `ModelPolicy` content؛
- `ConfigurationRelease`؛
- `RuntimeSnapshot`؛
- audit event؛
- frontend payload؛
- probe result؛
- prompt یا model input.

Frontend و audit فقط masked metadata، `credential_ref`، lifecycle state و آخرین probe status را می‌بینند.

### D-9 — Credential resolution

`credential_ref` فقط در آخرین trusted adapter boundary resolve می‌شود. AI Runtime حق resolve، cache،
rotate، reveal یا compare کردن secret را ندارد.

Revoke یا disable شناخته‌شده یک credential باید:

1. deploymentهای وابسته را فوراً ineligible کند؛
2. cache/LKG را برای همان dependency شکست دهد؛
3. انتخاب جدید را متوقف کند؛
4. فقط به candidate مجاز بعدی fallback کند؛
5. audit event ایجاد کند.

### D-10 — Frontend configuration path

System AI Administrator در Admin Website می‌تواند provider-neutral configuration را مدیریت کند:

- logical model pools؛
- deployment refs و model refs؛
- enabled/disabled state؛
- static priority/weight؛
- compatibility/fallback class؛
- timeout و bounded retry settings داخل hard bounds؛
- masked credential refs؛
- test/probe request؛
- Save and Apply؛
- rollback یا emergency disable با permission مناسب.

Frontend حق تغییر مستقیم این موارد را ندارد:

- LiteLLM raw YAML یا database؛
- raw API keys؛
- Redis topology؛
- hard safety ceilings؛
- Core globals؛
- active pointer بدون Control Plane command؛
- unqualified provider/model combination.

مسیر canonical:

```text
Admin Website
  -> Backend API
  -> authorized Control Plane command
  -> immutable ModelPolicy / ReliabilityPolicy revision
  -> validation and conditional provider probe
  -> ConfigurationRelease
  -> atomic activation
  -> RuntimeSnapshotFactory
  -> immutable RuntimeSnapshot
  -> AI Runtime
```

### D-11 — Probe semantics

Probe فقط برای combination دقیق provider/model/credential/profile انجام می‌شود و باید bounded، sanitized
و بدون داده سازمانی/کاربر باشد. موفقیت probe به‌تنهایی quality qualification نیست.

Activation در صورت probe لازم و ناموفق متوقف می‌شود؛ release قبلی فعال می‌ماند. freshness و expiry دقیق
probe evidence همچنان در `DEF-045` و CP-013 تعیین می‌شود.

### D-12 — Streaming

`ModelGatewayPort` باید streaming و non-streaming را بدون افشای vendor object پشتیبانی کند. Stream
chunkهای provider قبل از ورود به Core به valueهای provider-neutral تبدیل می‌شوند.

Cancellation و deadline باید از AI Runtime به adapter منتقل شوند. Client disconnect به‌تنهایی تصمیم
business cancellation نیست؛ Backend باید cancellation معتبر را به request context منتقل کند.

### D-13 — Redis separation

دو مسئولیت Redis از هم جدا هستند:

1. **Backend admission/queue Redis**: متعلق به Backend/CP-010/CP-012؛ AI Core آن را نمی‌شناسد.
2. **LiteLLM coordination Redis**: در صورت نیاز topology انتخاب‌شده، متعلق به LiteLLM adapter/service
   برای stateهای routing، cooldown، counters یا coordination؛ AI Core آن را نمی‌شناسد.

این دو باید حداقل namespace، credential، ownership و failure policy جدا داشته باشند. استفاده از instance
کاملاً جدا در production یک گزینه strong isolation است که topology دقیق آن به CP-012/PERF-001 واگذار
می‌شود.

### D-14 — Version and supply-chain pinning

LiteLLM version و container image باید exact pin و digest-qualified باشد. استفاده از `latest` یا
unqualified image ممنوع است. upgrade فقط پس از security review، regression، load test و rollback plan
فعال می‌شود.

### D-15 — Audit data

برای هر model invocation حداقل این lineage ثبت می‌شود، بدون raw secret و بدون الزام به raw prompt:

- request/run identifier؛
- logical pool و `ModelPolicy` revision؛
- selected `deployment_ref`، `provider_ref`، `model_ref` و masked `credential_ref`؛
- `ConfigurationRelease` و `RuntimeSnapshot`؛
- attempt count، fallback reason و terminal provider outcome؛
- latency، token usage و cost metadata where available؛
- cancellation/deadline state؛
- audit-safe error classification.

## Rejected alternatives

### RA-1 — Provider SDK inside AI Core

رد شد؛ vendor object، credential resolution و network semantics وارد Core می‌شود.

### RA-2 — LiteLLM SDK embedded in every AI worker as production topology

رد شد؛ health/cooldown/routing state و secret access میان workerها پخش و operational boundary مبهم می‌شود.

### RA-3 — Frontend edits LiteLLM config directly

رد شد؛ immutable revision، validation، authorization، release activation و audit دور زده می‌شود.

### RA-4 — LLM chooses provider or model

رد شد؛ مدل حق authority، capacity یا cost decision ندارد.

### RA-5 — Unbounded fallback across any model

رد شد؛ quality، capability، compliance و cost غیرقابل‌بازسازی می‌شود.

## Consequences

### Positive

- AI Core pure و vendor-neutral باقی می‌ماند.
- provider/key expansion بدون تغییر Core ممکن است.
- credential isolation و rotation قابل‌مدیریت می‌شود.
- ساده‌ترین load balancing قابل‌استفاده v1 تثبیت می‌شود.
- frontend configuration با Control Plane سازگار می‌ماند.
- failure و fallback reproducible و auditable است.

### Cost and complexity

- gateway service، secret manager، health coordination و rollout operations لازم است.
- model pool contracts و adapter tests باید ساخته شوند.
- compatibility و qualification evidence باید نگهداری شود.
- load balancing ساده هم بدون provider quota data قابل‌اعتماد نیست.

## Package ownership

| Responsibility | Primary owner | Supporting owner |
| --- | --- | --- |
| Provider-neutral model/pool/credential contracts | CP-001, CP-008 | AI-008 |
| Model invocation and structured-output runtime | AI-008 | AI-009 |
| Per-request budgets, deadlines, bounded retry/fallback | AI-009 | AI-008 |
| Control Plane commands, activation and probe orchestration | CP-009 | CP-008, CP-013 |
| Backend/API and Admin Website transport | CP-010, CP-011 | CP-009 |
| LiteLLM service, Redis integration, Secret Manager and provider adapters | CP-012 | CP-008 |
| Qualification, canary, load and regression gates | CP-013, PERF-001 | CP-008, AI-009 |
| Security hardening and incident closure | CP-014 | CP-012 |

## Acceptance criteria

- AC-1: هیچ `litellm`, Redis، Django، provider SDK یا Secret Manager type در AI Core contract نیست.
- AC-2: frontend فقط provider-neutral artifact fields و masked credential metadata را تغییر می‌دهد.
- AC-3: raw secret در artifact، snapshot، audit و log وجود ندارد.
- AC-4: pool و fallback فقط candidateهای pin‌شده و qualified را استفاده می‌کند.
- AC-5: retry/fallback bounded و با typed outcome است.
- AC-6: known disable/revoke فوراً eligibility را شکست می‌دهد.
- AC-7: streaming، deadline و cancellation از port provider-neutral عبور می‌کند.
- AC-8: LiteLLM version/image exact pin و قابل rollback است.
- AC-9: implementation claims فقط پس از CP-012/CP-013 evidence مجاز است.

## Open decisions preserved

- exact providerها، modelها، endpointها و API quotaها؛
- exact Secret Manager product؛
- exact LiteLLM version و routing mode؛
- exact Redis/Postgres topology؛
- exact model compatibility matrix؛
- exact probe evidence freshness؛
- exact production weights و fallback order؛
- exact load-test latency/SLO thresholds.
