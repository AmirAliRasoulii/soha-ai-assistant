"""Tests for the bounded asynchronous fast document orchestrator."""

import ast
import asyncio
import dataclasses
import sys
from collections.abc import Coroutine
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    BUNDLE_ID,
    CORRELATION_TEXT,
    DOCUMENT_FACT_ID,
    FOREIGN_ID,
    NOW,
    PLAN_ID,
    ROUTE_DECISION_ID,
    answer_plan,
    authorization,
    document_evidence,
    evidence_bundle,
    evidence_provenance,
    execution_plan,
    failed_step_result,
    principal,
    query_analysis,
    route_decision,
    runtime_snapshot,
    step_result,
    terminal_route_decision,
    turn_input,
)
from support.walking_skeleton_runtime_fakes import (
    ANALYTICS_CAPABILITY,
    AuthorizationPortFake,
    CapabilityPortFake,
    EvidenceMaterializerFake,
    denied_authorization,
)

from ai_assistant.contracts import (
    AmbiguityLevel,
    AuthorizationDecision,
    Evidence,
    EvidenceNeed,
    QueryAnalysis,
    QueryIntent,
)
from ai_assistant.core.runtime import (
    OrchestrationArtifacts,
    OrchestrationFailurePhase,
    OrchestrationResult,
    OrchestrationStatus,
    orchestrate_fast_document,
)
from ai_assistant.core.types import RuntimeContext

RUNTIME_MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "runtime.py"
)
CORE_INIT_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "__init__.py"
)
STDLIB_MODULES = frozenset(sys.stdlib_module_names)
ALLOWED_PACKAGES = ("ai_assistant.contracts", "ai_assistant.core")
FORBIDDEN_FRAGMENTS = (
    "Any",
    "cast(",
    "type: ignore",
    "noqa",
    "dict[",
    "Mapping[str, object]",
    "metadata:",
    "attributes:",
    "payload:",
    "model_construct",
    "model_copy",
    "uuid4",
    "datetime.now",
    "utcnow",
    "while ",
    "create_task",
    "TaskGroup",
    "shield",
    "logging",
    "IdempotencyStorePort",
    "AuditEventSink",
    "RuntimeTelemetrySink",
    "FinalAnswer",
    "ErrorEnvelope",
    "open(",
    "os.environ",
)
FORBIDDEN_VENDOR_ROOTS = (
    "requests",
    "httpx",
    "aiohttp",
    "boto3",
    "psycopg",
    "sqlalchemy",
    "elasticsearch",
    "opensearchpy",
    "openai",
    "anthropic",
    "opentelemetry",
)
ARTIFACTS = OrchestrationArtifacts(
    route_decision_id=ROUTE_DECISION_ID,
    route_decided_at=NOW,
    execution_plan_id=PLAN_ID,
    execution_plan_planned_at=NOW,
    evidence_bundle_id=BUNDLE_ID,
    evidence_bundle_built_at=NOW,
    answer_plan_id=ANSWER_PLAN_ID,
    answer_plan_built_at=NOW,
)
SHORT_DEADLINE = timedelta(milliseconds=50)


def runtime_context(*, deadline_at: datetime | None = None) -> RuntimeContext:
    return RuntimeContext(
        turn_input=turn_input(),
        principal=principal(),
        runtime_snapshot=runtime_snapshot(),
        correlation_id=CORRELATION_TEXT,
        started_at=NOW,
        deadline_at=deadline_at,
    )


def accepted_evidence() -> tuple[Evidence, ...]:
    return (document_evidence(),)


def unacceptable_evidence() -> tuple[Evidence, ...]:
    return (document_evidence(validation_status="degraded"),)


def ambiguous_analysis(level: AmbiguityLevel) -> QueryAnalysis:
    return query_analysis(ambiguity_level=level, ambiguity_codes=("ambiguity.scope",))


def unsupported_analysis(
    *,
    intent: QueryIntent = "analytics",
    evidence_needs: tuple[EvidenceNeed, ...] = ("analytics",),
) -> QueryAnalysis:
    return query_analysis(intent=intent, evidence_needs=evidence_needs)


