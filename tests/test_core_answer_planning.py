"""Tests for deterministic answer plan construction."""

from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
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
    SNAPSHOT_ID,
    answer_plan,
    authorized_context,
    evidence_bundle,
    execution_plan,
    fact_spec,
    parallel_group,
    plan_step,
    query_analysis,
    route_budget,
    route_decision,
    route_filter,
    terminal_route_decision,
)

from ai_assistant.contracts import EvidenceDecision, ProhibitedEvidenceClaim
from ai_assistant.core.answer_planning import build_answer_plan


def _build(**overrides: object):
    arguments = {
        "context": authorized_context(),
        "analysis": query_analysis(),
        "route_decision": route_decision(),
        "execution_plan": execution_plan(),
        "evidence_bundle": evidence_bundle(),
    }
    arguments.update(overrides)
    return build_answer_plan(
        arguments["context"],
        arguments["analysis"],
        arguments["route_decision"],
        arguments["execution_plan"],
        arguments["evidence_bundle"],
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )


def test_answer_bundle_produces_a_direct_answer_plan() -> None:
    plan = _build()
    assert plan.answer_plan_id == ANSWER_PLAN_ID
    assert plan.built_at == NOW
    assert plan.request_id == REQUEST_ID
    assert plan.evidence_bundle_id == BUNDLE_ID
    assert plan.route_decision_id == ROUTE_DECISION_ID
    assert plan.plan_id == PLAN_ID
    assert plan.authorization_decision_id == AUTHORIZATION_ID
    assert plan.runtime_snapshot_id == SNAPSHOT_ID
    assert plan.correlation_id == CORRELATION_ID
    assert plan.decision == "answer"
    assert plan.answer_type == "direct"
    assert plan.caveats == ()
    assert plan.answer_plan_builder_version == "1.0.0"


def test_allowed_claims_are_mirrored_exactly() -> None:
    bundle = evidence_bundle()
    plan = _build(evidence_bundle=bundle)
    assert len(plan.claims) == len(bundle.allowed_claims)
    claim = plan.claims[0]
    source = bundle.allowed_claims[0]
    assert claim.claim_id == source.claim_id
    assert claim.claim_code == source.claim_code
    assert claim.claim_type == source.claim_type
    assert claim.subject == source.subject
    assert claim.supporting_fact_ids == source.supporting_fact_ids
    assert claim.evidence_ids == source.evidence_ids


def test_answer_plan_declares_one_answer_section() -> None:
    plan = _build()
    assert len(plan.sections) == 1
    section = plan.sections[0]
    assert section.section_id == "section.answer"
    assert section.section_type == "answer"
    assert tuple(item.item_id for item in section.items) == ("claim.document",)
    assert all(item.item_kind == "claim" for item in section.items)


def test_every_claim_receives_one_inline_citation_slot() -> None:
    plan = _build()
    assert len(plan.citation_slots) == len(plan.claims)
    slot = plan.citation_slots[0]
    assert slot.slot_id == "slot.claim.document"
    assert slot.target_kind == "claim"
    assert slot.target_id == "claim.document"
    assert slot.evidence_ids == (EVIDENCE_ID,)
    assert slot.placement == "inline"


def test_tone_constraints_follow_the_turn_locale() -> None:
    plan = _build()
    assert plan.tone_constraints.response_locale == "fa-IR"
    assert plan.tone_constraints.tone_codes == ("clear", "concise")


def test_length_budget_is_fixed_for_the_walking_skeleton() -> None:
    budget = _build().length_budget
    assert budget.max_characters == 2000
    assert budget.max_sections == 1
    assert budget.max_claims == 32
    assert budget.max_caveats == 1
    assert budget.max_citations == 32


def test_prohibited_content_codes_are_always_declared() -> None:
    plan = _build()
    assert plan.prohibited_content_codes == (
        "content.raw_evidence",
        "content.secrets",
        "claim.unsupported",
    )


def test_prohibited_claim_codes_come_from_the_bundle() -> None:
    prohibited = (
        ProhibitedEvidenceClaim(
            claim_code="claim.speculative",
            reason_codes=("claim.unsupported",),
        ),
    )
    plan = _build(evidence_bundle=evidence_bundle(prohibited_claims=prohibited))
    assert plan.prohibited_claim_codes == ("claim.speculative",)


def test_decision_reason_codes_come_from_the_bundle() -> None:
    plan = _build()
    assert plan.decision_reason_codes == ("evidence.complete",)


def test_answer_plan_construction_is_deterministic() -> None:
    assert _build() == _build()


