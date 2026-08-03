"""Focused tests for the trusted WS-004A finalization services."""

import ast
import asyncio
import dataclasses
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID

import pytest
from support.walking_skeleton_finalization_fakes import (
    CAVEAT_TEXT,
    CITATION_ID,
    CLAIM_TEXT,
    FAILURE_DETAIL_REF,
    FINAL_ANSWER_ID,
    FOREIGN_CLIENT_KEY,
    FOREIGN_DEPLOYMENT_ID,
    FOREIGN_EVIDENCE_ID,
    FOREIGN_LOCATOR_REF,
    FOREIGN_PRINCIPAL_ID,
    FOREIGN_SECURITY_SCOPE_REF,
    FOREIGN_SNAPSHOT_DIGEST,
    FOREIGN_SNAPSHOT_ID,
    FOREIGN_SOURCE_REF,
    FOREIGN_SOURCE_TYPE,
    FOREIGN_SOURCE_VERSION,
    LOCATOR_REF,
    NON_UUID4,
    SECOND_CITATION_ID,
    AnswerRendererFake,
    CitationSourceResolverFake,
    acquired_lease,
    artifacts,
    completed_result,
    expected_key,
    faithful_draft,
    finalization_identifier,
    foreign_capability_bundle,
    foreign_typed_rejected_bundle,
    mismatched_key,
    pending_finalization,
    planned_answer,
    resolved_source,
    rule_evidence_bundle,
    selector_evidence,
    web_evidence,
)
from support.walking_skeleton_fixtures import (
    ANSWER_PLAN_ID,
    AUTHORIZATION_ID,
    BUNDLE_ID,
    CORRELATION_ID,
    CORRELATION_TEXT,
    DOCUMENT_FACT_ID,
    EVIDENCE_ID,
    FOREIGN_ID,
    NOW,
    PLAN_ID,
    RAW_MESSAGE,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SECOND_EVIDENCE_ID,
    SNAPSHOT_ID,
    allowed_claim,
    authorization,
    authorized_context,
    document_evidence,
    evidence_bundle,
    execution_plan,
    principal,
    query_analysis,
    route_decision,
    runtime_context,
    runtime_snapshot,
    sql_evidence,
    step_result,
    terminal_route_decision,
    turn_input,
)
from support.walking_skeleton_terminal_fakes import (
    stored_error_envelope,
    stored_final_answer,
)

from ai_assistant.contracts import (
    AnswerCaveat,
    AnswerClaimPlan,
    AnswerLengthBudget,
    AnswerPlan,
    AnswerSection,
    AnswerSectionItemRef,
    AnswerToneConstraints,
    CitationSlot,
    Evidence,
    EvidenceBundle,
    EvidenceFreshness,
    EvidenceSubjectRef,
    FactEvidenceMapEntry,
    FinalAnswer,
)
from ai_assistant.core.answer_planning import build_answer_plan
from ai_assistant.core.finalization import (
    CitationSourceResolutionRequest,
    FinalizationArtifacts,
    RenderedAnswerDraft,
    RenderedAnswerItem,
    RenderedAnswerSection,
    RenderRequest,
    ResolvedCitationSource,
    finalize_pending_answer,
)
from ai_assistant.core.runtime import OrchestrationResult, OrchestrationStatus
from ai_assistant.core.terminal_runtime import (
    TerminalCoordinationResult,
    TerminalCoordinationStatus,
)
from ai_assistant.core.types import RuntimeContext

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "finalization.py"
)
CORE_INIT_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core" / "__init__.py"
)
MODULE_SOURCE = MODULE_PATH.read_text(encoding="utf-8")
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
    "open(",
    "os.environ",
)
CONCURRENCY_FRAGMENTS = (
    "asyncio.Lock",
    "asyncio.Event",
    "asyncio.Semaphore",
    "asyncio.Condition",
    "asyncio.Queue",
    "threading",
    "Semaphore",
    "Condition(",
    "Queue",
    "create_task",
    "ensure_future",
    "TaskGroup",
    "shield",
    "sleep",
    "while ",
)
FORBIDDEN_VENDOR_ROOTS = (
    "requests",
    "httpx",
    "aiohttp",
    "boto3",
    "psycopg",
    "redis",
    "sqlalchemy",
    "elasticsearch",
    "opensearchpy",
    "openai",
    "anthropic",
    "opentelemetry",
)
FORBIDDEN_ANSWER_TEXT = (
    RAW_MESSAGE,
    "normalized query",
    "prompt",
    "chain_of_thought",
    "traceback",
    "secret",
    "token",
    "select ",
    "https://",
)
PRIVATE_DATACLASSES = (
    RenderedAnswerItem,
    RenderedAnswerSection,
    RenderedAnswerDraft,
    RenderRequest,
    ResolvedCitationSource,
    CitationSourceResolutionRequest,
    FinalizationArtifacts,
)
GENERATION_MODE = "model_generated"


def run(coroutine: object) -> FinalAnswer:
    return asyncio.run(coroutine)


def finalize(
    pending: TerminalCoordinationResult,
    *,
    context: RuntimeContext | None = None,
    renderer: AnswerRendererFake | None = None,
    resolver: CitationSourceResolverFake | None = None,
    injected: FinalizationArtifacts | None = None,
    entered_at: object = NOW,
    generation_mode: str = GENERATION_MODE,
) -> object:
    """Call the finalizer with deterministic defaults for the fixtures."""
    return finalize_pending_answer(
        context if context is not None else runtime_context(),
        pending,
        renderer=renderer if renderer is not None else AnswerRendererFake(),
        citation_source_resolver=(
            resolver if resolver is not None else CitationSourceResolverFake()
        ),
        artifacts=injected if injected is not None else artifacts(),
        entered_at=entered_at,
        generation_mode=generation_mode,
    )


def answered_setup() -> tuple[TerminalCoordinationResult, AnswerRendererFake]:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    return pending, AnswerRendererFake(draft=faithful_draft(plan))


def document_resolver() -> CitationSourceResolverFake:
    return CitationSourceResolverFake(sources=(resolved_source(),))


def freshness_bundle(values: tuple[EvidenceFreshness, ...]) -> EvidenceBundle:
    """Build an answering bundle whose accepted evidence carries given freshness."""
    identifiers = (EVIDENCE_ID, SECOND_EVIDENCE_ID)
    accepted: tuple[Evidence, ...] = tuple(
        document_evidence(
            evidence_id=identifiers[index],
            freshness=value,
            subject_ref=f"subject:document-{index}",
        )
        for index, value in enumerate(values)
    )
    evidence_ids = tuple(item.evidence_id for item in accepted)
    return EvidenceBundle(
        bundle_id=BUNDLE_ID,
        request_id=REQUEST_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        required_fact_ids=(DOCUMENT_FACT_ID,),
        accepted_evidence=accepted,
        fact_map=(FactEvidenceMapEntry(fact_id=DOCUMENT_FACT_ID, evidence_ids=evidence_ids),),
        sufficient=True,
        decision="answer",
        allowed_claims=(allowed_claim(evidence_ids=evidence_ids),),
        decision_reason_codes=("evidence.complete",),
        evidence_manager_version="1.0.0",
    )


def bundle_plan(bundle: EvidenceBundle) -> AnswerPlan:
    return build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        bundle,
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )


def partial_plan() -> AnswerPlan:
    """Build a contract valid partial answer plan that WS-004A must reject."""
    claim = AnswerClaimPlan(
        claim_id="claim.document",
        claim_code="claim.document",
        claim_type="factual",
        subject=EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1"),
        supporting_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
    )
    caveat = AnswerCaveat(
        caveat_id="caveat.degraded",
        caveat_code="caveat.degraded_evidence",
        reason_codes=("evidence.degraded",),
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=REQUEST_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        decision="partial_answer",
        answer_type="direct",
        sections=(
            AnswerSection(
                section_id="section.answer",
                section_type="answer",
                items=(
                    AnswerSectionItemRef(item_kind="claim", item_id="claim.document"),
                    AnswerSectionItemRef(item_kind="caveat", item_id="caveat.degraded"),
                ),
            ),
        ),
        claims=(claim,),
        caveats=(caveat,),
        citation_slots=(
            CitationSlot(
                slot_id="slot.claim.document",
                target_kind="claim",
                target_id="claim.document",
                evidence_ids=(EVIDENCE_ID,),
                placement="inline",
            ),
        ),
        tone_constraints=AnswerToneConstraints(
            response_locale="fa-IR",
            tone_codes=("clear",),
        ),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.degraded",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=1,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


# 26.1 Private types -------------------------------------------------------


@pytest.mark.parametrize("dataclass_type", PRIVATE_DATACLASSES)
def test_private_dataclasses_are_frozen_and_slotted(dataclass_type: type) -> None:
    assert dataclasses.is_dataclass(dataclass_type)
    assert dataclass_type.__dataclass_params__.frozen
    assert "__slots__" in dataclass_type.__dict__


@pytest.mark.parametrize("text", ("", "   ", " padded", "padded ", "with\x00nul"))
def test_rendered_item_rejects_defective_text(text: str) -> None:
    with pytest.raises(ValueError):
        RenderedAnswerItem(item_kind="claim", item_id="claim.document", rendered_text=text)


@pytest.mark.parametrize("item_id", ("", " ", " claim.document"))
def test_rendered_item_rejects_defective_identifiers(item_id: str) -> None:
    with pytest.raises(ValueError):
        RenderedAnswerItem(item_kind="claim", item_id=item_id, rendered_text=CLAIM_TEXT)


def test_rendered_item_rejects_an_unknown_item_kind() -> None:
    with pytest.raises(ValueError):
        RenderedAnswerItem(item_kind="note", item_id="claim.document", rendered_text=CLAIM_TEXT)


def test_rendered_section_requires_at_least_one_item() -> None:
    with pytest.raises(ValueError):
        RenderedAnswerSection(section_id="section.answer", items=())


def test_rendered_section_requires_a_non_empty_identifier() -> None:
    item = RenderedAnswerItem(item_kind="claim", item_id="claim.document", rendered_text=CLAIM_TEXT)
    with pytest.raises(ValueError):
        RenderedAnswerSection(section_id="", items=(item,))


def test_rendered_section_rejects_duplicate_items() -> None:
    item = RenderedAnswerItem(item_kind="claim", item_id="claim.document", rendered_text=CLAIM_TEXT)
    with pytest.raises(ValueError):
        RenderedAnswerSection(section_id="section.answer", items=(item, item))


def test_rendered_draft_requires_a_version_four_plan_identifier() -> None:
    section = faithful_draft(planned_answer()).sections[0]
    with pytest.raises(ValueError):
        RenderedAnswerDraft(answer_plan_id=NON_UUID4, sections=(section,))


def test_rendered_draft_requires_at_least_one_section() -> None:
    with pytest.raises(ValueError):
        RenderedAnswerDraft(answer_plan_id=ANSWER_PLAN_ID, sections=())


def test_rendered_draft_rejects_duplicate_section_identifiers() -> None:
    section = faithful_draft(planned_answer()).sections[0]
    with pytest.raises(ValueError):
        RenderedAnswerDraft(answer_plan_id=ANSWER_PLAN_ID, sections=(section, section))


def test_rendered_draft_rejects_an_item_repeated_across_sections() -> None:
    section = faithful_draft(planned_answer()).sections[0]
    twin = RenderedAnswerSection(section_id="section.second", items=section.items)
    with pytest.raises(ValueError):
        RenderedAnswerDraft(answer_plan_id=ANSWER_PLAN_ID, sections=(section, twin))


def test_resolved_citation_source_rejects_an_unknown_evidence_type() -> None:
    with pytest.raises(ValueError):
        resolved_source(evidence_type="spreadsheet")


@pytest.mark.parametrize(
    "field_name",
    (
        "display_label",
        "source_version",
        "locator_ref",
        "source_type",
        "source_ref",
        "security_scope_ref",
    ),
)
def test_resolved_citation_source_rejects_padded_text(field_name: str) -> None:
    with pytest.raises(ValueError):
        resolved_source(**{field_name: " padded "})


def test_resolved_citation_source_requires_a_version_four_evidence_id() -> None:
    with pytest.raises(ValueError):
        resolved_source(evidence_id=NON_UUID4)


def test_citation_source_request_requires_unique_evidence_identifiers() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=evidence_bundle(),
            answer_plan=planned_answer(),
            evidence_ids=(EVIDENCE_ID, EVIDENCE_ID),
        )


def test_citation_source_request_requires_at_least_one_evidence_identifier() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=evidence_bundle(),
            answer_plan=planned_answer(),
            evidence_ids=(),
        )


def test_citation_source_request_requires_authorization_matching_the_answer_plan() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(decision_id=FOREIGN_ID),
            evidence_bundle=evidence_bundle(),
            answer_plan=planned_answer(),
            evidence_ids=(EVIDENCE_ID,),
        )


def test_citation_source_request_requires_authorization_matching_the_evidence_bundle() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=evidence_bundle(authorization_id=FOREIGN_ID),
            answer_plan=planned_answer(),
            evidence_ids=(EVIDENCE_ID,),
        )


@pytest.mark.parametrize("identifier", ("final_answer_id", "failure_internal_detail_ref"))
def test_finalization_artifacts_require_version_four_identifiers(identifier: str) -> None:
    with pytest.raises(ValueError):
        artifacts(**{identifier: NON_UUID4})


def test_finalization_artifacts_require_version_four_citation_identifiers() -> None:
    with pytest.raises(ValueError):
        artifacts(citation_ids=(NON_UUID4,))


def test_finalization_artifacts_reject_duplicate_citation_identifiers() -> None:
    with pytest.raises(ValueError):
        artifacts(citation_ids=(CITATION_ID, CITATION_ID))


def test_finalization_artifacts_require_pairwise_distinct_identifiers() -> None:
    with pytest.raises(ValueError):
        artifacts(citation_ids=(FINAL_ANSWER_ID,))


def test_finalization_artifacts_require_a_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError):
        artifacts(finalized_at=NOW.replace(tzinfo=None))


# 26.2 Entry state ---------------------------------------------------------


def test_pending_finalization_without_a_lease_is_unconstructible() -> None:
    with pytest.raises(ValueError):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=expected_key(),
            orchestration_result=completed_result(),
        )


def test_pending_finalization_without_an_orchestration_result_is_unconstructible() -> None:
    key = expected_key()
    with pytest.raises(ValueError):
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=acquired_lease(key),
        )


@pytest.mark.parametrize(
    "artifact",
    ("authorization", "route_decision", "execution_plan", "step_result", "evidence_bundle"),
)
def test_a_completed_result_missing_an_artifact_is_unconstructible(artifact: str) -> None:
    values = {
        "authorization": authorization(),
        "route_decision": route_decision(),
        "execution_plan": execution_plan(),
        "step_result": step_result(),
        "evidence_bundle": evidence_bundle(),
        "answer_plan": planned_answer(),
    }
    values[artifact] = None
    with pytest.raises(ValueError):
        OrchestrationResult(status=OrchestrationStatus.COMPLETED, **values)


def test_a_completed_result_without_an_answer_plan_is_unconstructible() -> None:
    with pytest.raises(ValueError):
        OrchestrationResult(
            status=OrchestrationStatus.COMPLETED,
            authorization=authorization(),
            route_decision=route_decision(),
            execution_plan=execution_plan(),
            step_result=step_result(),
            evidence_bundle=evidence_bundle(),
        )


def assert_entry_rejected(
    pending: TerminalCoordinationResult,
    *,
    entered_at: object = NOW,
) -> None:
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver, entered_at=entered_at))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_a_replayed_coordination_is_rejected() -> None:
    assert_entry_rejected(
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.REPLAYED,
            effective_key=expected_key(),
            outcome=stored_final_answer(),
        )
    )


def test_a_terminal_error_coordination_is_rejected() -> None:
    assert_entry_rejected(
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.TERMINAL_ERROR,
            effective_key=expected_key(),
            outcome=stored_error_envelope(),
        )
    )


def test_a_stopped_orchestration_is_rejected() -> None:
    key = expected_key()
    stopped = OrchestrationResult(
        status=OrchestrationStatus.STOPPED,
        authorization=authorization(),
        route_decision=terminal_route_decision(),
    )
    assert_entry_rejected(
        TerminalCoordinationResult(
            status=TerminalCoordinationStatus.PENDING_FINALIZATION,
            effective_key=key,
            lease=acquired_lease(key),
            orchestration_result=stopped,
        )
    )


def test_a_naive_entry_timestamp_is_rejected() -> None:
    assert_entry_rejected(pending_finalization(), entered_at=NOW.replace(tzinfo=None))


def test_an_entry_timestamp_before_the_runtime_start_is_rejected() -> None:
    assert_entry_rejected(pending_finalization(), entered_at=NOW - timedelta(seconds=1))


# 26.3 Idempotency identity rebinding (WS-004A-R2 requirement 6) -----------


def assert_identity_rejected(pending: TerminalCoordinationResult) -> None:
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_effective_key_deployment_mismatch_is_rejected() -> None:
    key = mismatched_key(deployment_id=FOREIGN_DEPLOYMENT_ID)
    assert_identity_rejected(
        pending_finalization(effective_key_override=key, lease_key_override=key)
    )


def test_effective_key_principal_mismatch_is_rejected() -> None:
    key = mismatched_key(principal_id=FOREIGN_PRINCIPAL_ID)
    assert_identity_rejected(
        pending_finalization(effective_key_override=key, lease_key_override=key)
    )


