"""Tests for the deterministic routing policy and Core module boundaries."""

import ast
import sys
from pathlib import Path
from uuid import UUID

import pytest
from support.walking_skeleton_fixtures import (
    ANALYSIS_ID,
    AUTHORIZATION_ID,
    FOREIGN_ID,
    NOW,
    REQUEST_ID,
    ROUTE_DECISION_ID,
    SNAPSHOT_ID,
    authorized_context,
    query_analysis,
)

from ai_assistant.contracts import AmbiguityLevel, EvidenceNeed, QueryIntent, RiskLevel
from ai_assistant.core.routing import route_query

CORE_PACKAGE = "ai_assistant.core"
CORE_DIRECTORY = Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "core"
NEW_CORE_MODULES = (
    "routing.py",
    "planning.py",
    "step_validation.py",
    "evidence_manager.py",
    "answer_planning.py",
)
ALLOWED_IMPORT_PREFIXES = ("ai_assistant.contracts", "ai_assistant.core")
FORBIDDEN_VENDOR_ROOTS = (
    "boto3",
    "django",
    "fastapi",
    "httpx",
    "openai",
    "psycopg",
    "pydantic",
    "redis",
    "requests",
    "sqlalchemy",
)
FORBIDDEN_SOURCE_FRAGMENTS = (
    "uuid4",
    "datetime.now",
    "utcnow",
    "model_construct",
    "model_copy",
    "type: ignore",
    "noqa",
    "cast(",
    "dict[",
    "Mapping[",
    "Any",
    "os.environ",
    "open(",
    "logging",
)


def _source(module_file: str) -> str:
    return (CORE_DIRECTORY / module_file).read_text(encoding="utf-8")


def _imported_modules(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    package_parts = CORE_PACKAGE.split(".")
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package_parts[: len(package_parts) - node.level + 1]
                names.append(".".join([*base, node.module]) if node.module else ".".join(base))
            else:
                names.append(node.module or "")
    return tuple(names)


def _is_allowed_import(module_name: str) -> bool:
    if module_name.split(".")[0] in sys.stdlib_module_names:
        return True
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in ALLOWED_IMPORT_PREFIXES
    )


def test_factual_document_query_routes_to_the_fast_document_lane() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.decision_id == ROUTE_DECISION_ID
    assert decision.decided_at == NOW
    assert decision.request_id == REQUEST_ID
    assert decision.query_analysis_id == ANALYSIS_ID
    assert decision.authorization_decision_id == AUTHORIZATION_ID
    assert decision.runtime_snapshot_id == SNAPSHOT_ID
    assert decision.lane == "fast"
    assert decision.route == "fast.document"
    assert decision.effective_risk_level == "normal"
    assert decision.allowed_capabilities == ("document_retrieval",)
    assert decision.required_facts == ("fact.document",)
    assert decision.planner_required is False
    assert decision.filters == ()
    assert decision.approved_flow_ref is None
    assert decision.rationale_code == "query.single_document_need"
    assert decision.policy_version == "1.0.0"


def test_fast_route_budget_allows_exactly_one_step() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    budget = decision.budget
    assert budget.max_steps == 1
    assert budget.max_parallel_steps == 1
    assert budget.max_replans == 0
    assert budget.max_retrieval_retries == 0
    assert budget.max_analytics_repairs == 0
    assert budget.max_answer_repairs == 0


def test_routing_is_deterministic_for_equal_inputs() -> None:
    context = authorized_context()
    analysis = query_analysis()
    first = route_query(context, analysis, decision_id=ROUTE_DECISION_ID, decided_at=NOW)
    second = route_query(context, analysis, decision_id=ROUTE_DECISION_ID, decided_at=NOW)
    assert first == second


