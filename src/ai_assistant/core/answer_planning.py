"""Deterministic AnswerPlan construction for the fast document flow."""

from datetime import datetime
from uuid import UUID

from ai_assistant.contracts import (
    AnswerCaveat,
    AnswerClaimPlan,
    AnswerLengthBudget,
    AnswerPlan,
    AnswerSection,
    AnswerSectionItemRef,
    AnswerToneConstraints,
    AnswerType,
    CitationSlot,
    EvidenceBundle,
    ExecutionPlan,
    QueryAnalysis,
    RouteDecision,
)
from ai_assistant.core.planning import _require_canonical_plan, _require_canonical_route
from ai_assistant.core.types import AuthorizedRuntimeContext

ANSWER_PLAN_BUILDER_VERSION = "1.0.0"
BUILDER_SUBJECT = "the answer plan builder"
CANONICAL_ROUTE_ERROR = "the answer plan builder supports the fast.document route only"
ANSWER_SECTION_ID = "section.answer"
ANSWER_SECTION_TYPE = "answer"
ABSTAIN_SECTION_ID = "section.abstain"
ABSTAIN_SECTION_TYPE = "abstention"
ABSTAIN_CAVEAT_ID = "caveat.abstain"
ABSTAIN_CAVEAT_CODE = "caveat.insufficient_evidence"
TONE_CODES = ("clear", "concise")
PROHIBITED_CONTENT_CODES = (
    "content.raw_evidence",
    "content.secrets",
    "claim.unsupported",
)
_LENGTH_BUDGET = AnswerLengthBudget(
    max_characters=2000,
    max_sections=1,
    max_claims=32,
    max_caveats=1,
    max_citations=32,
)


def _require_analysis_binding(context: AuthorizedRuntimeContext, analysis: QueryAnalysis) -> None:
    turn_input = context.runtime.turn_input
    if analysis.request_id != turn_input.request_id:
        raise ValueError("query analysis request_id must match the runtime context")
    if analysis.message_id != turn_input.message_id:
        raise ValueError("query analysis message_id must match the runtime context")
    if analysis.runtime_snapshot_id != context.runtime.runtime_snapshot.snapshot_id:
        raise ValueError("query analysis runtime_snapshot_id must match the runtime context")


def _require_plan_binding(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
) -> None:
    runtime = context.runtime
    if route_decision.request_id != runtime.turn_input.request_id:
        raise ValueError("route decision request_id must match the runtime context")
    if route_decision.query_analysis_id != analysis.analysis_id:
        raise ValueError("route decision query_analysis_id must match the query analysis")
    if route_decision.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("route decision authorization_decision_id must match the authorization")
    if execution_plan.route_decision_id != route_decision.decision_id:
        raise ValueError("execution plan route_decision_id must match the route decision")
    if execution_plan.request_id != runtime.turn_input.request_id:
        raise ValueError("execution plan request_id must match the runtime context")
    if execution_plan.runtime_snapshot_id != runtime.runtime_snapshot.snapshot_id:
        raise ValueError("execution plan runtime_snapshot_id must match the runtime context")
    if route_decision.runtime_snapshot_id != runtime.runtime_snapshot.snapshot_id:
        raise ValueError("route decision runtime_snapshot_id must match the runtime context")
    if execution_plan.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("execution plan authorization_decision_id must match the authorization")
    _require_canonical_fast_flow(route_decision, execution_plan)


def _require_canonical_fast_flow(
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
) -> None:
    _require_canonical_route(route_decision, route_error=CANONICAL_ROUTE_ERROR)
    _require_canonical_plan(route_decision, execution_plan, subject=BUILDER_SUBJECT)


def _require_bundle_binding(
    context: AuthorizedRuntimeContext,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    evidence_bundle: EvidenceBundle,
) -> None:
    runtime = context.runtime
    if evidence_bundle.request_id != runtime.turn_input.request_id:
        raise ValueError("evidence bundle request_id must match the runtime context")
    if evidence_bundle.route_decision_id != route_decision.decision_id:
        raise ValueError("evidence bundle route_decision_id must match the route decision")
    if evidence_bundle.plan_id != execution_plan.plan_id:
        raise ValueError("evidence bundle plan_id must match the execution plan")
    if evidence_bundle.authorization_decision_id != context.authorization.decision_id:
        raise ValueError("evidence bundle authorization_decision_id must match the authorization")
    if evidence_bundle.runtime_snapshot_id != runtime.runtime_snapshot.snapshot_id:
        raise ValueError("evidence bundle runtime_snapshot_id must match the runtime context")
    if str(evidence_bundle.correlation_id) != runtime.correlation_id:
        raise ValueError("evidence bundle correlation_id must match the runtime context")
    if evidence_bundle.required_fact_ids != execution_plan.required_facts:
        raise ValueError("evidence bundle required facts must match the execution plan")


