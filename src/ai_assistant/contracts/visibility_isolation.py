"""Visibility policy and index isolation contracts, schema version 1.0.0.

Authority: `ADR-CP-002` rules `V-1`..`V-7` and `C-1`..`C-3` for visibility
policy definitions, and `ADR-CP-003` rules `T-1`..`T-7` and `P-1`..`P-5` for
physical isolation profiles. `ADR-CP-007` and `CP-000B` pin the per-source
binding to an exact immutable policy revision.

CP-001 owns typed shapes and local invariants only. Policy evaluation, scope
expansion, physical routing, promotion decisions, and audit emission belong to
CP-002, CP-003, CP-006, and CP-009 and are deliberately unrepresentable here.

Five architecture rules are enforced structurally rather than by comment:

1. The primitive vocabulary is closed (`V-1`, `V-3`): a predicate kind is a
   `Literal` over the seven Layer 1 primitives, so no administrator can
   introduce a new primitive through data.
2. Composition is declarative (`C-1`, `C-3`): a definition is an OR of clauses
   and a clause is an AND of predicates. There is no expression field, no
   script field, and no administrator-authored deny field at all.
3. Hard platform denies, organization isolation, revocation, disabled status,
   and classification ceilings are evaluated outside allow clauses (`C-2`), so
   this contract cannot express or weaken them.
4. A physical tier is not a permission (`T-6`) and is never derived from a
   request (`T-4`): `IndexIsolationProfile` carries no permission, role, group,
   membership, or request-supplied field.
5. A topology change is a new revision, not an edit (`P-1`): a profile that
   records a previous tier must also record a different previous revision.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    ContentDigest,
    DisplayName,
    OpaqueId,
    RevisionLabel,
    Uuid4,
    unique_by,
)
from ai_assistant.contracts.organization import OrganizationalNodeRef
from ai_assistant.contracts.source_registry import VisibilityPolicyRevisionRef

VISIBILITY_POLICY_DEFINITION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
VISIBILITY_POLICY_DEFINITION_SCHEMA_ID = (
    "urn:ai-assistant:contracts:visibility-policy-definition:1.0.0"
)
INDEX_ISOLATION_PROFILE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
INDEX_ISOLATION_PROFILE_SCHEMA_ID = "urn:ai-assistant:contracts:index-isolation-profile:1.0.0"

# Layer 1 of the two-layer model in `ADR-CP-002`. The catalog of definitions
# grows dynamically (`V-2`), but this vocabulary does not: adding a primitive
# requires new Core code and a new contract version, never new data.
VisibilityPredicateKind = Literal[
    "organization_member",
    "exact_node_member",
    "subtree_member",
    "scoped_role",
    "trusted_group",
    "explicit_principal",
    "classification_condition",
]

# A definition is validated and approved before activation and is immutable
# afterwards (`V-1`). `retired` keeps a superseded revision referenceable for
# lineage without making it bindable; enforcing that is CP-006 lifecycle work.
VisibilityPolicyStatus = Literal["draft", "approved", "active", "retired"]

# The four tiers of `ADR-CP-003`, in ascending order of physical isolation. The
# order is meaningful for promotion lineage only; it carries no access meaning.
PhysicalIsolationTier = Literal[
    "shared_logical_partition",
    "dedicated_shard",
    "dedicated_collection",
    "dedicated_deployment",
]

# Ascending physical isolation order, used only for promotion lineage. It is an
# immutable tuple because a contract module holds no mutable process-global state.
_TIER_ORDER: Final[tuple[PhysicalIsolationTier, ...]] = (
    "shared_logical_partition",
    "dedicated_shard",
    "dedicated_collection",
    "dedicated_deployment",
)

# Hard platform bounds administrators cannot weaken (`V-1`). A definition that
# needs more breadth is a policy design problem, not a larger array.
MAX_ALLOW_CLAUSES: Final = 16
MAX_CLAUSE_PREDICATES: Final = 8
MAX_PREDICATE_NODES: Final = 32
MAX_PREDICATE_PRINCIPALS: Final = 32


class VisibilityPredicate(ContractModel):
    """One Layer 1 primitive occurrence inside one allow clause.

    Exactly one operand family is populated, chosen by `kind`. The pairing is
    validated so that a predicate can never be half-specified or carry operands
    the platform would silently ignore.
    """

    kind: VisibilityPredicateKind
    # Node operands for the node-matching primitives. `subtree_member` names the
    # subtree root explicitly; it does not enumerate descendants, and expanding
    # it is a CP-002 evaluation step.
    node_refs: Annotated[
        tuple[OrganizationalNodeRef, ...],
        Field(max_length=MAX_PREDICATE_NODES),
        AfterValidator(unique_by("node_id", "predicate node identifiers")),
    ] = ()
    # Controlled role term. A role code is a label, never a permission set.
    role_code: CanonicalCode | None = None
    # Controlled group term resolved from trusted configuration, never from a
    # client-supplied group claim.
    trusted_group_code: CanonicalCode | None = None
    principal_ids: Annotated[
        tuple[Uuid4, ...],
        Field(max_length=MAX_PREDICATE_PRINCIPALS),
    ] = ()
    # Controlled classification term, for example a public or internal class.
    classification_code: CanonicalCode | None = None

    @model_validator(mode="after")
    def _require_operands_matching_kind(self) -> Self:
        node_kinds = {"exact_node_member", "subtree_member"}
        if self.kind in node_kinds:
            if not self.node_refs:
                raise ValueError(f"predicate kind {self.kind!r} requires at least one node ref")
        elif self.node_refs:
            raise ValueError(f"predicate kind {self.kind!r} must not carry node refs")

        if self.kind == "subtree_member" and len(self.node_refs) != 1:
            raise ValueError("a subtree predicate names exactly one subtree root")

        if self.kind == "scoped_role":
            if self.role_code is None:
                raise ValueError("a scoped-role predicate requires a role code")
        elif self.role_code is not None:
            raise ValueError(f"predicate kind {self.kind!r} must not carry a role code")

        if self.kind == "trusted_group":
            if self.trusted_group_code is None:
                raise ValueError("a trusted-group predicate requires a group code")
        elif self.trusted_group_code is not None:
            raise ValueError(f"predicate kind {self.kind!r} must not carry a group code")

        if self.kind == "explicit_principal":
            if not self.principal_ids:
                raise ValueError("an explicit-principal predicate requires at least one principal")
        elif self.principal_ids:
            raise ValueError(f"predicate kind {self.kind!r} must not carry principals")

        if self.kind == "classification_condition":
            if self.classification_code is None:
                raise ValueError("a classification predicate requires a classification code")
        elif self.classification_code is not None:
            raise ValueError(f"predicate kind {self.kind!r} must not carry a classification code")

        if len(set(self.principal_ids)) != len(self.principal_ids):
            raise ValueError("predicate principal identifiers must be unique")
        return self


class VisibilityAllowClause(ContractModel):
    """One conjunctive allow clause: every predicate inside it must match.

    A clause matches only if all of its predicates match (`C-1`). A clause
    cannot repeat a primitive kind, because two conjunctive occurrences of the
    same kind either duplicate or contradict each other and the resolution
    would be implicit.
    """

    predicates: Annotated[
        tuple[VisibilityPredicate, ...],
        Field(min_length=1, max_length=MAX_CLAUSE_PREDICATES),
        AfterValidator(unique_by("kind", "clause predicate kinds")),
    ]


class VisibilityPolicyDefinition(ContractModel):
    """One named, versioned, approved visibility policy definition.

    A definition allows a read only if at least one of its clauses matches
    (`C-1`). It is composed solely of Layer 1 primitives (`V-1`, `V-3`) and
    carries no executable predicate, no expression fragment, and no
    administrator-authored deny language (`C-3`). Restriction is expressed by
    writing narrower clauses.

    This is the per-source visibility policy, never the global `security_policy`
    configuration artifact (`ADR-CP-002` `O-8`, audit finding G-016). A source
    revision binds an exact immutable revision of this definition, not a policy
    identity that follows whichever revision is active (`V-4`, `V-5`).

    Deciding whether a definition allows a given principal is CP-002 work; an
    unresolvable reference means deny (`V-7`) and this contract therefore has no
    permissive default of any kind.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": VISIBILITY_POLICY_DEFINITION_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = VISIBILITY_POLICY_DEFINITION_SCHEMA_VERSION
    # Stable identity of the definition across revisions (`V-1`).
    visibility_policy_id: OpaqueId
    policy_revision: RevisionLabel
    policy_digest: ContentDigest
    # A platform-wide definition, for example an anonymous public profile, has
    # no owning organization. Cross-organization breadth is not implied: node
    # operands still name their organization explicitly.
    organization_id: Uuid4 | None = None
    # Human-facing catalog label. It carries no authorization meaning; the
    # matching semantics come only from the clauses.
    display_name: DisplayName
    status: VisibilityPolicyStatus
    clauses: Annotated[
        tuple[VisibilityAllowClause, ...],
        Field(min_length=1, max_length=MAX_ALLOW_CLAUSES),
    ]
    created_at: UtcDateTime
    # Approval under delegated authority (`V-1`). Recording who approved is
    # provenance for audit, never an authorization input.
    approved_by_principal_id: Uuid4 | None = None
    approved_at: UtcDateTime | None = None
    # Lineage to the revision this one replaces. Activated revisions are never
    # edited in place (`V-5`).
    previous_policy_revision: RevisionLabel | None = None

    @property
    def revision_ref(self) -> VisibilityPolicyRevisionRef:
        """The pinned reference a source revision binds (`V-4`)."""
        return VisibilityPolicyRevisionRef(
            visibility_policy_id=self.visibility_policy_id,
            policy_revision=self.policy_revision,
            policy_digest=self.policy_digest,
        )

    @model_validator(mode="after")
    def _require_consistent_approval_and_scope(self) -> Self:
        if self.status in {"approved", "active", "retired"}:
            if self.approved_by_principal_id is None or self.approved_at is None:
                raise ValueError(f"status {self.status!r} requires a recorded approval")
        elif self.approved_by_principal_id is not None or self.approved_at is not None:
            raise ValueError("a draft definition must not record an approval")

        if self.approved_at is not None and self.approved_at < self.created_at:
            raise ValueError("approved_at must not precede created_at")

        if self.previous_policy_revision == self.policy_revision:
            raise ValueError("a new revision must differ from the revision it replaces")

        if self.organization_id is not None:
            for clause in self.clauses:
                for predicate in clause.predicates:
                    for node_ref in predicate.node_refs:
                        if node_ref.organization_id != self.organization_id:
                            raise ValueError(
                                "every predicate node must belong to the policy organization"
                            )
        return self


