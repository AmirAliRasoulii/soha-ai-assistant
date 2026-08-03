"""Deterministic typed builders for the WS-002 walking skeleton tests."""

from datetime import UTC, datetime
from uuid import UUID

from ai_assistant.contracts import (
    AllowedEvidenceClaim,
    AmbiguityLevel,
    AnswerCaveat,
    AnswerClaimPlan,
    AnswerLengthBudget,
    AnswerPlan,
    AnswerSection,
    AnswerSectionItemRef,
    AnswerToneConstraints,
    AuthorizationDecision,
    AuthorizationResourceRef,
    CapabilityName,
    CitationSlot,
    CompositionType,
    DocumentEvidence,
    ErrorCode,
    Evidence,
    EvidenceBundle,
    EvidenceDecision,
    EvidenceFreshness,
    EvidenceNeed,
    EvidenceProvenance,
    EvidenceSecurityScope,
    EvidenceSourceRef,
    EvidenceSourceTime,
    EvidenceSubjectRef,
    EvidenceValidationStatus,
    EvidenceValidityWindow,
    ExecutionLane,
    ExecutionPlan,
    FactDataScope,
    FactEvidenceMapEntry,
    MissingEvidencePolicy,
    PlanFactSpec,
    PlanParallelGroup,
    PlanStep,
    ProhibitedEvidenceClaim,
    QueryAnalysis,
    QueryIntent,
    RejectedEvidenceRef,
    RiskLevel,
    RouteBudget,
    RouteDecision,
    RouteFilterRef,
    RouteLane,
    RuntimeArtifactRef,
    RuntimeSnapshot,
    RuntimeSnapshotContent,
    RuntimeSnapshotIntegrity,
    SecurityPrincipalContext,
    SqlEvidence,
    StepEvidenceRef,
    StepProvenance,
    StepResult,
    StepRetryMetadata,
    StepStatus,
    StepTypedOutputRef,
    TurnInput,
)
from ai_assistant.core.types import AuthorizedRuntimeContext, RuntimeContext


def _identifier(index: int) -> UUID:
    return UUID(f"{index:08d}-0000-4000-8000-000000000000")


REQUEST_ID = _identifier(1)
MESSAGE_ID = _identifier(2)
CONVERSATION_ID = _identifier(3)
IDEMPOTENCY_KEY = _identifier(4)
SECURITY_CONTEXT_ID = _identifier(5)
PRINCIPAL_ID = _identifier(6)
DEPLOYMENT_ID = _identifier(7)
AUTHORIZATION_ID = _identifier(8)
SNAPSHOT_ID = _identifier(9)
ANALYSIS_ID = _identifier(10)
ROUTE_DECISION_ID = _identifier(11)
PLAN_ID = _identifier(12)
STEP_RESULT_ID = _identifier(13)
EVIDENCE_ID = _identifier(14)
SECOND_EVIDENCE_ID = _identifier(15)
BUNDLE_ID = _identifier(16)
ANSWER_PLAN_ID = _identifier(17)
FOREIGN_ID = _identifier(18)
CORRELATION_ID = _identifier(19)

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
CORRELATION_TEXT = str(CORRELATION_ID)
SNAPSHOT_DIGEST = "sha256:" + "a" * 64
HEX_DIGEST = "b" * 64
RAW_MESSAGE = "sentinel-raw-message"
CONTENT_REF = "sentinel-content-ref"
DOCUMENT_REF = "sentinel-document-ref"
DOCUMENT_CAPABILITY: CapabilityName = "document_retrieval"
ANALYTICS_CAPABILITY: CapabilityName = "semantic_analytics"
DOCUMENT_FACT_ID = "fact.document"
SECOND_FACT_ID = "fact.support"
DOCUMENT_VALUE_TYPE = "type.document"
RETRIEVE_STEP_ID = "step.retrieve"
RETRIEVE_OPERATION = "document.retrieve"
RETRIEVE_GROUP_ID = "group.retrieve"
PLAN_GOAL = "goal.answer_question"
FAILURE_CODE: ErrorCode = "INTERNAL_ERROR"


def turn_input(*, request_id: UUID = REQUEST_ID, message_id: UUID = MESSAGE_ID) -> TurnInput:
    return TurnInput(
        request_id=request_id,
        message_id=message_id,
        conversation_id=CONVERSATION_ID,
        raw_message=RAW_MESSAGE,
        received_at=NOW,
        idempotency_key=IDEMPOTENCY_KEY,
    )