def _mirror_claims(evidence_bundle: EvidenceBundle) -> tuple[AnswerClaimPlan, ...]:
    return tuple(
        AnswerClaimPlan(
            claim_id=claim.claim_id,
            claim_code=claim.claim_code,
            claim_type=claim.claim_type,
            subject=claim.subject,
            supporting_fact_ids=claim.supporting_fact_ids,
            evidence_ids=claim.evidence_ids,
        )
        for claim in evidence_bundle.allowed_claims
    )


def _answer_sections(claims: tuple[AnswerClaimPlan, ...]) -> tuple[AnswerSection, ...]:
    items = tuple(
        AnswerSectionItemRef(item_kind="claim", item_id=claim.claim_id) for claim in claims
    )
    return (
        AnswerSection(
            section_id=ANSWER_SECTION_ID,
            section_type=ANSWER_SECTION_TYPE,
            items=items,
        ),
    )


def _citation_slots(claims: tuple[AnswerClaimPlan, ...]) -> tuple[CitationSlot, ...]:
    return tuple(
        CitationSlot(
            slot_id=f"slot.{claim.claim_id}",
            target_kind="claim",
            target_id=claim.claim_id,
            evidence_ids=claim.evidence_ids,
            placement="inline",
        )
        for claim in claims
    )


def _abstention_caveats(evidence_bundle: EvidenceBundle) -> tuple[AnswerCaveat, ...]:
    return (
        AnswerCaveat(
            caveat_id=ABSTAIN_CAVEAT_ID,
            caveat_code=ABSTAIN_CAVEAT_CODE,
            related_claim_ids=(),
            evidence_ids=(),
            reason_codes=evidence_bundle.decision_reason_codes,
        ),
    )


def _abstention_sections() -> tuple[AnswerSection, ...]:
    return (
        AnswerSection(
            section_id=ABSTAIN_SECTION_ID,
            section_type=ABSTAIN_SECTION_TYPE,
            items=(AnswerSectionItemRef(item_kind="caveat", item_id=ABSTAIN_CAVEAT_ID),),
        ),
    )


def build_answer_plan(
    context: AuthorizedRuntimeContext,
    analysis: QueryAnalysis,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    evidence_bundle: EvidenceBundle,
    *,
    answer_plan_id: UUID,
    built_at: datetime,
) -> AnswerPlan:
    """Build the semantic answer plan authorized by one evidence bundle."""
    _require_analysis_binding(context, analysis)
    _require_plan_binding(context, analysis, route_decision, execution_plan)
    _require_bundle_binding(context, route_decision, execution_plan, evidence_bundle)
    decision = evidence_bundle.decision
    answer_type: AnswerType
    if decision == "answer":
        claims = _mirror_claims(evidence_bundle)
        sections = _answer_sections(claims)
        citation_slots = _citation_slots(claims)
        caveats: tuple[AnswerCaveat, ...] = ()
        answer_type = "direct"
    elif decision == "abstain":
        claims = ()
        caveats = _abstention_caveats(evidence_bundle)
        sections = _abstention_sections()
        citation_slots = ()
        answer_type = "abstention"
    else:
        raise ValueError("the answer plan builder supports answer and abstain decisions only")
    return AnswerPlan(
        answer_plan_id=answer_plan_id,
        request_id=context.runtime.turn_input.request_id,
        evidence_bundle_id=evidence_bundle.bundle_id,
        route_decision_id=route_decision.decision_id,
        plan_id=execution_plan.plan_id,
        authorization_decision_id=context.authorization.decision_id,
        runtime_snapshot_id=context.runtime.runtime_snapshot.snapshot_id,
        correlation_id=evidence_bundle.correlation_id,
        built_at=built_at,
        decision=decision,
        answer_type=answer_type,
        sections=sections,
        claims=claims,
        caveats=caveats,
        citation_slots=citation_slots,
        tone_constraints=AnswerToneConstraints(
            response_locale=context.runtime.turn_input.locale,
            tone_codes=TONE_CODES,
        ),
        prohibited_claim_codes=tuple(
            claim.claim_code for claim in evidence_bundle.prohibited_claims
        ),
        prohibited_content_codes=PROHIBITED_CONTENT_CODES,
        decision_reason_codes=evidence_bundle.decision_reason_codes,
        length_budget=_LENGTH_BUDGET,
        answer_plan_builder_version=ANSWER_PLAN_BUILDER_VERSION,
    )
