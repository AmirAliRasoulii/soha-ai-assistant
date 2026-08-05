"""Configuration artifact, release, and model-pool contracts, schema version 1.0.0.

Authority: ADR-CP-004 (configuration artifact taxonomy, ownership, precedence),
ADR-CP-005 (configuration versioning, activation, rollback), ADR-CP-008 (model
gateway, provider pool, credential boundary), and CP-000D (configuration
catalog).

CP-001 owns the typed shapes only. The artifact registry, the active pointer,
atomic activation, and rollback storage are CP-003 obligations; the
configuration application service, provider pool operations, and probe
execution are CP-008 and CP-009 obligations; `RuntimeSnapshotFactory`, caching,
and last-known-good behavior are CP-004 obligations. None of them are
implemented here.

Credential boundary: no contract in this module can carry secret material. Only
an opaque `credential_ref` and its rotation-relevant metadata exist, so a
release, a manifest, an audit record, or a runtime snapshot built from these
shapes cannot leak a key even if a caller tries.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    ContentDigest,
    OpaqueId,
    RevisionLabel,
    Uuid4,
    unique_by,
)

CONFIGURATION_RELEASE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
CONFIGURATION_RELEASE_SCHEMA_ID = "urn:ai-assistant:contracts:configuration-release:1.0.0"
MODEL_POOL_POLICY_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
MODEL_POOL_POLICY_SCHEMA_ID = "urn:ai-assistant:contracts:model-pool-policy:1.0.0"

# ADR-CP-005 fixes the release lifecycle states. `active` is a property of the
# release record; which release is active is a separate pointer owned by CP-003.
ReleaseStatus = Literal[
    "draft",
    "validated",
    "rejected",
    "active",
    "superseded",
    "rolled_back",
    "archived",
]
ActivationKind = Literal["activation", "rollback"]

# A release manifest is a complete, closed list of effective artifacts. The
# ceiling is well above the CP-000D catalog size and exists so that no consumer
# of a manifest is ever unbounded.
MAX_MANIFEST_ENTRIES: Final = 128
# A logical pool is a small ordered preference list, not a provider inventory.
MAX_POOL_DEPLOYMENTS: Final = 16
MAX_POLICY_POOLS: Final = 32


class ArtifactNamespaceRef(ContractModel):
    """Namespace of one configuration artifact family.

    DEF-116 recorded that unnamespaced artifact identifiers are ambiguous and
    collision-prone. Every Control Plane artifact reference therefore carries an
    explicit namespace, so `security_policy` as a global configuration artifact
    can never collide with a per-source visibility policy.
    """

    namespace: CanonicalCode


class ConfigurationArtifactRef(ContractModel):
    """Namespaced identity of one configuration artifact, without a revision."""

    namespace: CanonicalCode
    artifact_id: OpaqueId


class ConfigurationArtifactRevisionRef(ContractModel):
    """Immutable reference to one revision of one configuration artifact.

    The digest is what downstream trust checks compare. This contract validates
    its syntax only: resolving, fetching, or verifying content is CP-003 and
    CP-004 work.
    """

    namespace: CanonicalCode
    artifact_id: OpaqueId
    revision: RevisionLabel
    digest: ContentDigest

    @property
    def artifact_ref(self) -> ConfigurationArtifactRef:
        return ConfigurationArtifactRef(namespace=self.namespace, artifact_id=self.artifact_id)

    @property
    def qualified_id(self) -> str:
        """Namespace-qualified artifact identity, for uniqueness checks only."""
        return f"{self.namespace}/{self.artifact_id}"


class ReleaseManifestEntry(ContractModel):
    """One artifact revision made effective by a release, with its owner.

    Ownership is recorded because ADR-CP-004 makes precedence and change
    authority explicit per artifact family: a frontend-owned, provider-neutral
    artifact and a platform-owned artifact are never interchangeable.
    """

    artifact: ConfigurationArtifactRevisionRef
    owner_role: CanonicalCode
    # Whether this artifact family is changeable through the Control Plane by an
    # operator surface. Provider-neutral configuration only; never a credential.
    operator_changeable: bool


def _require_ordered_release_times(
    created_at: UtcDateTime, candidate: UtcDateTime | None, label: str
) -> None:
    if candidate is not None and candidate < created_at:
        raise ValueError(f"{label} must not precede created_at")


_ManifestEntries = Annotated[
    tuple[ReleaseManifestEntry, ...],
    Field(min_length=1, max_length=MAX_MANIFEST_ENTRIES),
]


def _require_unique_manifest_artifacts(
    value: tuple[ReleaseManifestEntry, ...],
) -> tuple[ReleaseManifestEntry, ...]:
    keys = [entry.artifact.qualified_id for entry in value]
    if len(set(keys)) != len(keys):
        raise ValueError("a release manifest must name each artifact at most once")
    return value


class ConfigurationRelease(ContractModel):
    """Immutable, complete set of artifact revisions that may be made effective.

    A release is a candidate, not a state of the system: it never says that it
    is the one in use. The active pointer, atomic activation, and rollback
    storage are CP-003 obligations, and this contract deliberately cannot
    express them.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": CONFIGURATION_RELEASE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = CONFIGURATION_RELEASE_SCHEMA_VERSION
    release_id: Uuid4
    # Absent means a platform-wide release rather than an organization release.
    # Absent never means "all organizations may edit it".
    organization_id: Uuid4 | None = None
    release_label: RevisionLabel
    status: ReleaseStatus
    manifest: Annotated[_ManifestEntries, AfterValidator(_require_unique_manifest_artifacts)]
    # Digest over the canonical form of the manifest, so a release cannot be
    # silently re-pointed at different artifact revisions.
    manifest_digest: ContentDigest
    created_at: UtcDateTime
    validated_at: UtcDateTime | None = None
    # The release this one supersedes, used for rollback lineage.
    previous_release_id: Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_release(self) -> Self:
        _require_ordered_release_times(self.created_at, self.validated_at, "validated_at")
        if self.previous_release_id == self.release_id:
            raise ValueError("a release must not supersede itself")
        if self.status in ("validated", "active") and self.validated_at is None:
            raise ValueError(f"status {self.status!r} requires validated_at")
        if self.status == "draft" and self.validated_at is not None:
            raise ValueError("a draft release must not carry validated_at")
        return self


