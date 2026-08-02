"""Focused tests for private AI Core value types."""

from dataclasses import FrozenInstanceError, fields
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from hypothesis import assume, given, settings
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
    TerminalOutcome,
)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
NAIVE_NOW = datetime(2026, 1, 1, 12, 0)
IDS = [UUID(f"{index:08d}-0000-4000-8000-000000000000") for index in range(1, 40)]
DIGEST = "sha256:" + "a" * 64
HEX_DIGEST = "a" * 64
HEX_ALPHABET = "0123456789abcdef"
IDENTIFIER_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789-"
CAPABILITY = "rule_evaluator"
OPERATION = "rule.evaluate"
FIRST_STEP_ID = "step.answer"
SECOND_STEP_ID = "step.support"


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
    capability: str = CAPABILITY,
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
    capability: str = CAPABILITY,
    operation: str = OPERATION,
) -> ExecutionPlan:
    step = PlanStep(
        step_id=FIRST_STEP_ID,
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
        parallel_groups=(PlanParallelGroup(group_id="group.1", step_ids=(FIRST_STEP_ID,)),),
        composition_type="single",
        success_condition="all_required_facts",
        missing_evidence_policy="abstain",
        budget=route_decision(capability=capability).budget,
        revision=0,
        plan_builder_version="1.0.0",
    )


def two_step_plan() -> ExecutionPlan:
    first = PlanStep(
        step_id=FIRST_STEP_ID,
        capability=CAPABILITY,
        operation=OPERATION,
        produces=(PlanFactSpec(fact_id="fact.answer", value_type="answer", data_scope="general"),),
        required=True,
    )
    second = PlanStep(
        step_id=SECOND_STEP_ID,
        capability=CAPABILITY,
        operation=OPERATION,
        produces=(PlanFactSpec(fact_id="fact.support", value_type="answer", data_scope="general"),),
        required=True,
    )
    return ExecutionPlan(
        plan_id=IDS[11],
        request_id=IDS[0],
        route_decision_id=IDS[10],
        authorization_decision_id=IDS[8],
        runtime_snapshot_id=IDS[7],
        planned_at=NOW,
        lane="composite",
        goal="answer.factual",
        allowed_capabilities=(CAPABILITY,),
        required_facts=("fact.answer", "fact.support"),
        steps=(first, second),
        parallel_groups=(
            PlanParallelGroup(group_id="group.1", step_ids=(FIRST_STEP_ID, SECOND_STEP_ID)),
        ),
        composition_type="aggregate",
        success_condition="all_required_facts",
        missing_evidence_policy="abstain",
        budget=RouteBudget(
            max_steps=2,
            max_parallel_steps=2,
            max_replans=0,
            max_retrieval_retries=0,
            max_analytics_repairs=0,
            max_answer_repairs=0,
        ),
        revision=0,
        plan_builder_version="1.0.0",
    )


def step_result(
    result_id: UUID = IDS[12],
    request_id: UUID = IDS[0],
    plan_id: UUID = IDS[11],
    step_id: str = FIRST_STEP_ID,
    snapshot_id: UUID = IDS[7],
    correlation_id: UUID = IDS[14],
    capability: str = CAPABILITY,
    operation: str = OPERATION,
    fact_id: str = "fact.answer",
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
                fact_id=fact_id,
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


def idempotency_key(
    deployment_id: str = "deployment",
    principal_id: str = "principal",
    client_key: str = "client",
    runtime_snapshot_id: str = "snapshot",
    runtime_snapshot_digest: str = DIGEST,
) -> EffectiveIdempotencyKey:
    return EffectiveIdempotencyKey(
        deployment_id,
        principal_id,
        client_key,
        runtime_snapshot_id,
        runtime_snapshot_digest,
    )


def idempotency_lease(lease_id: str = "lease") -> IdempotencyLease:
    return IdempotencyLease(lease_id, idempotency_key(), HEX_DIGEST)


def telemetry_optional_ids(
    authorization_decision_id: str | None = None,
    plan_id: str | None = None,
    step_id: str | None = None,
) -> RuntimeTelemetryRecord:
    return RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_STARTED,
        NOW,
        "request",
        "correlation",
        "snapshot",
        authorization_decision_id=authorization_decision_id,
        plan_id=plan_id,
        step_id=step_id,
    )


def telemetry_required_ids(
    request_id: str = "request",
    correlation_id: str = "correlation",
    runtime_snapshot_id: str = "snapshot",
) -> RuntimeTelemetryRecord:
    return RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_STARTED,
        NOW,
        request_id,
        correlation_id,
        runtime_snapshot_id,
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