def principal() -> SecurityPrincipalContext:
    return SecurityPrincipalContext(
        context_id=SECURITY_CONTEXT_ID,
        principal_id=PRINCIPAL_ID,
        principal_type="user",
        deployment_id=DEPLOYMENT_ID,
        issuer="urn:test:issuer",
        authenticated_at=NOW,
        authentication_methods=("password",),
        assurance_level="assurance.standard",
    )


def authorization(
    *,
    decision_id: UUID = AUTHORIZATION_ID,
    request_id: UUID = REQUEST_ID,
) -> AuthorizationDecision:
    return AuthorizationDecision(
        decision_id=decision_id,
        request_id=request_id,
        security_context_id=SECURITY_CONTEXT_ID,
        action="runtime.answer",
        resource=AuthorizationResourceRef(
            resource_type="conversation",
            resource_id=str(CONVERSATION_ID),
        ),
        effect="allow",
        reason_codes=("policy.allow",),
        policy_version="1.0.0",
        evaluated_at=NOW,
    )


def _artifact(artifact_id: str) -> RuntimeArtifactRef:
    return RuntimeArtifactRef(artifact_id=artifact_id, revision="1", digest=SNAPSHOT_DIGEST)


def runtime_snapshot(*, snapshot_id: UUID = SNAPSHOT_ID) -> RuntimeSnapshot:
    content = RuntimeSnapshotContent(
        application_version="1.0.0",
        source_revision="a" * 40,
        build_artifact=_artifact("build"),
        config_bundle=_artifact("config"),
        prompt_bundle=_artifact("prompt"),
        model_policy=_artifact("model-policy"),
        model_artifacts=(_artifact("model"),),
        structured_output_backend=_artifact("structured-output"),
        retrieval_profile=_artifact("retrieval"),
        embedding_artifact=_artifact("embedding"),
        reranker_artifact=_artifact("reranker"),
        index_snapshot=_artifact("index"),
        semantic_catalog=_artifact("catalog"),
        rule_bundle=_artifact("rules"),
        security_policy=_artifact("security"),
        telemetry_schema=_artifact("telemetry"),
    )
    return RuntimeSnapshot(
        snapshot_id=snapshot_id,
        captured_at=NOW,
        content=content,
        integrity=RuntimeSnapshotIntegrity(canonicalization="rfc8785", digest=SNAPSHOT_DIGEST),
    )


def runtime_context(
    *,
    request_id: UUID = REQUEST_ID,
    message_id: UUID = MESSAGE_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    correlation_id: str = CORRELATION_TEXT,
) -> RuntimeContext:
    return RuntimeContext(
        turn_input=turn_input(request_id=request_id, message_id=message_id),
        principal=principal(),
        runtime_snapshot=runtime_snapshot(snapshot_id=snapshot_id),
        correlation_id=correlation_id,
        started_at=NOW,
    )


def authorized_context(
    *,
    request_id: UUID = REQUEST_ID,
    message_id: UUID = MESSAGE_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    correlation_id: str = CORRELATION_TEXT,
    authorization_id: UUID = AUTHORIZATION_ID,
) -> AuthorizedRuntimeContext:
    return AuthorizedRuntimeContext(
        runtime=runtime_context(
            request_id=request_id,
            message_id=message_id,
            snapshot_id=snapshot_id,
            correlation_id=correlation_id,
        ),
        authorization=authorization(decision_id=authorization_id, request_id=request_id),
    )


def query_analysis(
    *,
    analysis_id: UUID = ANALYSIS_ID,
    request_id: UUID = REQUEST_ID,
    message_id: UUID = MESSAGE_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    intent: QueryIntent = "factual",
    evidence_needs: tuple[EvidenceNeed, ...] = ("document",),
    ambiguity_level: AmbiguityLevel = "none",
    ambiguity_codes: tuple[str, ...] = (),
    is_personal: bool = False,
    is_multi_part: bool = False,
    risk_level: RiskLevel = "normal",
    risk_signals: tuple[str, ...] = (),
    confidence: float = 0.9,
) -> QueryAnalysis:
    return QueryAnalysis(
        analysis_id=analysis_id,
        request_id=request_id,
        message_id=message_id,
        runtime_snapshot_id=snapshot_id,
        analyzed_at=NOW,
        normalized_query="normalized query",
        intent=intent,
        ambiguity_level=ambiguity_level,
        ambiguity_codes=ambiguity_codes,
        is_personal=is_personal,
        is_multi_part=is_multi_part,
        risk_level=risk_level,
        risk_signals=risk_signals,
        evidence_needs=evidence_needs,
        confidence=confidence,
        analyzer_version="1.0.0",
    )


