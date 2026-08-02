"""Focused tests for private AI Core protocols and dependency boundaries."""

import ast
import inspect
import sys
from pathlib import Path

import pytest

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

STDLIB_MODULES = frozenset(sys.stdlib_module_names)
CORE_PACKAGE = "ai_assistant.core"
ALLOWED_PACKAGES = ("ai_assistant.contracts", "ai_assistant.core")


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


def is_module_allowed(module: str) -> bool:
    if not module:
        return False
    root_name = module.split(".", 1)[0]
    if root_name in STDLIB_MODULES:
        return True
    return any(
        module == allowed or module.startswith(f"{allowed}.") for allowed in ALLOWED_PACKAGES
    )


def resolve_relative_module(module: str, level: int, package: str) -> str | None:
    parts = package.split(".")
    if level < 1 or level > len(parts):
        return None
    base = parts[: len(parts) - level + 1]
    if not base:
        return None
    if not module:
        return ".".join(base)
    return ".".join([*base, module])


def is_import_allowed(node: ast.Import | ast.ImportFrom, package: str = CORE_PACKAGE) -> bool:
    if isinstance(node, ast.Import):
        return all(is_module_allowed(alias.name) for alias in node.names)
    module = node.module or ""
    if node.level == 0:
        return is_module_allowed(module)
    resolved = resolve_relative_module(module, node.level, package)
    return resolved is not None and is_module_allowed(resolved)


def parse_import_node(source: str) -> ast.Import | ast.ImportFrom:
    statement = ast.parse(source).body[0]
    assert isinstance(statement, (ast.Import, ast.ImportFrom))
    return statement


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


@pytest.mark.parametrize(
    "source",
    [
        "import json",
        "import dataclasses, enum",
        "from datetime import datetime",
        "from ai_assistant.contracts import StepResult",
        "from ai_assistant.contracts.errors import ErrorCode",
        "from ai_assistant.core.types import RuntimeContext",
        "from ai_assistant.core import ports",
        "from .types import RuntimeContext",
        "from .ports import CapabilityPort",
        "from ..contracts import StepResult",
        "from ..contracts.errors import ErrorCode",
        "from . import types",
    ],
)
def test_import_allowlist_accepts_permitted_imports(source: str) -> None:
    assert is_import_allowed(parse_import_node(source))


@pytest.mark.parametrize(
    "source",
    [
        "import numpy",
        "import json, numpy",
        "from requests import get",
        "from external_package.module import Value",
        "from ai_assistant.adapters import Adapter",
        "from ai_assistant import contracts",
        "from ...contracts import StepResult",
        "from .. import adapters",
    ],
)
def test_import_allowlist_rejects_forbidden_imports(source: str) -> None:
    assert not is_import_allowed(parse_import_node(source))


def test_relative_import_resolution_is_package_aware() -> None:
    assert resolve_relative_module("types", 1, CORE_PACKAGE) == "ai_assistant.core.types"
    assert resolve_relative_module("contracts", 2, CORE_PACKAGE) == "ai_assistant.contracts"
    assert resolve_relative_module("", 1, CORE_PACKAGE) == "ai_assistant.core"
    assert resolve_relative_module("contracts", 3, CORE_PACKAGE) is None
    assert resolve_relative_module("types", 0, CORE_PACKAGE) is None


def test_core_source_has_only_allowed_imports_and_no_dynamic_payloads() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core"
    paths = sorted(root.glob("*.py"))
    assert paths
    for path in paths:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                assert is_import_allowed(node, CORE_PACKAGE), f"{path.name}: {ast.dump(node)}"
        assert "Any" not in source
        assert "Mapping[str, object]" not in source
        assert "dict[" not in source
        assert not any(field in source for field in ("metadata:", "attributes:", "payload:"))