def test_runtime_context_rejects_blank_correlation_id() -> None:
    with pytest.raises(ValueError, match="correlation_id must be non-empty"):
        runtime_context(correlation_id=" ")


def test_runtime_context_rejects_naive_started_at() -> None:
    with pytest.raises(ValueError, match="started_at must be timezone-aware"):
        runtime_context(started_at=NAIVE_NOW)


def test_runtime_context_rejects_naive_deadline_at() -> None:
    with pytest.raises(ValueError, match="deadline_at must be timezone-aware"):
        runtime_context(started_at=NOW, deadline_at=NAIVE_NOW)


def test_runtime_context_rejects_deadline_earlier_than_started_at() -> None:
    with pytest.raises(ValueError, match="deadline_at must be later than started_at"):
        runtime_context(started_at=NOW, deadline_at=NOW - timedelta(seconds=1))


def test_runtime_context_rejects_deadline_equal_to_started_at() -> None:
    with pytest.raises(ValueError, match="deadline_at must be later than started_at"):
        runtime_context(started_at=NOW, deadline_at=NOW)


def test_runtime_context_accepts_deadline_later_than_started_at() -> None:
    context = runtime_context(started_at=NOW, deadline_at=NOW + timedelta(seconds=1))
    assert context.deadline_at == NOW + timedelta(seconds=1)
    assert context.started_at == NOW


def test_authorized_context_validates_authorization_bindings() -> None:
    assert authorized_context().authorization.effect == "allow"
    with pytest.raises(ValueError, match="authorization must allow the operation"):
        authorized_context(auth=authorization(effect="deny"))
    with pytest.raises(ValueError, match="authorization request_id and turn request_id"):
        authorized_context(auth=authorization(request_id=IDS[13]))
    with pytest.raises(ValueError, match="security_context_id"):
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
    with pytest.raises(ValueError, match="step must belong to execution_plan"):
        CapabilityInvocation(
            authorized_context(),
            query_analysis(),
            route_decision(),
            plan(),
            PlanStep(
                step_id="other",
                capability=CAPABILITY,
                operation=OPERATION,
                produces=(
                    PlanFactSpec(fact_id="fact.other", value_type="answer", data_scope="general"),
                ),
                required=True,
            ),
        )


def test_evidence_materialization_accepts_valid_single_result() -> None:
    request = EvidenceMaterializationRequest(
        authorized_context(), route_decision(), plan(), (step_result(),)
    )
    assert len(request.step_results) == 1