def route_budget(
    *,
    max_steps: int = 1,
    max_parallel_steps: int = 1,
    max_replans: int = 0,
    max_retrieval_retries: int = 0,
    max_analytics_repairs: int = 0,
    max_answer_repairs: int = 0,
) -> RouteBudget:
    return RouteBudget(
        max_steps=max_steps,
        max_parallel_steps=max_parallel_steps,
        max_replans=max_replans,
        max_retrieval_retries=max_retrieval_retries,
        max_analytics_repairs=max_analytics_repairs,
        max_answer_repairs=max_answer_repairs,
    )


def route_filter(
    *,
    filter_type: str = "filter.document_scope",
    filter_ref: str = "filter:documents",
) -> RouteFilterRef:
    return RouteFilterRef(filter_type=filter_type, filter_ref=filter_ref)


def route_decision(
    *,
    decision_id: UUID = ROUTE_DECISION_ID,
    request_id: UUID = REQUEST_ID,
    analysis_id: UUID = ANALYSIS_ID,
    authorization_id: UUID = AUTHORIZATION_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    lane: RouteLane = "fast",
    route: str = "fast.document",
    capabilities: tuple[CapabilityName, ...] = (DOCUMENT_CAPABILITY,),
    required_facts: tuple[str, ...] = (DOCUMENT_FACT_ID,),
    rationale_code: str = "query.single_document_need",
    effective_risk_level: RiskLevel = "normal",
    approved_flow_ref: str | None = None,
    filters: tuple[RouteFilterRef, ...] = (),
    policy_version: str = "1.0.0",
    budget: RouteBudget | None = None,
) -> RouteDecision:
    return RouteDecision(
        decision_id=decision_id,
        request_id=request_id,
        query_analysis_id=analysis_id,
        authorization_decision_id=authorization_id,
        runtime_snapshot_id=snapshot_id,
        decided_at=NOW,
        effective_risk_level=effective_risk_level,
        lane=lane,
        route=route,
        allowed_capabilities=capabilities,
        required_facts=required_facts,
        planner_required=lane == "composite",
        filters=filters,
        budget=budget if budget is not None else route_budget(),
        rationale_code=rationale_code,
        policy_version=policy_version,
        approved_flow_ref=approved_flow_ref,
    )


def terminal_route_decision(*, lane: RouteLane = "abstain") -> RouteDecision:
    return route_decision(
        lane=lane,
        route=f"{lane}.terminal_flow",
        capabilities=(),
        required_facts=(),
        rationale_code="query.unsupported_flow",
        budget=route_budget(max_steps=0, max_parallel_steps=0),
    )


def fact_spec(
    *,
    fact_id: str = DOCUMENT_FACT_ID,
    value_type: str = DOCUMENT_VALUE_TYPE,
    data_scope: FactDataScope = "general",
) -> PlanFactSpec:
    return PlanFactSpec(fact_id=fact_id, value_type=value_type, data_scope=data_scope)


def plan_step(
    *,
    step_id: str = RETRIEVE_STEP_ID,
    capability: CapabilityName = DOCUMENT_CAPABILITY,
    operation: str = RETRIEVE_OPERATION,
    produces: tuple[PlanFactSpec, ...] | None = None,
) -> PlanStep:
    return PlanStep(
        step_id=step_id,
        capability=capability,
        operation=operation,
        depends_on=(),
        input_bindings=(),
        produces=produces if produces is not None else (fact_spec(),),
        required=True,
    )


