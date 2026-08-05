# CP-001 — Control Plane Contracts

- Status: **implementation submitted for architect review** (not accepted, not
  merged, roadmap status unchanged)
- Base: tag `architecture-cp000e`, branch `feature/cp-001-control-plane-contracts`
- Authority applied, in order: committed implementation and typed contracts →
  `docs/architecture/architecture-authority-manifest.md` → accepted CP ADRs and
  Control Plane baselines (CP-000A–CP-000E, CP-000R) →
  `docs/architecture/ai-assistant-canonical-delivery-roadmap-fa.md` →
  `docs/deferred-items.md` → contract documentation →
  `docs/walking-skeleton-1.0.0.md` → supporting documents

## 1. Scope

CP-001 defines provider-neutral, transport-neutral **contracts and immutable
domain values** for the Control Plane and AI boundaries at four levels: Python
typed contracts, JSON Schema artifacts, contract documentation, and tests.

It implements no database, ORM, Django, HTTP endpoint, Redis, queue, gateway
adapter, provider SDK, Secret Manager, object storage, vector database, artifact
registry persistence, activation service, `RuntimeSnapshotFactory`, source
ingestion, authorization evaluation engine, admin website, or production adapter.

## 2. Implemented contract families

| Family | Module | Schema families | Doc |
| --- | --- | --- | --- |
| Organization and hierarchy | `contracts/organization.py` | `organization`, `organizational-node` | `docs/contracts/organization-hierarchy-1.0.0.md` |
| Membership and scoped role | `contracts/membership.py` | `node-membership`, `scoped-role-assignment` | `docs/contracts/membership-authorization-scope-1.0.0.md` |
| Principal and authorization boundary | `contracts/principal.py` | `request-actor-context`, `authorization-request` | `docs/contracts/principal-authorization-request-1.0.0.md` |
| Configuration and release | `contracts/configuration.py` | `configuration-release`, `model-pool-policy` | `docs/contracts/configuration-release-1.0.0.md` |
| Source registry and relationships | `contracts/source_registry.py` | `knowledge-source`, `source-revision`, `source-relationship` | `docs/contracts/source-registry-1.0.0.md` |
| Runtime lineage and retention | `contracts/runtime_lineage.py` | `runtime-lineage` | `docs/contracts/runtime-lineage-1.0.0.md` |
| Model gateway boundary | `contracts/model_gateway.py` + `core/ports.py` | `model-invocation-request`, `model-invocation-result` | `docs/contracts/model-gateway-1.0.0.md` |

Shared primitives (canonical code pattern, digest pattern, opaque identifier and
revision types, UTC instants) live in `contracts/control_plane_base.py` and build
on the published `contracts/base.py` conventions (`ContractModel` with
`extra="forbid"`, `frozen=True`, `validate_default=True`).

## 3. Inventory classification

### EXISTING_REUSE

- `ContractModel`, `SchemaVersion`, `UtcDateTime`, `SCHEMA_VERSION_PATTERN`
  (`contracts/base.py`)
- `SecurityPrincipalContext`, `AuthorizationDecision`, `AuthorizationResourceRef`
  (`security` 1.0.0) — decision contract untouched, resource reference reused
- `AuditEvent`, `AuditActorRef`, `AuditResourceRef` (`audit-event` 1.0.0)
- `RuntimeArtifactRef`, `RuntimeSnapshotContent`, `RuntimeSnapshotIntegrity`,
  `RuntimeSnapshot` (`runtime-snapshot` 1.0.0) — read as authority, not modified

### NEW_CONTRACT (all at `1.0.0`)

All fourteen schema families listed in section 2, plus the non-schema value types
and references documented in the per-family contract documents, plus the
`ModelGatewayPort` protocol in Core.

### VERSIONED_SUCCESSOR

None published in this package. The wider audit outcome taxonomy is introduced in
the **new** `runtime-lineage` family rather than by editing `audit-event` 1.0.0,
and release/snapshot lineage is introduced by new reference types rather than by
rewriting `runtime-snapshot` 1.0.0. Successor versions of those two published
families are recorded as open decisions (section 7).

### OUT_OF_SCOPE

Authorization evaluator, policy engine, scope expansion, hierarchy traversal
(CP-002); artifact registry, active pointer persistence, atomic activation,
rollback storage (CP-003); `RuntimeSnapshotFactory`, cache, LKG, digest
resolution (CP-004); registry persistence, ingestion, chunking, embedding, index
activation, revoke propagation (CP-005/CP-006); pool operations, probe execution,
configuration application service, commands, events (CP-008/CP-009); queue,
Redis, HTTP, gateway adapter, production adapters (CP-010/CP-012).

### DECISION_REQUIRED

See section 7.

## 4. Deferred item mapping

