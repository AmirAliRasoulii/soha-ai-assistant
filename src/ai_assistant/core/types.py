"""Private immutable value types for the provider-neutral AI Core."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ai_assistant.contracts import (
    AuthorizationDecision,
    CapabilityName,
    ErrorCode,
    ErrorEnvelope,
    ExecutionPlan,
    FinalAnswer,
    PlanStep,
    QueryAnalysis,
    RouteDecision,
    RuntimeSnapshot,
    SecurityPrincipalContext,
    StepResult,
    TurnInput,
)

_SHA256_HEX_LENGTH = 64


def _require_non_empty(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _require_aware(value: datetime, field_name: str) -> datetime:
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _require_snapshot_digest(value: str, field_name: str) -> str:
    if (
        len(value) != len("sha256:") + _SHA256_HEX_LENGTH
        or not value.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _require_hex_digest(value: str, field_name: str) -> str:
    if len(value) != _SHA256_HEX_LENGTH or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")
    return value


def _require_same(left: object, right: object, description: str) -> None:
    if left != right:
        raise ValueError(f"{description} must match")


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Trusted request, identity, configuration, and timing context."""

    turn_input: TurnInput
    principal: SecurityPrincipalContext
    runtime_snapshot: RuntimeSnapshot
    correlation_id: str
    started_at: datetime
    deadline_at: datetime | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.correlation_id, "correlation_id")
        _require_aware(self.started_at, "started_at")
        if self.deadline_at is not None:
            _require_aware(self.deadline_at, "deadline_at")
            if self.deadline_at <= self.started_at:
                raise ValueError("deadline_at must be later than started_at")


@dataclass(frozen=True, slots=True)
class AuthorizedRuntimeContext:
    """Runtime context paired with a successfully completed authorization."""

    runtime: RuntimeContext
    authorization: AuthorizationDecision

    def __post_init__(self) -> None:
        if self.authorization.effect != "allow":
            raise ValueError("authorization must allow the operation")
        _require_same(
            self.authorization.request_id,
            self.runtime.turn_input.request_id,
            "authorization request_id and turn request_id",
        )
        _require_same(
            self.authorization.security_context_id,
            self.runtime.principal.context_id,
            "authorization security_context_id and principal context_id",
        )


@dataclass(frozen=True, slots=True)
class CapabilityInvocation:
    """Validated binding of one authorized request to one planned step."""

    context: AuthorizedRuntimeContext
    query_analysis: QueryAnalysis
    route_decision: RouteDecision
    execution_plan: ExecutionPlan
    step: PlanStep

    def __post_init__(self) -> None:
        runtime = self.context.runtime
        authorization = self.context.authorization
        request_id = runtime.turn_input.request_id
        snapshot_id = runtime.runtime_snapshot.snapshot_id
        authorization_id = authorization.decision_id

        _require_same(self.query_analysis.request_id, request_id, "query analysis request_id")
        _require_same(
            self.query_analysis.runtime_snapshot_id,
            snapshot_id,
            "query analysis runtime_snapshot_id",
        )
        _require_same(self.route_decision.request_id, request_id, "route decision request_id")
        _require_same(
            self.route_decision.query_analysis_id,
            self.query_analysis.analysis_id,
            "route decision query_analysis_id",
        )
        _require_same(
            self.route_decision.authorization_decision_id,
            authorization_id,
            "route decision authorization_decision_id",
        )
        _require_same(
            self.route_decision.runtime_snapshot_id,
            snapshot_id,
            "route decision runtime_snapshot_id",
        )
        _require_same(self.execution_plan.request_id, request_id, "execution plan request_id")
        _require_same(
            self.execution_plan.route_decision_id,
            self.route_decision.decision_id,
            "execution plan route_decision_id",
        )
        _require_same(
            self.execution_plan.authorization_decision_id,
            authorization_id,
            "execution plan authorization_decision_id",
        )
        _require_same(
            self.execution_plan.runtime_snapshot_id,
            snapshot_id,
            "execution plan runtime_snapshot_id",
        )
        _require_same(
            self.execution_plan.lane,
            self.route_decision.lane,
            "execution plan lane and route decision lane",
        )
        _require_same(
            self.execution_plan.allowed_capabilities,
            self.route_decision.allowed_capabilities,
            "execution plan allowed_capabilities and route decision allowed_capabilities",
        )
        _require_same(
            self.execution_plan.required_facts,
            self.route_decision.required_facts,
            "execution plan required_facts and route decision required_facts",
        )
        _require_same(
            self.execution_plan.budget,
            self.route_decision.budget,
            "execution plan budget and route decision budget",
        )
        if self.step not in self.execution_plan.steps:
            raise ValueError("step must belong to execution_plan")
        if self.step.capability not in self.execution_plan.allowed_capabilities:
            raise ValueError("step capability must be allowlisted by execution_plan")
        if self.route_decision.lane == "fast":
            if len(self.execution_plan.steps) != 1 or self.step != self.execution_plan.steps[0]:
                raise ValueError("fast invocation must reference the sole plan step")


