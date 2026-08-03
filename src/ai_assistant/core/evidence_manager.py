"""Deterministic evidence bundle construction for the fast document flow."""

from datetime import datetime
from uuid import UUID

from ai_assistant.contracts import (
    AllowedEvidenceClaim,
    DocumentEvidence,
    Evidence,
    EvidenceBundle,
    EvidenceDecision,
    ExecutionPlan,
    FactEvidenceMapEntry,
    PlanStep,
    RejectedEvidenceRef,
    RouteDecision,
    StepResult,
)
from ai_assistant.core.planning import _require_canonical_plan, _require_canonical_route
from ai_assistant.core.step_validation import validate_step_result
from ai_assistant.core.types import AuthorizedRuntimeContext

EVIDENCE_MANAGER_VERSION = "1.0.0"
DOCUMENT_CLAIM_ID = "claim.document"
DOCUMENT_CLAIM_CODE = "claim.document"
DOCUMENT_CLAIM_TYPE = "factual"
DEGRADED_REASON = "evidence.degraded"
NOT_CURRENT_REASON = "evidence.not_current"
COMPLETE_REASON = "evidence.complete"
EMPTY_REASON = "evidence.empty"
NO_ACCEPTABLE_BASIS_REASON = "evidence.no_acceptable_basis"
MISSING_REQUIRED_FACT_REASON = "evidence.missing_required_fact"
INCOMPLETE_STEP_REASON = "step.incomplete"
USE_NOT_ALLOWED_REASON = "evidence.use_not_allowed"
ANSWER_USE = "use.answer"
FLOW_SUBJECT = "the fast document flow"
CANONICAL_ROUTE_ERROR = "the evidence manager supports the fast.document route only"


def _require_fast_document_flow(
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    step_results: tuple[StepResult, ...],
) -> PlanStep:
    _require_canonical_route(route_decision, route_error=CANONICAL_ROUTE_ERROR)
    step = _require_canonical_plan(route_decision, execution_plan, subject=FLOW_SUBJECT)
    if len(step_results) != 1:
        raise ValueError("the fast document flow requires exactly one step result")
    return step


def _parse_correlation_id(context: AuthorizedRuntimeContext) -> UUID:
    try:
        return UUID(context.runtime.correlation_id)
    except ValueError as error:
        raise ValueError("runtime correlation_id must be a UUID") from error


def _require_candidate_integrity(
    step: PlanStep,
    execution_plan: ExecutionPlan,
    result: StepResult,
    evidence: tuple[Evidence, ...],
) -> tuple[DocumentEvidence, ...]:
    references = {reference.evidence_id: reference for reference in result.evidence_refs}
    required = set(execution_plan.required_facts)
    # The canonical plan step is the only authority for the data scope of each
    # fact this flow may answer with.
    fact_specs = {specification.fact_id: specification for specification in step.produces}
    expected_provenance = (
        result.result_id,
        execution_plan.plan_id,
        step.step_id,
        step.capability,
        step.operation,
    )
    candidates: list[DocumentEvidence] = []
    seen: set[UUID] = set()
    for item in evidence:
        if not isinstance(item, DocumentEvidence):
            raise ValueError("the fast document flow accepts document evidence only")
        if item.evidence_id in seen:
            raise ValueError("candidate evidence identifiers must be unique")
        seen.add(item.evidence_id)
        reference = references.get(item.evidence_id)
        if reference is None:
            raise ValueError("candidate evidence must be referenced by the step result")
        provenance = item.provenance
        observed = (
            provenance.step_result_id,
            provenance.plan_id,
            provenance.step_id,
            provenance.capability,
            provenance.operation,
        )
        if observed != expected_provenance:
            raise ValueError("candidate evidence provenance must match the executed step")
        if not set(item.supports_fact_ids).issubset(required):
            raise ValueError("candidate evidence must support plan required facts only")
        for fact_id in item.supports_fact_ids:
            specification = fact_specs.get(fact_id)
            if specification is None:
                raise ValueError("candidate evidence must support planned step facts only")
            if item.security_scope.data_scope != specification.data_scope:
                raise ValueError("candidate evidence data_scope must match the planned fact")
        if item.supports_fact_ids != reference.supports_fact_ids:
            raise ValueError("candidate evidence must support exactly the referenced facts")
        candidates.append(item)
    for reference in result.evidence_refs:
        if reference.evidence_id not in seen:
            raise ValueError("every step evidence reference must resolve to candidate evidence")
    return tuple(candidates)


def _rejection_reason_codes(item: DocumentEvidence) -> tuple[str, ...]:
    reasons: list[str] = []
    if item.validation_status == "degraded":
        reasons.append(DEGRADED_REASON)
    if item.freshness != "current":
        reasons.append(NOT_CURRENT_REASON)
    if ANSWER_USE not in item.allowed_uses:
        reasons.append(USE_NOT_ALLOWED_REASON)
    return tuple(reasons)


