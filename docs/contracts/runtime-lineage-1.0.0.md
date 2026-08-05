# Runtime Lineage Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/runtime_lineage.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-010-audit-retention-emergency-controls-and-threat-model.md`,
  `docs/control-plane/CP-000E-model-integration-audit-threat-baseline.md`,
  `docs/adr/ADR-CP-006-runtime-snapshot-factory-cache-and-lkg.md`
- Schema artifact: `schemas/runtime-lineage/1.0.0.schema.json` —
  `urn:ai-assistant:contracts:runtime-lineage:1.0.0`
- Deferred items addressed: DEF-016 (audit outcome taxonomy width, still governed
  by compatibility governance for `audit-event`), DEF-116 (release/snapshot
  lineage references)

## Purpose

Give a single immutable value that can answer “who asked what, over which scope,
against which source and policy versions, under which configuration release and
runtime snapshot, with what outcome, and under which retention regime”.

## The nine lineage elements

| Element | Field |
| --- | --- |
| organization | `organization_id` |
| actor scope | `actor_scope` (`AuthorizationScopeRef`), `actor_principal_id` |
| subject | `subject` (`LineageSubjectRef`) |
| time scope | `time_scope` (`LineageTimeScope`) |
| source version | `source_revisions` (`SourceRevisionLineageRef`) |
| policy version | `consulted_policy` (`ConsultedPolicyRevisionRef`) |
| ConfigurationRelease | `configuration_release` (`ConfigurationReleaseLineageRef`) |
| RuntimeSnapshot | `runtime_snapshot` (`RuntimeSnapshotLineageRef`) |
| run/request identifier | `run_id`, `request_id` |

Supporting shapes: `RetentionPolicyRef`, `LegalHoldRef`, `EmergencyActionRef`, and
`ProviderSelectionLineage` (provider selection and fallback, from the model
gateway family).

## Outcome taxonomy

`answered`, `partial`, `clarification_required`, `abstained`, `policy_rejected`,
`authorization_denied`, `failed`, `cancelled`.

- `authorization_denied` and `policy_rejected` are **never** the same value:
  a denial must carry `authorization_decision_id`, and a content/policy rejection
  must not carry one.
- Every non-`answered` outcome must carry at least one reason code.
- `answered` requires at least one source revision reference.

The published `audit-event` 1.0.0 outcome union (`success`, `denied`, `failed`)
is **not** modified. The wider taxonomy lives in this new family; an
`audit-event` successor version remains an open decision (see the package
document).

## Invariants

1. Actor scope, when present, must belong to the lineage organization.
2. Source revision references are unique by revision and bounded by
   `MAX_LINEAGE_SOURCE_REVISIONS`; reason codes are bounded and canonical.
3. `LineageTimeScope` validity windows must be strictly ordered.
4. `RetentionPolicyRef` expresses a class, revision and optional positive day
   count — never deletion behavior.
5. `LegalHoldRef` state and `released_at` must agree: an active hold has no
   release instant, and a released hold must have one.
6. All instants are timezone-aware and normalized to UTC.

## Out of scope

Durable audit storage, emission semantics, retention enforcement, hold
enforcement, emergency control execution, and export tooling belong to CP-010 and
later packages.

## Versioning

New family at `1.0.0`. No published contract is modified in place; the
`runtime-snapshot` and `audit-event` 1.0.0 artifacts are byte-identical to their
committed baseline (asserted by tests).

## Tests

`tests/test_source_and_lineage_contracts.py::RuntimeLineageTests` and the
versioning-stability suite in `tests/test_cp001_boundary.py`.