@dataclass(frozen=True, slots=True)
class EvidenceMaterializationRequest:
    """Validated request for resolving step evidence references."""

    context: AuthorizedRuntimeContext
    route_decision: RouteDecision
    execution_plan: ExecutionPlan
    step_results: tuple[StepResult, ...]

    def __post_init__(self) -> None:
        if not self.step_results:
            raise ValueError("step_results must be non-empty")
        runtime = self.context.runtime
        request_id = runtime.turn_input.request_id
        snapshot_id = runtime.runtime_snapshot.snapshot_id
        correlation_id = runtime.correlation_id
        if self.route_decision.request_id != request_id:
            raise ValueError("route decision request_id must match runtime context")
        if self.route_decision.authorization_decision_id != self.context.authorization.decision_id:
            raise ValueError("route decision authorization_decision_id must match authorization")
        if self.route_decision.runtime_snapshot_id != snapshot_id:
            raise ValueError("route decision runtime_snapshot_id must match runtime context")
        if self.execution_plan.request_id != request_id:
            raise ValueError("execution plan request_id must match runtime context")
        if self.execution_plan.route_decision_id != self.route_decision.decision_id:
            raise ValueError("execution plan route_decision_id must match route decision")
        if self.execution_plan.authorization_decision_id != self.context.authorization.decision_id:
            raise ValueError("execution plan authorization_decision_id must match authorization")
        if self.execution_plan.runtime_snapshot_id != snapshot_id:
            raise ValueError("execution plan runtime_snapshot_id must match runtime context")
        plan_step_ids = {step.step_id for step in self.execution_plan.steps}
        result_ids: set[object] = set()
        for result in self.step_results:
            if result.result_id in result_ids:
                raise ValueError("step result IDs must be unique")
            result_ids.add(result.result_id)
            if result.request_id != request_id:
                raise ValueError("step result request_id must match runtime context")
            if result.plan_id != self.execution_plan.plan_id:
                raise ValueError("step result plan_id must match execution plan")
            if result.runtime_snapshot_id != snapshot_id:
                raise ValueError("step result runtime_snapshot_id must match runtime context")
            if str(result.correlation_id) != correlation_id:
                raise ValueError("step result correlation_id must match runtime context")
            if result.step_id not in plan_step_ids:
                raise ValueError("step result must refer to a step present in execution_plan")


@dataclass(frozen=True, slots=True)
class EffectiveIdempotencyKey:
    """Identity and runtime-scoped idempotency key, excluding request payload."""

    deployment_id: str
    principal_id: str
    client_key: str
    runtime_snapshot_id: str
    runtime_snapshot_digest: str

    def __post_init__(self) -> None:
        for name, value in (
            ("deployment_id", self.deployment_id),
            ("principal_id", self.principal_id),
            ("client_key", self.client_key),
            ("runtime_snapshot_id", self.runtime_snapshot_id),
        ):
            _require_non_empty(value, name)
        _require_snapshot_digest(self.runtime_snapshot_digest, "runtime_snapshot_digest")


