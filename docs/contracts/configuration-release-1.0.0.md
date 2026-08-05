# Configuration and Release Contract 1.0.0

- Status: implemented in `src/ai_assistant/contracts/configuration.py`
- Package: CP-001 (Control Plane Contracts)
- Authority: `docs/adr/ADR-CP-004-configuration-artifact-taxonomy-ownership-and-precedence.md`,
  `docs/adr/ADR-CP-005-configuration-versioning-activation-and-rollback.md`,
  `docs/adr/ADR-CP-008-model-gateway-provider-pool-and-credential-boundary.md`,
  `docs/control-plane/CP-000D-configuration-catalog.md`
- Schema artifacts:
  - `schemas/configuration-release/1.0.0.schema.json` — `urn:ai-assistant:contracts:configuration-release:1.0.0`
  - `schemas/model-pool-policy/1.0.0.schema.json` — `urn:ai-assistant:contracts:model-pool-policy:1.0.0`
- Deferred items addressed: DEF-114 (release/manifest shapes), DEF-115
  (provider-neutral model policy references)

## Purpose

Describe *which* configuration artifact revisions are bundled into a release,
which release is active, how activation and rollback are referenced, and how a
provider-neutral logical model policy is expressed — all without any credential
material, provider SDK concept, or persistence behavior.

## Shapes

| Type | Purpose |
| --- | --- |
| `ConfigurationArtifactRevisionRef` | `(namespace, artifact_id, revision, digest)` reference into the artifact taxonomy. |
| `ReleaseManifestEntry` | One artifact revision plus owner role and `operator_changeable` flag. |
| `ConfigurationRelease` | Release identity, label, status, manifest, manifest digest, lineage to the previous release. |
| `ActiveConfigurationReleaseRef` | The pointer shape: active release, label, manifest digest, activation instant and id. |
| `ConfigurationActivationRef` | Activation **or** rollback reference with reason code and actor. |
| `CredentialRef` | Opaque credential handle: `credential_ref`, `credential_class`, optional `rotated_at`. |
| `ModelDeploymentRef` | Opaque deployment/provider/model handles, compatibility class, preference rank, timeout. |
| `ProbeEvidenceRef` | Reference to compatibility/health probe evidence with digest. |
| `LogicalModelPoolRef` / `LogicalModelPool` | Logical pool code and the ordered deployment set behind it. |
| `ModelPoolPolicy` | Versioned, published set of logical pools. |

## Invariants

1. **No secret material may exist anywhere in this family.** Credentials are
   opaque references with a class; no `api_key`, `secret`, `token`, `password`, or
   header field exists, and `extra="forbid"` rejects any attempt to inject one.
2. A manifest is non-empty, unique per artifact, and bounded by
   `MAX_MANIFEST_ENTRIES`.
3. A `validated` release must record `validated_at`; a `draft` release must not.
4. A release may not declare itself as its own predecessor.
5. A rollback reference must name the release it moves away from, otherwise the
   action would not be auditable.
6. All deployments in a pool must share the pool's compatibility class, their
   preference ranks must be unique, and probe evidence must reference a
   deployment that is actually in the pool.
7. Pool codes are unique inside one `ModelPoolPolicy` revision, and pools are
   addressed by logical code — never by provider or model name.
8. Digests are `sha256:<64 hex>` with syntax and length validation and no storage
   or provider assumption.

## Out of scope

Artifact registry persistence, active-pointer storage, atomic activation,
rollback storage (CP-003); configuration application service, commands, events,
probe execution, and pool operations (CP-008/CP-009); Secret Manager integration
and any provider adapter (CP-012).

## Versioning

New families at `1.0.0`. `runtime-snapshot` 1.0.0 is untouched; the lineage
references that connect a release to a snapshot live in the runtime lineage
family instead of being retrofitted into the published snapshot contract.

## Tests

`tests/test_control_plane_contracts.py::ConfigurationReleaseTests` plus the
repository-wide secret scan in `tests/test_cp001_boundary.py`.