def run(coroutine: Coroutine[None, None, OrchestrationResult]) -> OrchestrationResult:
    return asyncio.run(coroutine)


def orchestrate(
    *,
    context: RuntimeContext | None = None,
    analysis: QueryAnalysis | None = None,
    authorization_port: AuthorizationPortFake,
    capability_port: CapabilityPortFake,
    evidence_materializer: EvidenceMaterializerFake,
    artifacts: OrchestrationArtifacts = ARTIFACTS,
    entered_at: datetime = NOW,
) -> Coroutine[None, None, OrchestrationResult]:
    return orchestrate_fast_document(
        context if context is not None else runtime_context(),
        analysis if analysis is not None else query_analysis(),
        authorization_port=authorization_port,
        capability_port=capability_port,
        evidence_materializer=evidence_materializer,
        artifacts=artifacts,
        entered_at=entered_at,
    )


def allowed_authorization() -> AuthorizationDecision:
    return authorization()


def successful_ports() -> tuple[
    AuthorizationPortFake,
    CapabilityPortFake,
    EvidenceMaterializerFake,
]:
    return (
        AuthorizationPortFake(decision=allowed_authorization()),
        CapabilityPortFake(result=step_result()),
        EvidenceMaterializerFake(evidence=accepted_evidence()),
    )


# 10.1 private result types -------------------------------------------------


def test_private_result_types_are_frozen_and_slotted() -> None:
    for model in (OrchestrationArtifacts, OrchestrationResult):
        assert dataclasses.is_dataclass(model)
        assert model.__dataclass_params__.frozen
        assert hasattr(model, "__slots__")


def test_frozen_results_reject_attribute_assignment() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.FAILED,
        error_code="INTERNAL_ERROR",
        failure_phase=OrchestrationFailurePhase.RUNTIME,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.status = OrchestrationStatus.COMPLETED


@pytest.mark.parametrize(
    "field_name",
    [
        "route_decided_at",
        "execution_plan_planned_at",
        "evidence_bundle_built_at",
        "answer_plan_built_at",
    ],
)
def test_naive_artifact_timestamps_are_rejected(field_name: str) -> None:
    values = dataclasses.asdict(ARTIFACTS)
    values[field_name] = NOW.replace(tzinfo=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        OrchestrationArtifacts(**values)


@pytest.mark.parametrize(
    "field_name",
    [
        "route_decision_id",
        "execution_plan_id",
        "evidence_bundle_id",
        "answer_plan_id",
    ],
)
def test_non_uuid4_artifact_identifiers_are_rejected(field_name: str) -> None:
    values = dataclasses.asdict(ARTIFACTS)
    values[field_name] = UUID(int=0, version=1)
    with pytest.raises(ValueError, match="version 4 UUID"):
        OrchestrationArtifacts(**values)


@pytest.mark.parametrize(
    "field_name",
    [
        "route_decided_at",
        "execution_plan_planned_at",
        "evidence_bundle_built_at",
    ],
)
def test_artifact_timestamp_order_violations_are_rejected(field_name: str) -> None:
    values = dataclasses.asdict(ARTIFACTS)
    values[field_name] = NOW + timedelta(minutes=5)
    with pytest.raises(ValueError, match="nondecreasing"):
        OrchestrationArtifacts(**values)


def test_nondecreasing_artifact_timestamps_are_accepted() -> None:
    artifacts = OrchestrationArtifacts(
        route_decision_id=ROUTE_DECISION_ID,
        route_decided_at=NOW,
        execution_plan_id=PLAN_ID,
        execution_plan_planned_at=NOW + timedelta(seconds=1),
        evidence_bundle_id=BUNDLE_ID,
        evidence_bundle_built_at=NOW + timedelta(seconds=2),
        answer_plan_id=ANSWER_PLAN_ID,
        answer_plan_built_at=NOW + timedelta(seconds=2),
    )
    assert artifacts.answer_plan_built_at >= artifacts.evidence_bundle_built_at


def completed_result() -> OrchestrationResult:
    return OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=allowed_authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=answer_plan(),
    )


