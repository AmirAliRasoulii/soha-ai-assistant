"""Canonical deterministic route decision contract, schema version 1.0.0."""

from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.query_analysis import RiskLevel

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ROUTE_DECISION_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
ROUTE_DECISION_SCHEMA_ID = "urn:ai-assistant:contracts:route-decision:1.0.0"

RouteLane = Literal[
    "deterministic",
    "fast",
    "composite",
    "clarify",
    "abstain",
    "deny",
]
CapabilityName = Literal[
    "document_retrieval",
    "semantic_analytics",
    "personal_selector",
    "rule_evaluator",
    "official_search",
]

_TERMINAL_LANES: Final[frozenset[str]] = frozenset({"clarify", "abstain", "deny"})
_FLOW_LANES: Final[frozenset[str]] = frozenset({"deterministic", "fast"})
_UNRESOLVED_RISK_LEVELS: Final[frozenset[str]] = frozenset({"high", "unknown"})

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]


def _require_exact_text(value: str) -> str:
    # References are opaque: malformed input is rejected rather than trimmed,
    # rewritten, or repaired by validation.
    if not value.strip():
        raise ValueError("value must contain at least one non-whitespace character")
    if "\x00" in value:
        raise ValueError("value must not contain the NUL character")
    if value != value.strip():
        raise ValueError("value must not have leading or trailing whitespace")
    return value


_OpaqueRef = Annotated[
    str,
    Field(min_length=1, max_length=256),
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


_Capabilities = Annotated[
    tuple[CapabilityName, ...],
    Field(max_length=5),
    AfterValidator(_require_unique_values),
]
_RequiredFacts = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_values),
]

_StepCount = Annotated[int, Field(strict=True, ge=0, le=5)]
_ParallelStepCount = Annotated[int, Field(strict=True, ge=0, le=3)]
_SingleAttemptCount = Annotated[int, Field(strict=True, ge=0, le=1)]


class RouteFilterRef(ContractModel):
    """Reference to an already approved filter or constraint set."""

    # This is a reference only: no predicate, operator, value, SQL, search DSL,
    # access-control expression, or provider object may be carried here.
    filter_type: _CanonicalCode
    filter_ref: _OpaqueRef


class RouteBudget(ContractModel):
    """Frozen count-based execution limits for a routed turn."""

    # Only count-based limits are frozen here. Deadlines, token budgets,
    # provider quotas, financial budgets, and capacity reservations belong to
    # future runtime and capability contracts.
    max_steps: _StepCount
    max_parallel_steps: _ParallelStepCount
    max_replans: _SingleAttemptCount
    max_retrieval_retries: _SingleAttemptCount
    max_analytics_repairs: _SingleAttemptCount
    max_answer_repairs: _SingleAttemptCount

    @model_validator(mode="after")
    def _require_consistent_budget(self) -> Self:
        if self.max_parallel_steps > self.max_steps:
            raise ValueError("max_parallel_steps must not exceed max_steps")
        if self.max_steps == 0 and self.max_parallel_steps != 0:
            raise ValueError("a zero step budget requires zero parallel steps")
        if self.max_steps > 0 and self.max_parallel_steps < 1:
            raise ValueError("a positive step budget requires at least one parallel step")
        return self

    def is_all_zero(self) -> bool:
        """Report whether every execution counter is zero."""
        return (
            self.max_steps == 0
            and self.max_parallel_steps == 0
            and self.max_replans == 0
            and self.max_retrieval_retries == 0
            and self.max_analytics_repairs == 0
            and self.max_answer_repairs == 0
        )


def _require_unique_filter_pairs(value: tuple[RouteFilterRef, ...]) -> tuple[RouteFilterRef, ...]:
    pairs = [(item.filter_type, item.filter_ref) for item in value]
    if len(set(pairs)) != len(pairs):
        raise ValueError("filters must be unique by (filter_type, filter_ref)")
    return value


_Filters = Annotated[
    tuple[RouteFilterRef, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_filter_pairs),
]