@dataclass(frozen=True, slots=True)
class IdempotencyLease:
    """Private lease for one acquired idempotency key."""

    lease_id: str
    key: EffectiveIdempotencyKey
    request_fingerprint: str

    def __post_init__(self) -> None:
        _require_non_empty(self.lease_id, "lease_id")
        _require_hex_digest(self.request_fingerprint, "request_fingerprint")


class IdempotencyAcquireStatus(StrEnum):
    ACQUIRED = "acquired"
    REPLAY = "replay"
    IN_FLIGHT = "in_flight"
    CONFLICT = "conflict"


type TerminalOutcome = FinalAnswer | ErrorEnvelope


@dataclass(frozen=True, slots=True)
class IdempotencyAcquireResult:
    """Result of an atomic idempotency acquisition attempt."""

    status: IdempotencyAcquireStatus
    lease: IdempotencyLease | None = None
    outcome: TerminalOutcome | None = None

    def __post_init__(self) -> None:
        has_lease = self.lease is not None
        has_outcome = self.outcome is not None
        valid = {
            IdempotencyAcquireStatus.ACQUIRED: (True, False),
            IdempotencyAcquireStatus.REPLAY: (False, True),
            IdempotencyAcquireStatus.IN_FLIGHT: (False, False),
            IdempotencyAcquireStatus.CONFLICT: (False, False),
        }[self.status]
        if (has_lease, has_outcome) != valid:
            raise ValueError("idempotency result state does not match status")


class RuntimeTelemetryEventName(StrEnum):
    RUNTIME_STARTED = "runtime_started"
    AUTHORIZATION_COMPLETED = "authorization_completed"
    CAPABILITY_STARTED = "capability_started"
    CAPABILITY_COMPLETED = "capability_completed"
    RUNTIME_COMPLETED = "runtime_completed"
    RUNTIME_FAILED = "runtime_failed"


class RuntimeTelemetryOutcome(StrEnum):
    ANSWERED = "answered"
    ABSTAINED = "abstained"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RuntimeTelemetryRecord:
    """Closed, low-cardinality operational telemetry record."""

    event_name: RuntimeTelemetryEventName
    occurred_at: datetime
    request_id: str
    correlation_id: str
    runtime_snapshot_id: str
    authorization_decision_id: str | None = None
    plan_id: str | None = None
    step_id: str | None = None
    capability: CapabilityName | None = None
    outcome: RuntimeTelemetryOutcome | None = None
    error_code: ErrorCode | None = None
    duration_ms: int | None = None

    def __post_init__(self) -> None:
        _require_aware(self.occurred_at, "occurred_at")
        for name, value in (
            ("request_id", self.request_id),
            ("correlation_id", self.correlation_id),
            ("runtime_snapshot_id", self.runtime_snapshot_id),
        ):
            _require_non_empty(value, name)
        optional_ids: tuple[tuple[str, str | None], ...] = (
            ("authorization_decision_id", self.authorization_decision_id),
            ("plan_id", self.plan_id),
            ("step_id", self.step_id),
        )
        for optional_name, optional_value in optional_ids:
            if optional_value is not None:
                _require_non_empty(optional_value, optional_name)
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        if self.event_name == RuntimeTelemetryEventName.RUNTIME_FAILED:
            if self.error_code is None:
                raise ValueError("runtime_failed requires an error_code")
        elif self.error_code is not None:
            raise ValueError("non-failure events must not carry an error_code")
        if self.event_name == RuntimeTelemetryEventName.RUNTIME_COMPLETED:
            if self.outcome is None:
                raise ValueError("runtime_completed requires an outcome")