def test_valid_completed_shape_is_accepted() -> None:
    assert completed_result().status is OrchestrationStatus.COMPLETED


def test_valid_stopped_shape_is_accepted() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.STOPPED,
        authorization=allowed_authorization(),
        route_decision=terminal_route_decision(lane="clarify"),
    )
    assert result.route_decision is not None


def test_valid_denied_shape_is_accepted() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.DENIED,
        authorization=denied_authorization(),
        error_code="UNAUTHORIZED",
        failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
    )
    assert result.error_code == "UNAUTHORIZED"


def test_valid_failed_shape_is_accepted() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.FAILED,
        authorization=allowed_authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=failed_step_result(),
        error_code="INTERNAL_ERROR",
        failure_phase=OrchestrationFailurePhase.CAPABILITY,
    )
    assert result.failure_phase is OrchestrationFailurePhase.CAPABILITY


def test_failure_before_authorization_may_carry_no_artifacts() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.FAILED,
        error_code="DEPENDENCY_TIMEOUT",
        failure_phase=OrchestrationFailurePhase.RUNTIME,
    )
    assert result.authorization is None


def test_completed_without_successful_step_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="successful step result"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=failed_step_result(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
        )


def test_completed_without_step_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="successful step result"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
        )


def test_completed_without_execution_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
        )


def test_completed_without_evidence_bundle_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence bundle"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            answer_plan=answer_plan(),
        )


def test_completed_without_answer_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="answer plan"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            evidence_bundle=evidence_bundle(),
        )


def test_completed_with_terminal_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="fast lane route decision"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=terminal_route_decision(lane="abstain"),
            execution_plan=execution_plan(),
            step_result=step_result(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
        )


def test_completed_with_denied_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="allowed authorization"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=denied_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
        )


def test_completed_with_failure_classification_is_rejected() -> None:
    with pytest.raises(ValueError, match="failure classification"):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            evidence_bundle=evidence_bundle(),
            answer_plan=answer_plan(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.CAPABILITY,
        )


def test_stopped_with_execution_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution artifacts"):
        OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=allowed_authorization(),
            route_decision=terminal_route_decision(lane="clarify"),
            execution_plan=execution_plan(),
        )


def test_stopped_with_fast_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="clarify or abstain route"):
        OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
        )


def test_stopped_without_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="clarify or abstain route"):
        OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=allowed_authorization(),
        )


def test_stopped_with_error_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="failure classification"):
        OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=allowed_authorization(),
            route_decision=terminal_route_decision(lane="clarify"),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.RUNTIME,
        )


def test_stopped_with_evidence_bundle_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence artifacts"):
        OrchestrationResult(
            status=OrchestrationStatus.STOPPED,
            authorization=allowed_authorization(),
            route_decision=terminal_route_decision(lane="clarify"),
            evidence_bundle=evidence_bundle(),
        )


def test_denied_with_route_decision_is_rejected() -> None:
    with pytest.raises(ValueError, match="routing artifacts"):
        OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=denied_authorization(),
            route_decision=route_decision(),
            error_code="UNAUTHORIZED",
            failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
        )


def test_denied_with_step_result_is_rejected() -> None:
    with pytest.raises(ValueError, match="step result"):
        OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=denied_authorization(),
            step_result=step_result(),
            error_code="UNAUTHORIZED",
            failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
        )


def test_denied_with_allowing_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="denying authorization"):
        OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=allowed_authorization(),
            error_code="UNAUTHORIZED",
            failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
        )


def test_denied_with_wrong_error_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="UNAUTHORIZED error code"):
        OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=denied_authorization(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.AUTHORIZATION,
        )


def test_denied_with_wrong_phase_is_rejected() -> None:
    with pytest.raises(ValueError, match="authorization phase"):
        OrchestrationResult(
            status=OrchestrationStatus.DENIED,
            authorization=denied_authorization(),
            error_code="UNAUTHORIZED",
            failure_phase=OrchestrationFailurePhase.RUNTIME,
        )