def test_effective_key_client_key_mismatch_is_rejected() -> None:
    key = mismatched_key(client_key=FOREIGN_CLIENT_KEY)
    assert_identity_rejected(
        pending_finalization(effective_key_override=key, lease_key_override=key)
    )


def test_effective_key_snapshot_id_mismatch_is_rejected() -> None:
    key = mismatched_key(runtime_snapshot_id=FOREIGN_SNAPSHOT_ID)
    assert_identity_rejected(
        pending_finalization(effective_key_override=key, lease_key_override=key)
    )


def test_effective_key_snapshot_digest_mismatch_is_rejected() -> None:
    key = mismatched_key(runtime_snapshot_digest=FOREIGN_SNAPSHOT_DIGEST)
    assert_identity_rejected(
        pending_finalization(effective_key_override=key, lease_key_override=key)
    )


def test_lease_key_diverging_from_the_pending_effective_key_is_rejected() -> None:
    """A lease bound to a different key than the pending effective key can
    never be constructed: the coordination result itself enforces binding."""
    correct = expected_key()
    foreign = mismatched_key(principal_id=FOREIGN_PRINCIPAL_ID)
    with pytest.raises(ValueError):
        pending_finalization(effective_key_override=correct, lease_key_override=foreign)


def test_a_correctly_bound_identity_is_accepted() -> None:
    plan = planned_answer()
    key = expected_key()
    pending = pending_finalization(
        result=completed_result(answer_plan=plan),
        effective_key_override=key,
        lease_key_override=key,
    )
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
        )
    )
    assert final.outcome == "answered"


# 26.4 Cross-artifact lineage ---------------------------------------------


def assert_lineage_rejected(
    pending: TerminalCoordinationResult,
    *,
    context: RuntimeContext | None = None,
) -> None:
    plan = pending.orchestration_result.answer_plan
    renderer = AnswerRendererFake(draft=faithful_draft(plan) if plan is not None else None)
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, context=context, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_request_mismatch_is_rejected() -> None:
    assert_lineage_rejected(
        pending_finalization(),
        context=runtime_context(request_id=FOREIGN_ID),
    )


def test_authorization_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(decision_id=FOREIGN_ID),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_route_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(decision_id=FOREIGN_ID),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_non_canonical_route_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(route="fast.sql"),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_execution_plan_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(plan_id=FOREIGN_ID),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_step_result_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(plan_id=FOREIGN_ID),
        evidence_bundle=evidence_bundle(),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_runtime_snapshot_mismatch_is_rejected() -> None:
    assert_lineage_rejected(
        pending_finalization(),
        context=runtime_context(snapshot_id=FOREIGN_ID),
    )


def test_correlation_mismatch_is_rejected() -> None:
    assert_lineage_rejected(
        pending_finalization(),
        context=runtime_context(correlation_id=str(FOREIGN_ID)),
    )


def test_evidence_bundle_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(bundle_id=FOREIGN_ID),
        answer_plan=planned_answer(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_answer_plan_bound_to_another_bundle_is_rejected() -> None:
    foreign = build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        evidence_bundle(bundle_id=FOREIGN_ID),
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(),
        answer_plan=foreign,
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_evidence_decision_mismatch_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(decision="answer"),
        answer_plan=planned_answer(decision="abstain", answer_plan_id=ANSWER_PLAN_ID),
    )
    assert_lineage_rejected(pending_finalization(result=result))


def test_partial_answer_decision_is_rejected() -> None:
    result = OrchestrationResult(
        status=OrchestrationStatus.COMPLETED,
        authorization=authorization(),
        route_decision=route_decision(),
        execution_plan=execution_plan(),
        step_result=step_result(),
        evidence_bundle=evidence_bundle(decision="partial_answer"),
        answer_plan=partial_plan(),
    )
    assert_lineage_rejected(pending_finalization(result=result))


# 26.5 Generation mode injection (WS-004A-R2 requirement 1) ----------------


def test_finalize_requires_the_generation_mode_keyword() -> None:
    pending, renderer = answered_setup()
    with pytest.raises(TypeError):
        run(
            finalize_pending_answer(
                runtime_context(),
                pending,
                renderer=renderer,
                citation_source_resolver=document_resolver(),
                artifacts=artifacts(),
                entered_at=NOW,
            )
        )


@pytest.mark.parametrize("illegal_mode", ("none", "invented_mode", "", "MODEL_GENERATED"))
def test_illegal_generation_modes_are_rejected_before_rendering(illegal_mode: str) -> None:
    pending, renderer = answered_setup()
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver, generation_mode=illegal_mode))
    assert renderer.calls == 0
    assert resolver.calls == 0


@pytest.mark.parametrize(
    "legal_mode",
    ("deterministic_template", "model_generated", "model_repaired", "safe_fallback"),
)
def test_a_successful_answer_preserves_the_injected_generation_mode(legal_mode: str) -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
            generation_mode=legal_mode,
        )
    )
    assert final.response_metadata.generation_mode == legal_mode


def test_a_failed_answer_always_uses_the_none_generation_mode() -> None:
    pending, _ = answered_setup()
    renderer = AnswerRendererFake(error=RuntimeError("sentinel-renderer-failure"))
    final = run(
        finalize(
            pending,
            renderer=renderer,
            resolver=document_resolver(),
            generation_mode="safe_fallback",
        )
    )
    assert final.outcome == "failed"
    assert final.response_metadata.generation_mode == "none"


# 26.6 Successful answered flow -------------------------------------------


def test_answered_finalization_produces_the_trusted_final_answer() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    final = run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 1
    assert resolver.calls == 1
    assert final.outcome == "answered"
    assert final.safe_error is None
    assert final.final_answer_id == FINAL_ANSWER_ID
    assert final.request_id == REQUEST_ID
    assert final.answer_plan_id == plan.answer_plan_id
    assert final.evidence_bundle_id == BUNDLE_ID
    assert final.route_decision_id == ROUTE_DECISION_ID
    assert final.plan_id == PLAN_ID
    assert final.authorization_decision_id == AUTHORIZATION_ID
    assert final.runtime_snapshot_id == SNAPSHOT_ID
    assert final.correlation_id == CORRELATION_ID
    assert final.finalized_at == NOW
    assert final.applied_length_budget == plan.length_budget
    assert final.finalizer_version == "1.0.0"


def test_answered_content_preserves_plan_structure_and_text() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
        )
    )
    content = final.validated_content
    assert content is not None
    assert tuple(section.section_id for section in content.sections) == tuple(
        section.section_id for section in plan.sections
    )
    rendered = tuple(
        (item.item_kind, item.item_id, item.rendered_text)
        for section in content.sections
        for item in section.items
    )
    assert rendered == (("claim", "claim.document", CLAIM_TEXT),)


def test_answered_citations_are_compiled_from_plan_slots() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
        )
    )
    slot = plan.citation_slots[0]
    citation = final.citations[0]
    assert len(final.citations) == len(plan.citation_slots)
    assert citation.citation_id == CITATION_ID
    assert citation.slot_id == slot.slot_id
    assert citation.target_kind == slot.target_kind
    assert citation.target_id == slot.target_id
    assert citation.placement == slot.placement
    assert tuple(source.evidence_id for source in citation.sources) == slot.evidence_ids
    assert citation.sources[0].evidence_type == "document"


def test_renderer_receives_only_trusted_planning_artifacts() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    run(finalize(pending, renderer=renderer, resolver=document_resolver()))
    request = renderer.requests[0]
    assert request.answer_plan is plan
    assert set(RenderRequest.__slots__) == {
        "context",
        "authorization",
        "route_decision",
        "execution_plan",
        "evidence_bundle",
        "answer_plan",
    }


def test_resolver_receives_only_required_evidence_identifiers() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    resolver = document_resolver()
    run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=resolver,
        )
    )
    request = resolver.requests[0]
    assert request.evidence_ids == (EVIDENCE_ID,)
    assert request.answer_plan is plan


def test_resolver_request_carries_the_exact_accepted_authorization() -> None:
    plan = planned_answer()
    accepted_authorization = authorization()
    result = completed_result(answer_plan=plan)
    pending = pending_finalization(result=result)
    resolver = document_resolver()
    run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=resolver,
        )
    )
    request = resolver.requests[0]
    assert request.authorization == accepted_authorization
    assert request.authorization is result.authorization


def test_answered_metadata_counts_are_exact() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
        )
    )
    metadata = final.response_metadata
    assert metadata.response_locale == plan.tone_constraints.response_locale
    assert metadata.answer_type == plan.answer_type
    assert metadata.generation_mode == GENERATION_MODE
    assert metadata.validation_status == "passed"
    assert metadata.degraded is False
    assert metadata.section_count == 1
    assert metadata.claim_count == 1
    assert metadata.caveat_count == 0
    assert metadata.citation_count == 1
    assert metadata.character_count == len(CLAIM_TEXT)


