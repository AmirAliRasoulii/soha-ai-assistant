"""Source Registry contract shapes, schema version 1.0.0.

Authority: ADR-CP-007 (source registry and content lifecycle), CP-000B (source
lifecycle matrix), ADR-CP-003 and CP-000C (index isolation), DEF-103 (source
authority binding), DEF-104 (source temporal derivation), DEF-119 (source
metadata class split), and DEF-121 (SourceRelationship).

CP-001 owns the typed shapes and their local invariants. Registry behavior,
review workflow, and activation are CP-005 obligations; ingestion, chunking,
embedding, index activation, and revoke propagation are CP-006 obligations.
Nothing here persists, resolves, fetches, or activates anything.

Four architecture rules are enforced structurally:

1. Metadata is four distinct resources, not one: citation-safe published,
   management, lifecycle-audit, and raw content are separate models so a single
   "view source metadata" permission cannot leak management or audit data to an
   ordinary reader or a Guest (DEF-119).
2. Upload time is never publication time: the uploaded instant lives in
   management metadata and the published instant lives in trusted temporal
   metadata, so the two cannot be conflated (DEF-104).
3. Contributor-proposed temporal metadata is untrusted: it has its own model and
   can never be mistaken for the trusted recorded values.
4. A revision is immutable and supersession is a new record: an active revision
   carries no supersession fields, and a superseded revision must name the
   revision that replaced it.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    ContentDigest,
    DisplayName,
    ExternalLocator,
    IdentifierText,
    OpaqueId,
    RevisionLabel,
    Uuid4,
)
from ai_assistant.contracts.organization import OrganizationalNodeRef

KNOWLEDGE_SOURCE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
KNOWLEDGE_SOURCE_SCHEMA_ID = "urn:ai-assistant:contracts:knowledge-source:1.0.0"
SOURCE_REVISION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SOURCE_REVISION_SCHEMA_ID = "urn:ai-assistant:contracts:source-revision:1.0.0"
SOURCE_RELATIONSHIP_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SOURCE_RELATIONSHIP_SCHEMA_ID = "urn:ai-assistant:contracts:source-relationship:1.0.0"

# ADR-CP-007 fixes exactly these two source types for this baseline.
SourceType = Literal["uploaded_document", "official_url"]
# Source-level lifecycle: the stable record itself.
SourceStatus = Literal["active", "archived", "revoked"]
# Revision-level lifecycle from ADR-CP-007. `active` is reachable only through
# approval, and `superseded` is always the result of a later activation.
RevisionStatus = Literal[
    "draft",
    "approved",
    "rejected",
    "active",
    "superseded",
    "revoked",
    "archived",
]
# DEF-121: exactly the two relationship kinds with an accepted canonical
# decision. `amends` and `partially_supersedes` are deliberately absent; they
# remain deferred and must never be inferred, so this closed union rejects them.
SourceRelationshipType = Literal["supersedes", "supplements"]

MAX_REVISION_NUMBER: Final = 10_000
_MEDIA_TYPE_PATTERN = r"^[a-z0-9]+/[a-z0-9][a-z0-9.+-]*$"
_MediaType = Annotated[
    str,
    Field(min_length=3, max_length=128, pattern=_MEDIA_TYPE_PATTERN),
]
_StableKey = Annotated[str, Field(min_length=1, max_length=256), IdentifierText]


class SourceAuthorityRef(ContractModel):
    """Trusted authority binding of one source revision (DEF-103).

    The authority class, the issuer, and the assignment policy are separate
    controlled references read from a versioned catalog. An authority is never
    derived from a display name, a filename, a domain, or contributor-supplied
    text.
    """

    authority_class_ref: CanonicalCode
    issuer_ref: OpaqueId
    authority_assignment_policy_ref: CanonicalCode
    catalog_revision: RevisionLabel


class VisibilityPolicyRevisionRef(ContractModel):
    """Reference to one revision of a per-source visibility policy definition.

    This is the per-source visibility policy, never the global `security_policy`
    configuration artifact; DEF-116 recorded that ambiguity explicitly.
    """

    visibility_policy_id: OpaqueId
    policy_revision: RevisionLabel
    policy_digest: ContentDigest


class ProposedSourceTemporalMetadata(ContractModel):
    """Temporal values proposed by a contributor or client.

    Untrusted by construction: nothing downstream may read these fields as
    effective business time. Approval and trusted recording are CP-005 work.
    """

    proposed_effective_from: UtcDateTime | None = None
    proposed_valid_until: UtcDateTime | None = None
    proposed_published_at: UtcDateTime | None = None
    proposed_by_principal_id: Uuid4
    proposed_at: UtcDateTime

    @model_validator(mode="after")
    def _require_ordered_proposal(self) -> Self:
        start = self.proposed_effective_from
        end = self.proposed_valid_until
        if start is not None and end is not None and end <= start:
            raise ValueError("proposed_valid_until must be strictly later than the start")
        return self


class TrustedSourceTemporalMetadata(ContractModel):
    """Trusted business time of one source revision.

    `valid_until` is nullable and means open-ended validity, never expiry.
    `published_at` is a business publication fact and is unrelated to the
    instant a file was uploaded, which lives in management metadata only.
    """

    effective_from: UtcDateTime
    valid_until: UtcDateTime | None = None
    published_at: UtcDateTime | None = None
    recorded_by_principal_id: Uuid4
    recorded_at: UtcDateTime

    @model_validator(mode="after")
    def _require_ordered_window(self) -> Self:
        if self.valid_until is not None and self.valid_until <= self.effective_from:
            raise ValueError("valid_until must be strictly later than effective_from")
        return self


class CitationSafePublishedSourceMetadata(ContractModel):
    """The minimum published facts needed to cite and explain a source.

    This is the only metadata class a reader or a Guest may ever receive. It
    carries no owner, no review state, no audit reason, no internal status, and
    no raw locator for uploaded content.
    """

    title: DisplayName
    source_type: SourceType
    authority: SourceAuthorityRef
    temporal: TrustedSourceTemporalMetadata
    publisher_display_name: DisplayName | None = None
    # Published, citable location of an official URL source. An uploaded
    # document has no public locator: its location is raw content metadata.
    public_locator: ExternalLocator | None = None

    @model_validator(mode="after")
    def _require_locator_matches_type(self) -> Self:
        if self.source_type == "official_url":
            if self.public_locator is None:
                raise ValueError("an official_url source requires a public locator")
        elif self.public_locator is not None:
            raise ValueError("an uploaded_document must not publish a locator")
        return self


class ManagementSourceMetadata(ContractModel):
    """Administrative metadata for operators of one source revision.

    Ownership is recorded here for management and accountability. Ownership
    grants no read access to anyone, and this contract states no permission.
    """

    owner_node: OrganizationalNodeRef
    owner_principal_id: Uuid4
    # The instant content was received by the platform. It is never business
    # publication time.
    uploaded_at: UtcDateTime
    review_state: CanonicalCode
    submitted_by_principal_id: Uuid4 | None = None
    reviewed_by_principal_id: Uuid4 | None = None


class LifecycleAuditMetadata(ContractModel):
    """Audit-only record of the last lifecycle transition of a revision.

    Reason text is never carried inline: only a controlled reason code and an
    opaque reference to the audit record.
    """

    reason_code: CanonicalCode
    transitioned_at: UtcDateTime
    transitioned_by_principal_id: Uuid4 | None = None
    audit_event_id: Uuid4 | None = None


class RawSourceContentRef(ContractModel):
    """Reference to the stored raw content of one revision.

    The reference is opaque and is never resolved or fetched by a contract. No
    object-storage, bucket, or provider concept appears here.
    """

    content_ref: OpaqueId
    content_digest: ContentDigest
    media_type: _MediaType
    byte_size: Annotated[int, Field(ge=1, le=5_368_709_120)]
    # Operator-supplied original locator. Untrusted, opaque, never fetched, and
    # never exposed as citation metadata.
    raw_locator: ExternalLocator | None = None


class MandatoryIsolationMetadata(ContractModel):
    """The mandatory, non-bypassable isolation subset of index metadata.

    ADR-CP-003 requires every retrieval to be pre-filtered by trusted isolation
    metadata. This is deliberately the minimum subset with a distinct name: it
    is not the complete chunk and index metadata contract, which remains a
    CP-006 obligation (DEF-119).
    """

    organization_id: Uuid4
    owner_node: OrganizationalNodeRef
    visibility_policy: VisibilityPolicyRevisionRef
    source_id: Uuid4
    revision_id: Uuid4
    index_namespace: CanonicalCode

    @model_validator(mode="after")
    def _require_same_organization(self) -> Self:
        if self.owner_node.organization_id != self.organization_id:
            raise ValueError("owner node must belong to the isolation organization")
        return self


class KnowledgeSource(ContractModel):
    """The stable registry record of one knowledge source.

    The source is the durable identity; its content lives in revisions. At most
    one revision can be active, which is expressible only as a single optional
    pointer, and a non-active source can carry no active revision at all.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": KNOWLEDGE_SOURCE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = KNOWLEDGE_SOURCE_SCHEMA_VERSION
    source_id: Uuid4
    organization_id: Uuid4
    owner_node: OrganizationalNodeRef
    source_type: SourceType
    # Operator-stable correlation key. Opaque, never parsed, never authorization.
    stable_key: _StableKey
    status: SourceStatus
    created_at: UtcDateTime
    # The single active revision, if the source currently has one.
    active_revision_id: Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_source(self) -> Self:
        if self.owner_node.organization_id != self.organization_id:
            raise ValueError("owner node must belong to the source organization")
        if self.status != "active" and self.active_revision_id is not None:
            raise ValueError(f"a {self.status} source must not carry an active revision")
        return self


