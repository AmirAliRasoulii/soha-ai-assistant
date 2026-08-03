"""Typed configurable port fakes for the WS-003A orchestrator tests."""

import asyncio
from datetime import datetime
from uuid import UUID

from ai_assistant.contracts import (
    AuthorizationDecision,
    AuthorizationResourceRef,
    CapabilityName,
    Evidence,
    StepResult,
)
from ai_assistant.core.types import (
    CapabilityInvocation,
    EvidenceMaterializationRequest,
    RuntimeContext,
)
from support.walking_skeleton_fixtures import (
    AUTHORIZATION_ID,
    CONVERSATION_ID,
    NOW,
    REQUEST_ID,
    SECURITY_CONTEXT_ID,
)

DOCUMENT_CAPABILITY: CapabilityName = "document_retrieval"
ANALYTICS_CAPABILITY: CapabilityName = "semantic_analytics"


def denied_authorization(
    *,
    decision_id: UUID = AUTHORIZATION_ID,
    request_id: UUID = REQUEST_ID,
    security_context_id: UUID = SECURITY_CONTEXT_ID,
    evaluated_at: datetime = NOW,
) -> AuthorizationDecision:
    """Build a contract valid denial decision through the normal constructor."""
    return AuthorizationDecision(
        decision_id=decision_id,
        request_id=request_id,
        security_context_id=security_context_id,
        action="runtime.answer",
        resource=AuthorizationResourceRef(
            resource_type="conversation",
            resource_id=str(CONVERSATION_ID),
        ),
        effect="deny",
        reason_codes=("policy.deny",),
        policy_version="1.0.0",
        evaluated_at=evaluated_at,
    )


class _BlockingFake:
    """Shared event based coordination without sleeping or polling."""

    def __init__(
        self,
        *,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        self.started = started
        self.gate = gate
        self.observed_cancellation = False

    async def _pause(self) -> None:
        if self.started is not None:
            self.started.set()
        if self.gate is None:
            return
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.observed_cancellation = True
            raise


class AuthorizationPortFake(_BlockingFake):
    """Configurable AuthorizationPort double."""

    def __init__(
        self,
        *,
        decision: AuthorizationDecision | None = None,
        error: Exception | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(started=started, gate=gate)
        self.decision = decision
        self.error = error
        self.calls = 0
        self.contexts: tuple[RuntimeContext, ...] = ()

    async def authorize(self, context: RuntimeContext) -> AuthorizationDecision:
        self.calls += 1
        self.contexts = (*self.contexts, context)
        await self._pause()
        if self.error is not None:
            raise self.error
        if self.decision is None:
            raise ValueError("the authorization fake requires a configured decision")
        return self.decision


class CapabilityPortFake(_BlockingFake):
    """Configurable CapabilityPort double."""

    def __init__(
        self,
        *,
        result: StepResult | None = None,
        error: Exception | None = None,
        name: CapabilityName = DOCUMENT_CAPABILITY,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(started=started, gate=gate)
        self.result = result
        self.error = error
        self.name = name
        self.calls = 0
        self.invocations: tuple[CapabilityInvocation, ...] = ()

    @property
    def capability_name(self) -> CapabilityName:
        return self.name

    async def execute(self, invocation: CapabilityInvocation) -> StepResult:
        self.calls += 1
        self.invocations = (*self.invocations, invocation)
        await self._pause()
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise ValueError("the capability fake requires a configured step result")
        return self.result


class EvidenceMaterializerFake(_BlockingFake):
    """Configurable EvidenceMaterializerPort double."""

    def __init__(
        self,
        *,
        evidence: tuple[Evidence, ...] = (),
        error: Exception | None = None,
        started: asyncio.Event | None = None,
        gate: asyncio.Event | None = None,
    ) -> None:
        super().__init__(started=started, gate=gate)
        self.evidence = evidence
        self.error = error
        self.calls = 0
        self.requests: tuple[EvidenceMaterializationRequest, ...] = ()

    async def materialize(
        self,
        request: EvidenceMaterializationRequest,
    ) -> tuple[Evidence, ...]:
        self.calls += 1
        self.requests = (*self.requests, request)
        await self._pause()
        if self.error is not None:
            raise self.error
        return self.evidence
