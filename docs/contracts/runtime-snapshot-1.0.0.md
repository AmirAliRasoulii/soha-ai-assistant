# RuntimeSnapshot 1.0.0

Status: Accepted and implemented as a bounded baseline
Owner: Chat Runtime Configuration Boundary
Schema identity: `urn:ai-assistant:contracts:runtime-snapshot:1.0.0`
JSON Schema dialect: `https://json-schema.org/draft/2020-12/schema`


## Bounded baseline status and known limitations (CP-000R)

This contract is **accepted and implemented as a bounded baseline**. Base repository evidence:
`6477c1c`. Bounded implementation existed at base commit `6477c1c`. CP-000R documentation acceptance
becomes effective when the CP-000R commit is reviewed and merged.
CP-000R changed no field, no type, no validation rule, no schema, and no version of this contract. It
records truthfully what this 1.0.0 contract does and does not yet cover, and who owns the remaining
work.

| Known limitation | Owner |
| --- | --- |
| `source_revision` names the **application** source revision, that is the deployed code revision. It is not a knowledge `SourceRevision`. The intended vNext rename is `application_source_revision` (audit finding G-014); this baseline changes no field name | CP-001 |
| `index_snapshot` must be interpreted as a **logical aggregate `IndexSnapshot` manifest** referencing one or more eligible physical snapshots plus routing metadata, not a single physical build (audit findings G-017, NEW-005) | CP-006 |
| `security_policy` is the **global** `SecurityPolicy` configuration artifact. It is not a per-source `VisibilityPolicyDefinition`, and it never carries per-source visibility (audit finding G-016) | CP-004 with CP-002 |
| `RuntimeArtifactRef` has no namespace field, so artifact-id collisions across artifact families are not structurally prevented (audit findings G-015, NEW-006) | CP-001 with CP-004 |
| `config_bundle` duplication versus the `ConfigurationRelease` manifest requires exact factory equivalence: the denormalized snapshot refs must match the release manifest exactly (audit findings G-018, NEW-007) | CP-004 with CP-006 |
| `config_bundle` must be interpreted as the **exact `ConfigurationRelease` manifest reference** for the active release, `security_policy` as the **global runtime `SecurityPolicy`** configuration artifact, `index_snapshot` as the **logical aggregate `IndexSnapshot` manifest**, and `source_revision` as the **application / source-code revision**. The release-pinned `BuildArtifact` binds or verifies `application_version`, the application `source_revision`, and the `build_artifact` identity. Named `RuntimeSnapshot` artifact references must exactly match the active `ConfigurationRelease` manifest. `RuntimeSnapshot 1.0.0` does **not** itself enforce the future RuntimeSnapshotFactory resolution algorithm | CP-004 RuntimeSnapshotFactory |
| `RuntimeSnapshot 1.0.0` permits at most **sixteen entries in `model_artifacts`** (at least one, unique) and at most **sixty-four effective `feature_flags`** (unique names). These are collection bounds on the snapshot; they are not sixteen named artifact reference fields, and they do not constrain the total number of artifact references inside a `ConfigurationRelease`. No CP-000D or CP-000R decision changes them | Unchanged constraint |
## Purpose

RuntimeSnapshot records the exact effective application and AI configuration references that were
in force for a run. It answers the question "which immutable configuration produced this
behaviour" without embedding any configuration content, secret, or vendor detail.

A snapshot is an immutable value. One snapshot may be referenced by many runs.

## AI Core boundary

This repository is the pure, vendor-neutral AI Core. This task defines the typed contract and its
exact semantics only. The contract does not and must not implement:

- configuration loading or environment-variable reading;
- Git command execution;
- Docker, OCI, Kubernetes, cloud, or CI/CD clients;
- artifact registry access or artifact retrieval;
- model or provider initialization;
- observability SDK integration;
- database or storage access;
- runtime snapshot capture;
- digest computation or verification.

Frontend, backend transport, deployment, DevOps, and infrastructure adapters live outside the AI
Core and may resolve the references carried by this contract.