def test_failed_without_error_code_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires an error code"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            failure_phase=OrchestrationFailurePhase.RUNTIME,
        )


def test_failed_without_failure_phase_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a failure phase"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            error_code="INTERNAL_ERROR",
        )


def test_failed_with_answer_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence artifacts"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            answer_plan=answer_plan(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.CAPABILITY,
        )


def test_failed_plan_without_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a route decision"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            authorization=allowed_authorization(),
            execution_plan=execution_plan(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.CAPABILITY,
        )


def test_failed_step_result_without_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires a plan"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            authorization=allowed_authorization(),
            route_decision=route_decision(),
            step_result=step_result(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.CAPABILITY,
        )


def test_failed_route_without_allowed_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="allowed authorization"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            route_decision=route_decision(),
            error_code="INTERNAL_ERROR",
            failure_phase=OrchestrationFailurePhase.CAPABILITY,
        )


def test_status_must_be_an_orchestration_status() -> None:
    with pytest.raises(ValueError, match="OrchestrationStatus"):
        OrchestrationResult(status="completed")


def test_failure_phase_must_be_an_orchestration_failure_phase() -> None:
    with pytest.raises(ValueError, match="OrchestrationFailurePhase"):
        OrchestrationResult(
            status=OrchestrationStatus.FAILED,
            error_code="INTERNAL_ERROR",
            failure_phase="runtime",
        )


# 10.2 successful answer flow ----------------------------------------------


def test_successful_flow_completes_with_a_direct_answer_plan() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.COMPLETED
    assert result.error_code is None
    assert result.failure_phase is None
    assert authorization_port.calls == 1
    assert capability_port.calls == 1
    assert materializer.calls == 1
    assert result.answer_plan is not None
    assert result.answer_plan.answer_type == "direct"
    assert result.evidence_bundle is not None
    assert result.evidence_bundle.decision == "answer"


def test_successful_flow_preserves_injected_identifiers_and_timestamps() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.route_decision is not None
    assert result.execution_plan is not None
    assert result.evidence_bundle is not None
    assert result.answer_plan is not None
    assert result.route_decision.decision_id == ARTIFACTS.route_decision_id
    assert result.route_decision.decided_at == ARTIFACTS.route_decided_at
    assert result.execution_plan.plan_id == ARTIFACTS.execution_plan_id
    assert result.execution_plan.planned_at == ARTIFACTS.execution_plan_planned_at
    assert result.evidence_bundle.bundle_id == ARTIFACTS.evidence_bundle_id
    assert result.evidence_bundle.built_at == ARTIFACTS.evidence_bundle_built_at
    assert result.answer_plan.answer_plan_id == ARTIFACTS.answer_plan_id
    assert result.answer_plan.built_at == ARTIFACTS.answer_plan_built_at


