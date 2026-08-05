"""Membership and scoped-role contracts, schema version 1.0.0.

Authority: ADR-CP-002 (membership, role, and authorization scope) and
CP-000A (authorization matrix). CP-001 owns the typed shapes and their local
invariants. Policy evaluation, scope expansion, hierarchy traversal, and any
effective-permission resolution are CP-002 obligations and are deliberately
unrepresentable here.

Three architecture rules are enforced structurally rather than by comment:

1. Membership alone grants no read access: `NodeMembership` carries no
   permission, no role, and no scope field at all.
2. A role label is not a permission: `ScopedRoleAssignment` carries a
   `RoleRef` plus the catalog revision it was read from, never a permission set.
3. Parent, child, and sibling access is never implicit: an
   `AuthorizationScopeRef` enumerates its nodes explicitly and has no
   "include descendants" flag.
"""

from typing import Annotated, Final, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    RevisionLabel,
    Uuid4,
    unique_by,
)
from ai_assistant.contracts.organization import OrganizationalNodeRef

NODE_MEMBERSHIP_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
NODE_MEMBERSHIP_SCHEMA_ID = "urn:ai-assistant:contracts:node-membership:1.0.0"
SCOPED_ROLE_ASSIGNMENT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SCOPED_ROLE_ASSIGNMENT_SCHEMA_ID = "urn:ai-assistant:contracts:scoped-role-assignment:1.0.0"

AssignmentStatus = Literal["active", "non_active"]
MembershipStatus = Literal["active", "non_active"]

# One assignment may target several explicitly named nodes, for example a
# delegated reviewer covering a handful of departments. The ceiling keeps every
# downstream consumer bounded; broader coverage is a policy decision in CP-002,
# not an unbounded list in a contract.
MAX_SCOPE_NODES: Final = 64

_ScopeNodes = Annotated[
    tuple[OrganizationalNodeRef, ...],
    Field(min_length=1, max_length=MAX_SCOPE_NODES),
    AfterValidator(unique_by("node_id", "scope node identifiers")),
]


class RoleRef(ContractModel):
    """Reference to one role term of the versioned role catalog.

    The role code is a controlled label. It never carries or implies a
    permission: resolving a role to permissions requires the catalog revision
    and is a CP-002 evaluation step.
    """

    role_code: CanonicalCode
    catalog_revision: RevisionLabel


class PermissionRef(ContractModel):
    """Reference to one permission term of the versioned permission catalog."""

    permission_code: CanonicalCode
    catalog_revision: RevisionLabel


class ValidityWindow(ContractModel):
    """Half-open validity window for an assignment or membership record.

    `valid_until` is nullable and means open-ended, never "already expired".
    A window that closes at or before it opens is valid for no instant and is
    rejected instead of being silently accepted.
    """

    valid_from: UtcDateTime
    valid_until: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_ordered_window(self) -> Self:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be strictly later than valid_from")
        return self


class AuthorizationScopeRef(ContractModel):
    """Explicit set of nodes an assignment or decision applies to.

    The enumeration is exhaustive by construction. There is no descendant,
    subtree, or wildcard flag, so no consumer of this contract can widen a
    scope by reading it; any breadth beyond these exact nodes must be produced
    by CP-002 policy evaluation and expressed as its own explicit scope value.
    """

    organization_id: Uuid4
    node_refs: _ScopeNodes

    @model_validator(mode="after")
    def _require_single_organization(self) -> Self:
        for node_ref in self.node_refs:
            if node_ref.organization_id != self.organization_id:
                raise ValueError("every scope node must belong to the scope organization")
        return self


class NodeMembership(ContractModel):
    """Binding of one principal to one organizational node.

    Membership is many-to-many by record multiplicity: a principal may hold
    several memberships, and a node may hold many members, while each record
    binds exactly one principal to exactly one node. Membership is an
    authorization input only. It grants no read access, no role, and no scope,
    and this contract cannot express any of those.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": NODE_MEMBERSHIP_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = NODE_MEMBERSHIP_SCHEMA_VERSION
    membership_id: Uuid4
    organization_id: Uuid4
    principal_id: Uuid4
    node: OrganizationalNodeRef
    # Controlled vocabulary term, for example a primary or secondary affiliation.
    # The term is descriptive metadata and never an authorization input.
    membership_kind: CanonicalCode
    status: MembershipStatus
    validity: ValidityWindow
    recorded_at: UtcDateTime

    @model_validator(mode="after")
    def _require_same_organization(self) -> Self:
        if self.node.organization_id != self.organization_id:
            raise ValueError("membership node must belong to the membership organization")
        return self


class ScopedRoleAssignment(ContractModel):
    """Assignment of one role to one principal over one explicit scope.

    The assignment states who holds which role over exactly which nodes and for
    which window. It never states what that role may do: permission resolution,
    conflict handling, and effective access are CP-002 evaluation concerns.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": SCOPED_ROLE_ASSIGNMENT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = SCOPED_ROLE_ASSIGNMENT_SCHEMA_VERSION
    assignment_id: Uuid4
    organization_id: Uuid4
    principal_id: Uuid4
    role: RoleRef
    scope: AuthorizationScopeRef
    status: AssignmentStatus
    validity: ValidityWindow
    assigned_at: UtcDateTime
    # Opaque reference to the principal that recorded the assignment. It is
    # provenance for audit, never an authorization input.
    assigned_by_principal_id: Uuid4 | None = None

    @model_validator(mode="after")
    def _require_same_organization(self) -> Self:
        if self.scope.organization_id != self.organization_id:
            raise ValueError("assignment scope must belong to the assignment organization")
        return self
