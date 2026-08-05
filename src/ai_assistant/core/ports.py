"""Provider-neutral runtime ports for the private AI Core."""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ai_assistant.contracts import (
    AuditEvent,
    AuthorizationDecision,
    CapabilityName,
    Evidence,
    ModelInvocationRequest,
    ModelInvocationResult,
    ModelStreamChunk,
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
class ModelGatewayPort(Protocol):
    """Provider-neutral model invocation boundary (DEF-037).

    Core depends on this protocol and on the bounded request, result, and chunk
    contracts only. No provider, gateway product, SDK type, endpoint, or
    credential ever crosses it: a provider adapter implements this protocol in
    CP-012, and runtime invocation behavior such as retry and budget enforcement
    belongs to AI-008.

    Deadline and cancellation are contractual, not incidental: every request
    carries an absolute deadline, cancellation is delivered through ordinary
    task cancellation, and both surface as distinct terminal outcomes in the
    result rather than as an implementation-specific exception.
    """

    async def invoke(self, request: ModelInvocationRequest) -> ModelInvocationResult: ...

    def stream(self, request: ModelInvocationRequest) -> AsyncIterator[ModelStreamChunk]: ...


@runtime_checkable
class AuditEventSink(Protocol):
    async def emit(self, event: AuditEvent) -> None: ...


@runtime_checkable
class RuntimeTelemetrySink(Protocol):
    async def emit(self, record: RuntimeTelemetryRecord) -> None: ...
