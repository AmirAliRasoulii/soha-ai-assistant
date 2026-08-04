# ADR-CP-009: Backend, Control Plane, and AI Runtime Integration Boundary

Status: Accepted architecture baseline (originated as CP-000E; acceptance becomes effective when the
CP-000E package commit is reviewed and merged)
Implementation remains owned by the packages identified in this document.
Date: 2026-08-04
Owner: Backend / Control Plane Integration Boundary
Scope: command, event, pull, admission, queue، cancellation، idempotency، config administration و
separation میان Backend، Control Plane، AI Runtime و production adapters. این ADR هیچ Django model،
HTTP endpoint، Redis product، worker framework یا transport implementation را انتخاب یا implemented
اعلام نمی‌کند.

Companions:

- `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`
- `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md`
- `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`
- `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`
- `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`

## Context

AI Module باید یک ماژول محض و مستقل باقی بماند. Backend مسئول authentication integration، admission،
HTTP/API، queue، user-facing status و product workflows است. Control Plane مسئول command semantics،
immutable revisions، validation، release activation و audit است. AI Runtime فقط request پذیرفته‌شده و
trusted inputs را اجرا می‌کند.

ظرفیت product assumption برای v1:

- جمعیت ثبت‌شده ممکن است تا حدود 20,000 دانشجو باشد؛
- Backend تا 300 AI job فعال را admission می‌کند؛
- تا 1,500 job پذیرفته‌شده ممکن است در صف Backend باشند؛
- درخواست بیشتر باید قبل از ورود به AI Runtime با overload response رد شود؛
- این اعداد hardcoded AI Core fields نیستند و بعداً بر اساس PERF-001 قابل تغییرند.

## Problem

- P-1: اگر AI Runtime صف global را مدیریت کند، product policy، user fairness، HTTP و infrastructure وارد
  Core می‌شود.
- P-2: اگر Backend مستقیماً Core variable یا LiteLLM config را mutate کند، release lifecycle دور زده
  می‌شود.
- P-3: command، event و pull بدون idempotency و optimistic concurrency می‌تواند activation یا emergency
  action تکراری و مبهم ایجاد کند.
- P-4: نگه داشتن 1,500 HTTP connection در انتظار model capacity، worker و memory را هدر می‌دهد.
- P-5: frontend باید تنظیمات را تغییر دهد، ولی secret، hard bounds و runtime pointer نباید client-owned
  شوند.
- P-6: queue Redis و LiteLLM Redis ممکن است با هم اشتباه شوند و failure domain مشترک بسازند.

## Decision

### D-1 — Four explicit layers

```text
Admin Website / User Client
  -> Backend/API Integration
  -> Control Plane Application Services
  -> AI Runtime and Production Adapters
```

هیچ layer حق دورزدن layer بعدی را ندارد.

### D-2 — Backend ownership

Backend مالک این رفتارهاست:

- authentication/session integration؛
- transport validation و HTTP/SSE/WebSocket mapping؛
- global admission control؛
- active-job ceiling و waiting queue؛
- per-user/product policy when later defined؛
- job status، queue status و cancellation API؛
- overload response و `Retry-After`؛
- product-safe localization؛
- Admin Website controllers/read models؛
- correlation میان product request و AI run.

AI Core queue size، queue position، registered-user count، user quota، HTTP status یا Redis key را
نمی‌بیند.

### D-3 — AI Runtime ownership

AI Runtime فقط requestی را می‌پذیرد که Backend admission آن را انجام داده است و این controls را برای
همان request enforce می‌کند:

- immutable `RuntimeSnapshot`؛
- trusted authorization decision؛
- request deadline؛
- cancellation signal؛
- idempotency binding؛
- bounded plan steps؛
- bounded parallel capability calls؛
- bounded retry/fallback؛
- token/cost budget؛
- terminal state and audit hooks.

AI Runtime global queue یا user fairness policy ندارد.

### D-4 — Backend queue model

Jobهای منتظر باید از request transport جدا شوند:

```text
Client request
  -> Backend admission
  -> ACCEPTED/RUNNING or QUEUED or OVERLOADED
  -> durable/bounded job reference
  -> polling, SSE, or WebSocket status
  -> AI Runtime execution after admission slot
```

Backend نباید برای همه jobهای queued یک Python task یا open provider request بسازد. Queue باید bounded
باشد و overflow سریع رد شود.