def execution_plan(
    *,
    plan_id: UUID = PLAN_ID,
    request_id: UUID = REQUEST_ID,
    route_decision_id: UUID = ROUTE_DECISION_ID,
    authorization_id: UUID = AUTHORIZATION_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    lane: ExecutionLane = "fast",
    capabilities: tuple[CapabilityName, ...] = (DOCUMENT_CAPABILITY,),
    required_facts: tuple[str, ...] = (DOCUMENT_FACT_ID,),
    steps: tuple[PlanStep, ...] | None = None,
    parallel_groups: tuple[PlanParallelGroup, ...] | None = None,
    composition_type: CompositionType = "single",
    budget: RouteBudget | None = None,
    goal: str = PLAN_GOAL,
    missing_evidence_policy: MissingEvidencePolicy = "abstain",
    plan_builder_version: str = "1.0.0",
) -> ExecutionPlan:
    plan_steps = steps if steps is not None else (plan_step(),)
    groups = (
        parallel_groups
        if parallel_groups is not None
        else (
            PlanParallelGroup(
                group_id=RETRIEVE_GROUP_ID,
                step_ids=tuple(step.step_id for step in plan_steps),
            ),
        )
    )
    return ExecutionPlan(
        plan_id=plan_id,
        request_id=request_id,
        route_decision_id=route_decision_id,
        authorization_decision_id=authorization_id,
        runtime_snapshot_id=snapshot_id,
        planned_at=NOW,
        lane=lane,
        goal=goal,
        allowed_capabilities=capabilities,
        required_facts=required_facts,
        steps=plan_steps,
        parallel_groups=groups,
        composition_type=composition_type,
        success_condition="all_required_facts",
        missing_evidence_policy=missing_evidence_policy,
        budget=budget if budget is not None else route_budget(),
        revision=0,
        parent_plan_id=None,
        plan_builder_version=plan_builder_version,
    )


def parallel_group(
    *,
    group_id: str = RETRIEVE_GROUP_ID,
    step_ids: tuple[str, ...] = (RETRIEVE_STEP_ID,),
) -> PlanParallelGroup:
    return PlanParallelGroup(group_id=group_id, step_ids=step_ids)


def deterministic_two_step_plan() -> ExecutionPlan:
    steps = (
        plan_step(),
        plan_step(step_id="step.second", produces=(fact_spec(fact_id=SECOND_FACT_ID),)),
    )
    return execution_plan(
        lane="deterministic",
        required_facts=(DOCUMENT_FACT_ID, SECOND_FACT_ID),
        steps=steps,
        composition_type="sectioned",
        budget=route_budget(max_steps=2, max_parallel_steps=2),
    )


def two_fact_execution_plan() -> ExecutionPlan:
    step = plan_step(produces=(fact_spec(), fact_spec(fact_id=SECOND_FACT_ID)))
    return execution_plan(
        required_facts=(DOCUMENT_FACT_ID, SECOND_FACT_ID),
        steps=(step,),
    )


def typed_output(
    *,
    fact_id: str = DOCUMENT_FACT_ID,
    value_type: str = DOCUMENT_VALUE_TYPE,
    data_scope: FactDataScope = "general",
) -> StepTypedOutputRef:
    return StepTypedOutputRef(
        fact_id=fact_id,
        value_type=value_type,
        data_scope=data_scope,
        schema_ref="schema:document",
        value_ref="value:document",
        sha256=HEX_DIGEST,
    )


def evidence_ref(
    *,
    evidence_id: UUID = EVIDENCE_ID,
    supports_fact_ids: tuple[str, ...] = (DOCUMENT_FACT_ID,),
) -> StepEvidenceRef:
    return StepEvidenceRef(evidence_id=evidence_id, supports_fact_ids=supports_fact_ids)


def retry_metadata(
    *,
    attempt: int = 1,
    max_attempts: int = 1,
    retryable: bool = False,
    previous_result_id: UUID | None = None,
) -> StepRetryMetadata:
    return StepRetryMetadata(
        attempt=attempt,
        max_attempts=max_attempts,
        retryable=retryable,
        previous_result_id=previous_result_id,
    )


def step_result(
    *,
    result_id: UUID = STEP_RESULT_ID,
    request_id: UUID = REQUEST_ID,
    plan_id: UUID = PLAN_ID,
    step_id: str = RETRIEVE_STEP_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    correlation_id: UUID = CORRELATION_ID,
    status: StepStatus = "success",
    typed_outputs: tuple[StepTypedOutputRef, ...] | None = None,
    missing_fact_ids: tuple[str, ...] = (),
    evidence_refs: tuple[StepEvidenceRef, ...] | None = None,
    capability: CapabilityName = DOCUMENT_CAPABILITY,
    operation: str = RETRIEVE_OPERATION,
    retry: StepRetryMetadata | None = None,
    failure_code: ErrorCode | None = None,
) -> StepResult:
    return StepResult(
        result_id=result_id,
        request_id=request_id,
        plan_id=plan_id,
        step_id=step_id,
        runtime_snapshot_id=snapshot_id,
        correlation_id=correlation_id,
        completed_at=NOW,
        status=status,
        typed_outputs=typed_outputs if typed_outputs is not None else (typed_output(),),
        missing_fact_ids=missing_fact_ids,
        evidence_refs=evidence_refs if evidence_refs is not None else (evidence_ref(),),
        latency_ms=12,
        retry=retry if retry is not None else retry_metadata(),
        failure_code=failure_code,
        provenance=StepProvenance(
            capability=capability,
            operation=operation,
            implementation_version="1.0.0",
            input_digest=HEX_DIGEST,
        ),
    )