@pytest.mark.parametrize(
    ("results", "message"),
    [
        ((), "step_results must be non-empty"),
        (
            (step_result(request_id=IDS[13]),),
            "step result request_id must match runtime context",
        ),
        ((step_result(plan_id=IDS[13]),), "step result plan_id must match execution plan"),
        (
            (step_result(snapshot_id=IDS[13]),),
            "step result runtime_snapshot_id must match runtime context",
        ),
        (
            (step_result(correlation_id=IDS[15]),),
            "step result correlation_id must match runtime context",
        ),
        (
            (step_result(step_id="unknown"),),
            "step result must refer to a step present in execution_plan",
        ),
        (
            (step_result(capability="document_retrieval"),),
            "step result capability must match the plan step",
        ),
        (
            (step_result(operation="rule.other"),),
            "step result operation must match the plan step",
        ),
    ],
)
def test_evidence_materialization_rejects_invalid_lineage(
    results: tuple[StepResult, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        EvidenceMaterializationRequest(authorized_context(), route_decision(), plan(), results)


def test_evidence_materialization_rejects_duplicate_result_ids() -> None:
    context = authorized_context()
    route = route_decision()
    execution_plan = two_step_plan()
    first = step_result(result_id=IDS[12], step_id=FIRST_STEP_ID, fact_id="fact.answer")
    second = step_result(result_id=IDS[12], step_id=SECOND_STEP_ID, fact_id="fact.support")

    assert first.result_id == second.result_id
    assert first.step_id != second.step_id
    assert EvidenceMaterializationRequest(context, route, execution_plan, (first,)).step_results
    assert EvidenceMaterializationRequest(context, route, execution_plan, (second,)).step_results

    with pytest.raises(ValueError, match="step result IDs must be unique"):
        EvidenceMaterializationRequest(context, route, execution_plan, (first, second))


def test_evidence_materialization_rejects_two_results_for_one_step() -> None:
    context = authorized_context()
    route = route_decision()
    execution_plan = two_step_plan()
    first = step_result(result_id=IDS[12], step_id=FIRST_STEP_ID, fact_id="fact.answer")
    second = step_result(result_id=IDS[13], step_id=FIRST_STEP_ID, fact_id="fact.answer")

    assert first.result_id != second.result_id
    assert first.step_id == second.step_id
    assert EvidenceMaterializationRequest(context, route, execution_plan, (first,)).step_results
    assert EvidenceMaterializationRequest(context, route, execution_plan, (second,)).step_results

    with pytest.raises(ValueError, match="only one step result is permitted per plan step"):
        EvidenceMaterializationRequest(context, route, execution_plan, (first, second))


VALID_IDEMPOTENCY_STATES: dict[IdempotencyAcquireStatus, tuple[bool, bool]] = {
    IdempotencyAcquireStatus.ACQUIRED: (True, False),
    IdempotencyAcquireStatus.REPLAY: (False, True),
    IdempotencyAcquireStatus.IN_FLIGHT: (False, False),
    IdempotencyAcquireStatus.CONFLICT: (False, False),
}

IDEMPOTENCY_STATE_MATRIX: tuple[tuple[IdempotencyAcquireStatus, bool, bool], ...] = tuple(
    (status, with_lease, with_outcome)
    for status in IdempotencyAcquireStatus
    for with_lease in (False, True)
    for with_outcome in (False, True)
)


def test_idempotency_state_matrix_is_exhaustive() -> None:
    assert len(IDEMPOTENCY_STATE_MATRIX) == 16
    assert len(set(IDEMPOTENCY_STATE_MATRIX)) == 16
    assert set(VALID_IDEMPOTENCY_STATES) == set(IdempotencyAcquireStatus)


@pytest.mark.parametrize(("status", "with_lease", "with_outcome"), IDEMPOTENCY_STATE_MATRIX)
def test_idempotency_result_state_matrix(
    status: IdempotencyAcquireStatus, with_lease: bool, with_outcome: bool
) -> None:
    lease: IdempotencyLease | None = idempotency_lease() if with_lease else None
    outcome: TerminalOutcome | None = error_envelope() if with_outcome else None
    if VALID_IDEMPOTENCY_STATES[status] == (with_lease, with_outcome):
        result = IdempotencyAcquireResult(status, lease, outcome)
        assert result.status is status
        assert (result.lease is not None) is with_lease
        assert (result.outcome is not None) is with_outcome
    else:
        with pytest.raises(ValueError, match="idempotency result state does not match status"):
            IdempotencyAcquireResult(status, lease, outcome)


def test_idempotency_result_rejects_raw_string_status() -> None:
    with pytest.raises(ValueError, match="status must be an IdempotencyAcquireStatus"):
        IdempotencyAcquireResult("replay", outcome=error_envelope())  # type: ignore[arg-type]


def test_idempotency_result_rejects_arbitrary_outcome_object() -> None:
    with pytest.raises(ValueError, match="outcome must be a FinalAnswer or ErrorEnvelope"):
        IdempotencyAcquireResult(
            IdempotencyAcquireStatus.REPLAY,
            outcome=object(),  # type: ignore[arg-type]
        )


def test_idempotency_result_accepts_error_envelope_replay_outcome() -> None:
    outcome = error_envelope()
    result = IdempotencyAcquireResult(IdempotencyAcquireStatus.REPLAY, outcome=outcome)
    assert result.outcome is outcome
    assert result.lease is None


def test_idempotency_lease_and_key_reject_non_lowercase_digests() -> None:
    with pytest.raises(ValueError, match="request_fingerprint must be a lowercase SHA-256 digest"):
        IdempotencyLease("lease", idempotency_key(), "A" * 64)
    with pytest.raises(
        ValueError, match="runtime_snapshot_digest must be a lowercase SHA-256 digest"
    ):
        idempotency_key(runtime_snapshot_digest="sha256:" + "A" * 64)


@pytest.mark.parametrize(
    "field_name", ["deployment_id", "principal_id", "client_key", "runtime_snapshot_id"]
)
def test_idempotency_key_rejects_blank_identifiers(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be non-empty"):
        idempotency_key(**{field_name: " "})


def test_idempotency_key_hash_is_stable_for_equal_values() -> None:
    assert idempotency_key() == idempotency_key()
    assert hash(idempotency_key()) == hash(idempotency_key())


KEY_COMPONENTS = (
    "deployment_id",
    "principal_id",
    "client_key",
    "runtime_snapshot_id",
    "runtime_snapshot_digest",
)


def _as_snapshot_digest(hex_value: str) -> str:
    return "sha256:" + hex_value


identifier_values = st.text(alphabet=IDENTIFIER_ALPHABET, min_size=1, max_size=12)
digest_values = st.text(alphabet=HEX_ALPHABET, min_size=64, max_size=64).map(_as_snapshot_digest)


@settings(max_examples=50, deadline=None)
@given(
    component=st.sampled_from(KEY_COMPONENTS),
    identifier=identifier_values,
    digest=digest_values,
)
def test_idempotency_key_component_isolation(component: str, identifier: str, digest: str) -> None:
    left = idempotency_key()
    replacement = digest if component == "runtime_snapshot_digest" else identifier
    assume(replacement != getattr(left, component))
    right = idempotency_key(**{component: replacement})

    assert left != right
    assert isinstance(hash(left), int)
    assert isinstance(hash(right), int)
    assert len({left, right}) == 2

    mapping = {left: "left", right: "right"}
    assert mapping[left] == "left"
    assert mapping[right] == "right"
    assert len(mapping) == 2


def test_telemetry_accepts_valid_lifecycle_records() -> None:
    started = RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_STARTED, NOW, "r", "c", "s")
    completed = RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_COMPLETED,
        NOW,
        "r",
        "c",
        "s",
        outcome=RuntimeTelemetryOutcome.ANSWERED,
    )
    failed = RuntimeTelemetryRecord(
        RuntimeTelemetryEventName.RUNTIME_FAILED, NOW, "r", "c", "s", error_code="INTERNAL_ERROR"
    )
    assert started.event_name is RuntimeTelemetryEventName.RUNTIME_STARTED
    assert completed.outcome is RuntimeTelemetryOutcome.ANSWERED
    assert failed.error_code == "INTERNAL_ERROR"


def test_telemetry_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="occurred_at must be timezone-aware"):
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_STARTED, NAIVE_NOW, "r", "c", "s")