| DEF | Disposition in CP-001 | Owner going forward |
| --- | --- | --- |
| DEF-016 | Not closed. CP-001 publishes only new `1.0.0` families and breaks no published contract, so no compatibility waiver is consumed. | Compatibility governance |
| DEF-037 | Contract half implemented: provider-neutral request/result/stream shapes and `ModelGatewayPort`. | CP-012 adapter, AI-008 runtime |
| DEF-103 | Implemented as shape: generic recursive node with root/parent invariants. | CP-002 behavior |
| DEF-104 | Implemented as shape: node status and lifecycle references. | CP-002 behavior |
| DEF-105 | Implemented as shape: membership and scoped role assignment. | CP-002 evaluation |
| DEF-106 | Implemented as shape: explicit, enumerated `AuthorizationScopeRef`. | CP-002 evaluation |
| DEF-107 | Out of scope for CP-001 (evaluation semantics). | CP-002 with AI-003 |
| DEF-108 | Implemented as shape: `DecisionBindingRef` request-to-decision binding. | CP-002 issuance |
| DEF-114 | Implemented as shape: release, manifest, active pointer, activation/rollback references. | CP-003 persistence |
| DEF-115 | Implemented as shape: logical pools, deployment/credential/probe references. | CP-008 operations |
| DEF-116 | Partially addressed: lineage reference types created; `RuntimeSnapshot` successor **not** created (open decision). | CP-001 successor decision with CP-004 |
| DEF-119 | Implemented as shape: four disjoint source metadata classes. | CP-005 lifecycle |
| DEF-121 | Only the two canonically decided relationship kinds are representable; `AMENDS` and `PARTIALLY_SUPERSEDES` remain unrepresentable. | Canonical decision, then CP-005 |

## 5. Versioning policy applied

- Every family introduced here is a new family at `1.0.0` with a new schema `$id`.
- No published `1.0.0` schema ID, field name, serialization semantic, or exported
  symbol was edited, renamed, or removed. `tests/test_cp001_boundary.py` asserts
  byte-level parity of all thirteen previously published artifacts against their
  models, and asserts that each schema family directory still contains exactly one
  version.
- Schema artifacts are generated from the models with the repository's existing
  canonical formatting (`indent=2`, `sort_keys=True`, `ensure_ascii=False`,
  trailing newline), verified by regenerating a pre-existing artifact
  byte-for-byte before writing any new one.

## 6. Boundary guarantees

`tests/test_cp001_boundary.py` scans every module under
`src/ai_assistant/contracts/` and `src/ai_assistant/core/` and fails on: any
import of a web framework, transport, queue, cache, database driver, provider SDK,
cloud SDK, or process/environment module; any vendor token in source text; any
mutable module-level container; any field or schema property whose name looks like
a secret. Only `pydantic`, a fixed standard-library allowlist, and internal
modules are importable inside the boundary.

## 7. Open decisions (not resolvable from canonical documents)

1. **`RuntimeSnapshot` successor version (DEF-116).** Whether release/snapshot
   lineage should become fields of a `runtime-snapshot` 2.0.0, or stay in the new
   `runtime-lineage` family as implemented. CP-001 chose the non-breaking option.
   Recommendation: keep lineage separate; revisit with CP-004.
2. **`audit-event` successor for the eight-value outcome taxonomy (DEF-016).**
   The published `audit-event` 1.0.0 union is `success | denied | failed`. The
   canonical taxonomy has eight values. CP-001 did not edit the published union.
   Recommendation: publish `audit-event` 2.0.0 once DEF-016 governance is closed.
3. **Node type vocabulary closure.** ADR-CP-001 defines node type as a versioned
   administrative vocabulary, so it is modelled as a catalog code, not a closed
   enum. If a closed enum is required, that is a major-version decision.
4. **`RetrievalAuthorizationEnvelope` ownership.** All inputs are now
   expressible, but the envelope aggregate binds evaluation output, which is
   CP-002 territory. Recommendation: CP-002 publishes the envelope.

## 8. Exit criteria status

| Criterion | Status |
| --- | --- |
| All CP-001 families inventoried | Met (section 3) |
| Every obligation implemented, deferred, or out-of-scope | Met (section 4) |
| No published 1.0.0 broken in place | Met, asserted by tests |
| Python ↔ JSON Schema parity | Met, asserted by tests |
| Docs and exports complete | Met (per-family docs, export coverage test) |
| No DB/HTTP/Django/Redis/gateway/provider dependency in Core | Met, asserted by tests |
| Real tests passed | Partially: the three CP-001 suites pass under the standard library test runner |
| Coverage gate passed | **Not runnable in this environment** |
| Build succeeded | **Not runnable in this environment** |
| `git diff --check` passed | Met |
| No gap closed by status change alone | Met; roadmap untouched |

The verification toolchain (`uv`, `ruff`, `mypy`, `pytest`, `coverage`) is absent
from this environment and cannot be installed (no network), so `./scripts/verify.sh`
and `uv build` were not executed. CP-001 is therefore submitted as **BLOCKED** on
verification, not as passing.
