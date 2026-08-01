"""Runtime configuration snapshot contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
RUNTIME_SNAPSHOT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
RUNTIME_SNAPSHOT_SCHEMA_ID = "urn:ai-assistant:contracts:runtime-snapshot:1.0.0"

# Digests and revisions are compared literally by downstream trust checks, so an
# uppercase or padded value is a rejection rather than a silently repaired value.
_CONTENT_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
_CONTENT_DIGEST_LENGTH = 71
_SOURCE_REVISION_PATTERN = r"^([0-9a-f]{40}|[0-9a-f]{64})$"
_FEATURE_FLAG_NAME_PATTERN = r"^[a-z][a-z0-9._:-]*$"

_ContentDigest = Annotated[
    str,
    Field(
        min_length=_CONTENT_DIGEST_LENGTH,
        max_length=_CONTENT_DIGEST_LENGTH,
        pattern=_CONTENT_DIGEST_PATTERN,
    ),
]
_SourceRevision = Annotated[
    str,
    Field(min_length=40, max_length=64, pattern=_SOURCE_REVISION_PATTERN),
]
_FeatureFlagName = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=_FEATURE_FLAG_NAME_PATTERN),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_identifier_text(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


_IdentifierText = AfterValidator(_require_identifier_text)
_ArtifactId = Annotated[str, Field(min_length=1, max_length=256), _IdentifierText]
_ArtifactRevision = Annotated[str, Field(min_length=1, max_length=128), _IdentifierText]


class RuntimeArtifactRef(ContractModel):
    """Immutable internal manifest reference to one effective configuration artifact."""

    artifact_id: _ArtifactId
    revision: _ArtifactRevision
    digest: _ContentDigest


class RuntimeFeatureFlag(ContractModel):
    """Effective boolean feature flag recorded for a run."""

    name: _FeatureFlagName
    enabled: bool


def _require_unique_artifact_ids(
    value: tuple[RuntimeArtifactRef, ...],
) -> tuple[RuntimeArtifactRef, ...]:
    identifiers = [artifact.artifact_id for artifact in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("model artifact identifiers must be unique")
    return value


def _require_unique_flag_names(
    value: tuple[RuntimeFeatureFlag, ...],
) -> tuple[RuntimeFeatureFlag, ...]:
    names = [flag.name for flag in value]
    if len(set(names)) != len(names):
        raise ValueError("feature flag names must be unique")
    return value


_ModelArtifacts = Annotated[
    tuple[RuntimeArtifactRef, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_artifact_ids),
]
_FeatureFlags = Annotated[
    tuple[RuntimeFeatureFlag, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_flag_names),
]


class RuntimeSnapshotContent(ContractModel):
    """Effective application and AI configuration references used by a run."""

    application_version: SchemaVersion
    source_revision: _SourceRevision
    build_artifact: RuntimeArtifactRef
    config_bundle: RuntimeArtifactRef
    prompt_bundle: RuntimeArtifactRef
    model_policy: RuntimeArtifactRef
    model_artifacts: _ModelArtifacts
    structured_output_backend: RuntimeArtifactRef
    retrieval_profile: RuntimeArtifactRef
    embedding_artifact: RuntimeArtifactRef
    reranker_artifact: RuntimeArtifactRef
    index_snapshot: RuntimeArtifactRef
    semantic_catalog: RuntimeArtifactRef
    rule_bundle: RuntimeArtifactRef
    security_policy: RuntimeArtifactRef
    telemetry_schema: RuntimeArtifactRef
    feature_flags: _FeatureFlags = ()


class RuntimeSnapshotIntegrity(ContractModel):
    """Integrity metadata describing how the content digest was produced."""

    # The digest is SHA-256 over the RFC 8785 canonical JSON form of
    # snapshot.content.model_dump(mode="json"). It excludes schema_version,
    # snapshot_id, captured_at, and integrity. This contract validates the format
    # only; computation and verification belong to the trusted factory.
    canonicalization: Literal["rfc8785"]
    digest: _ContentDigest


class RuntimeSnapshot(ContractModel):
    """Immutable record of the effective configuration references of a run."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": RUNTIME_SNAPSHOT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = RUNTIME_SNAPSHOT_SCHEMA_VERSION
    snapshot_id: _Uuid4
    captured_at: UtcDateTime
    content: RuntimeSnapshotContent
    integrity: RuntimeSnapshotIntegrity