# 26.7 Successful abstention flow -----------------------------------------


def test_abstained_finalization_produces_an_abstained_answer() -> None:
    plan = planned_answer(decision="abstain")
    pending = pending_finalization(
        result=completed_result(answer_plan=plan, bundle=evidence_bundle(decision="abstain"))
    )
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    final = run(
        finalize(pending, renderer=renderer, resolver=resolver, injected=artifacts(citation_ids=()))
    )
    assert final.outcome == "abstained"
    assert renderer.calls == 1
    assert resolver.calls == 0
    assert final.citations == ()
    assert final.safe_error is None
    assert final.outcome_reason_codes == plan.decision_reason_codes
    content = final.validated_content
    assert content is not None
    items = tuple(item for section in content.sections for item in section.items)
    assert tuple(item.item_kind for item in items) == ("caveat",)
    assert items[0].rendered_text == CAVEAT_TEXT
    assert final.response_metadata.caveat_count == 1
    assert final.response_metadata.claim_count == 0
    assert final.response_metadata.citation_count == 0
    assert final.freshness_note.status == "not_applicable"


# 26.8 Renderer integrity --------------------------------------------------


def assert_draft_rejected(draft: RenderedAnswerDraft, *, plan: AnswerPlan | None = None) -> None:
    approved = plan if plan is not None else planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=approved))
    renderer = AnswerRendererFake(draft=draft)
    resolver = document_resolver()
    citation_ids = tuple(
        finalization_identifier(90 + index) for index in range(len(approved.citation_slots))
    )
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                renderer=renderer,
                resolver=resolver,
                injected=artifacts(citation_ids=citation_ids),
            )
        )
    assert renderer.calls == 1
    assert resolver.calls == 0


def claim_item(text: str = CLAIM_TEXT, item_id: str = "claim.document") -> RenderedAnswerItem:
    return RenderedAnswerItem(item_kind="claim", item_id=item_id, rendered_text=text)


def test_draft_for_another_answer_plan_is_rejected() -> None:
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=FOREIGN_ID,
            sections=(RenderedAnswerSection(section_id="section.answer", items=(claim_item(),)),),
        )
    )


def test_extra_rendered_section_is_rejected() -> None:
    plan = planned_answer()
    base = faithful_draft(plan).sections
    extra = RenderedAnswerSection(
        section_id="section.extra",
        items=(claim_item(item_id="claim.extra"),),
    )
    assert_draft_rejected(
        RenderedAnswerDraft(answer_plan_id=plan.answer_plan_id, sections=(*base, extra)),
        plan=plan,
    )


def test_renamed_rendered_section_is_rejected() -> None:
    plan = planned_answer()
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(RenderedAnswerSection(section_id="section.other", items=(claim_item(),)),),
        ),
        plan=plan,
    )


def test_extra_rendered_item_is_rejected() -> None:
    plan = planned_answer()
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(
                RenderedAnswerSection(
                    section_id="section.answer",
                    items=(claim_item(), claim_item(item_id="claim.extra")),
                ),
            ),
        ),
        plan=plan,
    )


def test_unknown_rendered_item_identifier_is_rejected() -> None:
    plan = planned_answer()
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(
                RenderedAnswerSection(
                    section_id="section.answer",
                    items=(claim_item(item_id="claim.unknown"),),
                ),
            ),
        ),
        plan=plan,
    )


def test_claim_rendered_as_caveat_is_rejected() -> None:
    plan = planned_answer()
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(
                RenderedAnswerSection(
                    section_id="section.answer",
                    items=(
                        RenderedAnswerItem(
                            item_kind="caveat",
                            item_id="claim.document",
                            rendered_text=CLAIM_TEXT,
                        ),
                    ),
                ),
            ),
        ),
        plan=plan,
    )


def two_section_plan() -> AnswerPlan:
    """Build a two section answered plan used for ordering and membership tests."""
    subject = EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1")
    claims = tuple(
        AnswerClaimPlan(
            claim_id=claim_id,
            claim_code=claim_id,
            claim_type="factual",
            subject=subject,
            supporting_fact_ids=(DOCUMENT_FACT_ID,),
            evidence_ids=(EVIDENCE_ID,),
        )
        for claim_id in ("claim.first", "claim.second")
    )
    sections = tuple(
        AnswerSection(
            section_id=section_id,
            section_type="answer",
            items=(AnswerSectionItemRef(item_kind="claim", item_id=claim.claim_id),),
        )
        for section_id, claim in zip(("section.first", "section.second"), claims, strict=True)
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=REQUEST_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        decision="answer",
        answer_type="direct",
        sections=sections,
        claims=claims,
        caveats=(),
        citation_slots=tuple(
            CitationSlot(
                slot_id=f"slot.{claim.claim_id}",
                target_kind="claim",
                target_id=claim.claim_id,
                evidence_ids=(EVIDENCE_ID,),
                placement="inline",
            )
            for claim in claims
        ),
        tone_constraints=AnswerToneConstraints(response_locale="fa-IR", tone_codes=("clear",)),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.complete",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=2,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


def test_reordered_rendered_sections_are_rejected() -> None:
    plan = two_section_plan()
    sections = faithful_draft(plan).sections
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=tuple(reversed(sections)),
        ),
        plan=plan,
    )


def test_item_moved_to_another_section_is_rejected() -> None:
    plan = two_section_plan()
    sections = faithful_draft(plan).sections
    swapped = (
        RenderedAnswerSection(section_id=sections[0].section_id, items=sections[1].items),
        RenderedAnswerSection(section_id=sections[1].section_id, items=sections[0].items),
    )
    assert_draft_rejected(
        RenderedAnswerDraft(answer_plan_id=plan.answer_plan_id, sections=swapped),
        plan=plan,
    )


def test_missing_rendered_section_is_rejected() -> None:
    plan = two_section_plan()
    sections = faithful_draft(plan).sections
    assert_draft_rejected(
        RenderedAnswerDraft(answer_plan_id=plan.answer_plan_id, sections=(sections[0],)),
        plan=plan,
    )


def test_budget_overflow_is_rejected() -> None:
    plan = planned_answer()
    overflowing = "x" * (plan.length_budget.max_characters + 1)
    assert_draft_rejected(
        RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(
                RenderedAnswerSection(
                    section_id="section.answer",
                    items=(claim_item(text=overflowing),),
                ),
            ),
        ),
        plan=plan,
    )


# 26.9 Untrusted port return type validation (requirement 3) --------------


def test_a_non_draft_render_result_is_rejected() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(result="not-a-draft")
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert resolver.calls == 0


def test_a_non_tuple_resolution_result_is_rejected() -> None:
    pending, renderer = answered_setup()
    resolver = CitationSourceResolverFake(use_result=True, result=[resolved_source()])
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))


def test_a_resolution_result_with_a_non_resolved_source_item_is_rejected() -> None:
    pending, renderer = answered_setup()
    resolver = CitationSourceResolverFake(use_result=True, result=("not-a-resolved-source",))
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))


# 26.10 Citation integrity --------------------------------------------------


def assert_resolution_rejected(resolver: CitationSourceResolverFake) -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 1
    assert resolver.calls == 1


def test_missing_resolved_source_is_rejected() -> None:
    assert_resolution_rejected(CitationSourceResolverFake(sources=()))


def test_extra_resolved_source_is_rejected() -> None:
    assert_resolution_rejected(
        CitationSourceResolverFake(
            sources=(resolved_source(), resolved_source(evidence_id=SECOND_EVIDENCE_ID))
        )
    )


def test_duplicate_resolved_source_is_rejected() -> None:
    assert_resolution_rejected(
        CitationSourceResolverFake(sources=(resolved_source(), resolved_source()))
    )


def test_unknown_resolved_evidence_is_rejected() -> None:
    assert_resolution_rejected(
        CitationSourceResolverFake(sources=(resolved_source(evidence_id=FOREIGN_EVIDENCE_ID),))
    )


def test_wrong_resolved_evidence_type_is_rejected() -> None:
    assert_resolution_rejected(
        CitationSourceResolverFake(sources=(resolved_source(evidence_type="sql"),))
    )


@pytest.mark.parametrize(
    "field_name,foreign_value",
    (
        ("source_type", FOREIGN_SOURCE_TYPE),
        ("source_ref", FOREIGN_SOURCE_REF),
        ("source_version", FOREIGN_SOURCE_VERSION),
        ("security_scope_ref", FOREIGN_SECURITY_SCOPE_REF),
        ("locator_ref", FOREIGN_LOCATOR_REF),
    ),
)
def test_a_foreign_source_binding_field_is_rejected_even_when_evidence_matches(
    field_name: str, foreign_value: str
) -> None:
    """A resolved source binding must match the exact accepted Evidence record.

    evidence_id and evidence_type alone are never sufficient: each of
    source_type, source_ref, source_version, security_scope_ref and
    locator_ref is independently checked against the trusted Evidence.
    """
    assert_resolution_rejected(
        CitationSourceResolverFake(sources=(resolved_source(**{field_name: foreign_value}),))
    )