def test_telemetry_rejects_negative_duration() -> None:
    with pytest.raises(ValueError, match="duration_ms must be non-negative"):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_STARTED, NOW, "r", "c", "s", duration_ms=-1
        )


@pytest.mark.parametrize("field_name", ["request_id", "correlation_id", "runtime_snapshot_id"])
def test_telemetry_rejects_blank_required_ids(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be non-empty"):
        telemetry_required_ids(**{field_name: " "})


@pytest.mark.parametrize("field_name", ["authorization_decision_id", "plan_id", "step_id"])
def test_telemetry_rejects_blank_optional_ids(field_name: str) -> None:
    with pytest.raises(ValueError, match=f"{field_name} must be non-empty"):
        telemetry_optional_ids(**{field_name: " "})


@pytest.mark.parametrize("field_name", ["authorization_decision_id", "plan_id", "step_id"])
def test_telemetry_accepts_populated_optional_ids(field_name: str) -> None:
    record = telemetry_optional_ids(**{field_name: "value"})
    assert getattr(record, field_name) == "value"


def test_telemetry_failed_event_requires_error_code() -> None:
    with pytest.raises(ValueError, match="runtime_failed requires an error_code"):
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_FAILED, NOW, "r", "c", "s")


def test_telemetry_non_failure_event_rejects_error_code() -> None:
    with pytest.raises(ValueError, match="non-failure events must not carry an error_code"):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_STARTED,
            NOW,
            "r",
            "c",
            "s",
            error_code="INTERNAL_ERROR",
        )


def test_telemetry_completed_event_requires_outcome() -> None:
    with pytest.raises(ValueError, match="runtime_completed requires an outcome"):
        RuntimeTelemetryRecord(RuntimeTelemetryEventName.RUNTIME_COMPLETED, NOW, "r", "c", "s")


def test_telemetry_rejects_raw_string_event_name() -> None:
    with pytest.raises(ValueError, match="event_name must be a RuntimeTelemetryEventName"):
        RuntimeTelemetryRecord("runtime_started", NOW, "r", "c", "s")  # type: ignore[arg-type]


def test_telemetry_rejects_raw_string_outcome() -> None:
    with pytest.raises(ValueError, match="outcome must be a RuntimeTelemetryOutcome"):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_COMPLETED,
            NOW,
            "r",
            "c",
            "s",
            outcome="answered",  # type: ignore[arg-type]
        )


def test_telemetry_rejects_unknown_capability() -> None:
    with pytest.raises(ValueError, match="capability must be a legal CapabilityName"):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_STARTED,
            NOW,
            "r",
            "c",
            "s",
            capability="unknown",  # type: ignore[arg-type]
        )


def test_telemetry_rejects_unknown_error_code() -> None:
    with pytest.raises(ValueError, match="error_code must be a legal ErrorCode"):
        RuntimeTelemetryRecord(
            RuntimeTelemetryEventName.RUNTIME_FAILED,
            NOW,
            "r",
            "c",
            "s",
            error_code="UNKNOWN",  # type: ignore[arg-type]
        )


def test_telemetry_record_declares_no_content_bearing_fields() -> None:
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