@pytest.mark.parametrize("confidence", [0.0, 0.25, 0.5, 0.99, 1.0])
def test_confidence_alone_never_changes_the_route(confidence: float) -> None:
    context = authorized_context()
    baseline = route_query(
        context,
        query_analysis(confidence=0.9),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    observed = route_query(
        context,
        query_analysis(confidence=confidence),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert observed == baseline


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
        route_query(
            authorized_context(),
            query_analysis(**overrides),
            decision_id=ROUTE_DECISION_ID,
            decided_at=NOW,
        )


@pytest.mark.parametrize(
    ("ambiguity_level", "ambiguity_codes"),
    [
        ("blocking", ("ambiguity.multiple_subjects",)),
        ("non_blocking", ("ambiguity.vague_time_range",)),
    ],
)
def test_ambiguous_query_routes_to_clarify(
    ambiguity_level: AmbiguityLevel,
    ambiguity_codes: tuple[str, ...],
) -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(ambiguity_level=ambiguity_level, ambiguity_codes=ambiguity_codes),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "clarify"
    assert decision.route == "clarify.ambiguous_query"
    assert decision.rationale_code == "query.requires_clarification"
    assert decision.allowed_capabilities == ()
    assert decision.required_facts == ()
    assert decision.budget.is_all_zero()


def test_ambiguity_takes_precedence_over_an_unsupported_shape() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(
            intent="analytics",
            evidence_needs=("analytics",),
            ambiguity_level="blocking",
            ambiguity_codes=("ambiguity.multiple_subjects",),
        ),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "clarify"


@pytest.mark.parametrize(
    ("intent", "evidence_needs"),
    [
        ("greeting", ("none",)),
        ("capability_help", ("none",)),
        ("analytics", ("analytics",)),
        ("procedural", ("document", "official_source")),
        ("unknown", ("document",)),
        ("eligibility", ("rule",)),
    ],
)
def test_unsupported_query_shapes_abstain(
    intent: QueryIntent,
    evidence_needs: tuple[EvidenceNeed, ...],
) -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(intent=intent, evidence_needs=evidence_needs),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "abstain"
    assert decision.route == "abstain.unsupported_flow"
    assert decision.rationale_code == "query.unsupported_flow"
    assert decision.effective_risk_level == "normal"
    assert decision.budget.is_all_zero()


def test_personal_query_abstains() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(is_personal=True),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "abstain"
    assert decision.rationale_code == "query.unsupported_flow"


def test_multi_part_query_abstains() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(is_multi_part=True),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "abstain"
    assert decision.rationale_code == "query.unsupported_flow"


@pytest.mark.parametrize(
    ("risk_level", "risk_signals", "expected_risk"),
    [
        ("elevated", (), "unknown"),
        ("high", (), "high"),
        ("unknown", (), "unknown"),
        ("normal", ("risk.prompt_injection",), "unknown"),
        ("high", ("risk.prompt_injection",), "high"),
    ],
)
def test_unresolved_risk_abstains_with_the_derived_risk_level(
    risk_level: RiskLevel,
    risk_signals: tuple[str, ...],
    expected_risk: RiskLevel,
) -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(risk_level=risk_level, risk_signals=risk_signals),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.lane == "abstain"
    assert decision.route == "abstain.unsupported_flow"
    assert decision.rationale_code == "risk.not_eligible_for_fast"
    assert decision.effective_risk_level == expected_risk
    assert decision.allowed_capabilities == ()
    assert decision.budget.is_all_zero()


def test_terminal_decisions_never_carry_an_approved_flow_reference() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(risk_level="high"),
        decision_id=ROUTE_DECISION_ID,
        decided_at=NOW,
    )
    assert decision.approved_flow_ref is None
    assert decision.planner_required is False
    assert decision.filters == ()


def test_injected_identifiers_and_timestamps_are_used_verbatim() -> None:
    decision = route_query(
        authorized_context(),
        query_analysis(),
        decision_id=FOREIGN_ID,
        decided_at=NOW,
    )
    assert decision.decision_id == FOREIGN_ID
    assert decision.decided_at == NOW


@pytest.mark.parametrize("module_file", NEW_CORE_MODULES)
def test_new_core_modules_import_only_allowed_packages(module_file: str) -> None:
    for module_name in _imported_modules(_source(module_file)):
        assert _is_allowed_import(module_name), module_name


@pytest.mark.parametrize("module_file", NEW_CORE_MODULES)
def test_new_core_modules_import_no_vendor_packages(module_file: str) -> None:
    for module_name in _imported_modules(_source(module_file)):
        assert module_name.split(".")[0] not in FORBIDDEN_VENDOR_ROOTS, module_name


@pytest.mark.parametrize("module_file", NEW_CORE_MODULES)
@pytest.mark.parametrize("fragment", FORBIDDEN_SOURCE_FRAGMENTS)
def test_new_core_modules_avoid_forbidden_constructs(module_file: str, fragment: str) -> None:
    assert fragment not in _source(module_file)


def test_core_package_exposes_no_public_symbols() -> None:
    init_source = _source("__init__.py")
    tree = ast.parse(init_source)
    imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
    assert imports == []
