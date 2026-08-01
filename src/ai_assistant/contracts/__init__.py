"""Typed contracts shared across the application."""

from ai_assistant.contracts.base import (
    SCHEMA_VERSION_PATTERN,
    ContractModel,
    SchemaVersion,
    UtcDateTime,
)
from ai_assistant.contracts.runtime_snapshot import (
    RuntimeArtifactRef,
    RuntimeFeatureFlag,
    RuntimeSnapshot,
    RuntimeSnapshotContent,
    RuntimeSnapshotIntegrity,
)
from ai_assistant.contracts.security import (
    AuthorizationDecision,
    AuthorizationResourceRef,
    SecurityPrincipalContext,
)
from ai_assistant.contracts.turn_input import AttachmentRef, TurnInput

__all__ = [
    "SCHEMA_VERSION_PATTERN",
    "AttachmentRef",
    "AuthorizationDecision",
    "AuthorizationResourceRef",
    "ContractModel",
    "RuntimeArtifactRef",
    "RuntimeFeatureFlag",
    "RuntimeSnapshot",
    "RuntimeSnapshotContent",
    "RuntimeSnapshotIntegrity",
    "SchemaVersion",
    "SecurityPrincipalContext",
    "TurnInput",
    "UtcDateTime",
]
