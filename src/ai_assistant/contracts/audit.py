"""Canonical AI Core audit event contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, UtcDateTime

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
AUDIT_EVENT_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
AUDIT_EVENT_SCHEMA_ID = "urn:ai-assistant:contracts:audit-event:1.0.0"

AuditActorType = Literal["user", "service", "system"]
AuditOutcome = Literal["success", "denied", "failed"]

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"

# Canonical codes are controlled, namespaced identifiers, never free user text, so
# they are never lowercased or otherwise repaired: a malformed code is rejected.
_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_resource_id_text(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


_ResourceId = Annotated[
    str,
    Field(min_length=1, max_length=256),
    AfterValidator(_require_resource_id_text),
]


def _require_unique_reason_codes(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("reason codes must be unique")
    return value


_ReasonCodes = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_reason_codes),
]


class AuditActorRef(ContractModel):
    """Trusted identity reference recorded for an audited action."""

    actor_type: AuditActorType
    principal_id: _Uuid4 | None = None
    security_context_id: _Uuid4 | None = None

    @model_validator(mode="after")
    def _require_consistent_identity(self) -> Self:
        has_principal = self.principal_id is not None
        has_security_context = self.security_context_id is not None
        if self.actor_type in ("user", "service"):
            if not (has_principal and has_security_context):
                raise ValueError(
                    f"actor_type {self.actor_type!r} requires both principal_id "
                    "and security_context_id"
                )
        elif has_principal or has_security_context:
            raise ValueError("actor_type 'system' must not carry an identity reference")
        return self


class AuditResourceRef(ContractModel):
    """Opaque reference to the resource affected by an audited action."""

    resource_type: _CanonicalCode
    resource_id: _ResourceId
    classification: _CanonicalCode | None = None


class AuditEvent(ContractModel):
    """Safe, minimal, replayable audit fact emitted by trusted AI runtime code."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": AUDIT_EVENT_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = AUDIT_EVENT_SCHEMA_VERSION
    event_id: _Uuid4
    event_type: _CanonicalCode
    occurred_at: UtcDateTime
    producer: _CanonicalCode
    correlation_id: _Uuid4
    request_id: _Uuid4
    actor: AuditActorRef
    action: _CanonicalCode
    resource: AuditResourceRef | None = None
    outcome: AuditOutcome
    reason_codes: _ReasonCodes = ()
    authorization_decision_id: _Uuid4 | None = None
    runtime_snapshot_id: _Uuid4
    error_id: _Uuid4 | None = None
    # Opaque reference to an internal error or diagnostic record. It carries no
    # raw detail itself and is never resolved or persisted by this contract.
    internal_detail_ref: _Uuid4 | None = None
    retention_class: _CanonicalCode
    sensitivity: _CanonicalCode

    @model_validator(mode="after")
    def _require_consistent_outcome(self) -> Self:
        if self.outcome == "success":
            if self.error_id is not None:
                raise ValueError("outcome 'success' must not carry an error_id")
        elif self.outcome == "denied":
            if self.authorization_decision_id is None:
                raise ValueError("outcome 'denied' requires authorization_decision_id")
            if not self.reason_codes:
                raise ValueError("outcome 'denied' requires at least one reason code")
            if self.error_id is not None:
                raise ValueError("outcome 'denied' must not carry an error_id")
        else:
            if self.error_id is None:
                raise ValueError("outcome 'failed' requires error_id")
            if not self.reason_codes:
                raise ValueError("outcome 'failed' requires at least one reason code")
        return self