def test_answer_plan_matches_the_expected_contract_shape() -> None:
    assert _build() == answer_plan()


def test_answer_plan_never_carries_raw_input_or_evidence_content() -> None:
    serialized = _build().model_dump_json()
    assert "sentinel-raw-message" not in serialized
    assert "sentinel-content-ref" not in serialized
    assert "sentinel-document-ref" not in serialized


def test_abstain_bundle_produces_an_abstention_plan() -> None:
    plan = _build(evidence_bundle=evidence_bundle(decision="abstain"))
    assert plan.decision == "abstain"
    assert plan.answer_type == "abstention"
    assert plan.claims == ()
    assert plan.citation_slots == ()
    assert plan.decision_reason_codes == ("evidence.empty",)


def test_abstention_plan_declares_one_caveat() -> None:
    plan = _build(evidence_bundle=evidence_bundle(decision="abstain"))
    assert len(plan.caveats) == 1
    caveat = plan.caveats[0]
    assert caveat.caveat_id == "caveat.abstain"
    assert caveat.caveat_code == "caveat.insufficient_evidence"
    assert caveat.related_claim_ids == ()
    assert caveat.evidence_ids == ()
    assert caveat.reason_codes == ("evidence.empty",)


def test_abstention_section_references_the_caveat_once() -> None:
    plan = _build(evidence_bundle=evidence_bundle(decision="abstain"))
    assert len(plan.sections) == 1
    section = plan.sections[0]
    assert section.section_id == "section.abstain"
    assert section.section_type == "abstention"
    assert len(section.items) == 1
    assert section.items[0].item_kind == "caveat"
    assert section.items[0].item_id == "caveat.abstain"


@pytest.mark.parametrize("decision", ["partial_answer", "clarify"])
def test_unsupported_bundle_decisions_are_rejected(decision: EvidenceDecision) -> None:
    with pytest.raises(ValueError, match="answer and abstain decisions only"):
        _build(evidence_bundle=evidence_bundle(decision=decision))


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "query analysis request_id must match the runtime context"),
        ("message_id", "query analysis message_id must match the runtime context"),
        ("snapshot_id", "query analysis runtime_snapshot_id must match the runtime context"),
    ],
)
def test_mismatched_analysis_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        _build(analysis=query_analysis(**overrides))


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "route decision request_id must match the runtime context"),
        ("analysis_id", "route decision query_analysis_id must match the query analysis"),
        (
            "authorization_id",
            "route decision authorization_decision_id must match the authorization",
        ),
    ],
)
def test_mismatched_route_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        _build(route_decision=route_decision(**overrides))


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("route_decision_id", "execution plan route_decision_id must match the route decision"),
        ("request_id", "execution plan request_id must match the runtime context"),
        ("snapshot_id", "execution plan runtime_snapshot_id must match the runtime context"),
    ],
)
def test_mismatched_plan_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        _build(execution_plan=execution_plan(**overrides))


@pytest.mark.parametrize(
    ("field", "expected_message"),
    [
        ("request_id", "evidence bundle request_id must match the runtime context"),
        ("route_decision_id", "evidence bundle route_decision_id must match the route decision"),
        (
            "authorization_id",
            "evidence bundle authorization_decision_id must match the authorization",
        ),
        ("snapshot_id", "evidence bundle runtime_snapshot_id must match the runtime context"),
        ("correlation_id", "evidence bundle correlation_id must match the runtime context"),
    ],
)
def test_mismatched_bundle_lineage_is_rejected(field: str, expected_message: str) -> None:
    overrides: dict[str, UUID] = {field: FOREIGN_ID}
    with pytest.raises(ValueError, match=expected_message):
        _build(evidence_bundle=evidence_bundle(**overrides))


def test_bundle_bound_to_a_foreign_plan_is_rejected() -> None:
    with pytest.raises(ValueError, match="evidence bundle plan_id must match the execution plan"):
        _build(evidence_bundle=evidence_bundle(decision="abstain", plan_id=FOREIGN_ID))


def test_bundle_with_foreign_required_facts_is_rejected() -> None:
    with pytest.raises(ValueError, match="required facts must match the execution plan"):
        _build(
            evidence_bundle=evidence_bundle(
                decision="abstain",
                required_fact_ids=("fact.other",),
            )
        )


def test_injected_identifier_and_timestamp_are_used_verbatim() -> None:
    plan = build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        evidence_bundle(),
        answer_plan_id=FOREIGN_ID,
        built_at=NOW,
    )
    assert plan.answer_plan_id == FOREIGN_ID
    assert plan.built_at == NOW
    assert plan.claims[0].supporting_fact_ids == (DOCUMENT_FACT_ID,)