class ActiveConfigurationReleaseRef(ContractModel):
    """Reference to the release that a scope currently treats as effective.

    This is a read reference produced by CP-003. Nothing here performs, orders,
    or guarantees an activation.
    """

    organization_id: Uuid4 | None = None
    release_id: Uuid4
    release_label: RevisionLabel
    manifest_digest: ContentDigest
    activated_at: UtcDateTime
    activation_id: Uuid4


class ConfigurationActivationRef(ContractModel):
    """Reference to one activation or rollback event of a release.

    A rollback is recorded as its own directed event with an explicit target,
    never as an in-place edit of a previous activation.
    """

    activation_id: Uuid4
    kind: ActivationKind
    organization_id: Uuid4 | None = None
    target_release_id: Uuid4
    previous_release_id: Uuid4 | None = None
    occurred_at: UtcDateTime
    actor_principal_id: Uuid4 | None = None
    reason_code: CanonicalCode

    @model_validator(mode="after")
    def _require_distinct_releases(self) -> Self:
        if self.previous_release_id == self.target_release_id:
            raise ValueError("target and previous release must differ")
        if self.kind == "rollback" and self.previous_release_id is None:
            raise ValueError("a rollback requires the release it moves away from")
        return self


class CredentialRef(ContractModel):
    """Opaque reference to a credential held outside the AI boundary.

    This is the only credential representation any Control Plane contract may
    use. It has no secret, key, token, or header field, and the reference is
    never resolved, decoded, or logged by a contract. Resolution belongs to a
    CP-012 adapter against the deployment's secret store.
    """

    credential_ref: OpaqueId
    # Controlled class of the credential, for example an api-key or a workload
    # identity. It describes handling, never the value.
    credential_class: CanonicalCode
    rotated_at: UtcDateTime | None = None


