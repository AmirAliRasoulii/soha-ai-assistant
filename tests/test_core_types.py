"""Focused tests for private AI Core value types."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime
from uuid import UUID

import pytest

from ai_assistant.contracts import (
    AuthorizationDecision,
    AuthorizationResourceRef,
    ExecutionPlan,
    PlanFactSpec,
    PlanParallelGroup,
    PlanStep,
    QueryAnalysis,
    RouteBudget,
    RouteDecision,
    RuntimeArtifactRef,
    RuntimeSnapshot,
    RuntimeSnapshotContent,
    RuntimeSnapshotIntegrity,
    SecurityPrincipalContext,
    StepProvenance,
    StepResult,
    StepRetryMetadata,
    StepTypedOutputRef,
    TurnInput,
)
from ai_assistant.core.types import (
    AuthorizedRuntimeContext,
    CapabilityInvocation,
    EffectiveIdempotencyKey,
    EvidenceMaterializationRequest,
    IdempotencyAcquireResult,
    IdempotencyAcquireStatus,
    IdempotencyLease,
    RuntimeContext,
    RuntimeTelemetryEventName,
    RuntimeTelemetryOutcome,
    RuntimeTelemetryRecord,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
IDS = [UUID(f"{index:08d}-0000-4000-8000-000000000000") for index in range(1, 20)]
DIGEST = "sha256:" + "a" * 64
HEX_DIGEST = "a" * 64


def turn_input() -> TurnInput:
    return TurnInput(
        request_id=IDS[0],
        message_id=IDS[1],
        conversation_id=IDS[2],
        raw_message="hello",
        received_at=NOW,
        idempotency_key=IDS[3],
    )


def principal() -> SecurityPrincipalContext:
    return SecurityPrincipalContext(
        context_id=IDS[4],
        principal_id=IDS[5],
        principal_type="user",
        deployment_id=IDS[6],
        issuer="test.identity",
        authenticated_at=NOW,
        authentication_methods=("mfa",),
        assurance_level="aal2",
    )


def snapshot(snapshot_id: UUID = IDS[7], digest: str = DIGEST) -> RuntimeSnapshot:
    artifact = RuntimeArtifactRef(artifact_id="artifact", revision="1", digest=DIGEST)
    content = RuntimeSnapshotContent(
        application_version="1.0.0",
        source_revision="a" * 40,
        build_artifact=artifact,
        config_bundle=artifact,
        prompt_bundle=artifact,
        model_policy=artifact,
        model_artifacts=(artifact,),
        structured_output_backend=artifact,
        retrieval_profile=artifact,
        embedding_artifact=artifact,
        reranker_artifact=artifact,
        index_snapshot=artifact,
        semantic_catalog=artifact,
        rule_bundle=artifact,
        security_policy=artifact,
        telemetry_schema=artifact,
    )
    return RuntimeSnapshot(
        snapshot_id=snapshot_id,
        captured_at=NOW,
        content=content,
        integrity=RuntimeSnapshotIntegrity(canonicalization="rfc8785", digest=digest),
    )


def authorization(
    effect: str = "allow", request_id: UUID = IDS[0], context_id: UUID = IDS[4]
) -> AuthorizationDecision:
    return AuthorizationDecision(
        decision_id=IDS[8],
        request_id=request_id,
        security_context_id=context_id,
        action="document:read",
        resource=AuthorizationResourceRef(resource_type="document", resource_id="doc-1"),
        effect=effect,
        reason_codes=("policy.allowed",),
        policy_version="1.0.0",
        evaluated_at=NOW,
    )


def runtime_context() -> RuntimeContext:
    return RuntimeContext(turn_input(), principal(), snapshot(), str(IDS[14]), NOW)


def authorized_context() -> AuthorizedRuntimeContext:
    return AuthorizedRuntimeContext(runtime_context(), authorization())


def query_analysis() -> QueryAnalysis:
    return QueryAnalysis(
        analysis_id=IDS[9],
        request_id=IDS[0],
        message_id=IDS[1],
        runtime_snapshot_id=IDS[7],
        analyzed_at=NOW,
        normalized_query="hello",
        intent="factual",
        ambiguity_level="none",
        is_personal=False,
        is_multi_part=False,
        risk_level="normal",
        evidence_needs=("rule",),
        confidence=1.0,
        analyzer_version="1.0.0",
    )


def route_decision() -> RouteDecision:
    return RouteDecision(
        decision_id=IDS[10],
        request_id=IDS[0],
        query_analysis_id=IDS[9],
        authorization_decision_id=IDS[8],
        runtime_snapshot_id=IDS[7],
        decided_at=NOW,
        effective_risk_level="normal",
        lane="fast",
        route="fast.rule",
        allowed_capabilities=("rule_evaluator",),
        required_facts=("fact.answer",),
        planner_required=False,
        budget=RouteBudget(
            max_steps=1,
            max_parallel_steps=1,
            max_replans=0,
            max_retrieval_retries=0,
            max_analytics_repairs=0,
            max_answer_repairs=0,
        ),
        rationale_code="query.factual",
        policy_version="1.0.0",
    )


def plan() -> ExecutionPlan:
    step = PlanStep(
        step_id="step.answer",
        capability="rule_evaluator",
        operation="rule.evaluate",
        produces=(PlanFactSpec(fact_id="fact.answer", value_type="answer", data_scope="general"),),
        required=True,
    )
    return ExecutionPlan(
        plan_id=IDS[11],
        request_id=IDS[0],
        route_decision_id=IDS[10],
        authorization_decision_id=IDS[8],
        runtime_snapshot_id=IDS[7],
        planned_at=NOW,
        lane="fast",
        goal="answer.factual",
        allowed_capabilities=("rule_evaluator",),
        required_facts=("fact.answer",),
        steps=(step,),
        parallel_groups=(PlanParallelGroup(group_id="group.1", step_ids=("step.answer",)),),
        composition_type="single",
        success_condition="all_required_facts",
        missing_evidence_policy="abstain",
        budget=route_decision().budget,
        revision=0,
        plan_builder_version="1.0.0",
    )


def step_result(plan_id: UUID = IDS[11], step_id: str = "step.answer") -> StepResult:
    return StepResult(
        result_id=IDS[12],
        request_id=IDS[0],
        plan_id=plan_id,
        step_id=step_id,
        runtime_snapshot_id=IDS[7],
        correlation_id=str(IDS[14]),
        completed_at=NOW,
        status="success",
        typed_outputs=(
            StepTypedOutputRef(
                fact_id="fact.answer",
                value_type="answer",
                data_scope="general",
                schema_ref="schema:answer",
                value_ref="value:answer",
                sha256=HEX_DIGEST,
            ),
        ),
        latency_ms=1,
        retry=StepRetryMetadata(attempt=1, max_attempts=1, retryable=False),
        provenance=StepProvenance(
            capability="rule_evaluator",
            operation="rule.evaluate",
            implementation_version="1.0.0",
            input_digest=HEX_DIGEST,
        ),
    )


def test_private_dataclasses_are_frozen_and_tuple_based() -> None:
    values = [
        runtime_context(),
        authorized_context(),
        EffectiveIdempotencyKey("d", "p", "c", "s", DIGEST),
    ]
    for value in values:
        with pytest.raises((FrozenInstanceError, AttributeError, TypeError)):
            value.turn_input = turn_input()
    assert all(
        field.name not in {"metadata", "attributes", "payload"}
        for field in fields(RuntimeTelemetryRecord)
    )


def test_runtime_context_validates_time_and_correlation() -> None:
    assert runtime_context().turn_input is not None
    with pytest.raises(ValueError):
        RuntimeContext(turn_input(), principal(), snapshot(), " ", NOW)
    with pytest.raises(ValueError):
        RuntimeContext(turn_input(), principal(), snapshot(), "c", datetime(2026, 1, 1, 12))
    with pytest.raises(ValueError):
        RuntimeContext(turn_input(), principal(), snapshot(), "c", NOW, NOW)


def test_authorized_context_validates_authorization_bindings() -> None:
    assert authorized_context().authorization.effect == "allow"
    with pytest.raises(ValueError):
        AuthorizedRuntimeContext(runtime_context(), authorization("deny"))
    with pytest.raises(ValueError):
        AuthorizedRuntimeContext(runtime_context(), authorization(request_id=IDS[13]))
    with pytest.raises(ValueError):
        AuthorizedRuntimeContext(runtime_context(), authorization(context_id=IDS[13]))


def test_capability_invocation_validates_artifact_chain() -> None:
    invocation = CapabilityInvocation(
        authorized_context(), query_analysis(), route_decision(), plan(), plan().steps[0]
    )
    assert invocation.step.step_id == "step.answer"
    with pytest.raises(ValueError):
        CapabilityInvocation(
            authorized_context(),
            query_analysis(),
            route_decision(),
            plan(),
            PlanStep(
                step_id="other",
                capability="rule_evaluator",
                operation="rule.evaluate",
                produces=(
                    PlanFactSpec(fact_id="fact.other", value_type="answer", data_scope="general"),
                ),
                required=True,
            ),
        )


@pytest.mark.parametrize("field", ["request_id", "runtime_snapshot_id", "correlation_id"])
def test_evidence_materialization_rejects_mismatched_results(field: str) -> None:
    result = step_result()
    if field == "request_id":
        result = result.model_copy(update={"request_id": IDS[13]})
    elif field == "runtime_snapshot_id":
        result = result.model_copy(update={"runtime_snapshot_id": IDS[13]})
    else:
        result = result.model_copy(update={"correlation_id": IDS[15]})
    with pytest.raises(ValueError):
        EvidenceMaterializationRequest(authorized_context(), route_decision(), plan(), (result,))


def test_evidence_materialization_validates_results() -> None:
    result = step_result()
    request = EvidenceMaterializationRequest(
        authorized_context(), route_decision(), plan(), (result,)
    )
    assert request.step_results == (result,)
    with pytest.raises(ValueError):
        EvidenceMaterializationRequest(authorized_context(), route_decision(), plan(), ())
    with pytest.raises(ValueError):
        EvidenceMaterializationRequest(
            authorized_context(), route_decision(), plan(), (result, result)
        )
    with pytest.raises(ValueError):
        EvidenceMaterializationRequest(
            authorized_context(), route_decision(), plan(), (step_result(step_id="unknown"),)
        )


def test_idempotency_key_isolates_each_scope_component() -> None:
    base = EffectiveIdempotencyKey("deployment", "principal", "client", "snapshot", DIGEST)
    variants = (
        EffectiveIdempotencyKey("other", "principal", "client", "snapshot", DIGEST),
        EffectiveIdempotencyKey("deployment", "other", "client", "snapshot", DIGEST),
        EffectiveIdempotencyKey("deployment", "principal", "client", "other", DIGEST),
        EffectiveIdempotencyKey(
            "deployment", "principal", "client", "snapshot", "sha256:" + "b" * 64
        ),
    )
    assert all(base != variant for variant in variants)
    with pytest.raises(ValueError):
        EffectiveIdempotencyKey("d", "p", "c", "s", "sha256:" + "A" * 64)
    with pytest.raises(ValueError):
        IdempotencyLease("lease", base, "A" * 64)


def test_idempotency_acquire_result_states_are_closed() -> None:
    key = EffectiveIdempotencyKey("d", "p", "c", "s", DIGEST)
    lease = IdempotencyLease("lease", key, HEX_DIGEST)
    acquired = IdempotencyAcquireResult(IdempotencyAcquireStatus.ACQUIRED, lease=lease)
    assert acquired.lease == lease
    for status, kwargs in (
        (IdempotencyAcquireStatus.REPLAY, {"lease": lease}),
        (IdempotencyAcquireStatus.ACQUIRED, {}),
        (IdempotencyAcquireStatus.IN_FLIGHT, {"lease": lease}),
    ):
        with pytest.raises(ValueError):
            IdempotencyAcquireResult(status, **kwargs)


def test_telemetry_is_timezone_aware_and_low_cardinality() -> None:
    record = RuntimeTelemetryRecord(
        event_name=RuntimeTelemetryEventName.RUNTIME_COMPLETED,
        occurred_at=NOW,
        request_id="request",
        correlation_id="correlation",
        runtime_snapshot_id="snapshot",
        outcome=RuntimeTelemetryOutcome.ANSWERED,
        duration_ms=0,
    )
    assert record.duration_ms == 0
    with pytest.raises(ValueError):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_STARTED, datetime(2026, 1, 1, 12), "r", "c", "s"
        )
    with pytest.raises(ValueError):
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_FAILED, NOW, "r", "c", "s")
    with pytest.raises(ValueError):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_STARTED,
            NOW,
            "r",
            "c",
            "s",
            error_code="INTERNAL_ERROR",
        )
    with pytest.raises(ValueError):
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_COMPLETED, NOW, "r", "c", "s")
    assert not {field.name for field in fields(record)}.intersection(
        {
            "raw_message",
            "prompt",
            "content",
            "evidence",
            "secret",
            "token",
            "payload",
            "metadata",
            "attributes",
            "details",
        }
    )
