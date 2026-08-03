"""Tests for deterministic step result validation."""

from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    DOCUMENT_FACT_ID,
    FOREIGN_ID,
    SECOND_FACT_ID,
    authorized_context,
    deterministic_two_step_plan,
    evidence_ref,
    execution_plan,
    failed_step_result,
    retry_metadata,
    route_budget,
    route_decision,
    route_filter,
    step_result,
    terminal_route_decision,
    two_fact_execution_plan,
    typed_output,
)

from ai_assistant.core.step_validation import validate_step_result


def test_valid_success_result_is_returned_unchanged() -> None:
    result = step_result()
    validated = validate_step_result(
        authorized_context(), route_decision(), execution_plan(), result
    )
    assert validated is result


def test_validation_does_not_mutate_the_step_result() -> None:
    result = step_result()
    before = result.model_dump()
    validate_step_result(authorized_context(), route_decision(), execution_plan(), result)
    assert result.model_dump() == before


def test_two_fact_plan_is_rejected_before_result_validation() -> None:
    # WS-002 authorizes one canonical plan: a second required fact is refused
    # even though the result itself is a valid partial result.
    result = step_result(
        status="partial",
        typed_outputs=(typed_output(),),
        missing_fact_ids=(SECOND_FACT_ID,),
        failure_code="INTERNAL_ERROR",
    )
    with pytest.raises(ValueError, match="required facts must match the route decision"):
        validate_step_result(
            authorized_context(), route_decision(), two_fact_execution_plan(), result
        )


def test_valid_failed_result_is_accepted() -> None:
    result = failed_step_result()
    validated = validate_step_result(
        authorized_context(), route_decision(), execution_plan(), result
    )
    assert validated is result


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "step result request_id must match the runtime context"),
        ("plan_id", "step result plan_id must match the execution plan"),
        ("snapshot_id", "step result runtime_snapshot_id must match the runtime context"),
        ("correlation_id", "step result correlation_id must match the runtime context"),
    ],
)
def test_mismatched_result_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(),
            step_result(**overrides),
        )


def test_mismatched_route_request_is_rejected() -> None:
    with pytest.raises(ValueError, match="route decision request_id must match"):
        validate_step_result(
            authorized_context(),
            route_decision(request_id=FOREIGN_ID),
            execution_plan(),
            step_result(),
        )


def test_mismatched_route_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="route decision authorization_decision_id must match"):
        validate_step_result(
            authorized_context(),
            route_decision(authorization_id=FOREIGN_ID),
            execution_plan(),
            step_result(),
        )


def test_plan_that_does_not_bind_to_the_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan route_decision_id must match"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(route_decision_id=FOREIGN_ID),
            step_result(),
        )


def test_plan_with_foreign_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan authorization_decision_id must match"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(authorization_id=FOREIGN_ID),
            step_result(),
        )


def test_plan_with_foreign_snapshot_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan runtime_snapshot_id must match"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(snapshot_id=FOREIGN_ID),
            step_result(),
        )


def test_result_for_an_unknown_step_is_rejected() -> None:
    with pytest.raises(ValueError, match="must refer to a step declared by the execution plan"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(),
            step_result(step_id="step.unknown", evidence_refs=()),
        )


def test_capability_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="step result capability must match the plan step"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(),
            step_result(capability="semantic_analytics"),
        )


def test_operation_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="step result operation must match the plan step"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            execution_plan(),
            step_result(operation="document.search"),
        )


def test_undeclared_typed_output_is_rejected() -> None:
    result = step_result(
        typed_outputs=(typed_output(fact_id="fact.undeclared"),),
        evidence_refs=(evidence_ref(supports_fact_ids=("fact.undeclared",)),),
    )
    with pytest.raises(ValueError, match="must not produce an undeclared fact"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_value_type_mismatch_is_rejected() -> None:
    result = step_result(typed_outputs=(typed_output(value_type="type.summary"),))
    with pytest.raises(ValueError, match="value_type must match the planned fact"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_data_scope_mismatch_is_rejected() -> None:
    result = step_result(typed_outputs=(typed_output(data_scope="personal"),))
    with pytest.raises(ValueError, match="data_scope must match the planned fact"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_unknown_missing_fact_is_rejected() -> None:
    result = step_result(
        status="partial",
        typed_outputs=(typed_output(),),
        missing_fact_ids=("fact.unknown",),
        failure_code="INTERNAL_ERROR",
    )
    with pytest.raises(ValueError, match="must partition the planned facts exactly"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_partial_result_that_misses_an_unplanned_fact_is_rejected() -> None:
    result = step_result(
        status="partial",
        typed_outputs=(typed_output(),),
        missing_fact_ids=(SECOND_FACT_ID,),
        failure_code="INTERNAL_ERROR",
    )
    with pytest.raises(ValueError, match="must partition the planned facts exactly"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_deterministic_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan lane must match the route decision"):
        validate_step_result(
            authorized_context(),
            route_decision(),
            deterministic_two_step_plan(),
            step_result(),
        )


def test_route_carrying_filters_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not carry filters"):
        validate_step_result(
            authorized_context(),
            route_decision(filters=(route_filter(),)),
            execution_plan(),
            step_result(),
        )


def test_high_risk_route_is_rejected() -> None:
    decision = route_decision(
        effective_risk_level="high",
        approved_flow_ref="flow:approved-1",
    )
    with pytest.raises(ValueError, match="requires a normal effective risk level"):
        validate_step_result(authorized_context(), decision, execution_plan(), step_result())


def test_terminal_route_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"supports the fast\.document route only"):
        validate_step_result(
            authorized_context(),
            terminal_route_decision(),
            execution_plan(),
            step_result(),
        )


def test_plan_budget_mismatch_is_rejected() -> None:
    plan = execution_plan(budget=route_budget(max_retrieval_retries=1))
    with pytest.raises(ValueError, match="execution plan budget must match the route decision"):
        validate_step_result(authorized_context(), route_decision(), plan, step_result())


def test_non_canonical_plan_goal_is_rejected() -> None:
    plan = execution_plan(goal="goal.other")
    with pytest.raises(ValueError, match="requires the canonical plan goal"):
        validate_step_result(authorized_context(), route_decision(), plan, step_result())


def test_contract_rejects_a_fact_that_is_both_produced_and_missing() -> None:
    with pytest.raises(ValueError):
        step_result(
            status="partial",
            typed_outputs=(typed_output(),),
            missing_fact_ids=(DOCUMENT_FACT_ID,),
            failure_code="INTERNAL_ERROR",
        )


def test_multi_attempt_budget_is_rejected() -> None:
    result = step_result(retry=retry_metadata(max_attempts=2))
    with pytest.raises(ValueError, match="exactly one final attempt"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_second_attempt_is_rejected() -> None:
    result = step_result(
        retry=retry_metadata(attempt=2, max_attempts=2, previous_result_id=FOREIGN_ID)
    )
    with pytest.raises(ValueError, match="exactly one final attempt"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_retryable_result_is_rejected() -> None:
    result = step_result(
        status="failed",
        typed_outputs=(),
        missing_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_refs=(),
        failure_code="DEPENDENCY_TIMEOUT",
        retry=retry_metadata(max_attempts=2, retryable=True),
    )
    with pytest.raises(ValueError, match="exactly one final attempt"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)


def test_previous_result_reference_is_rejected() -> None:
    result = step_result(
        retry=retry_metadata(attempt=2, max_attempts=2, previous_result_id=FOREIGN_ID)
    )
    with pytest.raises(ValueError, match="exactly one final attempt"):
        validate_step_result(authorized_context(), route_decision(), execution_plan(), result)
