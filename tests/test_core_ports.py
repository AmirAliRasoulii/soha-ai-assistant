"""Focused tests for private AI Core protocols and dependency boundaries."""

import ast
import inspect
import sys
from pathlib import Path

from ai_assistant.contracts import (
    AuditEvent,
    AuthorizationDecision,
    CapabilityName,
    Evidence,
    StepResult,
)
from ai_assistant.core import __all__
from ai_assistant.core.ports import (
    AuditEventSink,
    AuthorizationPort,
    CapabilityPort,
    EvidenceMaterializerPort,
    IdempotencyStorePort,
    RuntimeTelemetrySink,
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


class AuthorizationFake:
    async def authorize(self, context: RuntimeContext) -> AuthorizationDecision:
        raise NotImplementedError


class CapabilityFake:
    @property
    def capability_name(self) -> CapabilityName:
        return "rule_evaluator"

    async def execute(self, invocation: CapabilityInvocation) -> StepResult:
        raise NotImplementedError


class EvidenceFake:
    async def materialize(
        self,
        request: EvidenceMaterializationRequest,
    ) -> tuple[Evidence, ...]:
        raise NotImplementedError


class IdempotencyFake:
    async def acquire(
        self,
        key: EffectiveIdempotencyKey,
        request_fingerprint: str,
    ) -> IdempotencyAcquireResult:
        raise NotImplementedError

    async def complete(self, lease: IdempotencyLease, outcome: TerminalOutcome) -> None:
        raise NotImplementedError

    async def abandon(self, lease: IdempotencyLease) -> None:
        raise NotImplementedError


class AuditFake:
    async def emit(self, event: AuditEvent) -> None:
        raise NotImplementedError


class TelemetryFake:
    async def emit(self, record: RuntimeTelemetryRecord) -> None:
        raise NotImplementedError


class IncompleteFake:
    pass


def test_runtime_checkable_protocols_accept_complete_fakes() -> None:
    assert isinstance(AuthorizationFake(), AuthorizationPort)
    assert isinstance(CapabilityFake(), CapabilityPort)
    assert isinstance(EvidenceFake(), EvidenceMaterializerPort)
    assert isinstance(IdempotencyFake(), IdempotencyStorePort)
    assert isinstance(AuditFake(), AuditEventSink)
    assert isinstance(TelemetryFake(), RuntimeTelemetrySink)


def test_runtime_checkable_protocols_reject_incomplete_fakes() -> None:
    assert not isinstance(IncompleteFake(), AuthorizationPort)
    assert not isinstance(IncompleteFake(), CapabilityPort)
    assert not isinstance(IncompleteFake(), EvidenceMaterializerPort)
    assert not isinstance(IncompleteFake(), IdempotencyStorePort)
    assert not isinstance(IncompleteFake(), AuditEventSink)
    assert not isinstance(IncompleteFake(), RuntimeTelemetrySink)


def test_protocol_methods_have_required_async_shape() -> None:
    assert inspect.iscoroutinefunction(AuthorizationPort.authorize)
    assert inspect.iscoroutinefunction(CapabilityPort.execute)
    assert inspect.iscoroutinefunction(EvidenceMaterializerPort.materialize)
    assert inspect.iscoroutinefunction(IdempotencyStorePort.acquire)
    assert inspect.iscoroutinefunction(IdempotencyStorePort.complete)
    assert inspect.iscoroutinefunction(IdempotencyStorePort.abandon)
    assert inspect.iscoroutinefunction(AuditEventSink.emit)
    assert inspect.iscoroutinefunction(RuntimeTelemetrySink.emit)
    assert isinstance(CapabilityPort.capability_name, property)


def test_core_package_has_no_public_re_exports() -> None:
    assert __all__ == ()


def test_core_source_has_only_allowed_imports_and_no_dynamic_payloads() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core"
    stdlib = set(sys.stdlib_module_names)
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                root_name = name.split(".", 1)[0]
                assert (
                    root_name in stdlib
                    or name.startswith("ai_assistant.contracts")
                    or name.startswith("ai_assistant.core")
                )
        source = path.read_text(encoding="utf-8")
        assert "Any" not in source
        assert "Mapping[str, object]" not in source
        assert "dict[" not in source
        assert not any(field in source for field in ("metadata:", "attributes:", "payload:"))