def test_successful_flow_binds_the_capability_invocation() -> None:
    executed = step_result()
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=executed)
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    context = runtime_context()
    analysis = query_analysis()
    result = run(
        orchestrate(
            context=context,
            analysis=analysis,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    invocation = capability_port.invocations[0]
    assert invocation.context.runtime is context
    assert invocation.query_analysis is analysis
    assert invocation.route_decision is result.route_decision
    assert invocation.execution_plan is result.execution_plan
    assert invocation.execution_plan is not None
    assert invocation.step is invocation.execution_plan.steps[0]
    assert authorization_port.contexts[0] is context
    assert result.step_result is executed


def test_successful_flow_binds_the_materialization_request() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    request = materializer.requests[0]
    assert request.route_decision is result.route_decision
    assert request.execution_plan is result.execution_plan
    assert request.step_results == (result.step_result,)


def test_successful_flow_performs_no_retry_or_replan() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert (authorization_port.calls, capability_port.calls, materializer.calls) == (1, 1, 1)


# 10.3 abstention flow ------------------------------------------------------


def test_unacceptable_evidence_completes_as_an_abstention() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=unacceptable_evidence())
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.COMPLETED
    assert result.error_code is None
    assert result.evidence_bundle is not None
    assert result.evidence_bundle.decision == "abstain"
    assert result.answer_plan is not None
    assert result.answer_plan.answer_type == "abstention"
    assert capability_port.calls == 1
    assert materializer.calls == 1


# 10.4 terminal routing -----------------------------------------------------


@pytest.mark.parametrize("level", ["blocking", "non_blocking"])
def test_ambiguous_queries_stop_before_planning(level: AmbiguityLevel) -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            analysis=ambiguous_analysis(level),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.STOPPED
    assert result.route_decision is not None
    assert result.route_decision.lane == "clarify"
    assert result.execution_plan is None
    assert authorization_port.calls == 1
    assert capability_port.calls == 0
    assert materializer.calls == 0


def test_unsupported_queries_stop_with_an_abstain_lane() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            analysis=unsupported_analysis(),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.STOPPED
    assert result.route_decision is not None
    assert result.route_decision.lane == "abstain"
    assert capability_port.calls == 0
    assert materializer.calls == 0


# 10.5 authorization denial -------------------------------------------------


def test_denial_short_circuits_before_any_analysis_use() -> None:
    authorization_port = AuthorizationPortFake(decision=denied_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    mismatched_analysis = query_analysis(analysis_id=FOREIGN_ID, request_id=FOREIGN_ID)
    result = run(
        orchestrate(
            analysis=mismatched_analysis,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.DENIED
    assert result.error_code == "UNAUTHORIZED"
    assert result.failure_phase is OrchestrationFailurePhase.AUTHORIZATION
    assert result.route_decision is None
    assert result.execution_plan is None
    assert authorization_port.calls == 1
    assert capability_port.calls == 0
    assert materializer.calls == 0


# 10.6 authorization integrity and failure ----------------------------------


def test_authorization_request_mismatch_raises_value_error() -> None:
    authorization_port = AuthorizationPortFake(
        decision=authorization(request_id=FOREIGN_ID),
    )
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="request_id"):
        run(
            orchestrate(
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert capability_port.calls == 0


def test_authorization_security_context_mismatch_raises_value_error() -> None:
    authorization_port = AuthorizationPortFake(
        decision=denied_authorization(security_context_id=FOREIGN_ID),
    )
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="security_context_id"):
        run(
            orchestrate(
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert capability_port.calls == 0


def test_ordinary_authorization_exception_is_classified_internally() -> None:
    authorization_port = AuthorizationPortFake(error=RuntimeError("sentinel-secret-text"))
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "INTERNAL_ERROR"
    assert result.failure_phase is OrchestrationFailurePhase.AUTHORIZATION
    assert result.authorization is None
    assert capability_port.calls == 0
    assert materializer.calls == 0
    assert "sentinel-secret-text" not in repr(result)


# 10.7 capability configuration and exceptions ------------------------------


def test_capability_name_mismatch_fails_without_execution() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result(), name=ANALYTICS_CAPABILITY)
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "INTERNAL_ERROR"
    assert result.failure_phase is OrchestrationFailurePhase.CAPABILITY
    assert result.execution_plan is not None
    assert result.step_result is None
    assert capability_port.calls == 0
    assert materializer.calls == 0


def test_ordinary_capability_exception_is_classified_internally() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(error=RuntimeError("sentinel-secret-text"))
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "INTERNAL_ERROR"
    assert result.failure_phase is OrchestrationFailurePhase.CAPABILITY
    assert result.step_result is None
    assert capability_port.calls == 1
    assert materializer.calls == 0
    assert "sentinel-secret-text" not in repr(result)


# 10.8 step result failures -------------------------------------------------


def test_failed_step_result_is_reported_with_its_failure_code() -> None:
    failed = failed_step_result()
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=failed)
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == failed.failure_code
    assert result.failure_phase is OrchestrationFailurePhase.CAPABILITY
    assert result.step_result is failed
    assert materializer.calls == 0


def test_cross_artifact_invalid_step_result_propagates_value_error() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result(plan_id=FOREIGN_ID))
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    with pytest.raises(ValueError, match="plan_id"):
        run(
            orchestrate(
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert capability_port.calls == 1
    assert materializer.calls == 0


# 10.9 evidence materialization failures ------------------------------------


def test_ordinary_materializer_exception_is_classified_internally() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(error=RuntimeError("sentinel-secret-text"))
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "INTERNAL_ERROR"
    assert result.failure_phase is OrchestrationFailurePhase.EVIDENCE_MATERIALIZATION
    assert result.evidence_bundle is None
    assert result.answer_plan is None
    assert capability_port.calls == 1
    assert materializer.calls == 1
    assert "sentinel-secret-text" not in repr(result)


def test_invalid_evidence_provenance_propagates_value_error() -> None:
    invalid_evidence = document_evidence(
        provenance=evidence_provenance(step_result_id=FOREIGN_ID),
    )
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=(invalid_evidence,))
    with pytest.raises(ValueError, match="provenance"):
        run(
            orchestrate(
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
    assert materializer.calls == 1


# 10.10 deadline behavior ---------------------------------------------------


def test_absent_deadline_completes_normally() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=None),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.COMPLETED


def test_generous_deadline_completes_normally() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=NOW + timedelta(minutes=5)),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.COMPLETED


def test_expired_deadline_fails_before_authorization() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=NOW + timedelta(seconds=1)),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
            entered_at=NOW + timedelta(seconds=1),
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "DEPENDENCY_TIMEOUT"
    assert result.failure_phase is OrchestrationFailurePhase.RUNTIME
    assert authorization_port.calls == 0
    assert capability_port.calls == 0
    assert materializer.calls == 0


def test_timeout_while_authorization_is_blocked() -> None:
    authorization_port = AuthorizationPortFake(
        decision=allowed_authorization(),
        gate=asyncio.Event(),
    )
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=NOW + SHORT_DEADLINE),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "DEPENDENCY_TIMEOUT"
    assert result.failure_phase is OrchestrationFailurePhase.AUTHORIZATION
    assert authorization_port.observed_cancellation
    assert capability_port.calls == 0
    assert materializer.calls == 0


def test_timeout_while_the_capability_is_blocked() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result(), gate=asyncio.Event())
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=NOW + SHORT_DEADLINE),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "DEPENDENCY_TIMEOUT"
    assert result.failure_phase is OrchestrationFailurePhase.CAPABILITY
    assert capability_port.observed_cancellation
    assert materializer.calls == 0