def failed_step_result(*, missing_fact_ids: tuple[str, ...] = (DOCUMENT_FACT_ID,)) -> StepResult:
    return step_result(
        status="failed",
        typed_outputs=(),
        missing_fact_ids=missing_fact_ids,
        evidence_refs=(),
        failure_code=FAILURE_CODE,
    )


def evidence_provenance(
    *,
    step_result_id: UUID = STEP_RESULT_ID,
    plan_id: UUID = PLAN_ID,
    step_id: str = RETRIEVE_STEP_ID,
    capability: CapabilityName = DOCUMENT_CAPABILITY,
    operation: str = RETRIEVE_OPERATION,
) -> EvidenceProvenance:
    return EvidenceProvenance(
        step_result_id=step_result_id,
        plan_id=plan_id,
        step_id=step_id,
        capability=capability,
        operation=operation,
        materializer_version="1.0.0",
        input_digest=HEX_DIGEST,
    )


def document_evidence(
    *,
    evidence_id: UUID = EVIDENCE_ID,
    supports_fact_ids: tuple[str, ...] = (DOCUMENT_FACT_ID,),
    validation_status: EvidenceValidationStatus = "validated",
    freshness: EvidenceFreshness = "current",
    provenance: EvidenceProvenance | None = None,
    subject_ref: str = "subject:document-1",
    data_scope: FactDataScope = "general",
    allowed_uses: tuple[str, ...] = ("use.answer",),
) -> DocumentEvidence:
    return DocumentEvidence(
        evidence_id=evidence_id,
        subject=EvidenceSubjectRef(subject_type="document", subject_ref=subject_ref),
        valid_time=EvidenceValidityWindow(as_of=NOW),
        source_time=EvidenceSourceTime(observed_at=NOW),
        source=EvidenceSourceRef(
            source_type="document_store",
            source_ref="store:main",
            source_version="1",
        ),
        authority="authority.internal",
        security_scope=EvidenceSecurityScope(
            scope_ref=f"scope:{data_scope}",
            data_scope=data_scope,
            classification="classification.internal",
        ),
        validation_status=validation_status,
        freshness=freshness,
        provenance=provenance if provenance is not None else evidence_provenance(),
        allowed_uses=allowed_uses,
        retention_class="retention.standard",
        supports_fact_ids=supports_fact_ids,
        document_ref=DOCUMENT_REF,
        document_version="1",
        chunk_ref="chunk:1",
        locator_ref="locator:1",
        content_ref=CONTENT_REF,
        content_sha256=HEX_DIGEST,
    )


def sql_evidence(*, evidence_id: UUID = EVIDENCE_ID) -> SqlEvidence:
    return SqlEvidence(
        evidence_id=evidence_id,
        subject=EvidenceSubjectRef(subject_type="dataset", subject_ref="subject:dataset-1"),
        valid_time=EvidenceValidityWindow(as_of=NOW),
        source_time=EvidenceSourceTime(observed_at=NOW),
        source=EvidenceSourceRef(
            source_type="semantic_layer",
            source_ref="catalog:main",
            source_version="1",
        ),
        authority="authority.internal",
        security_scope=EvidenceSecurityScope(
            scope_ref="scope:general",
            data_scope="general",
            classification="classification.internal",
        ),
        validation_status="validated",
        freshness="current",
        provenance=evidence_provenance(capability=ANALYTICS_CAPABILITY, operation="analytics.run"),
        allowed_uses=("use.answer",),
        retention_class="retention.standard",
        supports_fact_ids=(DOCUMENT_FACT_ID,),
        semantic_query_ref="query:1",
        semantic_catalog_version="1.0.0",
        result_ref="result:1",
        result_sha256=HEX_DIGEST,
        metric_codes=("metric.count",),
        result_shape="shape.scalar",
        suppression_applied=False,
    )


