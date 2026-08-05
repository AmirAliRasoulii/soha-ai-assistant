"""Principal and authorization-boundary contracts, schema version 1.0.0.

Authority: ADR-CP-002 (membership, role, and authorization scope), ADR-CP-003
(data and index isolation), DEF-106 (typed AuthorizationRequest and decision
binding), and DEF-108 (first-class typed Guest principal).

Scope split:

- CP-001 owns the typed shapes and their local validation, including the
  request-to-decision binding value and the consulted policy revision
  reference.
- CP-002 owns policy evaluation, decision expiry enforcement, scope expansion,
  and the `RetrievalAuthorizationEnvelope` (DEF-107, owned by CP-002 with
  AI-003); none of that is implemented here.

The existing committed contracts are reused rather than restated:
`SecurityPrincipalContext 1.0.0` remains the trusted identity fact, and
`AuthorizationDecision 1.0.0` remains the decision record. This module adds the
actor shape that Guest access needs and the binding that DEF-106 found missing.
"""

from typing import Final, Literal, Self

from pydantic import ConfigDict, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime
from ai_assistant.contracts.control_plane_base import (
    JSON_SCHEMA_DIALECT,
    CanonicalCode,
    ContentDigest,
    RevisionLabel,
    Uuid4,
)
from ai_assistant.contracts.membership import AuthorizationScopeRef, PermissionRef
from ai_assistant.contracts.security import AuthorizationResourceRef

REQUEST_ACTOR_CONTEXT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
REQUEST_ACTOR_CONTEXT_SCHEMA_ID = "urn:ai-assistant:contracts:request-actor-context:1.0.0"
AUTHORIZATION_REQUEST_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
AUTHORIZATION_REQUEST_SCHEMA_ID = "urn:ai-assistant:contracts:authorization-request:1.0.0"

# The two actor kinds are exhaustive on purpose. There is no third kind for a
# failed, partial, expired, or unverified authentication, so an authentication
# failure cannot be represented as an actor at all and can never be downgraded
# into a Guest (DEF-108).
ActorKind = Literal["authenticated_principal", "anonymous_guest"]

# CP-000B grants Guest, at most, citation-safe published metadata of sources
# published under the public visibility class. The code is carried explicitly so
# no consumer infers Guest breadth from the absence of a principal.
GUEST_VISIBILITY_CLASS: Final = "anonymous-public"


class AuthenticatedPrincipalRef(ContractModel):
    """Reference to a principal whose identity was already established.

    The trusted identity facts themselves live in `SecurityPrincipalContext
    1.0.0`; this reference only binds a request to that context and to the
    organization the request is made in.
    """

    principal_id: Uuid4
    security_context_id: Uuid4
    organization_id: Uuid4


class AnonymousGuest(ContractModel):
    """First-class typed Guest actor (DEF-108).

    A Guest is an accepted architecture actor, not a fallback: it is only ever
    constructed deliberately for an unauthenticated public surface. It carries
    no principal identifier, no role, no membership, and no scope, so nothing
    downstream can mistake a Guest for a narrowed authenticated principal.
    """

    guest_session_id: Uuid4
    organization_id: Uuid4
    established_at: UtcDateTime
    # The single visibility class a Guest may ever read under.
    visibility_class: CanonicalCode


class RequestActorContext(ContractModel):
    """The actor a request is evaluated for: exactly one authenticated principal
    or exactly one Guest.

    The mutually exclusive shape is the invariant: a payload that carries both
    an authenticated principal and a Guest, or neither, is rejected. Combined
    with the closed `ActorKind`, this makes "authentication failed, continue as
    Guest" structurally impossible.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": REQUEST_ACTOR_CONTEXT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = REQUEST_ACTOR_CONTEXT_SCHEMA_VERSION
    actor_kind: ActorKind
    authenticated_principal: AuthenticatedPrincipalRef | None = None
    guest: AnonymousGuest | None = None

    @model_validator(mode="after")
    def _require_exactly_one_actor(self) -> Self:
        if self.actor_kind == "authenticated_principal":
            if self.authenticated_principal is None:
                raise ValueError("actor_kind 'authenticated_principal' requires the principal ref")
            if self.guest is not None:
                raise ValueError("an authenticated actor must not carry a guest actor")
        else:
            if self.guest is None:
                raise ValueError("actor_kind 'anonymous_guest' requires the guest actor")
            if self.authenticated_principal is not None:
                raise ValueError("a guest actor must not carry an authenticated principal ref")
        return self

    @property
    def organization_id(self) -> Uuid4:
        """Organization the actor acts in, regardless of actor kind."""
        if self.authenticated_principal is not None:
            return self.authenticated_principal.organization_id
        assert self.guest is not None
        return self.guest.organization_id


class ConsultedPolicyRevisionRef(ContractModel):
    """Reference to the exact policy revision a decision was evaluated against.

    `AuthorizationDecision 1.0.0` carries `policy_version` only, which cannot
    identify which policy document and revision were actually consulted
    (DEF-106). This reference closes that gap without touching the published
    decision contract.
    """

    policy_id: CanonicalCode
    policy_revision: RevisionLabel
    policy_digest: ContentDigest


class AuthorizationRequest(ContractModel):
    """The exact question put to authorization: actor, action, permission,
    resource, and requested scope, at a stated instant.

    This contract states the question only. It carries no effect, no reason
    code, and no obligation, so it can never be mistaken for a decision.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": AUTHORIZATION_REQUEST_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = AUTHORIZATION_REQUEST_SCHEMA_VERSION
    request_id: Uuid4
    organization_id: Uuid4
    actor: RequestActorContext
    action: CanonicalCode
    permission: PermissionRef
    resource: AuthorizationResourceRef
    # Explicit node scope the caller asks about. Absent means the request is not
    # node-scoped; it never means "all nodes".
    requested_scope: AuthorizationScopeRef | None = None
    requested_at: UtcDateTime
    deadline_at: UtcDateTime | None = None
    # Digest over the canonical form of this request, used to bind a decision to
    # exactly this question. This contract validates the syntax only; computing
    # and comparing the digest is CP-002 work.
    request_fingerprint: ContentDigest

    @model_validator(mode="after")
    def _require_consistent_request(self) -> Self:
        if self.actor.organization_id != self.organization_id:
            raise ValueError("actor organization must match the request organization")
        if self.requested_scope is not None:
            if self.requested_scope.organization_id != self.organization_id:
                raise ValueError("requested scope must belong to the request organization")
        if self.deadline_at is not None and self.deadline_at <= self.requested_at:
            raise ValueError("deadline_at must be strictly later than requested_at")
        return self


class DecisionBindingRef(ContractModel):
    """Binding of exactly one authorization decision to exactly one request.

    The binding names the request, the decision, the fingerprint of the question
    that was answered, the policy revision that was consulted, the scope that
    was authorized, and the instant the authorization stops being usable.
    Enforcing the binding and the expiry at use time is CP-002 behavior; this
    contract makes the binding expressible and internally consistent.
    """

    request_id: Uuid4
    decision_id: Uuid4
    request_fingerprint: ContentDigest
    consulted_policy: ConsultedPolicyRevisionRef
    # The scope actually authorized, which is never widened from the requested
    # scope by this contract. Absent means no node scope was authorized.
    authorized_scope: AuthorizationScopeRef | None = None
    bound_at: UtcDateTime
    expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_expiry_after_binding(self) -> Self:
        if self.expires_at is not None and self.expires_at <= self.bound_at:
            raise ValueError("expires_at must be strictly later than bound_at")
        return self