## Structure

```
RuntimeSnapshot
  content: RuntimeSnapshotContent
    build_artifact, config_bundle, ... : RuntimeArtifactRef
    model_artifacts: tuple[RuntimeArtifactRef, ...]
    feature_flags: tuple[RuntimeFeatureFlag, ...]
  integrity: RuntimeSnapshotIntegrity
```

Nested value objects do not carry their own `schema_version`. They inherit the root RuntimeSnapshot
schema version.

## RuntimeSnapshot fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `schema_version` | literal `"1.0.0"` | no, default `"1.0.0"` | any other value is rejected |
| `snapshot_id` | UUID | yes | must be UUID version 4 |
| `captured_at` | UtcDateTime | yes | aware instant, normalized to UTC; naive rejected |
| `content` | RuntimeSnapshotContent | yes | closed nested model |
| `integrity` | RuntimeSnapshotIntegrity | yes | closed nested model |

`run_id` is intentionally absent. Run binding belongs to a future RunContext or ChatRun contract.

## RuntimeSnapshotContent fields

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `application_version` | SchemaVersion | yes | `major.minor.patch` |
| `source_revision` | str | yes | exactly 40 or 64 lowercase hexadecimal characters |
| `build_artifact` | RuntimeArtifactRef | yes | generic immutable build provenance |
| `config_bundle` | RuntimeArtifactRef | yes | effective configuration bundle |
| `prompt_bundle` | RuntimeArtifactRef | yes | effective prompt bundle |
| `model_policy` | RuntimeArtifactRef | yes | model selection and routing policy |
| `model_artifacts` | tuple of RuntimeArtifactRef | yes | 1 to 16, unique by `artifact_id`, ordered |
| `structured_output_backend` | RuntimeArtifactRef | yes | structured output backend manifest |
| `retrieval_profile` | RuntimeArtifactRef | yes | retrieval configuration |
| `embedding_artifact` | RuntimeArtifactRef | yes | embedding manifest |
| `reranker_artifact` | RuntimeArtifactRef | yes | reranker manifest |
| `index_snapshot` | RuntimeArtifactRef | yes | index snapshot manifest |
| `semantic_catalog` | RuntimeArtifactRef | yes | semantic catalog manifest |
| `rule_bundle` | RuntimeArtifactRef | yes | deterministic rule bundle |
| `security_policy` | RuntimeArtifactRef | yes | security policy bundle |
| `telemetry_schema` | RuntimeArtifactRef | yes | telemetry schema manifest |
| `feature_flags` | tuple of RuntimeFeatureFlag | no, default `()` | at most 64, unique by `name`, ordered |

Every named artifact field is required and explicit. They are never replaced by a dictionary or by
a generic list of arbitrary component names. Missing `feature_flags` becomes an empty tuple, while
an explicit `null` is rejected. Model artifacts and feature flags are never sorted automatically.

## RuntimeArtifactRef fields

| Field | Type | Rules |
| --- | --- | --- |
| `artifact_id` | str | 1 to 256 characters, non-blank, no NUL, no surrounding whitespace, preserved exactly |
| `revision` | str | 1 to 128 characters, non-blank, no NUL, no surrounding whitespace, preserved exactly |
| `digest` | content digest | `sha256:` followed by 64 lowercase hexadecimal characters |

## RuntimeFeatureFlag fields

| Field | Type | Rules |
| --- | --- | --- |
| `name` | str | 1 to 64 characters, starts with a lowercase ASCII letter, then lowercase letters, digits, `.`, `_`, `:`, or `-` |
| `enabled` | bool | boolean only; multivariate values are not supported in 1.0.0 |

## RuntimeSnapshotIntegrity fields

| Field | Type | Rules |
| --- | --- | --- |
| `canonicalization` | literal `"rfc8785"` | any other value is rejected |
| `digest` | content digest | `sha256:` followed by 64 lowercase hexadecimal characters |

## Artifact reference semantics

A RuntimeArtifactRef is an immutable internal manifest reference. It identifies an artifact inside
the organization's own manifest space and pins it with a content digest.