def test_a_faithful_source_binding_with_a_foreign_display_label_is_accepted() -> None:
    """display_label is presentation only: it never participates in authorization."""
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=CitationSourceResolverFake(
                sources=(resolved_source(display_label="Some other department's label"),)
            ),
        )
    )
    assert final.outcome == "answered"


def test_citation_identifier_count_must_match_the_plan_slots() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                renderer=renderer,
                resolver=resolver,
                injected=artifacts(citation_ids=(CITATION_ID, SECOND_CITATION_ID)),
            )
        )
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_too_few_citation_identifiers_is_rejected_before_any_port_call() -> None:
    plan = caveat_citation_plan()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = CitationSourceResolverFake(sources=(resolved_source(),))
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                renderer=renderer,
                resolver=resolver,
                injected=artifacts(citation_ids=(CITATION_ID,)),
            )
        )
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_abstained_plan_rejects_injected_citation_identifiers() -> None:
    plan = planned_answer(decision="abstain")
    pending = pending_finalization(
        result=completed_result(answer_plan=plan, bundle=evidence_bundle(decision="abstain"))
    )
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_citation_slot_citing_unaccepted_evidence_is_rejected() -> None:
    bundle = freshness_bundle(("current", "current"))
    plan = bundle_plan(bundle)
    reduced = freshness_bundle(("current",))
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=reduced))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert resolver.calls == 0


def test_renderer_cannot_influence_structured_citation_fields() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    final = run(finalize(pending, renderer=renderer, resolver=document_resolver()))
    assert not hasattr(renderer.requests[0], "citation_slots")
    assert all(
        source.locator_ref == LOCATOR_REF and source.display_label == "Document store"
        for citation in final.citations
        for source in citation.sources
    )


# 26.11 Timestamp ordering preflight (requirement 5) -----------------------


def test_a_finalized_at_before_the_entry_time_is_rejected() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                renderer=renderer,
                resolver=resolver,
                injected=artifacts(finalized_at=NOW - timedelta(seconds=1)),
                entered_at=NOW,
            )
        )
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_a_finalized_at_before_the_answer_plan_build_time_is_rejected() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                renderer=renderer,
                resolver=resolver,
                injected=artifacts(finalized_at=NOW - timedelta(seconds=1)),
                entered_at=NOW - timedelta(seconds=2),
            )
        )
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_a_finalized_at_equal_to_entry_and_build_time_is_accepted() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=document_resolver(),
            injected=artifacts(finalized_at=NOW),
            entered_at=NOW,
        )
    )
    assert final.outcome == "answered"


# 26.12 Freshness -----------------------------------------------------------


def finalize_with_freshness(values: tuple[EvidenceFreshness, ...]) -> FinalAnswer:
    bundle = freshness_bundle(values)
    plan = bundle_plan(bundle)
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    citation_ids = tuple(
        finalization_identifier(60 + index) for index in range(len(plan.citation_slots))
    )
    sources = tuple(
        resolved_source(evidence_id=item.evidence_id) for item in bundle.accepted_evidence
    )
    return run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=CitationSourceResolverFake(sources=sources),
            injected=artifacts(citation_ids=citation_ids),
        )
    )


def test_current_evidence_produces_a_current_freshness_note() -> None:
    final = finalize_with_freshness(("current",))
    assert final.freshness_note.status == "current"
    assert final.freshness_note.data_as_of == NOW
    assert final.freshness_note.reason_codes == ()
    assert final.response_metadata.degraded is False


def test_stale_evidence_produces_a_stale_freshness_note() -> None:
    final = finalize_with_freshness(("stale",))
    assert final.freshness_note.status == "stale"
    assert final.freshness_note.data_as_of == NOW
    assert final.freshness_note.reason_codes == ("freshness.stale",)
    assert final.response_metadata.degraded is True


def test_unknown_evidence_produces_an_unknown_freshness_note() -> None:
    final = finalize_with_freshness(("unknown",))
    assert final.freshness_note.status == "unknown"
    assert final.freshness_note.data_as_of is None
    assert final.freshness_note.reason_codes == ("freshness.unknown",)


def test_mixed_evidence_produces_a_mixed_freshness_note() -> None:
    final = finalize_with_freshness(("current", "stale"))
    assert final.freshness_note.status == "mixed"
    assert final.freshness_note.data_as_of is None
    assert final.freshness_note.reason_codes == ("freshness.current", "freshness.stale")


def test_freshness_is_independent_of_the_wall_clock() -> None:
    first = finalize_with_freshness(("current",))
    second = finalize_with_freshness(("current",))
    assert first.freshness_note == second.freshness_note
    assert "datetime.now" not in MODULE_SOURCE


# 26.13 Controlled failures -------------------------------------------------


def bounded_context(*, seconds: float) -> RuntimeContext:
    return RuntimeContext(
        turn_input=turn_input(),
        principal=principal(),
        runtime_snapshot=runtime_snapshot(),
        correlation_id=CORRELATION_TEXT,
        started_at=NOW,
        deadline_at=NOW + timedelta(seconds=seconds),
    )


def assert_failed_answer(final: FinalAnswer, code: str, *, retryable: bool) -> None:
    assert final.outcome == "failed"
    assert final.validated_content is None
    assert final.citations == ()
    error = final.safe_error
    assert error is not None
    assert error.code == code
    assert error.safe_message_key == f"error.{code.lower()}"
    assert error.retryable is retryable
    assert error.internal_detail_ref == FAILURE_DETAIL_REF
    assert final.final_answer_id == FINAL_ANSWER_ID
    assert final.answer_plan_id == ANSWER_PLAN_ID
    assert final.request_id == REQUEST_ID
    assert final.evidence_bundle_id == BUNDLE_ID
    assert final.response_metadata.character_count == 0
    assert final.response_metadata.degraded is True
    assert final.response_metadata.generation_mode == "none"
    assert final.freshness_note.status == "not_applicable"


def test_expired_deadline_produces_a_dependency_timeout_answer() -> None:
    pending, renderer = answered_setup()
    resolver = document_resolver()
    later = NOW + timedelta(seconds=5)
    final = run(
        finalize(
            pending,
            context=bounded_context(seconds=1),
            renderer=renderer,
            resolver=resolver,
            entered_at=later,
            injected=artifacts(finalized_at=later),
        )
    )
    assert_failed_answer(final, "DEPENDENCY_TIMEOUT", retryable=True)
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_renderer_timeout_produces_a_dependency_timeout_answer() -> None:
    async def scenario() -> FinalAnswer:
        pending, _ = answered_setup()
        plan = pending.orchestration_result.answer_plan
        renderer = AnswerRendererFake(draft=faithful_draft(plan), gate=asyncio.Event())
        return await finalize(
            pending,
            context=bounded_context(seconds=0.01),
            renderer=renderer,
            resolver=document_resolver(),
        )

    assert_failed_answer(asyncio.run(scenario()), "DEPENDENCY_TIMEOUT", retryable=True)


def test_resolver_timeout_produces_a_dependency_timeout_answer() -> None:
    async def scenario() -> FinalAnswer:
        pending, renderer = answered_setup()
        resolver = CitationSourceResolverFake(
            sources=(resolved_source(),),
            gate=asyncio.Event(),
        )
        return await finalize(
            pending,
            context=bounded_context(seconds=0.01),
            renderer=renderer,
            resolver=resolver,
        )

    assert_failed_answer(asyncio.run(scenario()), "DEPENDENCY_TIMEOUT", retryable=True)


def test_renderer_exception_produces_an_internal_error_answer() -> None:
    pending, _ = answered_setup()
    renderer = AnswerRendererFake(error=RuntimeError("sentinel-renderer-failure"))
    resolver = document_resolver()
    final = run(finalize(pending, renderer=renderer, resolver=resolver))
    assert_failed_answer(final, "INTERNAL_ERROR", retryable=False)
    assert resolver.calls == 0
    assert "sentinel-renderer-failure" not in repr(final)


def test_resolver_exception_produces_an_internal_error_answer() -> None:
    pending, renderer = answered_setup()
    resolver = CitationSourceResolverFake(error=RuntimeError("sentinel-resolver-failure"))
    final = run(finalize(pending, renderer=renderer, resolver=resolver))
    assert_failed_answer(final, "INTERNAL_ERROR", retryable=False)
    assert renderer.calls == 1
    assert "sentinel-resolver-failure" not in repr(final)