def test_foreign_route_runtime_snapshot_is_rejected() -> None:
    with pytest.raises(ValueError, match="route decision runtime_snapshot_id must match"):
        _build(route_decision=route_decision(snapshot_id=FOREIGN_ID))


def test_foreign_execution_plan_authorization_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan authorization_decision_id must match"):
        _build(execution_plan=execution_plan(authorization_id=FOREIGN_ID))


def test_non_fast_route_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"supports the fast\.document route only"):
        _build(route_decision=terminal_route_decision())


def test_unknown_fast_route_code_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"supports the fast\.document route only"):
        _build(route_decision=route_decision(route="fast.official"))


def test_route_and_plan_lane_mismatch_is_rejected() -> None:
    with pytest.raises(ValueError, match="execution plan lane must match the route decision"):
        _build(execution_plan=execution_plan(lane="deterministic"))


def test_route_and_plan_capability_mismatch_is_rejected() -> None:
    plan = execution_plan(
        capabilities=("semantic_analytics",),
        steps=(plan_step(capability="semantic_analytics", operation="analytics.run"),),
    )
    with pytest.raises(ValueError, match="allowed_capabilities must match the route decision"):
        _build(execution_plan=plan)


def test_route_and_plan_required_fact_mismatch_is_rejected() -> None:
    plan = execution_plan(
        required_facts=("fact.other",),
        steps=(plan_step(produces=(fact_spec(fact_id="fact.other"),)),),
    )
    with pytest.raises(ValueError, match="required facts must match the route decision"):
        _build(execution_plan=plan)


def test_route_and_plan_budget_mismatch_is_rejected() -> None:
    plan = execution_plan(budget=route_budget(max_retrieval_retries=1))
    with pytest.raises(ValueError, match="execution plan budget must match the route decision"):
        _build(execution_plan=plan)


def test_non_single_step_route_budget_is_rejected() -> None:
    decision = route_decision(budget=route_budget(max_retrieval_retries=1))
    with pytest.raises(ValueError, match="requires the single step budget"):
        _build(route_decision=decision)


def test_route_carrying_filters_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not carry filters"):
        _build(route_decision=route_decision(filters=(route_filter(),)))


def test_high_risk_route_is_rejected() -> None:
    decision = route_decision(
        effective_risk_level="high",
        approved_flow_ref="flow:approved-1",
    )
    with pytest.raises(ValueError, match="requires a normal effective risk level"):
        _build(route_decision=decision)


def test_wrong_route_rationale_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical rationale code"):
        _build(route_decision=route_decision(rationale_code="query.other_reason"))


def test_wrong_route_policy_version_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical policy version"):
        _build(route_decision=route_decision(policy_version="2.0.0"))


def test_wrong_route_required_facts_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires exactly the document fact"):
        _build(route_decision=route_decision(required_facts=("fact.other",)))


def test_wrong_route_capability_is_rejected() -> None:
    decision = route_decision(capabilities=("semantic_analytics",))
    with pytest.raises(ValueError, match="requires the document_retrieval capability"):
        _build(route_decision=decision)


def test_personal_plan_fact_scope_is_rejected() -> None:
    plan = execution_plan(steps=(plan_step(produces=(fact_spec(data_scope="personal"),)),))
    with pytest.raises(ValueError, match="requires the canonical document fact"):
        _build(execution_plan=plan)


def test_wrong_plan_fact_value_type_is_rejected() -> None:
    plan = execution_plan(steps=(plan_step(produces=(fact_spec(value_type="type.other"),)),))
    with pytest.raises(ValueError, match="requires the canonical document fact"):
        _build(execution_plan=plan)


def test_wrong_parallel_group_is_rejected() -> None:
    plan = execution_plan(parallel_groups=(parallel_group(group_id="group.other"),))
    with pytest.raises(ValueError, match="requires the canonical parallel group"):
        _build(execution_plan=plan)


def test_wrong_plan_goal_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical plan goal"):
        _build(execution_plan=execution_plan(goal="goal.other"))


def test_wrong_missing_evidence_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="requires the canonical plan policies"):
        _build(execution_plan=execution_plan(missing_evidence_policy="clarify"))


def test_non_canonical_retrieval_step_is_rejected() -> None:
    plan = execution_plan(steps=(plan_step(operation="document.search"),))
    with pytest.raises(ValueError, match="requires the canonical retrieval step"):
        _build(execution_plan=plan)
