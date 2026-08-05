"""Shared primitives for the Control Plane contract families (CP-001).

These primitives exist so that every Control Plane contract family validates
opaque identifiers, canonical codes, content digests, display names, and
bounded collections identically. They add no behavior: CP-001 owns typed
shapes and local invariants only. Persistence, policy evaluation, activation,
and emission belong to later packages.
"""

from collections.abc import Callable
from typing import Annotated, TypeVar
from uuid import UUID

from pydantic import AfterValidator, Field

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

# Canonical codes are controlled, namespaced internal identifiers. They are
# never free user text and never display labels, so a malformed code is a
# rejection rather than a silently normalized value.
CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
# Digests are compared literally by downstream trust checks. Only the syntax is
# validated here: no storage technology or provider is implied or hardcoded.
CONTENT_DIGEST_PATTERN = r"^sha256:[0-9a-f]{64}$"
CONTENT_DIGEST_LENGTH = 71


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_identifier_text(value: str) -> str:
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


def _require_display_text(value: str) -> str:
    text = _require_identifier_text(value)
    # Control characters would let a display label smuggle structure into logs,
    # exports, and citations, so they are rejected instead of being stripped.
    if not text.isprintable():
        raise ValueError("value must not contain control characters")
    return text


IdentifierText = AfterValidator(_require_identifier_text)

CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=CANONICAL_CODE_PATTERN),
]
# Opaque identifiers are never parsed, resolved, or interpreted by a contract.
OpaqueId = Annotated[str, Field(min_length=1, max_length=256), IdentifierText]
RevisionLabel = Annotated[str, Field(min_length=1, max_length=128), IdentifierText]
ContentDigest = Annotated[
    str,
    Field(
        min_length=CONTENT_DIGEST_LENGTH,
        max_length=CONTENT_DIGEST_LENGTH,
        pattern=CONTENT_DIGEST_PATTERN,
    ),
]
# A display name is human text for humans only. It carries no authorization
# meaning and is never parsed to derive scope, authority, or hierarchy.
DisplayName = Annotated[
    str,
    Field(min_length=1, max_length=200),
    AfterValidator(_require_display_text),
]
# An absolute locator proposed by an operator or contributor. It is untrusted
# input, stored as opaque text, and never fetched by a contract.
ExternalLocator = Annotated[str, Field(min_length=1, max_length=2048), IdentifierText]

_ItemT = TypeVar("_ItemT")


def require_unique_values(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


UniqueValues = AfterValidator(require_unique_values)


def require_unique_uuids(value: tuple[UUID, ...]) -> tuple[UUID, ...]:
    if len(set(value)) != len(value):
        raise ValueError("identifiers must be unique")
    return value


UniqueUuids = AfterValidator(require_unique_uuids)


def unique_by(attribute: str, label: str) -> Callable[[tuple[_ItemT, ...]], tuple[_ItemT, ...]]:
    """Build a validator that rejects duplicate ``attribute`` values in a tuple."""

    def _validator(value: tuple[_ItemT, ...]) -> tuple[_ItemT, ...]:
        keys = [getattr(item, attribute) for item in value]
        if len(set(keys)) != len(keys):
            raise ValueError(f"{label} must be unique")
        return value

    return _validator