def test_a_generous_deadline_still_answers() -> None:
    pending, renderer = answered_setup()
    final = run(
        finalize(
            pending,
            context=bounded_context(seconds=30),
            renderer=renderer,
            resolver=document_resolver(),
        )
    )
    assert final.outcome == "answered"


# 26.14 Cancellation -------------------------------------------------------


def test_cancellation_during_rendering_propagates() -> None:
    async def scenario() -> AnswerRendererFake:
        pending, _ = answered_setup()
        plan = pending.orchestration_result.answer_plan
        started = asyncio.Event()
        renderer = AnswerRendererFake(
            draft=faithful_draft(plan),
            started=started,
            gate=asyncio.Event(),
        )
        task = asyncio.ensure_future(
            finalize(pending, renderer=renderer, resolver=document_resolver())
        )
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return renderer

    renderer = asyncio.run(scenario())
    assert renderer.observed_cancellation


def test_cancellation_during_citation_resolution_propagates() -> None:
    async def scenario() -> CitationSourceResolverFake:
        pending, renderer = answered_setup()
        started = asyncio.Event()
        resolver = CitationSourceResolverFake(
            sources=(resolved_source(),),
            started=started,
            gate=asyncio.Event(),
        )
        task = asyncio.ensure_future(finalize(pending, renderer=renderer, resolver=resolver))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return resolver

    resolver = asyncio.run(scenario())
    assert resolver.observed_cancellation


# 26.15 ValueError propagation (requirement 2) -----------------------------


def test_renderer_shape_defects_are_not_converted_into_failed_answers() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    renderer = AnswerRendererFake(
        draft=RenderedAnswerDraft(
            answer_plan_id=plan.answer_plan_id,
            sections=(
                RenderedAnswerSection(
                    section_id="section.answer",
                    items=(claim_item(item_id="claim.unknown"),),
                ),
            ),
        )
    )
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                context=bounded_context(seconds=30),
                renderer=renderer,
                resolver=document_resolver(),
            )
        )


def test_citation_defects_are_not_converted_into_failed_answers() -> None:
    pending, renderer = answered_setup()
    with pytest.raises(ValueError):
        run(
            finalize(
                pending,
                context=bounded_context(seconds=30),
                renderer=renderer,
                resolver=CitationSourceResolverFake(sources=()),
            )
        )


def test_a_renderer_raised_value_error_propagates_and_is_not_an_internal_error() -> None:
    """A renderer ValueError is a trusted-boundary rejection: it must propagate
    uncaught, never becoming a safe INTERNAL_ERROR FinalAnswer."""
    pending, _ = answered_setup()
    renderer = AnswerRendererFake(error=ValueError("sentinel-renderer-value-error"))
    resolver = document_resolver()
    with pytest.raises(ValueError, match="sentinel-renderer-value-error"):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert resolver.calls == 0


def test_a_resolver_raised_value_error_propagates_and_is_not_an_internal_error() -> None:
    """A resolver ValueError is a trusted-boundary rejection: it must propagate
    uncaught, never becoming a safe INTERNAL_ERROR FinalAnswer."""
    pending, renderer = answered_setup()
    resolver = CitationSourceResolverFake(error=ValueError("sentinel-resolver-value-error"))
    with pytest.raises(ValueError, match="sentinel-resolver-value-error"):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 1


# 26.16 Immutability -------------------------------------------------------


def test_finalization_does_not_mutate_any_input_artifact() -> None:
    plan = planned_answer()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    context = runtime_context()
    draft = faithful_draft(plan)
    sources = (resolved_source(),)
    injected = artifacts()
    snapshots = tuple(
        repr(value)
        for value in (
            context,
            pending,
            pending.lease,
            pending.orchestration_result,
            plan,
            draft,
            sources,
            injected,
        )
    )
    run(
        finalize(
            pending,
            context=context,
            renderer=AnswerRendererFake(draft=draft),
            resolver=CitationSourceResolverFake(sources=sources),
            injected=injected,
        )
    )
    refreshed = tuple(
        repr(value)
        for value in (
            context,
            pending,
            pending.lease,
            pending.orchestration_result,
            plan,
            draft,
            sources,
            injected,
        )
    )
    assert refreshed == snapshots


def test_the_final_answer_is_immutable() -> None:
    pending, renderer = answered_setup()
    final = run(finalize(pending, renderer=renderer, resolver=document_resolver()))
    with pytest.raises(ValueError):
        final.outcome = "failed"


# 26.17 Safety -------------------------------------------------------------


@pytest.mark.parametrize("fragment", FORBIDDEN_ANSWER_TEXT)
def test_the_final_answer_carries_no_unsafe_text(fragment: str) -> None:
    pending, renderer = answered_setup()
    final = run(finalize(pending, renderer=renderer, resolver=document_resolver()))
    assert fragment.lower() not in repr(final).lower()


def test_the_failed_answer_carries_no_unsafe_text() -> None:
    pending, _ = answered_setup()
    renderer = AnswerRendererFake(error=RuntimeError("sentinel-renderer-failure"))
    final = run(finalize(pending, renderer=renderer, resolver=document_resolver()))
    rendered = repr(final).lower()
    assert "sentinel" not in rendered
    assert "traceback" not in rendered


@pytest.mark.parametrize("fragment", FORBIDDEN_FRAGMENTS)
def test_production_module_avoids_forbidden_fragments(fragment: str) -> None:
    assert fragment not in MODULE_SOURCE


# 26.18 Scalability architecture -------------------------------------------


@pytest.mark.parametrize("fragment", CONCURRENCY_FRAGMENTS)
def test_production_module_avoids_concurrency_primitives(fragment: str) -> None:
    assert fragment not in MODULE_SOURCE


def test_production_module_declares_no_module_level_mutable_state() -> None:
    tree = ast.parse(MODULE_SOURCE)
    for node in tree.body:
        if isinstance(node, ast.Assign | ast.AnnAssign):
            value = node.value
            assert not isinstance(value, ast.Dict | ast.List | ast.Set | ast.DictComp)


def test_production_module_uses_exactly_one_timeout() -> None:
    assert MODULE_SOURCE.count("asyncio.timeout(") == 1


def test_production_module_never_hardcodes_a_generation_mode_constant() -> None:
    assert 'GENERATION_MODE: FinalGenerationMode = "model_generated"' not in MODULE_SOURCE
    assert "generation_mode: FinalGenerationMode" in MODULE_SOURCE


def test_finalization_never_resolves_once_per_citation() -> None:
    bundle = freshness_bundle(("current", "current"))
    plan = bundle_plan(bundle)
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    resolver = CitationSourceResolverFake(
        sources=tuple(
            resolved_source(evidence_id=item.evidence_id) for item in bundle.accepted_evidence
        )
    )
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    citation_ids = tuple(
        finalization_identifier(70 + index) for index in range(len(plan.citation_slots))
    )
    final = run(
        finalize(
            pending,
            renderer=renderer,
            resolver=resolver,
            injected=artifacts(citation_ids=citation_ids),
        )
    )
    assert renderer.calls == 1
    assert resolver.calls == 1
    assert len(resolver.requests[0].evidence_ids) == len(bundle.accepted_evidence)
    assert len(final.citations) == len(plan.citation_slots)


# 26.19 Dependency boundary ------------------------------------------------


def imported_roots() -> tuple[str, ...]:
    tree = ast.parse(MODULE_SOURCE)
    roots: tuple[str, ...] = ()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = (*roots, *(alias.name for alias in node.names))
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            assert node.module is not None
            roots = (*roots, node.module)
    return roots


def test_production_module_imports_only_allowed_packages() -> None:
    for name in imported_roots():
        root = name.split(".")[0]
        allowed = root in STDLIB_MODULES or name.startswith(ALLOWED_PACKAGES)
        assert allowed, name


@pytest.mark.parametrize("vendor", FORBIDDEN_VENDOR_ROOTS)
def test_production_module_imports_no_vendor_sdk(vendor: str) -> None:
    assert all(not name.startswith(vendor) for name in imported_roots())


def test_core_package_init_remains_import_free() -> None:
    source = CORE_INIT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
    assert "__all__: tuple[str, ...] = ()" in source


# Additional lineage and citation coverage ---------------------------------


CLAIM_SUBJECT = EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1")


