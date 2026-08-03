"""Tests for deterministic evidence bundle construction."""

import pytest
from support.walking_skeleton_fixtures import (
    AUTHORIZATION_ID,
    BUNDLE_ID,
    CORRELATION_ID,
    DOCUMENT_FACT_ID,
    EVIDENCE_ID,
    FOREIGN_ID,
    NOW,
    PLAN_ID,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SECOND_EVIDENCE_ID,
    SECOND_FACT_ID,
    SNAPSHOT_ID,
    authorized_context,
    deterministic_two_step_plan,
    document_evidence,
    evidence_provenance,
    evidence_ref,
    execution_plan,
    fact_spec,
    failed_step_result,
    parallel_group,
    plan_step,
    route_decision,
    route_filter,
    sql_evidence,
    step_result,
    terminal_route_decision,
    two_fact_execution_plan,
    typed_output,
)

from ai_assistant.contracts import DocumentEvidence, Evidence, StepResult
from ai_assistant.core.evidence_manager import build_evidence_bundle

BOTH_FACTS = (DOCUMENT_FACT_ID, SECOND_FACT_ID)


def _bundle(
    *,
    result: StepResult | None = None,
    evidence: tuple[Evidence, ...] = (),
    plan_facts_are_paired: bool = False,
):
    plan = two_fact_execution_plan() if plan_facts_are_paired else execution_plan()
    return build_evidence_bundle(
        authorized_context(),
        route_decision(),
        plan,
        (result if result is not None else step_result(),),
        evidence,
        bundle_id=BUNDLE_ID,
        built_at=NOW,
    )


def _two_fact_success_result() -> StepResult:
    return step_result(
        typed_outputs=(typed_output(), typed_output(fact_id=SECOND_FACT_ID)),
        evidence_refs=(
            evidence_ref(supports_fact_ids=(DOCUMENT_FACT_ID,)),
            evidence_ref(evidence_id=SECOND_EVIDENCE_ID, supports_fact_ids=(SECOND_FACT_ID,)),
        ),
    )


def test_complete_evidence_produces_an_answer_bundle() -> None:
    bundle = _bundle(evidence=(document_evidence(),))
    assert bundle.decision == "answer"
    assert bundle.sufficient is True
    assert bundle.decision_reason_codes == ("evidence.complete",)
    assert bundle.missing_fact_ids == ()
    assert bundle.rejected_evidence == ()
    assert bundle.conflicts == ()
    assert bundle.prohibited_claims == ()
    assert bundle.evidence_manager_version == "1.0.0"


def test_answer_bundle_carries_the_full_lineage() -> None:
    bundle = _bundle(evidence=(document_evidence(),))
    assert bundle.bundle_id == BUNDLE_ID
    assert bundle.built_at == NOW
    assert bundle.request_id == REQUEST_ID
    assert bundle.route_decision_id == ROUTE_DECISION_ID
    assert bundle.plan_id == PLAN_ID
    assert bundle.authorization_decision_id == AUTHORIZATION_ID
    assert bundle.runtime_snapshot_id == SNAPSHOT_ID
    assert bundle.correlation_id == CORRELATION_ID
    assert bundle.required_fact_ids == (DOCUMENT_FACT_ID,)


def test_answer_bundle_declares_one_document_claim() -> None:
    bundle = _bundle(evidence=(document_evidence(),))
    assert len(bundle.allowed_claims) == 1
    claim = bundle.allowed_claims[0]
    assert claim.claim_id == "claim.document"
    assert claim.claim_code == "claim.document"
    assert claim.claim_type == "factual"
    assert claim.supporting_fact_ids == (DOCUMENT_FACT_ID,)
    assert claim.evidence_ids == (EVIDENCE_ID,)


def test_fact_map_maps_every_required_fact() -> None:
    bundle = _bundle(evidence=(document_evidence(),))
    assert len(bundle.fact_map) == 1
    assert bundle.fact_map[0].fact_id == DOCUMENT_FACT_ID
    assert bundle.fact_map[0].evidence_ids == (EVIDENCE_ID,)