class IndexIsolationProfile(ContractModel):
    """Trusted, versioned physical placement profile for one logical tenant.

    The profile records where content is physically placed and why. It never
    grants access: the mandatory trusted-metadata pre-filter is identical at
    every tier (`T-2`, `T-6`), and this contract carries no permission, role,
    group, or membership field. Physical location is resolved from trusted
    configuration only (`T-4`), so nothing here may be populated from a request.

    Promotion above the shared tier must be evidence-based (`P-2`) and must not
    be triggered by role, group, membership counts, or ordinary organizational
    depth (`P-3`); those counts are structurally absent. An informal
    sensitivity label is not sufficient grounds (`P-4`), so a promotion states
    a controlled reason code plus a reference to the recorded evidence.

    No numeric threshold is defined in this package (`P-5`). Resolving routing,
    executing promotion or demotion, and emitting the audited before/after
    topology (`T-5`) are CP-003, CP-006, and CP-009 obligations.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": INDEX_ISOLATION_PROFILE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = INDEX_ISOLATION_PROFILE_SCHEMA_VERSION
    # Stable identity of the profile across revisions (`P-1`).
    isolation_profile_id: OpaqueId
    profile_revision: RevisionLabel
    organization_id: Uuid4
    # Trusted logical tenant key used by the mandatory pre-filter. It is a
    # filter input, never a permission and never a physical address.
    logical_tenant_key: OpaqueId
    physical_isolation_tier: PhysicalIsolationTier
    # Opaque, provider-neutral references. No backend name, connection string,
    # endpoint, region string, or credential appears in this contract.
    routing_profile_ref: OpaqueId | None = None
    capacity_class: CanonicalCode | None = None
    residency_policy_ref: OpaqueId | None = None
    encryption_policy_ref: OpaqueId | None = None
    index_configuration_ref: OpaqueId | None = None
    # Controlled reason code plus the reference to recorded promotion evidence
    # (`P-2`). A free-text justification is deliberately not accepted.
    promotion_reason: CanonicalCode | None = None
    promotion_evidence_ref: OpaqueId | None = None
    # Before/after topology lineage for an audited promotion or demotion
    # (`T-5`). Absent on the first revision of a profile.
    previous_isolation_tier: PhysicalIsolationTier | None = None
    previous_profile_revision: RevisionLabel | None = None
    effective_at: UtcDateTime
    recorded_at: UtcDateTime
    # Provenance only, never an authorization input.
    recorded_by_principal_id: Uuid4 | None = None

    @property
    def is_promotion(self) -> bool:
        """True when this revision moves to a strictly stronger physical tier."""
        if self.previous_isolation_tier is None:
            return False
        current = _TIER_ORDER.index(self.physical_isolation_tier)
        previous = _TIER_ORDER.index(self.previous_isolation_tier)
        return current > previous

    @model_validator(mode="after")
    def _require_consistent_topology_lineage(self) -> Self:
        if self.recorded_at < self.effective_at:
            raise ValueError("recorded_at must not precede effective_at")

        if (self.previous_isolation_tier is None) != (self.previous_profile_revision is None):
            raise ValueError("previous tier and previous revision must be recorded together")

        if self.previous_profile_revision is not None:
            if self.previous_profile_revision == self.profile_revision:
                raise ValueError("a topology change requires a new revision, not an edit")
            if self.previous_isolation_tier == self.physical_isolation_tier:
                raise ValueError("a recorded topology change must change the isolation tier")

        if self.physical_isolation_tier != "shared_logical_partition":
            if self.promotion_reason is None or self.promotion_evidence_ref is None:
                raise ValueError(
                    "a tier above the shared partition requires a reason code and evidence ref"
                )

        if self.physical_isolation_tier == "dedicated_deployment":
            if self.residency_policy_ref is None and self.encryption_policy_ref is None:
                raise ValueError(
                    "a dedicated deployment requires a residency or encryption policy ref"
                )
        return self