class RouteDecision(ContractModel):
    """Immutable output of trusted deterministic routing policy."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": ROUTE_DECISION_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = ROUTE_DECISION_SCHEMA_VERSION
    decision_id: _Uuid4
    request_id: _Uuid4
    query_analysis_id: _Uuid4
    authorization_decision_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    decided_at: UtcDateTime
    # The routing policy produces the effective risk level; it is never copied
    # blindly from analyzer output.
    effective_risk_level: RiskLevel
    lane: RouteLane
    route: _CanonicalCode
    allowed_capabilities: _Capabilities = ()
    required_facts: _RequiredFacts = ()
    planner_required: bool
    filters: _Filters = ()
    budget: RouteBudget
    rationale_code: _CanonicalCode
    policy_version: SchemaVersion
    approved_flow_ref: _OpaqueRef | None = None

    @model_validator(mode="after")
    def _require_consistent_decision(self) -> Self:
        self._require_planner_agreement()
        self._require_lane_shape()
        self._require_approved_flow_rules()
        return self

    def _require_planner_agreement(self) -> None:
        if self.planner_required != (self.lane == "composite"):
            raise ValueError("planner_required must be true if and only if lane is 'composite'")

    def _require_lane_shape(self) -> None:
        if self.lane in _TERMINAL_LANES:
            self._require_terminal_shape()
        elif self.lane == "fast":
            self._require_fast_shape()
        elif self.lane == "composite":
            self._require_composite_shape()
        else:
            self._require_deterministic_shape()

    def _require_terminal_shape(self) -> None:
        if self.allowed_capabilities:
            raise ValueError(f"lane {self.lane!r} must not allow capabilities")
        if self.required_facts:
            raise ValueError(f"lane {self.lane!r} must not require facts")
        if self.filters:
            raise ValueError(f"lane {self.lane!r} must not carry filters")
        if self.approved_flow_ref is not None:
            raise ValueError(f"lane {self.lane!r} must not carry an approved flow reference")
        if not self.budget.is_all_zero():
            raise ValueError(f"lane {self.lane!r} requires an all-zero budget")

    def _require_fast_shape(self) -> None:
        if len(self.allowed_capabilities) != 1:
            raise ValueError("the fast lane requires exactly one allowed capability")
        if not self.required_facts:
            raise ValueError("the fast lane requires at least one required fact")
        if self.budget.max_steps != 1 or self.budget.max_parallel_steps != 1:
            raise ValueError("the fast lane requires exactly one step and one parallel step")
        if self.budget.max_replans != 0:
            raise ValueError("the fast lane must not permit replanning")

    def _require_composite_shape(self) -> None:
        if not self.allowed_capabilities:
            raise ValueError("the composite lane requires at least one allowed capability")
        if not self.required_facts:
            raise ValueError("the composite lane requires at least one required fact")
        if self.budget.max_steps < 2:
            raise ValueError("the composite lane requires at least two steps")
        if self.budget.max_parallel_steps < 1:
            raise ValueError("the composite lane requires at least one parallel step")

    def _require_deterministic_shape(self) -> None:
        if self.budget.max_replans != 0:
            raise ValueError("the deterministic lane must not permit replanning")
        if self.allowed_capabilities:
            if not self.required_facts:
                raise ValueError(
                    "a deterministic executable flow requires at least one required fact"
                )
            if self.budget.max_steps < 1 or self.budget.max_parallel_steps < 1:
                raise ValueError(
                    "a deterministic executable flow requires at least one step "
                    "and one parallel step"
                )
        else:
            if self.required_facts:
                raise ValueError("a deterministic fixed response must not require facts")
            if self.filters:
                raise ValueError("a deterministic fixed response must not carry filters")
            if not self.budget.is_all_zero():
                raise ValueError("a deterministic fixed response requires an all-zero budget")

    def _require_approved_flow_rules(self) -> None:
        if self.approved_flow_ref is not None and self.lane not in _FLOW_LANES:
            raise ValueError(
                "an approved flow reference is allowed only for the deterministic and fast lanes"
            )
        if (
            self.lane == "fast"
            and self.effective_risk_level in _UNRESOLVED_RISK_LEVELS
            and self.approved_flow_ref is None
        ):
            raise ValueError(
                "a high-risk or unknown-risk fast decision requires an approved flow reference"
            )
