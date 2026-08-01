"""TurnInput contract, schema version 1.0.0."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field

from ai_assistant.contracts.base import ContractModel, UtcDateTime

TURN_INPUT_SCHEMA_VERSION = "1.0.0"
TURN_INPUT_SCHEMA_ID = "urn:ai-assistant:contracts:turn-input:1.0.0"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
MAX_RAW_MESSAGE_LENGTH = 32000
MAX_ATTACHMENTS = 10


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_meaningful_message(value: str) -> str:
    # Blank and NUL checks only: the accepted value is returned unchanged so that
    # whitespace and Unicode form stay byte-for-byte identical to the client input.
    if not value.strip():
        raise ValueError("raw_message must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("raw_message must not contain the NUL character")
    return value


RawMessage = Annotated[
    str,
    Field(min_length=1, max_length=MAX_RAW_MESSAGE_LENGTH),
    AfterValidator(_require_meaningful_message),
]


class AttachmentRef(ContractModel):
    """Reference to an attachment already stored in trusted storage."""

    attachment_id: Uuid4
    version: Annotated[int, Field(gt=0)]


def _require_unique_attachments(
    value: tuple[AttachmentRef, ...],
) -> tuple[AttachmentRef, ...]:
    identifiers = [item.attachment_id for item in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("attachment_id values must be unique")
    return value


AttachmentRefs = Annotated[
    tuple[AttachmentRef, ...],
    Field(max_length=MAX_ATTACHMENTS),
    AfterValidator(_require_unique_attachments),
]


class TurnInput(ContractModel):
    """Validated input handed to the Chat Runtime after transport parsing."""

    # Only schema identity is added here; the inherited closed and frozen
    # configuration is merged by Pydantic and stays in effect.
    model_config = ConfigDict(
        json_schema_extra={"$schema": JSON_SCHEMA_DIALECT, "$id": TURN_INPUT_SCHEMA_ID}
    )

    schema_version: Literal["1.0.0"] = TURN_INPUT_SCHEMA_VERSION
    request_id: Uuid4
    message_id: Uuid4
    conversation_id: Uuid4
    raw_message: RawMessage
    locale: Literal["fa-IR"] = "fa-IR"
    channel: Literal["web"] = "web"
    received_at: UtcDateTime
    idempotency_key: Uuid4
    attachments: AttachmentRefs = ()