### D-5 — Capacity assumptions

Baseline اولیه محصول:

| Capacity item | v1 assumption | Owner |
| --- | --- | --- |
| Registered population | approximately 20,000 | Product/Backend planning |
| Active admitted AI jobs | maximum 300 | Backend admission / PERF-001 |
| Accepted waiting jobs | maximum 1,500 | Backend queue / PERF-001 |
| Beyond active + queued | reject with overload response | Backend/API |
| Per-user fairness | deferred product policy | Backend, not AI Core |

این اعداد performance target هستند، نه guarantee تا زمانی که PERF-001 load evidence تولید نشده باشد.

### D-6 — Redis ownership

Backend queue state در adapter/infrastructure قرار دارد. Redis یک candidate implementation برای CP-012
است، نه contract requirement برای Core.

```text
Backend Queue Port
  -> CP-012 Redis/Queue Adapter
```

LiteLLM coordination Redis، در صورت استفاده، boundary جدا دارد:

```text
ModelGatewayPort
  -> CP-012 LiteLLM Adapter/Service
  -> LiteLLM coordination store
```

Backend queue و LiteLLM coordination نباید key space، credential یا ownership مشترک نامشخص داشته باشند.

### D-7 — Configuration command path

Frontend تنظیمات AI را از طریق Control Plane تغییر می‌دهد:

```text
Admin Website
  -> Backend command DTO
  -> authenticated + authorized Control Plane command
  -> optimistic concurrency check
  -> validation
  -> conditional provider probe where required
  -> immutable artifact revision
  -> ConfigurationRelease
  -> atomic active pointer update
  -> audit event
  -> RuntimeSnapshotFactory pull/resolve
```

Frontend هیچ‌گاه:

- Core variable را mutate نمی‌کند؛
- active release pointer را مستقیم نمی‌نویسد؛
- LiteLLM config database را مستقیم تغییر نمی‌دهد؛
- raw secret را read/write نمی‌کند؛
- untrusted deployment metadata را authorization input نمی‌کند.

### D-8 — Command semantics

Control Plane command حداقل این envelope provider-neutral را دارد:

- command type and version؛
- command id؛
- actor/principal reference؛
- authorization decision/binding reference؛
- target resource/revision؛
- expected version for optimistic concurrency؛
- idempotency key؛
- reason/change note؛
- requested timestamp and deadline؛
- correlation/causation identifiers.

Transport-specific headers و Django objects داخل command contract نیستند.

### D-9 — Idempotency and optimistic concurrency

- هر mutating command idempotent است؛
- duplicate command همان outcome قبلی را برمی‌گرداند یا typed conflict می‌دهد؛
- activation با expected active pointer/version انجام می‌شود؛
- stale edit یا stale activation overwrite خاموش ایجاد نمی‌کند؛
- retry transport نباید revision یا release اضافی بسازد؛
- emergency commands نیز idempotent هستند.

### D-10 — Event boundary

Domain/control-plane events immutable و versioned هستند. Event حداقل actor، resource، before/after refs،
correlation، causation، timestamp و outcome را حمل می‌کند.

Event bus delivery به‌تنهایی truth نیست. Canonical state در registry/active pointer باقی می‌ماند. Consumer
باید idempotent باشد و event replay را تحمل کند.

### D-11 — Runtime snapshot pull

AI Runtime config را از mutable Backend dictionary push نمی‌گیرد. Runtime از trusted boundary یک
`RuntimeSnapshot` immutable و digest-verified می‌گیرد یا reference آن را resolve می‌کند.

Snapshot refresh:

- activation notification می‌تواند cache invalidation hint باشد؛
- notification loss نباید correctness را بشکند؛
- pull/resolve و digest verification authority دارد؛
- request در شروع به یک snapshot pin می‌شود؛
- snapshot در میانه request تغییر نمی‌کند؛
- revoke/disable شناخته‌شده LKG را شکست می‌دهد.

### D-12 — Cancellation

Backend cancellation request را authorize و به runtime منتقل می‌کند. AI Runtime cancellation را در
safe points و adapter calls رعایت می‌کند.

Cancellation باید:

- idempotent باشد؛
- terminal state دقیق ایجاد کند؛
- provider call را best-effort cancel کند؛
- partial output را بدون policy صریح publish نکند؛
- audit شود؛
- job slot را آزاد کند.

### D-13 — Overload response

