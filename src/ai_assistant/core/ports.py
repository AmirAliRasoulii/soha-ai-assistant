"""Provider-neutral runtime ports for the private AI Core."""

from typing import Protocol, runtime_checkable

from ai_assistant.contracts import (
    AuditEvent,
    AuthorizationDecision,
    CapabilityName,
    Evidence,
    StepResult,
)
from ai_assistant.core.types import (
    CapabilityInvocation,
    EffectiveIdempotencyKey,
    EvidenceMaterializationRequest,
    IdempotencyAcquireResult,
    IdempotencyLease,
    RuntimeContext,
    RuntimeTelemetryRecord,
    TerminalOutcome,
)


@runtime_checkable
class AuthorizationPort(Protocol):
    async def authorize(self, context: RuntimeContext) -> AuthorizationDecision: ...


@runtime_checkable
class CapabilityPort(Protocol):
    @property
    def capability_name(self) -> CapabilityName: ...

    async def execute(self, invocation: CapabilityInvocation) -> StepResult: ...


@runtime_checkable
class EvidenceMaterializerPort(Protocol):
    async def materialize(
        self,
        request: EvidenceMaterializationRequest,
    ) -> tuple[Evidence, ...]: ...


@runtime_checkable
class IdempotencyStorePort(Protocol):
    async def acquire(
        self,
        key: EffectiveIdempotencyKey,
        request_fingerprint: str,
    ) -> IdempotencyAcquireResult: ...

    async def complete(self, lease: IdempotencyLease, outcome: TerminalOutcome) -> None: ...

    async def abandon(self, lease: IdempotencyLease) -> None: ...


@runtime_checkable
class AuditEventSink(Protocol):
    async def emit(self, event: AuditEvent) -> None: ...


@runtime_checkable
class RuntimeTelemetrySink(Protocol):
    async def emit(self, record: RuntimeTelemetryRecord) -> None: ...