class ModelDeploymentRef(ContractModel):
    """Provider-neutral reference to one concrete model deployment.

    The provider, model, and deployment identifiers are opaque strings owned by
    the Control Plane. No provider SDK type, endpoint object, or vendor client
    appears here, and no field names a specific gateway implementation.
    """

    deployment_ref: OpaqueId
    provider_ref: OpaqueId
    model_ref: OpaqueId
    credential: CredentialRef
    # Deployments in the same compatibility class may substitute for each other
    # under a fallback rule. The class is a controlled code, never a provider
    # name and never inferred from `provider_ref`.
    compatibility_class: CanonicalCode
    # Lower values are preferred first. Ordering is data, not behavior: pool
    # selection and fallback execution are CP-008 and AI-008 concerns.
    preference_rank: Annotated[int, Field(ge=0, le=64)]
    request_timeout_ms: Annotated[int, Field(ge=1, le=600_000)]


class ProbeEvidenceRef(ContractModel):
    """Reference to the recorded evidence of one deployment qualification probe.

    Only the reference and its integrity digest are carried. Probe execution,
    scheduling, and interpretation are CP-008 obligations, so this contract can
    never be mistaken for a live health signal.
    """

    probe_id: Uuid4
    deployment_ref: OpaqueId
    probe_kind: CanonicalCode
    evaluated_at: UtcDateTime
    evidence_digest: ContentDigest


class LogicalModelPoolRef(ContractModel):
    """Reference to one logical, provider-neutral model pool."""

    pool_code: CanonicalCode
    catalog_revision: RevisionLabel


_PoolDeployments = Annotated[
    tuple[ModelDeploymentRef, ...],
    Field(min_length=1, max_length=MAX_POOL_DEPLOYMENTS),
    AfterValidator(unique_by("deployment_ref", "deployment references")),
]
_ProbeEvidence = Annotated[
    tuple[ProbeEvidenceRef, ...],
    Field(max_length=MAX_POOL_DEPLOYMENTS),
    AfterValidator(unique_by("probe_id", "probe identifiers")),
]


class LogicalModelPool(ContractModel):
    """One logical pool: an ordered, provider-neutral preference list.

    Callers address the pool, never a provider. A pool whose deployments do not
    share one compatibility class could silently change answer semantics on
    fallback, so it is rejected here rather than at runtime.
    """

    pool: LogicalModelPoolRef
    compatibility_class: CanonicalCode
    deployments: _PoolDeployments
    probe_evidence: _ProbeEvidence = ()

    @model_validator(mode="after")
    def _require_consistent_pool(self) -> Self:
        known_deployments = {deployment.deployment_ref for deployment in self.deployments}
        for deployment in self.deployments:
            if deployment.compatibility_class != self.compatibility_class:
                raise ValueError("every deployment must share the pool compatibility class")
        ranks = [deployment.preference_rank for deployment in self.deployments]
        if len(set(ranks)) != len(ranks):
            raise ValueError("deployment preference ranks must be unique")
        for probe in self.probe_evidence:
            if probe.deployment_ref not in known_deployments:
                raise ValueError("probe evidence must reference a deployment of this pool")
        return self


_PolicyPools = Annotated[
    tuple[LogicalModelPool, ...],
    Field(min_length=1, max_length=MAX_POLICY_POOLS),
]


def _require_unique_pool_codes(
    value: tuple[LogicalModelPool, ...],
) -> tuple[LogicalModelPool, ...]:
    codes = [pool.pool.pool_code for pool in value]
    if len(set(codes)) != len(codes):
        raise ValueError("logical pool codes must be unique")
    return value


class ModelPoolPolicy(ContractModel):
    """Provider-neutral model policy artifact content: the logical pools and the
    revision they were published as.

    This is configuration data addressed by a `ConfigurationRelease` manifest
    entry. It performs no selection, no probing, and no invocation.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": MODEL_POOL_POLICY_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = MODEL_POOL_POLICY_SCHEMA_VERSION
    policy_revision: RevisionLabel
    published_at: UtcDateTime
    pools: Annotated[_PolicyPools, AfterValidator(_require_unique_pool_codes)]