وقتی Backend capacity ندارد، request قبل از AI Runtime با product-safe overload outcome رد می‌شود.
HTTP mapping، localization و `Retry-After` متعلق به CP-010 است.

AI Core ممکن است فقط per-request dependency capacity failure را به typed domain error تبدیل کند؛ این
با Backend global overload یکی نیست.

### D-14 — Admin read models

Admin Website read model ممکن است وضعیت زیر را نشان دهد:

- active ConfigurationRelease؛
- artifact revisions and validation status؛
- provider/model deployment refs؛
- masked credential metadata؛
- health/probe summary؛
- activation/rollback history؛
- audit references؛
- load/capacity summary where authorized.

Read model نباید raw secret، raw unrestricted prompt/content، internal Redis keys یا provider tokens را
نمایش دهد.

### D-15 — No backend leakage into Core

ممنوع در AI Core:

- Django model/queryset/request/session؛
- HTTP headers/status objects؛
- Redis clients/keys؛
- Celery/RQ/worker job objects؛
- LiteLLM/OpenAI/Anthropic SDK objects؛
- mutable ORM entities؛
- Secret Manager clients؛
- frontend role labels.

### D-16 — Failure ownership

| Failure | Owning layer |
| --- | --- |
| User/session authentication failure | Backend/Identity adapter |
| Global queue full / overload | Backend/API |
| Stale admin edit | Control Plane command service |
| Invalid artifact/release | Control Plane validation |
| Snapshot resolution failure | RuntimeSnapshotFactory/adapter |
| Provider timeout/rate limit | Model gateway adapter + AI-009 policy |
| Per-request deadline/cancellation | AI Runtime + adapter |
| UI rendering/localization | Backend/UI |

## Rejected alternatives

### RA-1 — AI Core owns Redis queue

رد شد؛ product admission، fairness، transport و infrastructure وارد Core می‌شود.

### RA-2 — Backend directly mutates AI config

رد شد؛ immutable revision، authorization، validation، audit و rollback را دور می‌زند.

### RA-3 — Long-lived HTTP wait for all queued jobs

رد شد؛ connection و worker resources را با 1,500 job منتظر اشغال می‌کند.

### RA-4 — Push mutable config into running requests

رد شد؛ reproducibility و snapshot pinning را می‌شکند.

## Consequences

- AI Module مستقل و قابل تست باقی می‌ماند.
- Backend می‌تواند queue technology را بدون تغییر Core عوض کند.
- frontend configuration حفظ می‌شود ولی authority در Control Plane می‌ماند.
- operational complexity queue، Redis، workers و event delivery به CP-012 منتقل می‌شود.
- product باید job lifecycle و overload UX را طراحی کند.

## Package ownership

| Responsibility | Primary owner | Supporting owner |
| --- | --- | --- |
| Command/event/snapshot contracts | CP-001 | CP-009, CP-010 |
| Control Plane application services | CP-009 | CP-003, CP-004, CP-008 |
| Backend/API boundary and admission | CP-010 | CP-009, PERF-001 |
| Admin Website | CP-011 | CP-009, CP-010 |
| Redis queue, workers, events and LiteLLM adapters | CP-012 | CP-010 |
| Per-request runtime controls | AI-002, AI-009 | AI-008 |
| Load qualification | PERF-001, CP-013 | CP-010, CP-012 |

## Acceptance criteria

- AC-1: AI Core هیچ queue/Redis/HTTP/Django type ندارد.
- AC-2: global 300/1,500 capacity controls فقط Backend assumptions هستند.
- AC-3: queued job transport از AI execution جداست.
- AC-4: Admin Website فقط Control Plane command می‌فرستد.
- AC-5: commandها idempotent و optimistic-concurrency protected هستند.
- AC-6: RuntimeSnapshot immutable، pinned و digest-verified است.
- AC-7: cancellation و overload ownership صریح و جداست.
- AC-8: Backend queue Redis و LiteLLM coordination store boundary جدا دارند.
- AC-9: implementation تا packageهای مربوط ادعا نمی‌شود.

## Open decisions preserved

- exact queue technology، worker framework و Redis topology؛
- exact job-status transport: polling، SSE یا WebSocket؛
- exact per-user fairness and quota policy؛
- exact queue timeout و `Retry-After` calculation؛
- exact deployment SLO و autoscaling policy؛
- exact command/event transport؛
- exact Admin Website layout.
