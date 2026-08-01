"""Trusted identity and authorization decision contracts, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
SECURITY_PRINCIPAL_CONTEXT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
SECURITY_PRINCIPAL_CONTEXT_SCHEMA_ID = "urn:ai-assistant:contracts:security-principal-context:1.0.0"
AUTHORIZATION_DECISION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
AUTHORIZATION_DECISION_SCHEMA_ID = "urn:ai-assistant:contracts:authorization-decision:1.0.0"

# Canonical codes are internal identifiers. They are never lowercased or otherwise
# normalized, so an unexpected casing or separator is a rejection, not a silent fix.
_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
_MAX_CANONICAL_CODE_LENGTH = 64

_CanonicalCode = Annotated[
    str,
    Field(
        min_length=1,
        max_length=_MAX_CANONICAL_CODE_LENGTH,
        pattern=_CANONICAL_CODE_PATTERN,
    ),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_meaningful_text(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    return value


def _require_unique_codes(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_Unique = AfterValidator(_require_unique_codes)
_MeaningfulText = AfterValidator(_require_meaningful_text)

_Issuer = Annotated[str, Field(min_length=1, max_length=512), _MeaningfulText]
_ResourceId = Annotated[str, Field(min_length=1, max_length=256), _MeaningfulText]
_AuthenticationMethods = Annotated[
    tuple[_CanonicalCode, ...], Field(min_length=1, max_length=8), _Unique
]
_Roles = Annotated[tuple[_CanonicalCode, ...], Field(max_length=64), _Unique]
_Groups = Annotated[tuple[_CanonicalCode, ...], Field(max_length=256), _Unique]
_AllowedScopes = Annotated[tuple[_CanonicalCode, ...], Field(max_length=128), _Unique]
_ClassificationAllowances = Annotated[tuple[_CanonicalCode, ...], Field(max_length=32), _Unique]
_ReasonCodes = Annotated[tuple[_CanonicalCode, ...], Field(min_length=1, max_length=16), _Unique]
_Obligations = Annotated[tuple[_CanonicalCode, ...], Field(max_length=16), _Unique]
_ConstraintReferences = Annotated[tuple[_CanonicalCode, ...], Field(max_length=16), _Unique]


class SecurityPrincipalContext(ContractModel):
    """Trusted identity facts established by the Identity Adapter."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": SECURITY_PRINCIPAL_CONTEXT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = SECURITY_PRINCIPAL_CONTEXT_SCHEMA_VERSION
    context_id: _Uuid4
    principal_id: _Uuid4
    principal_type: Literal["user", "service"]
    deployment_id: _Uuid4
    issuer: _Issuer
    authenticated_at: UtcDateTime
    authentication_methods: _AuthenticationMethods
    assurance_level: _CanonicalCode
    session_id: _Uuid4 | None = None
    # Roles, groups, scopes, and classification allowances are authorization inputs.
    # They never express an access decision by themselves.
    roles: _Roles = ()
    groups: _Groups = ()
    allowed_scopes: _AllowedScopes = ()
    data_classification_allowances: _ClassificationAllowances = ()


class AuthorizationResourceRef(ContractModel):
    """Opaque reference to the resource an authorization decision applies to."""

    resource_type: _CanonicalCode
    # resource_id stays opaque: it is never parsed, resolved, or interpreted here.
    resource_id: _ResourceId
    classification: _CanonicalCode | None = None


class AuthorizationDecision(ContractModel):
    """Deterministic result of applying a versioned policy to an action and resource."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": AUTHORIZATION_DECISION_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = AUTHORIZATION_DECISION_SCHEMA_VERSION
    decision_id: _Uuid4
    request_id: _Uuid4
    security_context_id: _Uuid4
    action: _CanonicalCode
    resource: AuthorizationResourceRef
    effect: Literal["allow", "deny"]
    # Every decision, including an allow, must state why it was reached.
    reason_codes: _ReasonCodes
    obligations: _Obligations = ()
    constraint_references: _ConstraintReferences = ()
    policy_version: SchemaVersion
    evaluated_at: UtcDateTime
    expires_at: UtcDateTime | None = None

    @model_validator(mode="after")
    def _require_expiry_after_evaluation(self) -> Self:
        # An expiry at or before evaluation would make the decision valid for no
        # instant, which must fail closed instead of being silently accepted.
        if self.expires_at is not None and self.expires_at <= self.evaluated_at:
            raise ValueError("expires_at must be strictly later than evaluated_at")
        return self