def lineage_plan(
    *,
    request_id: UUID = REQUEST_ID,
    evidence_bundle_id: UUID = BUNDLE_ID,
    route_decision_id: UUID = ROUTE_DECISION_ID,
    plan_id: UUID = PLAN_ID,
    authorization_decision_id: UUID = AUTHORIZATION_ID,
    runtime_snapshot_id: UUID = SNAPSHOT_ID,
    correlation_id: UUID = CORRELATION_ID,
    locale: str = "fa-IR",
    decision: str = "answer",
    answer_type: str = "direct",
) -> AnswerPlan:
    """Build a structurally valid plan whose lineage fields can be perturbed."""
    claim = AnswerClaimPlan(
        claim_id="claim.document",
        claim_code="claim.document",
        claim_type="factual",
        subject=CLAIM_SUBJECT,
        supporting_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
    )
    caveat = AnswerCaveat(
        caveat_id="caveat.abstain",
        caveat_code="caveat.abstain",
        reason_codes=("evidence.empty",),
    )
    answered = decision == "answer"
    items = (
        AnswerSectionItemRef(
            item_kind="claim" if answered else "caveat",
            item_id=claim.claim_id if answered else caveat.caveat_id,
        ),
    )
    section = AnswerSection(
        section_id="section.answer" if answered else "section.abstain",
        section_type="answer" if answered else "abstention",
        items=items,
    )
    slots = (
        CitationSlot(
            slot_id="slot.claim.document",
            target_kind="claim",
            target_id="claim.document",
            evidence_ids=(EVIDENCE_ID,),
            placement="inline",
        ),
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=request_id,
        evidence_bundle_id=evidence_bundle_id,
        route_decision_id=route_decision_id,
        plan_id=plan_id,
        authorization_decision_id=authorization_decision_id,
        runtime_snapshot_id=runtime_snapshot_id,
        correlation_id=correlation_id,
        built_at=NOW,
        decision=decision,
        answer_type=answer_type,
        sections=(section,),
        claims=(claim,) if answered else (),
        caveats=() if answered else (caveat,),
        citation_slots=slots if answered else (),
        tone_constraints=AnswerToneConstraints(response_locale=locale, tone_codes=("clear",)),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.complete",) if answered else ("evidence.empty",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=1,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


def assert_plan_rejected(plan: AnswerPlan, *, bundle: EvidenceBundle | None = None) -> None:
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    assert_lineage_rejected(pending)


@pytest.mark.parametrize(
    "field_name",
    (
        "request_id",
        "route_decision_id",
        "plan_id",
        "authorization_decision_id",
        "runtime_snapshot_id",
        "correlation_id",
    ),
)
def test_answer_plan_lineage_fields_must_match(field_name: str) -> None:
    assert_plan_rejected(lineage_plan(**{field_name: FOREIGN_ID}))


def test_answer_plan_locale_must_match_the_turn_input() -> None:
    assert_plan_rejected(lineage_plan(locale="en-US"))


@pytest.mark.parametrize(
    "field_name",
    (
        "request_id",
        "route_decision_id",
        "authorization_id",
        "snapshot_id",
        "correlation_id",
    ),
)
def test_evidence_bundle_lineage_fields_must_match(field_name: str) -> None:
    bundle = evidence_bundle(**{field_name: FOREIGN_ID})
    pending = pending_finalization(
        result=completed_result(answer_plan=planned_answer(), bundle=bundle)
    )
    assert_lineage_rejected(pending)


def caveat_citation_plan() -> AnswerPlan:
    """Build an answered plan whose caveat also carries a citation slot."""
    claim = AnswerClaimPlan(
        claim_id="claim.document",
        claim_code="claim.document",
        claim_type="factual",
        subject=CLAIM_SUBJECT,
        supporting_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
    )
    caveat = AnswerCaveat(
        caveat_id="caveat.scope",
        caveat_code="caveat.scope",
        related_claim_ids=("claim.document",),
        evidence_ids=(EVIDENCE_ID,),
        reason_codes=("evidence.scope",),
    )
    items = (AnswerSectionItemRef(item_kind="claim", item_id="claim.document"),)
    items = (*items, AnswerSectionItemRef(item_kind="caveat", item_id="caveat.scope"))
    section = AnswerSection(section_id="section.answer", section_type="answer", items=items)
    slots = (
        CitationSlot(
            slot_id="slot.claim.document",
            target_kind="claim",
            target_id="claim.document",
            evidence_ids=(EVIDENCE_ID,),
            placement="inline",
        ),
        CitationSlot(
            slot_id="slot.caveat.scope",
            target_kind="caveat",
            target_id="caveat.scope",
            evidence_ids=(EVIDENCE_ID,),
            placement="section_end",
        ),
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=REQUEST_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        decision="answer",
        answer_type="direct",
        sections=(section,),
        claims=(claim,),
        caveats=(caveat,),
        citation_slots=slots,
        tone_constraints=AnswerToneConstraints(response_locale="fa-IR", tone_codes=("clear",)),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.complete",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=1,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


def test_a_caveat_citation_slot_is_compiled_from_trusted_metadata() -> None:
    plan = caveat_citation_plan()
    pending = pending_finalization(result=completed_result(answer_plan=plan))
    final = run(
        finalize(
            pending,
            renderer=AnswerRendererFake(draft=faithful_draft(plan)),
            resolver=CitationSourceResolverFake(sources=(resolved_source(),)),
            injected=artifacts(citation_ids=(CITATION_ID, SECOND_CITATION_ID)),
        )
    )
    assert final.outcome == "answered"
    assert tuple(citation.target_kind for citation in final.citations) == ("claim", "caveat")
    assert tuple(citation.placement for citation in final.citations) == ("inline", "section_end")
    assert tuple(citation.citation_id for citation in final.citations) == (
        CITATION_ID,
        SECOND_CITATION_ID,
    )
    assert final.response_metadata.citation_count == 2


def test_a_non_coordination_input_is_rejected() -> None:
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    with pytest.raises(ValueError):
        run(
            finalize_pending_answer(
                runtime_context(),
                "not-a-coordination-result",
                renderer=renderer,
                citation_source_resolver=document_resolver(),
                artifacts=artifacts(),
                entered_at=NOW,
                generation_mode=GENERATION_MODE,
            )
        )
    assert renderer.calls == 0


def test_an_abstained_bundle_bound_to_another_execution_plan_is_rejected() -> None:
    bundle = evidence_bundle(decision="abstain", plan_id=FOREIGN_ID)
    plan = planned_answer(decision="abstain")
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    assert_lineage_rejected(pending)


def test_bundle_required_facts_must_match_the_execution_plan() -> None:
    bundle = evidence_bundle(decision="abstain", required_fact_ids=("fact.other",))
    plan = planned_answer(decision="abstain")
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    assert_lineage_rejected(pending)


# 26.20 Department isolation and fail-closed sourcing (requirement 9) ------


def test_evidence_outside_the_accepted_bundle_cannot_be_cited() -> None:
    """No evidence outside EvidenceBundle.accepted_evidence may ever be cited,
    and no alternative or global-fallback source may be substituted for it."""
    assert_resolution_rejected(
        CitationSourceResolverFake(sources=(resolved_source(evidence_id=FOREIGN_EVIDENCE_ID),))
    )


def test_resolver_scope_is_limited_to_runtime_context_and_authorization() -> None:
    """The resolver request carries only RuntimeContext, AuthorizationDecision,
    the accepted EvidenceBundle, the approved AnswerPlan and the required
    evidence ids: no broader or process-local scope is ever passed."""
    assert set(CitationSourceResolutionRequest.__slots__) == {
        "context",
        "authorization",
        "evidence_bundle",
        "answer_plan",
        "evidence_ids",
    }


def test_missing_evidence_fails_closed_with_no_alternative_source_selected() -> None:
    """When the resolver cannot supply a required source, finalization fails
    closed with ValueError rather than silently answering without it."""
    assert_resolution_rejected(CitationSourceResolverFake(sources=()))


# 26.21 Fast-document evidence type enforcement (WS-004A-R3) --------------


def foreign_evidence_pending(evidence: Evidence) -> TerminalCoordinationResult:
    """Build a pending finalization whose accepted evidence is foreign.

    Every root identifier matches the canonical fast.document turn exactly;
    only the accepted evidence subtype is not DocumentEvidence.
    """
    bundle = foreign_capability_bundle(evidence)
    plan = build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        bundle,
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )
    return pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))


def assert_foreign_evidence_rejected(evidence: Evidence) -> None:
    pending = foreign_evidence_pending(evidence)
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def foreign_bundle_pending(bundle: EvidenceBundle) -> TerminalCoordinationResult:
    """Build a pending finalization from an already contract-valid bundle."""
    plan = build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        bundle,
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )
    return pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))


def assert_foreign_bundle_rejected(bundle: EvidenceBundle) -> None:
    pending = foreign_bundle_pending(bundle)
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_web_evidence_in_a_fast_document_bundle_is_rejected() -> None:
    assert_foreign_evidence_rejected(web_evidence(evidence_id=FOREIGN_EVIDENCE_ID))


def test_sql_evidence_in_a_fast_document_bundle_is_rejected() -> None:
    assert_foreign_evidence_rejected(sql_evidence(evidence_id=FOREIGN_EVIDENCE_ID))