def test_timeout_while_the_materializer_is_blocked() -> None:
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result())
    materializer = EvidenceMaterializerFake(
        evidence=accepted_evidence(),
        gate=asyncio.Event(),
    )
    result = run(
        orchestrate(
            context=runtime_context(deadline_at=NOW + SHORT_DEADLINE),
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.status is OrchestrationStatus.FAILED
    assert result.error_code == "DEPENDENCY_TIMEOUT"
    assert result.failure_phase is OrchestrationFailurePhase.EVIDENCE_MATERIALIZATION
    assert materializer.observed_cancellation


# 10.11 cancellation --------------------------------------------------------


def test_external_cancellation_propagates_unchanged() -> None:
    started = asyncio.Event()
    gate = asyncio.Event()
    authorization_port = AuthorizationPortFake(decision=allowed_authorization())
    capability_port = CapabilityPortFake(result=step_result(), started=started, gate=gate)
    materializer = EvidenceMaterializerFake(evidence=accepted_evidence())

    async def scenario() -> bool:
        task = asyncio.ensure_future(
            orchestrate(
                authorization_port=authorization_port,
                capability_port=capability_port,
                evidence_materializer=materializer,
            )
        )
        await started.wait()
        task.cancel()
        cancelled = False
        try:
            await task
        except asyncio.CancelledError:
            cancelled = True
        return cancelled and task.cancelled()

    assert asyncio.run(scenario())
    assert capability_port.observed_cancellation
    assert materializer.calls == 0


# 10.12 input immutability --------------------------------------------------


def test_orchestration_does_not_mutate_its_inputs() -> None:
    context = runtime_context()
    analysis = query_analysis()
    decision = allowed_authorization()
    executed = step_result()
    evidence = accepted_evidence()
    before = (
        context.turn_input.model_dump(),
        context.principal.model_dump(),
        context.runtime_snapshot.model_dump(),
        analysis.model_dump(),
        decision.model_dump(),
        executed.model_dump(),
        tuple(item.model_dump() for item in evidence),
    )
    authorization_port = AuthorizationPortFake(decision=decision)
    capability_port = CapabilityPortFake(result=executed)
    materializer = EvidenceMaterializerFake(evidence=evidence)
    result = run(
        orchestrate(
            context=context,
            analysis=analysis,
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    after = (
        context.turn_input.model_dump(),
        context.principal.model_dump(),
        context.runtime_snapshot.model_dump(),
        analysis.model_dump(),
        decision.model_dump(),
        executed.model_dump(),
        tuple(item.model_dump() for item in evidence),
    )
    assert before == after
    assert context.correlation_id == CORRELATION_TEXT
    assert result.status is OrchestrationStatus.COMPLETED


def test_produced_artifacts_are_not_mutated_after_completion() -> None:
    authorization_port, capability_port, materializer = successful_ports()
    result = run(
        orchestrate(
            authorization_port=authorization_port,
            capability_port=capability_port,
            evidence_materializer=materializer,
        )
    )
    assert result.route_decision is not None
    assert result.execution_plan is not None
    before = (result.route_decision.model_dump(), result.execution_plan.model_dump())
    replay = OrchestrationResult(
        status=result.status,
        authorization=result.authorization,
        route_decision=result.route_decision,
        execution_plan=result.execution_plan,
        step_result=result.step_result,
        evidence_bundle=result.evidence_bundle,
        answer_plan=result.answer_plan,
    )
    after = (result.route_decision.model_dump(), result.execution_plan.model_dump())
    assert before == after
    assert replay.status is OrchestrationStatus.COMPLETED
    assert result.execution_plan.required_facts == (DOCUMENT_FACT_ID,)


# 10.13 safety and dependency architecture ----------------------------------


def runtime_source() -> str:
    return RUNTIME_MODULE_PATH.read_text(encoding="utf-8")


def module_is_allowed(module: str) -> bool:
    if not module:
        return False
    root_name = module.split(".", 1)[0]
    if root_name in STDLIB_MODULES:
        return True
    return any(
        module == allowed or module.startswith(f"{allowed}.") for allowed in ALLOWED_PACKAGES
    )


def imported_modules(tree: ast.AST) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "runtime.py must use absolute imports"
            modules.append(node.module or "")
    return tuple(modules)


def test_runtime_module_imports_only_allowed_packages() -> None:
    tree = ast.parse(runtime_source(), filename=str(RUNTIME_MODULE_PATH))
    modules = imported_modules(tree)
    assert modules
    for module in modules:
        assert module_is_allowed(module), module
        assert module.split(".", 1)[0] not in FORBIDDEN_VENDOR_ROOTS


@pytest.mark.parametrize("fragment", list(FORBIDDEN_FRAGMENTS))
def test_runtime_module_avoids_forbidden_fragments(fragment: str) -> None:
    assert fragment not in runtime_source()


def test_runtime_module_contains_no_direct_recursion() -> None:
    tree = ast.parse(runtime_source(), filename=str(RUNTIME_MODULE_PATH))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                assert inner.func.id != node.name


def test_runtime_module_declares_no_module_level_mutable_state() -> None:
    tree = ast.parse(runtime_source(), filename=str(RUNTIME_MODULE_PATH))
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            assert not isinstance(node.value, (ast.List, ast.Dict, ast.Set))


def test_core_package_stays_import_free_and_exports_nothing() -> None:
    source = CORE_INIT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(CORE_INIT_PATH))
    assert not [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
    assert "__all__: tuple[str, ...] = ()" in source

    from ai_assistant.core import __all__ as core_exports

    assert core_exports == ()