def test_two_fact_plan_is_rejected() -> None:
    # The R1 build accepted a plan whose required facts differed from the
    # route: WS-002 now refuses it before any candidate is inspected.
    with pytest.raises(ValueError, match="required facts must match the route decision"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            two_fact_execution_plan(),
            (_two_fact_success_result(),),
            (
                document_evidence(
                    evidence_id=SECOND_EVIDENCE_ID,
                    supports_fact_ids=(SECOND_FACT_ID,),
                ),
                document_evidence(),
            ),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_bundle_construction_is_deterministic() -> None:
    first = _bundle(evidence=(document_evidence(),))
    second = _bundle(evidence=(document_evidence(),))
    assert first == second


def test_bundle_construction_does_not_mutate_inputs() -> None:
    result = step_result()
    evidence = document_evidence()
    before = (result.model_dump(), evidence.model_dump())
    _bundle(result=result, evidence=(evidence,))
    assert (result.model_dump(), evidence.model_dump()) == before


def test_degraded_evidence_is_rejected_and_forces_abstention() -> None:
    bundle = _bundle(evidence=(document_evidence(validation_status="degraded"),))
    assert bundle.decision == "abstain"
    assert bundle.sufficient is False
    assert bundle.allowed_claims == ()
    assert bundle.accepted_evidence == ()
    assert bundle.decision_reason_codes == ("evidence.no_acceptable_basis",)
    assert bundle.rejected_evidence[0].reason_codes == ("evidence.degraded",)


@pytest.mark.parametrize("freshness", ["stale", "unknown"])
def test_evidence_that_is_not_current_is_rejected(freshness: str) -> None:
    bundle = _bundle(evidence=(document_evidence(freshness=freshness),))
    assert bundle.rejected_evidence[0].reason_codes == ("evidence.not_current",)
    assert bundle.decision == "abstain"


def test_rejection_reason_codes_use_a_deterministic_order() -> None:
    bundle = _bundle(evidence=(document_evidence(validation_status="degraded", freshness="stale"),))
    assert bundle.rejected_evidence[0].reason_codes == (
        "evidence.degraded",
        "evidence.not_current",
    )


def test_rejection_records_never_carry_raw_content() -> None:
    bundle = _bundle(evidence=(document_evidence(freshness="stale"),))
    record = bundle.rejected_evidence[0]
    assert set(record.model_dump()) == {"evidence_id", "evidence_type", "reason_codes"}
    assert record.evidence_type == "document"
    assert "sentinel-content-ref" not in record.model_dump_json()


def test_missing_candidate_evidence_produces_an_empty_basis() -> None:
    bundle = _bundle(result=step_result(evidence_refs=()), evidence=())
    assert bundle.decision == "abstain"
    assert bundle.decision_reason_codes == ("evidence.empty",)
    assert bundle.missing_fact_ids == (DOCUMENT_FACT_ID,)


def test_failed_step_result_produces_an_empty_basis() -> None:
    bundle = _bundle(result=failed_step_result(), evidence=())
    assert bundle.decision == "abstain"
    assert bundle.decision_reason_codes == ("evidence.empty",)


def test_partial_step_result_against_the_canonical_plan_is_rejected() -> None:
    # A partial result must miss a planned fact; the canonical plan declares
    # exactly one fact, so any partial result fails the partition rule.
    result = step_result(
        status="partial",
        typed_outputs=(typed_output(),),
        missing_fact_ids=(SECOND_FACT_ID,),
        failure_code="INTERNAL_ERROR",
    )
    with pytest.raises(ValueError, match="must partition the planned facts exactly"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            execution_plan(),
            (result,),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_plan_group_identifier_is_rejected() -> None:
    plan = execution_plan(parallel_groups=(parallel_group(group_id="group.other"),))
    with pytest.raises(ValueError, match="requires the canonical parallel group"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_plan_goal_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical plan goal"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            execution_plan(goal="goal.other"),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_missing_evidence_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical plan policies"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            execution_plan(missing_evidence_policy="clarify"),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_plan_builder_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical plan builder version"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            execution_plan(plan_builder_version="2.0.0"),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_route_carrying_filters_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not carry filters"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(filters=(route_filter(),)),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_high_risk_route_is_rejected() -> None:
    decision = route_decision(
        effective_risk_level="high",
        approved_flow_ref="flow:approved-1",
    )
    with pytest.raises(ValueError, match="requires a normal effective risk level"):
        build_evidence_bundle(
            authorized_context(),
            decision,
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_route_rationale_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical rationale code"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(rationale_code="query.other_reason"),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_wrong_route_policy_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical policy version"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(policy_version="2.0.0"),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_non_document_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="accepts document evidence only"):
        _bundle(evidence=(sql_evidence(),))


def test_unreferenced_candidate_evidence_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be referenced by the step result"):
        _bundle(evidence=(document_evidence(evidence_id=SECOND_EVIDENCE_ID),))


def test_unresolved_evidence_reference_is_rejected() -> None:
    with pytest.raises(ValueError, match="must resolve to candidate evidence"):
        _bundle(evidence=())


def test_duplicate_candidate_identifiers_are_rejected() -> None:
    with pytest.raises(ValueError, match="identifiers must be unique"):
        _bundle(evidence=(document_evidence(), document_evidence()))


@pytest.mark.parametrize(
    "provenance",
    [
        evidence_provenance(step_result_id=FOREIGN_ID),
        evidence_provenance(plan_id=FOREIGN_ID),
        evidence_provenance(step_id="step.other"),
        evidence_provenance(operation="document.search"),
    ],
)
def test_mismatched_evidence_provenance_is_rejected(provenance: object) -> None:
    with pytest.raises(ValueError, match="provenance must match the executed step"):
        _bundle(evidence=(document_evidence(provenance=provenance),))


def test_plan_fact_value_type_must_be_canonical() -> None:
    plan = execution_plan(steps=(plan_step(produces=(fact_spec(value_type="type.other"),)),))
    result = step_result(typed_outputs=(typed_output(value_type="type.other"),))
    with pytest.raises(ValueError, match="requires the canonical document fact"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (result,),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_plan_fact_identifier_must_be_canonical() -> None:
    plan = execution_plan(
        required_facts=("fact.other",),
        steps=(plan_step(produces=(fact_spec(fact_id="fact.other"),)),),
    )
    result = step_result(
        typed_outputs=(typed_output(fact_id="fact.other"),),
        evidence_refs=(evidence_ref(supports_fact_ids=("fact.other",)),),
    )
    with pytest.raises(ValueError, match="required facts must match the route decision"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (result,),
            (document_evidence(supports_fact_ids=("fact.other",)),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_multiple_evidence_subjects_are_rejected() -> None:
    result = step_result(
        evidence_refs=(
            evidence_ref(),
            evidence_ref(evidence_id=SECOND_EVIDENCE_ID),
        )
    )
    evidence: tuple[Evidence, ...] = (
        document_evidence(),
        document_evidence(evidence_id=SECOND_EVIDENCE_ID, subject_ref="subject:document-2"),
    )
    with pytest.raises(ValueError, match="one identical evidence subject"):
        _bundle(result=result, evidence=evidence)


def test_multiple_accepted_documents_support_one_claim() -> None:
    result = step_result(
        evidence_refs=(
            evidence_ref(),
            evidence_ref(evidence_id=SECOND_EVIDENCE_ID),
        )
    )
    evidence: tuple[Evidence, ...] = (
        document_evidence(),
        document_evidence(evidence_id=SECOND_EVIDENCE_ID),
    )
    bundle = _bundle(result=result, evidence=evidence)
    assert bundle.decision == "answer"
    assert bundle.fact_map[0].evidence_ids == (EVIDENCE_ID, SECOND_EVIDENCE_ID)
    assert bundle.allowed_claims[0].evidence_ids == (EVIDENCE_ID, SECOND_EVIDENCE_ID)


def test_non_uuid_correlation_identifier_is_rejected() -> None:
    with pytest.raises(ValueError, match="correlation_id must be a UUID"):
        build_evidence_bundle(
            authorized_context(correlation_id="not-a-uuid"),
            route_decision(),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_terminal_route_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"supports the fast\.document route only"):
        build_evidence_bundle(
            authorized_context(),
            terminal_route_decision(),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_unknown_fast_route_code_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"supports the fast\.document route only"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(route="fast.official"),
            execution_plan(),
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_multiple_step_results_are_rejected() -> None:
    with pytest.raises(ValueError, match="exactly one step result"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            execution_plan(),
            (step_result(), step_result()),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_deterministic_multi_step_plan_is_rejected() -> None:
    plan = deterministic_two_step_plan()
    with pytest.raises(ValueError, match="execution plan lane must match the route decision"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (step_result(),),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_non_canonical_retrieval_step_is_rejected() -> None:
    plan = execution_plan(steps=(plan_step(operation="document.search"),))
    with pytest.raises(ValueError, match="canonical retrieval step"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (step_result(operation="document.search"),),
            (document_evidence(provenance=evidence_provenance(operation="document.search")),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_accepted_evidence_keeps_the_document_contract_type() -> None:
    bundle = _bundle(evidence=(document_evidence(),))
    assert all(isinstance(item, DocumentEvidence) for item in bundle.accepted_evidence)


def test_personal_evidence_cannot_satisfy_a_general_fact() -> None:
    with pytest.raises(ValueError, match="data_scope must match the planned fact"):
        _bundle(evidence=(document_evidence(data_scope="personal"),))


def test_personal_plan_fact_scope_is_rejected() -> None:
    plan = execution_plan(steps=(plan_step(produces=(fact_spec(data_scope="personal"),)),))
    result = step_result(typed_outputs=(typed_output(data_scope="personal"),))
    with pytest.raises(ValueError, match="requires the canonical document fact"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (result,),
            (document_evidence(),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_matching_personal_scope_is_still_rejected() -> None:
    # R1 accepted a personal plan fact paired with personal evidence. WS-002
    # authorizes exactly one plan fact, so the whole flow is refused.
    plan = execution_plan(steps=(plan_step(produces=(fact_spec(data_scope="personal"),)),))
    result = step_result(typed_outputs=(typed_output(data_scope="personal"),))
    with pytest.raises(ValueError, match="requires the canonical document fact"):
        build_evidence_bundle(
            authorized_context(),
            route_decision(),
            plan,
            (result,),
            (document_evidence(data_scope="personal"),),
            bundle_id=BUNDLE_ID,
            built_at=NOW,
        )


def test_evidence_without_the_answer_use_is_rejected() -> None:
    bundle = _bundle(evidence=(document_evidence(allowed_uses=("use.audit",)),))
    assert bundle.decision == "abstain"
    assert bundle.sufficient is False
    assert bundle.accepted_evidence == ()
    assert bundle.allowed_claims == ()
    assert bundle.decision_reason_codes == ("evidence.no_acceptable_basis",)
    assert bundle.rejected_evidence[0].reason_codes == ("evidence.use_not_allowed",)


def test_evidence_with_the_answer_use_is_accepted() -> None:
    bundle = _bundle(evidence=(document_evidence(allowed_uses=("use.answer", "use.audit")),))
    assert bundle.decision == "answer"
    assert bundle.accepted_evidence[0].evidence_id == EVIDENCE_ID
    assert bundle.rejected_evidence == ()


def test_all_rejection_reasons_use_the_canonical_order() -> None:
    bundle = _bundle(
        evidence=(
            document_evidence(
                validation_status="degraded",
                freshness="stale",
                allowed_uses=("use.audit",),
            ),
        )
    )
    assert bundle.rejected_evidence[0].reason_codes == (
        "evidence.degraded",
        "evidence.not_current",
        "evidence.use_not_allowed",
    )
    assert bundle.decision == "abstain"


def test_one_acceptable_document_still_supports_an_answer() -> None:
    result = step_result(
        evidence_refs=(
            evidence_ref(),
            evidence_ref(evidence_id=SECOND_EVIDENCE_ID),
        )
    )
    evidence: tuple[Evidence, ...] = (
        document_evidence(),
        document_evidence(evidence_id=SECOND_EVIDENCE_ID, allowed_uses=("use.audit",)),
    )
    bundle = _bundle(result=result, evidence=evidence)
    assert bundle.decision == "answer"
    assert tuple(item.evidence_id for item in bundle.accepted_evidence) == (EVIDENCE_ID,)
    assert bundle.rejected_evidence[0].evidence_id == SECOND_EVIDENCE_ID