def test_selector_evidence_in_a_fast_document_bundle_is_rejected() -> None:
    assert_foreign_evidence_rejected(selector_evidence(evidence_id=FOREIGN_EVIDENCE_ID))


def test_rule_evidence_in_a_fast_document_bundle_is_rejected() -> None:
    assert_foreign_bundle_rejected(rule_evidence_bundle())


def test_foreign_evidence_rejection_never_produces_an_answered_final_answer() -> None:
    pending = foreign_evidence_pending(web_evidence(evidence_id=FOREIGN_EVIDENCE_ID))
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = document_resolver()
    try:
        run(finalize(pending, renderer=renderer, resolver=resolver))
    except ValueError:
        pass
    else:
        raise AssertionError("expected finalization to fail closed for foreign evidence")
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_rejected_evidence_with_a_foreign_type_is_rejected_in_preflight() -> None:
    bundle = foreign_typed_rejected_bundle()
    plan = build_answer_plan(
        authorized_context(),
        query_analysis(),
        route_decision(),
        execution_plan(),
        bundle,
        answer_plan_id=ANSWER_PLAN_ID,
        built_at=NOW,
    )
    pending = pending_finalization(result=completed_result(answer_plan=plan, bundle=bundle))
    renderer = AnswerRendererFake(draft=faithful_draft(plan))
    resolver = document_resolver()
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def test_document_evidence_with_matching_locator_is_accepted() -> None:
    pending, renderer = answered_setup()
    resolver = document_resolver()
    final = run(finalize(pending, renderer=renderer, resolver=resolver))
    assert final.outcome == "answered"
    assert final.citations[0].sources[0].locator_ref == LOCATOR_REF


def test_document_evidence_with_a_foreign_locator_is_rejected() -> None:
    pending, renderer = answered_setup()
    resolver = CitationSourceResolverFake(
        sources=(resolved_source(locator_ref=FOREIGN_LOCATOR_REF),)
    )
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))


def test_resolved_source_for_non_document_evidence_is_rejected_even_if_bound() -> None:
    """A resolved source must describe DocumentEvidence: matching every other
    binding field is not sufficient once the accepted evidence itself is a
    foreign evidence subtype."""
    evidence = web_evidence(evidence_id=FOREIGN_EVIDENCE_ID)
    source = resolved_source(
        evidence_id=evidence.evidence_id,
        evidence_type=evidence.evidence_type,
        source_type=evidence.source.source_type,
        source_ref=evidence.source.source_ref,
        source_version=evidence.source.source_version,
        security_scope_ref=evidence.security_scope.scope_ref,
        locator_ref=evidence.locator_ref,
    )
    pending = foreign_evidence_pending(evidence)
    renderer = AnswerRendererFake(draft=faithful_draft(planned_answer()))
    resolver = CitationSourceResolverFake(sources=(source,))
    with pytest.raises(ValueError):
        run(finalize(pending, renderer=renderer, resolver=resolver))
    assert renderer.calls == 0
    assert resolver.calls == 0


def two_evidence_plan() -> AnswerPlan:
    """Build a two-claim answered plan citing two distinct evidence records."""
    subject = EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1")
    claims = (
        AnswerClaimPlan(
            claim_id="claim.first",
            claim_code="claim.first",
            claim_type="factual",
            subject=subject,
            supporting_fact_ids=(DOCUMENT_FACT_ID,),
            evidence_ids=(EVIDENCE_ID,),
        ),
        AnswerClaimPlan(
            claim_id="claim.second",
            claim_code="claim.second",
            claim_type="factual",
            subject=subject,
            supporting_fact_ids=(DOCUMENT_FACT_ID,),
            evidence_ids=(SECOND_EVIDENCE_ID,),
        ),
    )
    sections = tuple(
        AnswerSection(
            section_id=section_id,
            section_type="answer",
            items=(AnswerSectionItemRef(item_kind="claim", item_id=claim.claim_id),),
        )
        for section_id, claim in zip(("section.first", "section.second"), claims, strict=True)
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=REQUEST_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        decision="answer",
        answer_type="direct",
        sections=sections,
        claims=claims,
        caveats=(),
        citation_slots=(
            CitationSlot(
                slot_id="slot.claim.first",
                target_kind="claim",
                target_id="claim.first",
                evidence_ids=(EVIDENCE_ID,),
                placement="inline",
            ),
            CitationSlot(
                slot_id="slot.claim.second",
                target_kind="claim",
                target_id="claim.second",
                evidence_ids=(SECOND_EVIDENCE_ID,),
                placement="inline",
            ),
        ),
        tone_constraints=AnswerToneConstraints(response_locale="fa-IR", tone_codes=("clear",)),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.complete",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=2,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


def two_evidence_bundle() -> EvidenceBundle:
    return freshness_bundle(("current", "current"))


def test_citation_source_request_rejects_a_foreign_evidence_id() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=evidence_bundle(),
            answer_plan=planned_answer(),
            evidence_ids=(FOREIGN_EVIDENCE_ID,),
        )


def test_citation_source_request_rejects_an_accepted_but_unplanned_evidence_id() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=two_evidence_bundle(),
            answer_plan=planned_answer(),
            evidence_ids=(EVIDENCE_ID, SECOND_EVIDENCE_ID),
        )


def test_citation_source_request_rejects_a_missing_planned_evidence_id() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=two_evidence_bundle(),
            answer_plan=two_evidence_plan(),
            evidence_ids=(EVIDENCE_ID,),
        )


def test_citation_source_request_rejects_reordered_evidence_ids() -> None:
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=two_evidence_bundle(),
            answer_plan=two_evidence_plan(),
            evidence_ids=(SECOND_EVIDENCE_ID, EVIDENCE_ID),
        )


def test_citation_source_request_accepts_the_exact_ordered_deduplicated_ids() -> None:
    request = CitationSourceResolutionRequest(
        context=runtime_context(),
        authorization=authorization(),
        evidence_bundle=two_evidence_bundle(),
        answer_plan=two_evidence_plan(),
        evidence_ids=(EVIDENCE_ID, SECOND_EVIDENCE_ID),
    )
    assert request.evidence_ids == (EVIDENCE_ID, SECOND_EVIDENCE_ID)


def rejected_evidence_plan() -> AnswerPlan:
    """A single-claim plan whose lone citation slot cites a rejected evidence id.

    Used to prove that a requested evidence id must belong to
    evidence_bundle.accepted_evidence even when it exactly matches what the
    plan's citation slots require.
    """
    subject = EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1")
    claim = AnswerClaimPlan(
        claim_id="claim.rejected",
        claim_code="claim.rejected",
        claim_type="factual",
        subject=subject,
        supporting_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_ids=(FOREIGN_EVIDENCE_ID,),
    )
    section = AnswerSection(
        section_id="section.rejected",
        section_type="answer",
        items=(AnswerSectionItemRef(item_kind="claim", item_id=claim.claim_id),),
    )
    return AnswerPlan(
        answer_plan_id=ANSWER_PLAN_ID,
        request_id=REQUEST_ID,
        evidence_bundle_id=BUNDLE_ID,
        route_decision_id=ROUTE_DECISION_ID,
        plan_id=PLAN_ID,
        authorization_decision_id=AUTHORIZATION_ID,
        runtime_snapshot_id=SNAPSHOT_ID,
        correlation_id=CORRELATION_ID,
        built_at=NOW,
        decision="answer",
        answer_type="direct",
        sections=(section,),
        claims=(claim,),
        caveats=(),
        citation_slots=(
            CitationSlot(
                slot_id="slot.claim.rejected",
                target_kind="claim",
                target_id="claim.rejected",
                evidence_ids=(FOREIGN_EVIDENCE_ID,),
                placement="inline",
            ),
        ),
        tone_constraints=AnswerToneConstraints(response_locale="fa-IR", tone_codes=("clear",)),
        prohibited_content_codes=("content.secrets",),
        decision_reason_codes=("evidence.complete",),
        length_budget=AnswerLengthBudget(
            max_characters=2000,
            max_sections=2,
            max_claims=32,
            max_caveats=1,
            max_citations=32,
        ),
        answer_plan_builder_version="1.0.0",
    )


def test_citation_source_request_rejects_a_rejected_evidence_id() -> None:
    """An id that matches the plan's citation slot exactly but is declared in
    evidence_bundle.rejected_evidence must still be refused: matching the
    expected-id tuple is not sufficient on its own."""
    with pytest.raises(ValueError):
        CitationSourceResolutionRequest(
            context=runtime_context(),
            authorization=authorization(),
            evidence_bundle=foreign_typed_rejected_bundle(),
            answer_plan=rejected_evidence_plan(),
            evidence_ids=(FOREIGN_EVIDENCE_ID,),
        )
