"""Organization and organizational hierarchy contracts, schema version 1.0.0.

Authority: ADR-CP-001 (organization and department hierarchy). CP-001 owns the
typed shapes and the local invariants only. Node create, rename, move, path or
scope cache invalidation, and node-metadata publication remain DEF-105 work in
CP-002, CP-009, and CP-010.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    DisplayName,
    OpaqueId,
    RevisionLabel,
    UniqueUuids,
    Uuid4,
)

ORGANIZATION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
ORGANIZATION_SCHEMA_ID = "urn:ai-assistant:contracts:organization:1.0.0"
ORGANIZATIONAL_NODE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
ORGANIZATIONAL_NODE_SCHEMA_ID = "urn:ai-assistant:contracts:organizational-node:1.0.0"

# ADR-CP-001 L-1: these are the only two authorization-relevant lifecycle
# states. Archival, deletion, and root retirement stay deferred (DEF-105).
NodeStatus = Literal["active", "non_active"]
OrganizationStatus = Literal["active", "non_active"]

# ADR-CP-001 rule 3: `department` is one NodeType term among many. It is not the
# universal root abstraction and it grants nothing by itself.
NODE_TYPE_DEPARTMENT: Final = "department"

# A hierarchy is generic and recursive. The depth bound exists so that a path
# reference, and any bounded consumer of it, can never grow without limit; the
# accepted deployment examples (faculty, office, department, laboratory, ward,
# clinical unit, team, project) are far shallower than this ceiling.
MAX_HIERARCHY_DEPTH: Final = 32

_AncestorNodeIds = Annotated[
    tuple[Uuid4, ...],
    Field(max_length=MAX_HIERARCHY_DEPTH),
    UniqueUuids,
]


class NodeTypeRef(ContractModel):
    """Reference to one term of the versioned NodeType vocabulary.

    ADR-CP-001 rule 4 fixes NodeType as a dynamic, versioned vocabulary rather
    than a subclass hierarchy or a closed enumeration, so the term is carried as
    a controlled code plus the vocabulary revision it was read from. The
    vocabulary contents and their versioning rules are an open decision owned by
    the control-plane vocabulary package, and no authorization rule may be
    written against a specific value.
    """

    code: CanonicalCode
    vocabulary_revision: RevisionLabel


class OrganizationRef(ContractModel):
    """Opaque reference to exactly one organization."""

    organization_id: Uuid4


class OrganizationalNodeRef(ContractModel):
    """Opaque reference to exactly one node inside exactly one organization.

    The organization identifier travels with every node reference so that a
    cross-organization relationship is structurally detectable at the contract
    boundary instead of depending on a later lookup.
    """

    organization_id: Uuid4
    node_id: Uuid4


class HierarchyPathRef(ContractModel):
    """Materialized ancestor path of one node, root first.

    This is a read reference to a derived structure. Computing it, caching it,
    and invalidating it after a move are CP-002 and CP-009 obligations
    (DEF-105); this contract only proves that a given path value is internally
    consistent.
    """

    organization_id: Uuid4
    node_id: Uuid4
    root_node_id: Uuid4
    # Root first, immediate parent last. A root node has an empty tuple.
    ancestor_node_ids: _AncestorNodeIds = ()
    depth: Annotated[int, Field(ge=0, le=MAX_HIERARCHY_DEPTH)]
    path_revision: RevisionLabel

    @model_validator(mode="after")
    def _require_consistent_path(self) -> Self:
        if self.depth != len(self.ancestor_node_ids):
            raise ValueError("depth must equal the number of ancestors")
        if self.node_id in self.ancestor_node_ids:
            raise ValueError("a node must not appear in its own ancestor path")
        if self.depth == 0:
            # A depth-zero path can only describe the root of the organization.
            if self.root_node_id != self.node_id:
                raise ValueError("a depth-zero path must describe the root node itself")
        elif self.ancestor_node_ids[0] != self.root_node_id:
            raise ValueError("the first ancestor must be the root node")
        return self


class Organization(ContractModel):
    """One tenant organization with exactly one root node.

    Isolation between organizations is structural: nothing in this contract can
    express a shared node, a shared root, or an inherited relationship across
    organizations.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": ORGANIZATION_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = ORGANIZATION_SCHEMA_VERSION
    organization_id: Uuid4
    # Human label only. It carries no authorization meaning and is never parsed
    # to derive scope, authority, or hierarchy.
    display_name: DisplayName
    # Opaque external correlation key owned by the operator. Never resolved,
    # never interpreted, and never an authorization input.
    external_ref: OpaqueId | None = None
    status: OrganizationStatus
    root_node_id: Uuid4
    created_at: UtcDateTime
    status_changed_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_status_change_after_creation(self) -> Self:
        if self.status_changed_at is not None and self.status_changed_at < self.created_at:
            raise ValueError("status_changed_at must not precede created_at")
        return self


class OrganizationalNode(ContractModel):
    """One structural unit inside exactly one organization.

    Local invariants proven here: a root node never carries a parent, a
    non-root node always does, a node is never its own parent, and a parent
    always belongs to the same organization. Re-parenting a root is therefore
    unrepresentable rather than merely forbidden by a later service.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": ORGANIZATIONAL_NODE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = ORGANIZATIONAL_NODE_SCHEMA_VERSION
    organization_id: Uuid4
    node_id: Uuid4
    node_type: NodeTypeRef
    display_name: DisplayName
    external_ref: OpaqueId | None = None
    is_root: bool
    parent: OrganizationalNodeRef | None = None
    status: NodeStatus
    created_at: UtcDateTime
    status_changed_at: UtcDateTime | None = None
    # Optional derived lineage reference, validated against this node only.
    path: HierarchyPathRef | None = None

    @model_validator(mode="after")
    def _require_consistent_structure(self) -> Self:
        if self.is_root:
            if self.parent is not None:
                raise ValueError("a root node must not carry a parent")
        elif self.parent is None:
            raise ValueError("a non-root node requires a parent")
        if self.parent is not None:
            if self.parent.organization_id != self.organization_id:
                raise ValueError("a parent must belong to the same organization")
            if self.parent.node_id == self.node_id:
                raise ValueError("a node must not be its own parent")
        if self.status_changed_at is not None and self.status_changed_at < self.created_at:
            raise ValueError("status_changed_at must not precede created_at")
        return self

    @model_validator(mode="after")
    def _require_consistent_path(self) -> Self:
        path = self.path
        if path is None:
            return self
        if path.organization_id != self.organization_id or path.node_id != self.node_id:
            raise ValueError("path must describe this node in this organization")
        if self.is_root:
            if path.depth != 0:
                raise ValueError("a root node requires a depth-zero path")
        else:
            if path.depth == 0:
                raise ValueError("a non-root node requires a non-empty ancestor path")
            if self.parent is not None and path.ancestor_node_ids[-1] != self.parent.node_id:
                raise ValueError("the last ancestor must be the parent node")
        return self

    @property
    def node_ref(self) -> OrganizationalNodeRef:
        """Reference form of this node, for use in scopes and lineage records."""
        return OrganizationalNodeRef(
            organization_id=self.organization_id,
            node_id=self.node_id,
        )
