"""Canonical AI Core error contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self, get_args
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ERROR_ENVELOPE_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
ERROR_ENVELOPE_SCHEMA_ID = "urn:ai-assistant:contracts:error-envelope:1.0.0"

ErrorCode = Literal[
    "INVALID_INPUT",
    "UNAUTHENTICATED",
    "UNAUTHORIZED",
    "AMBIGUOUS_REQUEST",
    "POLICY_REJECTED",
    "NO_EVIDENCE",
    "CONFLICTING_EVIDENCE",
    "SCHEMA_INVALID",
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "BUDGET_EXCEEDED",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
    "INTERNAL_ERROR",
]

# Retry eligibility is a property of the code itself, so an envelope may never
# claim a retry that policy does not allow, or hide one that it does.
_RETRYABLE_ERROR_CODES: Final[frozenset[str]] = frozenset(
    {
        "DEPENDENCY_TIMEOUT",
        "TRANSIENT_DEPENDENCY",
        "RATE_LIMITED",
        "CAPACITY_REJECTED",
    }
)
_ERROR_CODES: Final[tuple[str, ...]] = get_args(ErrorCode)
_SAFE_MESSAGE_KEY_PATTERN = r"^error\.[a-z0-9._-]*$"

_SafeMessageKey = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_SAFE_MESSAGE_KEY_PATTERN),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


class DomainError(ContractModel):
    """Machine-readable error semantics produced by trusted runtime code."""

    code: ErrorCode
    safe_message_key: _SafeMessageKey
    retryable: bool
    # Opaque reference to an internal error record. It carries no diagnostic data
    # and is never resolved, persisted, or exposed by this contract.
    internal_detail_ref: _Uuid4

    @model_validator(mode="after")
    def _require_canonical_semantics(self) -> Self:
        expected_key = f"error.{self.code.lower()}"
        if self.safe_message_key != expected_key:
            raise ValueError(f"safe_message_key must be {expected_key!r} for code {self.code!r}")
        expected_retryable = self.code in _RETRYABLE_ERROR_CODES
        if self.retryable is not expected_retryable:
            raise ValueError(f"retryable must be {expected_retryable} for code {self.code!r}")
        return self


class ErrorEnvelope(ContractModel):
    """Canonical internal error contract of the AI Core."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": ERROR_ENVELOPE_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = ERROR_ENVELOPE_SCHEMA_VERSION
    error_id: _Uuid4
    correlation_id: _Uuid4
    error: DomainError
