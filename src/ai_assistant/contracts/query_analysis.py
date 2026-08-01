"""Canonical AI Core query analysis contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
QUERY_ANALYSIS_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
QUERY_ANALYSIS_SCHEMA_ID = "urn:ai-assistant:contracts:query-analysis:1.0.0"

QueryIntent = Literal[
    "greeting",
    "capability_help",
    "factual",
    "procedural",
    "status",
    "eligibility",
    "comparison",
    "analytics",
    "unknown",
]
EvidenceNeed = Literal[
    "none",
    "document",
    "analytics",
    "personal",
    "rule",
    "official_source",
]
AmbiguityLevel = Literal["none", "non_blocking", "blocking"]
RiskLevel = Literal["normal", "elevated", "high", "unknown"]
EntityResolutionStatus = Literal["resolved", "unresolved", "ambiguous"]
TimeExpressionType = Literal["date", "date_range", "relative", "academic_term", "unknown"]

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]


def _require_exact_text(value: str) -> str:
    # Query, mention, and identifier text is preserved exactly: malformed input
    # is rejected rather than trimmed, rewritten, or repaired by validation.
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


_OpaqueId = Annotated[
    str,
    Field(min_length=1, max_length=256),
    AfterValidator(_require_exact_text),
]
_DerivedQueryText = Annotated[
    str,
    Field(min_length=1, max_length=32000),
    AfterValidator(_require_exact_text),
]
_MentionText = Annotated[
    str,
    Field(min_length=1, max_length=512),
    AfterValidator(_require_exact_text),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_unique_values(value: tuple[str, ...]) -> tuple[str, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_CandidateIds = Annotated[
    tuple[_OpaqueId, ...],
    Field(max_length=8),
    AfterValidator(_require_unique_values),
]
_Codes16 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_values),
]
_EvidenceNeeds = Annotated[
    tuple[EvidenceNeed, ...],
    Field(min_length=1, max_length=6),
    AfterValidator(_require_unique_values),
]


def _require_consistent_resolution(
    status: EntityResolutionStatus,
    canonical: str | None,
    candidates: tuple[str, ...],
    kind: str,
) -> None:
    # Canonical identifiers and values are minted only by trusted resolvers; the
    # resolution status must agree exactly with what the resolver produced.
    if status == "resolved":
        if canonical is None:
            raise ValueError(f"resolved {kind} requires a canonical value")
        if candidates:
            raise ValueError(f"resolved {kind} must not carry candidates")
    elif status == "unresolved":
        if canonical is not None:
            raise ValueError(f"unresolved {kind} must not carry a canonical value")
        if candidates:
            raise ValueError(f"unresolved {kind} must not carry candidates")
    else:
        if canonical is not None:
            raise ValueError(f"ambiguous {kind} must not carry a canonical value")
        if not 2 <= len(candidates):
            raise ValueError(f"ambiguous {kind} requires 2..8 candidates")


class QueryEntity(ContractModel):
    """Structured entity mention with explicit trusted-resolver state."""

    entity_type: _CanonicalCode
    mention: _MentionText
    resolution_status: EntityResolutionStatus
    canonical_id: _OpaqueId | None = None
    candidate_ids: _CandidateIds = ()

    @model_validator(mode="after")
    def _require_consistent_entity(self) -> Self:
        _require_consistent_resolution(
            self.resolution_status,
            self.canonical_id,
            self.candidate_ids,
            "entity",
        )
        return self


class QueryTimeExpression(ContractModel):
    """Structured time expression with explicit trusted-resolver state."""

    expression: _MentionText
    time_type: TimeExpressionType
    resolution_status: EntityResolutionStatus
    canonical_value: _OpaqueId | None = None
    candidate_values: _CandidateIds = ()

    @model_validator(mode="after")
    def _require_consistent_time_expression(self) -> Self:
        _require_consistent_resolution(
            self.resolution_status,
            self.canonical_value,
            self.candidate_values,
            "time expression",
        )
        return self


def _require_unique_entity_pairs(value: tuple[QueryEntity, ...]) -> tuple[QueryEntity, ...]:
    pairs = [(entity.entity_type, entity.mention) for entity in value]
    if len(set(pairs)) != len(pairs):
        raise ValueError("entities must be unique by (entity_type, mention)")
    return value


_Entities = Annotated[
    tuple[QueryEntity, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_entity_pairs),
]


def _require_unique_time_pairs(
    value: tuple[QueryTimeExpression, ...],
) -> tuple[QueryTimeExpression, ...]:
    pairs = [(item.time_type, item.expression) for item in value]
    if len(set(pairs)) != len(pairs):
        raise ValueError("time expressions must be unique by (time_type, expression)")
    return value


_TimeExpressions = Annotated[
    tuple[QueryTimeExpression, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_time_pairs),
]


class QueryAnalysis(ContractModel):
    """Immutable structured query features assembled by trusted analyzer code."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": QUERY_ANALYSIS_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = QUERY_ANALYSIS_SCHEMA_VERSION
    analysis_id: _Uuid4
    request_id: _Uuid4
    message_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    analyzed_at: UtcDateTime
    normalized_query: _DerivedQueryText
    intent: QueryIntent
    entities: _Entities = ()
    time_expressions: _TimeExpressions = ()
    ambiguity_level: AmbiguityLevel
    ambiguity_codes: _Codes16 = ()
    is_personal: bool
    is_multi_part: bool
    risk_level: RiskLevel
    risk_signals: _Codes16 = ()
    evidence_needs: _EvidenceNeeds
    # Confidence is advisory only; it must never be the sole input to
    # authorization, denial, high-risk routing, capability allowlisting, or
    # policy enforcement.
    confidence: Annotated[float, Field(ge=0.0, le=1.0, allow_inf_nan=False)]
    analyzer_version: SchemaVersion

    @model_validator(mode="after")
    def _require_consistent_analysis(self) -> Self:
        if self.ambiguity_level == "none":
            if self.ambiguity_codes:
                raise ValueError("ambiguity_level 'none' must not carry ambiguity codes")
        elif not self.ambiguity_codes:
            raise ValueError(
                f"ambiguity_level {self.ambiguity_level!r} requires at least one ambiguity code"
            )
        if "none" in self.evidence_needs and len(self.evidence_needs) > 1:
            raise ValueError("evidence need 'none' must be the only evidence need")
        if "personal" in self.evidence_needs and not self.is_personal:
            raise ValueError("evidence need 'personal' requires is_personal to be true")
        return self