class SourceRevision(ContractModel):
    """One immutable revision of one knowledge source.

    A revision is never edited in place: a lifecycle change is a new record, and
    supersession must name the replacing revision. The four metadata classes are
    carried as separate, separately permissionable values.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": SOURCE_REVISION_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = SOURCE_REVISION_SCHEMA_VERSION
    revision_id: Uuid4
    source_id: Uuid4
    organization_id: Uuid4
    revision_number: Annotated[int, Field(ge=1, le=MAX_REVISION_NUMBER)]
    source_type: SourceType
    status: RevisionStatus
    created_at: UtcDateTime
    citation_safe: CitationSafePublishedSourceMetadata
    management: ManagementSourceMetadata
    lifecycle_audit: LifecycleAuditMetadata
    isolation: MandatoryIsolationMetadata
    raw_content: RawSourceContentRef | None = None
    proposed_temporal: ProposedSourceTemporalMetadata | None = None
    superseded_by_revision_id: Uuid4 | None = None
    superseded_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_consistent_identity(self) -> Self:
        if self.isolation.organization_id != self.organization_id:
            raise ValueError("isolation metadata must match the revision organization")
        if self.isolation.source_id != self.source_id:
            raise ValueError("isolation metadata must match the revision source")
        if self.isolation.revision_id != self.revision_id:
            raise ValueError("isolation metadata must match this revision")
        if self.management.owner_node.organization_id != self.organization_id:
            raise ValueError("owner node must belong to the revision organization")
        if self.citation_safe.source_type != self.source_type:
            raise ValueError("citation-safe metadata must declare the same source type")
        return self

    @model_validator(mode="after")
    def _require_consistent_content(self) -> Self:
        if self.source_type == "uploaded_document" and self.raw_content is None:
            raise ValueError("an uploaded_document revision requires stored raw content")
        return self

    @model_validator(mode="after")
    def _require_consistent_supersession(self) -> Self:
        has_successor = self.superseded_by_revision_id is not None
        if self.status == "superseded":
            if not has_successor or self.superseded_at is None:
                raise ValueError(
                    "a superseded revision requires superseded_by_revision_id and superseded_at"
                )
        elif has_successor or self.superseded_at is not None:
            raise ValueError(f"a {self.status} revision must not carry supersession fields")
        if self.superseded_by_revision_id == self.revision_id:
            raise ValueError("a revision must not supersede itself")
        if self.superseded_at is not None and self.superseded_at < self.created_at:
            raise ValueError("superseded_at must not precede created_at")
        return self


class SupersedesLink(ContractModel):
    """Revision replacement inside exactly one knowledge source."""

    source_id: Uuid4
    superseding_revision_id: Uuid4
    superseded_revision_id: Uuid4

    @model_validator(mode="after")
    def _require_distinct_revisions(self) -> Self:
        if self.superseding_revision_id == self.superseded_revision_id:
            raise ValueError("a revision must not supersede itself")
        return self


class SupplementsLink(ContractModel):
    """Relationship between two separate knowledge sources."""

    from_source_id: Uuid4
    to_source_id: Uuid4

    @model_validator(mode="after")
    def _require_distinct_sources(self) -> Self:
        if self.from_source_id == self.to_source_id:
            raise ValueError("a source must not supplement itself")
        return self


class SourceRelationship(ContractModel):
    """A declared relationship between source content (DEF-121).

    Supersession is always within one source and between two of its revisions.
    Supplementation is always across two distinct sources. The absence of a
    relationship record means the sources are independent; it is never inferred.
    Partial amendment stays deferred and is unrepresentable here.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": SOURCE_RELATIONSHIP_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = SOURCE_RELATIONSHIP_SCHEMA_VERSION
    relationship_id: Uuid4
    organization_id: Uuid4
    relationship_type: SourceRelationshipType
    supersedes: SupersedesLink | None = None
    supplements: SupplementsLink | None = None
    declared_at: UtcDateTime
    declared_by_principal_id: Uuid4 | None = None
    reason_code: CanonicalCode

    @model_validator(mode="after")
    def _require_exactly_one_link(self) -> Self:
        if self.relationship_type == "supersedes":
            if self.supersedes is None:
                raise ValueError("a supersedes relationship requires the supersedes link")
            if self.supplements is not None:
                raise ValueError("a supersedes relationship must not carry a supplements link")
        else:
            if self.supplements is None:
                raise ValueError("a supplements relationship requires the supplements link")
            if self.supersedes is not None:
                raise ValueError("a supplements relationship must not carry a supersedes link")
        return self