- It must not contain URLs, filesystem paths, registry hosts, registry credentials, provider
  objects, or raw artifact content.
- `artifact_id` and `revision` are opaque to this contract. They are never parsed, resolved,
  normalized, or lowercased.
- Build provenance uses the generic `build_artifact` field. Fields such as `container_digest`,
  `docker_image`, `image_tag`, `registry_url`, `kubernetes_namespace`, or `cloud_region` are
  forbidden. A deployment adapter may resolve `build_artifact` to an OCI image, a Python package,
  an executable bundle, or another immutable deployment artifact.
- Model and provider neutrality is mandatory. Fields such as `provider`, `provider_object`,
  `endpoint`, `base_url`, `api_key`, `deployment_name`, or `raw_model_config` are forbidden.
  Provider and backend selection is resolved through the referenced immutable model policy and
  artifact manifests, outside this contract.

## Content digest semantics

`integrity.digest` is SHA-256 over the RFC 8785 canonical JSON representation of:

```
snapshot.content.model_dump(mode="json")
```

The digest covers the content object only. It excludes:

```
schema_version
snapshot_id
captured_at
integrity
```

This contract validates the format of the integrity metadata only. It does not compute, recompute,
or verify the digest, and it adds no RFC 8785 dependency. Computation and verification belong to a
trusted RuntimeSnapshotFactory, which is owned by **CP-004 RuntimeSnapshotFactory** and was **not**
delivered in the Walking Skeleton task.

Explicitly:

- this contract does not authorize artifact retrieval;
- this contract does not prove that referenced artifacts exist;
- this contract does not compute or verify the content digest;
- registry resolution and digest verification are fail-closed responsibilities of the future
  trusted factory;
- no raw configuration and no secret may be persisted in the snapshot.

## Producer and consumer trust rules

Producer rules:

- Only trusted server-side code inside the Chat Runtime Configuration Boundary may construct a
  RuntimeSnapshot.
- Every value must come from already-resolved, immutable, digest-pinned internal manifests.
- No value may be taken from a client request, an environment variable read at contract level, or
  from model output.

Consumer rules:

- A consumer may treat the snapshot as an accurate reference set only after the trusted factory has
  verified digests; the contract alone provides no such guarantee.
- A consumer must not attempt to derive URLs, hosts, or filesystem locations from `artifact_id` or
  `revision`.
- Traces, logs, and audit records should carry `snapshot_id` and, where useful,
  `integrity.digest`, rather than a copy of the full snapshot content.

## Sensitive-data restrictions

The models are closed, so any of the following field names, and any other unknown field, fails
validation at every level:

```
api_key access_token token secret password credentials endpoint_url provider_response
raw_config environment_variables docker_registry kubernetes_namespace cloud_region
database_url filesystem_path container_digest docker_image image_tag registry_url
provider provider_object endpoint base_url deployment_name raw_model_config run_id
```

No secret, credential, raw configuration value, environment variable, URL, filesystem location, or
provider response belongs in this contract.

## Error semantics

Validation failures raise Pydantic `ValidationError`. Domain and API error mapping are deferred; no
error envelope and no HTTP error handling exist in this task.

## Compatibility

RuntimeSnapshot 1.0.0 is closed.

- PATCH changes must not alter accepted or serialized payloads.
- Adding, removing, or renaming a field requires a new major schema version.
- Changing validation, canonicalization, digest semantics, trust meaning, or field semantics
  requires a new major schema version.
- Version 1.0.0 becomes immutable after approval.

## Valid JSON example