def allowed_claim(
    *,
    supporting_fact_ids: tuple[str, ...] = (DOCUMENT_FACT_ID,),
    evidence_ids: tuple[UUID, ...] = (EVIDENCE_ID,),
    subject_ref: str = "subject:document-1",
) -> AllowedEvidenceClaim:
    return AllowedEvidenceClaim(
        claim_id="claim.document",
        claim_code="claim.document",
        claim_type="factual",
        subject=EvidenceSubjectRef(subject_type="document", subject_ref=subject_ref),
        supporting_fact_ids=supporting_fact_ids,
        evidence_ids=evidence_ids,
    )


def evidence_bundle(
    *,
    bundle_id: UUID = BUNDLE_ID,
    request_id: UUID = REQUEST_ID,
    route_decision_id: UUID = ROUTE_DECISION_ID,
    plan_id: UUID = PLAN_ID,
    authorization_id: UUID = AUTHORIZATION_ID,
    snapshot_id: UUID = SNAPSHOT_ID,
    correlation_id: UUID = CORRELATION_ID,
    decision: EvidenceDecision = "answer",
    required_fact_ids: tuple[str, ...] = (DOCUMENT_FACT_ID,),
    prohibited_claims: tuple[ProhibitedEvidenceClaim, ...] = (),
) -> EvidenceBundle:
    accepted: tuple[Evidence, ...] = ()
    rejected: tuple[RejectedEvidenceRef, ...] = ()
    fact_map: tuple[FactEvidenceMapEntry, ...] = ()
    missing: tuple[str, ...] = ()
    claims: tuple[AllowedEvidenceClaim, ...] = ()
    reason_codes: tuple[str, ...] = ("evidence.complete",)
    if decision in ("answer", "partial_answer"):
        degraded = decision == "partial_answer"
        accepted = (document_evidence(validation_status="degraded" if degraded else "validated"),)
        fact_map = (FactEvidenceMapEntry(fact_id=DOCUMENT_FACT_ID, evidence_ids=(EVIDENCE_ID,)),)
        claims = (allowed_claim(),)
        if degraded:
            reason_codes = ("evidence.degraded",)
    else:
        missing = required_fact_ids
        reason_codes = ("evidence.empty",)
    return EvidenceBundle(
        bundle_id=bundle_id,
        request_id=request_id,
        route_decision_id=route_decision_id,
        plan_id=plan_id,
        authorization_decision_id=authorization_id,
        runtime_snapshot_id=snapshot_id,
        correlation_id=correlation_id,
        built_at=NOW,
        required_fact_ids=required_fact_ids,
        accepted_evidence=accepted,
        rejected_evidence=rejected,
        fact_map=fact_map,
        missing_fact_ids=missing,
        conflicts=(),
        sufficient=decision == "answer",
        decision=decision,
        allowed_claims=claims,
        prohibited_claims=prohibited_claims,
        decision_reason_codes=reason_codes,
        evidence_manager_version="1.0.0",
    )


def answer_plan(*, answer_plan_id: UUID = ANSWER_PLAN_ID) -> AnswerPlan:
    claim = AnswerClaimPlan(
        claim_id="claim.document",
        claim_code="claim.document",
        claim_type="factual",
        subject=EvidenceSubjectRef(subject_type="document", subject_ref="subject:document-1"),
        supporting_fact_ids=(DOCUMENT_FACT_ID,),
        evidence_ids=(EVIDENCE_ID,),
    )
    return AnswerPlan(
        answer_plan_id=answer_plan_id,
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
        sections=(
            AnswerSection(
                section_id="section.answer",
                section_type="answer",
                items=(AnswerSectionItemRef(item_kind="claim", item_id="claim.document"),),
            ),
        ),
        claims=(claim,),
        caveats=(),
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
            tone_codes=("clear", "concise"),
        ),
        prohibited_claim_codes=(),
        prohibited_content_codes=(
            "content.raw_evidence",
            "content.secrets",
            "claim.unsupported",
        ),
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


def abstention_caveat(*, reason_codes: tuple[str, ...] = ("evidence.empty",)) -> AnswerCaveat:
    return AnswerCaveat(
        caveat_id="caveat.abstain",
        caveat_code="caveat.insufficient_evidence",
        related_claim_ids=(),
        evidence_ids=(),
        reason_codes=reason_codes,
    )
