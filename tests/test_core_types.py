"""Focused tests for private AI Core value types."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ai_assistant.contracts import (
    AuthorizationDecision,
    AuthorizationResourceRef,
    ErrorEnvelope,
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
IDS = [UUID(f"{index:08d}-0000-4000-8000-000000000000") for index in range(1, 40)]
DIGEST = "sha256:" + "a" * 64
HEX_DIGEST = "a" * 64


def turn_input(request_id: UUID = IDS[0], message_id: UUID = IDS[1]) -> TurnInput:
    return TurnInput(
        request_id=request_id,
        message_id=message_id,
        conversation_id=IDS[2],
        raw_message="hello",
        received_at=NOW,
        idempotency_key=IDS[3],
    )


def principal(context_id: UUID = IDS[4]) -> SecurityPrincipalContext:
    return SecurityPrincipalContext(
        context_id=context_id,
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
    decision_id: UUID = IDS[8],
    effect: str = "allow",
    request_id: UUID = IDS[0],
    context_id: UUID = IDS[4],
) -> AuthorizationDecision:
    return AuthorizationDecision(
        decision_id=decision_id,
        request_id=request_id,
        security_context_id=context_id,
        action="document:read",
        resource=AuthorizationResourceRef(resource_type="document", resource_id="doc-1"),
        effect=effect,
        reason_codes=("policy.allowed",),
        policy_version="1.0.0",
        evaluated_at=NOW,
    )


def runtime_context(
    correlation_id: str = str(IDS[14]),
    started_at: datetime = NOW,
    deadline_at: datetime | None = None,
) -> RuntimeContext:
    return RuntimeContext(
        turn_input(), principal(), snapshot(), correlation_id, started_at, deadline_at
    )


def authorized_context(
    runtime: RuntimeContext | None = None,
    auth: AuthorizationDecision | None = None,
) -> AuthorizedRuntimeContext:
    runtime = runtime or runtime_context()
    return AuthorizedRuntimeContext(runtime, auth or authorization())


def query_analysis(
    request_id: UUID = IDS[0], message_id: UUID = IDS[1], snapshot_id: UUID = IDS[7]
) -> QueryAnalysis:
    return QueryAnalysis(
        analysis_id=IDS[9],
        request_id=request_id,
        message_id=message_id,
        runtime_snapshot_id=snapshot_id,
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


def route_decision(
    decision_id: UUID = IDS[10],
    request_id: UUID = IDS[0],
    query_id: UUID = IDS[9],
    authorization_id: UUID = IDS[8],
    snapshot_id: UUID = IDS[7],
    capability: str = "rule_evaluator",
) -> RouteDecision:
    return RouteDecision(
        decision_id=decision_id,
        request_id=request_id,
        query_analysis_id=query_id,
        authorization_decision_id=authorization_id,
        runtime_snapshot_id=snapshot_id,
        decided_at=NOW,
        effective_risk_level="normal",
        lane="fast",
        route="fast.rule",
        allowed_capabilities=(capability,),
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


def plan(
    plan_id: UUID = IDS[11],
    request_id: UUID = IDS[0],
    route_id: UUID = IDS[10],
    authorization_id: UUID = IDS[8],
    snapshot_id: UUID = IDS[7],
    capability: str = "rule_evaluator",
    operation: str = "rule.evaluate",
) -> ExecutionPlan:
    step = PlanStep(
        step_id="step.answer",
        capability=capability,
        operation=operation,
        produces=(PlanFactSpec(fact_id="fact.answer", value_type="answer", data_scope="general"),),
        required=True,
    )
    return ExecutionPlan(
        plan_id=plan_id,
        request_id=request_id,
        route_decision_id=route_id,
        authorization_decision_id=authorization_id,
        runtime_snapshot_id=snapshot_id,
        planned_at=NOW,
        lane="fast",
        goal="answer.factual",
        allowed_capabilities=(capability,),
        required_facts=("fact.answer",),
        steps=(step,),
        parallel_groups=(PlanParallelGroup(group_id="group.1", step_ids=("step.answer",)),),
        composition_type="single",
        success_condition="all_required_facts",
        missing_evidence_policy="abstain",
        budget=route_decision(capability=capability).budget,
        revision=0,
        plan_builder_version="1.0.0",
    )


def step_result(
    result_id: UUID = IDS[12],
    request_id: UUID = IDS[0],
    plan_id: UUID = IDS[11],
    step_id: str = "step.answer",
    snapshot_id: UUID = IDS[7],
    correlation_id: UUID = IDS[14],
    capability: str = "rule_evaluator",
    operation: str = "rule.evaluate",
) -> StepResult:
    return StepResult(
        result_id=result_id,
        request_id=request_id,
        plan_id=plan_id,
        step_id=step_id,
        runtime_snapshot_id=snapshot_id,
        correlation_id=correlation_id,
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
            capability=capability,
            operation=operation,
            implementation_version="1.0.0",
            input_digest=HEX_DIGEST,
        ),
    )


def error_envelope() -> ErrorEnvelope:
    return ErrorEnvelope(
        error_id=IDS[20],
        correlation_id=IDS[14],
        error={
            "code": "INVALID_INPUT",
            "safe_message_key": "error.invalid_input",
            "retryable": False,
            "internal_detail_ref": IDS[21],
        },
    )


def test_private_dataclasses_are_frozen_slotted_and_reject_real_field_assignment() -> None:
    values = [
        runtime_context(),
        authorized_context(),
        CapabilityInvocation(
            authorized_context(), query_analysis(), route_decision(), plan(), plan().steps[0]
        ),
        EvidenceMaterializationRequest(
            authorized_context(), route_decision(), plan(), (step_result(),)
        ),
        EffectiveIdempotencyKey("d", "p", "c", "s", DIGEST),
        IdempotencyLease("lease", EffectiveIdempotencyKey("d", "p", "c", "s", DIGEST), HEX_DIGEST),
        IdempotencyAcquireResult(IdempotencyAcquireStatus.IN_FLIGHT),
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_STARTED, NOW, "r", "c", "s"),
    ]
    for value in values:
        assert value.__dataclass_params__.frozen is True
        assert hasattr(value, "__slots__")
        declared_field = fields(value)[0]
        with pytest.raises(FrozenInstanceError):
            setattr(value, declared_field.name, getattr(value, declared_field.name))


def test_runtime_context_time_and_correlation_invariants() -> None:
    assert runtime_context(deadline_at=NOW + timedelta(seconds=1)).deadline_at is not None
    cases = (
        (" ", NOW, None),
        ("c", datetime(2026, 1, 1, 12), None),
        ("c", NOW, datetime(2026, 1, 1, 12)),
        ("c", NOW, NOW - timedelta(seconds=1)),
        ("c", NOW, NOW + timedelta(seconds=1)),
    )
    for correlation, started, deadline in cases[:-1]:
        with pytest.raises(ValueError):
            runtime_context(correlation, started, deadline)


def test_authorized_context_validates_authorization_bindings() -> None:
    assert authorized_context().authorization.effect == "allow"
    with pytest.raises(ValueError):
        authorized_context(auth=authorization(effect="deny"))
    with pytest.raises(ValueError):
        authorized_context(auth=authorization(request_id=IDS[13]))
    with pytest.raises(ValueError):
        authorized_context(auth=authorization(context_id=IDS[13]))


def test_capability_invocation_validates_each_artifact_binding() -> None:
    def valid(**kwargs: object) -> CapabilityInvocation:
        query_kwargs = kwargs.get("query", {})
        route_kwargs = kwargs.get("route", {})
        plan_kwargs = kwargs.get("plan", {})
        assert isinstance(query_kwargs, dict)
        assert isinstance(route_kwargs, dict)
        assert isinstance(plan_kwargs, dict)
        return CapabilityInvocation(
            authorized_context(),
            query_analysis(**query_kwargs),
            route_decision(**route_kwargs),
            plan(**plan_kwargs),
            plan(**plan_kwargs).steps[0],
        )

    valid()
    cases = (
        {"query": {"request_id": IDS[13]}},
        {"query": {"message_id": IDS[13]}},
        {"query": {"snapshot_id": IDS[13]}},
        {"route": {"authorization_id": IDS[13]}},
        {"route": {"query_id": IDS[13]}},
        {"plan": {"route_id": IDS[13]}},
        {"plan": {"authorization_id": IDS[13]}},
        {"plan": {"snapshot_id": IDS[13]}},
        {"route": {"capability": "document_retrieval"}},
    )
    for case in cases:
        with pytest.raises(ValueError):
            valid(**case)
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


def test_evidence_materialization_validates_bindings_and_provenance() -> None:
    context = authorized_context()
    valid = EvidenceMaterializationRequest(context, route_decision(), plan(), (step_result(),))
    assert valid.step_results
    cases = (
        (),
        (step_result(request_id=IDS[13]),),
        (step_result(plan_id=IDS[13]),),
        (step_result(snapshot_id=IDS[13]),),
        (step_result(correlation_id=IDS[15]),),
        (step_result(step_id="unknown"),),
        (step_result(), step_result(result_id=IDS[13])),
        (step_result(), step_result(result_id=IDS[13], capability="rule_evaluator")),
        (step_result(capability="document_retrieval"),),
        (step_result(operation="rule.other"),),
    )
    for results in cases:
        with pytest.raises(ValueError):
            EvidenceMaterializationRequest(context, route_decision(), plan(), results)


def test_idempotency_result_state_matrix_and_closed_values() -> None:
    key = EffectiveIdempotencyKey("d", "p", "c", "s", DIGEST)
    lease = IdempotencyLease("lease", key, HEX_DIGEST)
    outcome = error_envelope()
    valid = (
        IdempotencyAcquireResult(IdempotencyAcquireStatus.ACQUIRED, lease=lease),
        IdempotencyAcquireResult(IdempotencyAcquireStatus.REPLAY, outcome=outcome),
        IdempotencyAcquireResult(IdempotencyAcquireStatus.IN_FLIGHT),
        IdempotencyAcquireResult(IdempotencyAcquireStatus.CONFLICT),
    )
    assert len(valid) == 4
    for status in IdempotencyAcquireStatus:
        for invalid_lease, invalid_outcome in ((lease, None), (None, outcome), (lease, outcome)):
            if (
                status == IdempotencyAcquireStatus.ACQUIRED
                and invalid_lease is lease
                and invalid_outcome is None
            ) or (
                status == IdempotencyAcquireStatus.REPLAY
                and invalid_lease is None
                and invalid_outcome is outcome
            ):
                continue
            with pytest.raises(ValueError):
                IdempotencyAcquireResult(status, invalid_lease, invalid_outcome)
    with pytest.raises(ValueError):
        IdempotencyAcquireResult("replay", outcome=outcome)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        IdempotencyAcquireResult(IdempotencyAcquireStatus.REPLAY, outcome=object())  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        IdempotencyLease("lease", key, "A" * 64)
    with pytest.raises(ValueError):
        EffectiveIdempotencyKey("d", "p", "c", "s", "sha256:" + "A" * 64)
    assert hash(key) == hash(key)


@pytest.mark.parametrize("component", range(5))
@given(st.text(alphabet="0123456789abcdef", min_size=1, max_size=12))
def test_idempotency_key_hash_and_equality_isolation(component: int, value: str) -> None:
    base = ["deployment", "principal", "client", "snapshot", DIGEST]
    changed = base.copy()
    changed[component] = value if component < 4 else "sha256:" + (value + "a" * 64)[:64]
    if changed == base:
        changed[component] = "other" if component < 4 else "sha256:" + "b" * 64
    left = EffectiveIdempotencyKey(*base)
    right = EffectiveIdempotencyKey(*changed)
    assert left != right
    assert hash(left) != hash(right)


def test_telemetry_validation_is_closed_and_safe() -> None:
    assert RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_STARTED, NOW, "r", "c", "s")
    assert RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_COMPLETED,
        NOW,
        "r",
        "c",
        "s",
        outcome=RuntimeTelemetryOutcome.ANSWERED,
    )
    assert RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_FAILED, NOW, "r", "c", "s", error_code="INTERNAL_ERROR"
    )
    invalid = (
        (datetime(2026, 1, 1, 12), "r", "c", "s"),
        (NOW, " ", "c", "s"),
        (NOW, "r", " ", "s"),
        (NOW, "r", "c", " "),
    )
    for timestamp, request, correlation, snapshot_id in invalid:
        with pytest.raises(ValueError):
            RuntimeTelemetryRecord(
                RuntimeTelemetryEventName.RUNTIME_STARTED,
                timestamp,
                request,
                correlation,
                snapshot_id,
            )
    for kwargs in (
        {"duration_ms": -1},
        {"event_name": RuntimeTelemetryEventName.RUNTIME_FAILED},
        {"event_name": RuntimeTelemetryEventName.RUNTIME_STARTED, "error_code": "INTERNAL_ERROR"},
        {"event_name": RuntimeTelemetryEventName.RUNTIME_COMPLETED},
        {"event_name": "runtime_started"},
        {"outcome": "answered"},
        {"capability": "unknown"},
        {"error_code": "UNKNOWN"},
        {"authorization_decision_id": " "},
    ):
        values = {
            "event_name": RuntimeTelemetryEventName.RUNTIME_STARTED,
            "occurred_at": NOW,
            "request_id": "r",
            "correlation_id": "c",
            "runtime_snapshot_id": "s",
        }
        values.update(kwargs)
        with pytest.raises(ValueError):
            RuntimeTelemetryRecord(**values)  # type: ignore[arg-type]
    assert not {field.name for field in fields(RuntimeTelemetryRecord)}.intersection(
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