```json
{
  "schema_version": "1.0.0",
  "snapshot_id": "77777777-7777-4777-8777-777777777777",
  "captured_at": "2026-01-01T08:30:00Z",
  "content": {
    "application_version": "1.4.2",
    "source_revision": "0123456789abcdef0123456789abcdef01234567",
    "build_artifact": {
      "artifact_id": "build.ai-assistant",
      "revision": "2026.01.01",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "config_bundle": {
      "artifact_id": "config.default",
      "revision": "7",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "prompt_bundle": {
      "artifact_id": "prompts.chat",
      "revision": "12",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "model_policy": {
      "artifact_id": "policy.model-routing",
      "revision": "3",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "model_artifacts": [
      {
        "artifact_id": "model.primary",
        "revision": "2026-01",
        "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    ],
    "structured_output_backend": {
      "artifact_id": "structured-output.default",
      "revision": "2",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "retrieval_profile": {
      "artifact_id": "retrieval.default",
      "revision": "5",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "embedding_artifact": {
      "artifact_id": "embedding.primary",
      "revision": "4",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "reranker_artifact": {
      "artifact_id": "reranker.primary",
      "revision": "1",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "index_snapshot": {
      "artifact_id": "index.knowledge",
      "revision": "2026-01-01",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "semantic_catalog": {
      "artifact_id": "catalog.semantic",
      "revision": "9",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "rule_bundle": {
      "artifact_id": "rules.core",
      "revision": "11",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "security_policy": {
      "artifact_id": "policy.security",
      "revision": "6",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "telemetry_schema": {
      "artifact_id": "telemetry.schema",
      "revision": "2",
      "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    "feature_flags": [
      { "name": "retrieval.rerank", "enabled": true },
      { "name": "structured-output.strict", "enabled": false }
    ]
  },
  "integrity": {
    "canonicalization": "rfc8785",
    "digest": "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
  }
}
```

## Representative invalid examples

| Invalid input | Reason |
| --- | --- |
| `"schema_version": "1.1.0"` | only the exact literal `1.0.0` is accepted |
| `"snapshot_id": "11111111-1111-1111-8111-111111111111"` | not a version 4 UUID |
| `"captured_at": "2026-01-01T12:00:00"` | timezone-naive instant |
| `"source_revision": "0123456"` | not a full 40 or 64 character revision |
| `"source_revision": "0123456789ABCDEF..."` | uppercase hexadecimal |
| `"digest": "0123...cdef"` | missing `sha256:` prefix |
| `"digest": "md5:..."` | unsupported algorithm |
| `"digest": "sha256:0123ABCD..."` | uppercase hexadecimal |
| `"artifact_id": " build "` | leading or trailing whitespace is rejected, not trimmed |
| `"artifact_id": ""` | empty value |
| `"model_artifacts": []` | at least one model artifact is required |
| duplicate `artifact_id` in `model_artifacts` | model artifacts must be unique |
| duplicate `name` in `feature_flags` | feature flag names must be unique |
| `"feature_flags": null` | explicit null is rejected; omit the field instead |
| `"name": "Feature Flag"` | flag names must match the canonical pattern |
| `"canonicalization": "jcs"` | only `rfc8785` is accepted |
| `"api_key": "..."` | unknown and forbidden field |
| `"registry_url": "..."` | infrastructure detail does not belong in the AI Core |
| `"run_id": "..."` | run binding is not part of this contract |

## Non-goals

- Loading configuration or reading environment variables.
- Executing Git, Docker, OCI, Kubernetes, cloud, or CI/CD commands.
- Resolving, downloading, or validating the existence of artifacts.
- Initializing models, providers, or observability SDKs.
- Persisting snapshots to a database or storage backend.
- Capturing a snapshot from a live process.
- Computing or verifying any hash.
- Binding a snapshot to a specific run.

## Deferred RuntimeSnapshotFactory responsibility

The trusted RuntimeSnapshotFactory is owned by **CP-004 RuntimeSnapshotFactory**. It was not delivered
in the Walking Skeleton task and does not exist today. When implemented, it will:

- collect the effective configuration references from trusted internal sources;
- perform RFC 8785 canonicalization of `content.model_dump(mode="json")`;
- compute the SHA-256 content digest and populate `integrity`;
- verify digests of referenced artifacts through registry resolution;
- fail closed when an artifact is missing, unreadable, or digest-mismatched;
- bind snapshots to runs through the future RunContext or ChatRun contract.
