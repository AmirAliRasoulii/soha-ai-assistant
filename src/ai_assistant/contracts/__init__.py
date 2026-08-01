"""Typed contracts shared across the application."""

from ai_assistant.contracts.audit import (
    AuditActorRef,
    AuditEvent,
    AuditResourceRef,
)
from ai_assistant.contracts.base import (
    SCHEMA_VERSION_PATTERN,
    ContractModel,
    SchemaVersion,
    UtcDateTime,
)
from ai_assistant.contracts.errors import (
    DomainError,
    ErrorCode,
    ErrorEnvelope,
)
from ai_assistant.contracts.query_analysis import (
    AmbiguityLevel,
    EntityResolutionStatus,
    EvidenceNeed,
    QueryAnalysis,
    QueryEntity,
    QueryIntent,
    QueryTimeExpression,
    RiskLevel,
    TimeExpressionType,
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
    "AmbiguityLevel",
    "AttachmentRef",
    "AuditActorRef",
    "AuditEvent",
    "AuditResourceRef",
    "AuthorizationDecision",
    "AuthorizationResourceRef",
    "ContractModel",
    "DomainError",
    "EntityResolutionStatus",
    "ErrorCode",
    "ErrorEnvelope",
    "EvidenceNeed",
    "QueryAnalysis",
    "QueryEntity",
    "QueryIntent",
    "QueryTimeExpression",
    "RiskLevel",
    "RuntimeArtifactRef",
    "RuntimeFeatureFlag",
    "RuntimeSnapshot",
    "RuntimeSnapshotContent",
    "RuntimeSnapshotIntegrity",
    "SchemaVersion",
    "SecurityPrincipalContext",
    "TimeExpressionType",
    "TurnInput",
    "UtcDateTime",
]