def _apply_acceptance_policy(
    candidates: tuple[DocumentEvidence, ...],
) -> tuple[tuple[DocumentEvidence, ...], tuple[RejectedEvidenceRef, ...]]:
    accepted: list[DocumentEvidence] = []
    rejected: list[RejectedEvidenceRef] = []
    for item in candidates:
        reasons = _rejection_reason_codes(item)
        if reasons:
            rejected.append(
                RejectedEvidenceRef(
                    evidence_id=item.evidence_id,
                    evidence_type=item.evidence_type,
                    reason_codes=reasons,
                )
            )
        else:
            accepted.append(item)
    return tuple(accepted), tuple(rejected)


def _build_fact_map(
    required_facts: tuple[str, ...],
    accepted: tuple[DocumentEvidence, ...],
) -> tuple[tuple[FactEvidenceMapEntry, ...], tuple[str, ...]]:
    entries: list[FactEvidenceMapEntry] = []
    missing: list[str] = []
    for fact_id in required_facts:
        evidence_ids = tuple(
            item.evidence_id for item in accepted if fact_id in item.supports_fact_ids
        )
        if evidence_ids:
            entries.append(FactEvidenceMapEntry(fact_id=fact_id, evidence_ids=evidence_ids))
        else:
            missing.append(fact_id)
    return tuple(entries), tuple(missing)


def _build_allowed_claim(
    execution_plan: ExecutionPlan,
    accepted: tuple[DocumentEvidence, ...],
) -> AllowedEvidenceClaim:
    subjects = {item.subject for item in accepted}
    if len(subjects) != 1:
        raise ValueError("a document claim requires one identical evidence subject")
    return AllowedEvidenceClaim(
        claim_id=DOCUMENT_CLAIM_ID,
        claim_code=DOCUMENT_CLAIM_CODE,
        claim_type=DOCUMENT_CLAIM_TYPE,
        subject=accepted[0].subject,
        supporting_fact_ids=execution_plan.required_facts,
        evidence_ids=tuple(item.evidence_id for item in accepted),
    )


def _abstain_reason_codes(
    candidates: tuple[DocumentEvidence, ...],
    accepted: tuple[DocumentEvidence, ...],
    result: StepResult,
) -> tuple[str, ...]:
    if not candidates:
        return (EMPTY_REASON,)
    if not accepted:
        return (NO_ACCEPTABLE_BASIS_REASON,)
    if result.status != "success":
        return (INCOMPLETE_STEP_REASON, MISSING_REQUIRED_FACT_REASON)
    return (MISSING_REQUIRED_FACT_REASON,)


def build_evidence_bundle(
    context: AuthorizedRuntimeContext,
    route_decision: RouteDecision,
    execution_plan: ExecutionPlan,
    step_results: tuple[StepResult, ...],
    evidence: tuple[Evidence, ...],
    *,
    bundle_id: UUID,
    built_at: datetime,
) -> EvidenceBundle:
    """Normalize already materialized evidence into one sufficiency decision."""
    step = _require_fast_document_flow(route_decision, execution_plan, step_results)
    correlation_id = _parse_correlation_id(context)
    result = validate_step_result(context, route_decision, execution_plan, step_results[0])
    candidates = _require_candidate_integrity(step, execution_plan, result, evidence)
    accepted, rejected = _apply_acceptance_policy(candidates)
    fact_map, missing_fact_ids = _build_fact_map(execution_plan.required_facts, accepted)
    answerable = result.status == "success" and bool(accepted) and not missing_fact_ids
    decision: EvidenceDecision = "answer" if answerable else "abstain"
    allowed_claims = (_build_allowed_claim(execution_plan, accepted),) if answerable else ()
    reason_codes = (
        (COMPLETE_REASON,) if answerable else _abstain_reason_codes(candidates, accepted, result)
    )
    return EvidenceBundle(
        bundle_id=bundle_id,
        request_id=context.runtime.turn_input.request_id,
        route_decision_id=route_decision.decision_id,
        plan_id=execution_plan.plan_id,
        authorization_decision_id=context.authorization.decision_id,
        runtime_snapshot_id=context.runtime.runtime_snapshot.snapshot_id,
        correlation_id=correlation_id,
        built_at=built_at,
        required_fact_ids=execution_plan.required_facts,
        accepted_evidence=accepted,
        rejected_evidence=rejected,
        fact_map=fact_map,
        missing_fact_ids=missing_fact_ids,
        conflicts=(),
        sufficient=answerable,
        decision=decision,
        allowed_claims=allowed_claims,
        prohibited_claims=(),
        decision_reason_codes=reason_codes,
        evidence_manager_version=EVIDENCE_MANAGER_VERSION,
    )
