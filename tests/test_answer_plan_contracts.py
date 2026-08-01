"""Tests for the AnswerPlan contract."""

import copy
import importlib.util
import json
import unittest
import warnings
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant import contracts
from ai_assistant.contracts.answer_plan import (
    ANSWER_PLAN_SCHEMA_ID,
    ANSWER_PLAN_SCHEMA_VERSION,
    AnswerCaveat,
    AnswerClaimPlan,
    AnswerLengthBudget,
    AnswerPlan,
    AnswerSection,
    AnswerSectionItemRef,
    AnswerToneConstraints,
    CitationSlot,
)

ANSWER_PLAN_ID = "11111111-1111-4111-8111-111111111111"
REQUEST_ID = "22222222-2222-4222-8222-222222222222"
EVIDENCE_BUNDLE_ID = "33333333-3333-4333-8333-333333333333"
ROUTE_DECISION_ID = "44444444-4444-4444-8444-444444444444"
PLAN_ID = "55555555-5555-4555-8555-555555555555"
AUTHORIZATION_DECISION_ID = "66666666-6666-4666-8666-666666666666"
RUNTIME_SNAPSHOT_ID = "77777777-7777-4777-8777-777777777777"
CORRELATION_ID = "88888888-8888-4888-8888-888888888888"

CLAIM_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000001"
SECOND_CLAIM_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000002"
CAVEAT_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000003"
UNKNOWN_EVIDENCE_ID = "a0000000-0000-4000-8000-000000000099"
NOT_UUID4 = "a0000000-0000-1000-8000-000000000001"

BUILT_AT = "2026-01-01T12:00:00+00:00"
OFFSET_BUILT_AT = "2026-01-01T15:30:00+03:30"
EXPECTED_UTC_HOUR = 12
NAIVE_BUILT_AT = "2026-01-01T12:00:00"

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "ai_assistant" / "contracts" / "answer_plan.py"
)
SCHEMA_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "schemas" / "answer-plan" / "1.0.0.schema.json"
)

ANSWER_TEXT_FORBIDDEN_FIELDS = (
    "answer",
    "answer_text",
    "final_answer",
    "clarification",
    "clarification_text",
    "clarification_message",
    "abstention_text",
    "denial_message",
    "claim_text",
    "statement",
    "sentence",
    "explanation",
    "caveat_text",
    "title",
    "heading",
    "heading_text",
    "content",
    "text",
    "body",
    "data",
    "payload",
    "value",
)
PROMPT_AND_MODEL_FORBIDDEN_FIELDS = (
    "raw_message",
    "raw_query",
    "normalized_query",
    "standalone_query",
    "query_text",
    "prompt",
    "system_prompt",
    "developer_prompt",
    "model",
    "model_name",
    "model_output",
    "provider",
    "provider_response",
    "raw_response",
    "raw_output",
    "typed_output",
    "output_value",
)
SOURCE_LOCATOR_FORBIDDEN_FIELDS = (
    "citation_text",
    "citation_label",
    "source_name",
    "source_label",
    "url",
    "uri",
    "page",
    "page_number",
    "section_number",
    "quote",
    "excerpt",
    "snippet",
    "locator",
    "document_text",
    "html",
)
SQL_AND_TOOL_FORBIDDEN_FIELDS = (
    "rows",
    "documents",
    "chunks",
    "sql",
    "query",
    "where",
    "predicate",
    "table",
    "column",
    "join",
    "tool",
    "tool_name",
    "tool_arguments",
    "function_call",
    "endpoint",
    "path",
    "bucket",
)
CREDENTIAL_FORBIDDEN_FIELDS = (
    "api_key",
    "token",
    "access_token",
    "secret",
    "password",
    "credentials",
)
REASONING_FORBIDDEN_FIELDS = (
    "exception",
    "exception_type",
    "exception_message",
    "stack_trace",
    "traceback",
    "safe_error",
    "error_message",
    "rationale",
    "rationale_text",
    "reasoning",
    "chain_of_thought",
    "confidence",
    "self_confidence",
    "sufficient",
)
IDENTITY_FORBIDDEN_FIELDS = (
    "roles",
    "groups",
    "principal_id",
    "security_context_id",
    "email",
    "display_name",
    "session_id",
    "headers",
    "http_status",
    "metadata",
    "attributes",
    "deadline_ms",
    "timeout_ms",
    "token_budget",
    "cost_budget",
    "traceparent",
    "span_id",
    "vendor_trace_id",
)
ALL_FORBIDDEN_FIELDS = (
    ANSWER_TEXT_FORBIDDEN_FIELDS
    + PROMPT_AND_MODEL_FORBIDDEN_FIELDS
    + SOURCE_LOCATOR_FORBIDDEN_FIELDS
    + SQL_AND_TOOL_FORBIDDEN_FIELDS
    + CREDENTIAL_FORBIDDEN_FIELDS
    + REASONING_FORBIDDEN_FIELDS
    + IDENTITY_FORBIDDEN_FIELDS
)


def tone_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {"response_locale": "en", "tone_codes": ["neutral"]}
    payload.update(overrides)
    return payload


def budget_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "max_characters": 4000,
        "max_sections": 8,
        "max_claims": 32,
        "max_caveats": 32,
        "max_citations": 64,
    }
    payload.update(overrides)
    return payload


def subject_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "subject_type": "subject.policy",
        "subject_ref": "subject:alpha",
    }
    payload.update(overrides)
    return payload


def item_payload(item_kind: str, item_id: str) -> dict[str, object]:
    return {"item_kind": item_kind, "item_id": item_id}


def section_payload(
    section_id: str = "section.one",
    section_type: str = "section.summary",
    items: list[dict[str, object]] | None = None,
    **overrides: object,
) -> dict[str, object]:
    if items is None:
        items = [item_payload("claim", "claim.one")]
    payload: dict[str, object] = {
        "section_id": section_id,
        "section_type": section_type,
        "items": items,
    }
    payload.update(overrides)
    return payload


def claim_payload(
    claim_id: str = "claim.one",
    claim_code: str = "claim.code.one",
    evidence_ids: tuple[str, ...] = (CLAIM_EVIDENCE_ID,),
    fact_ids: tuple[str, ...] = ("fact.alpha",),
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "claim_id": claim_id,
        "claim_code": claim_code,
        "claim_type": "claim.type.direct",
        "subject": subject_payload(),
        "supporting_fact_ids": list(fact_ids),
        "evidence_ids": list(evidence_ids),
    }
    payload.update(overrides)
    return payload


def caveat_payload(
    caveat_id: str = "caveat.one",
    caveat_code: str = "caveat.code.missing_fact",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "caveat_id": caveat_id,
        "caveat_code": caveat_code,
        "reason_codes": ["reason.missing_fact"],
    }
    payload.update(overrides)
    return payload


def citation_payload(
    slot_id: str = "citation.one",
    target_kind: str = "claim",
    target_id: str = "claim.one",
    evidence_ids: tuple[str, ...] = (CLAIM_EVIDENCE_ID,),
    placement: str = "inline",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "slot_id": slot_id,
        "target_kind": target_kind,
        "target_id": target_id,
        "evidence_ids": list(evidence_ids),
        "placement": placement,
    }
    payload.update(overrides)
    return payload


def answer_plan_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "answer_plan_id": ANSWER_PLAN_ID,
        "request_id": REQUEST_ID,
        "evidence_bundle_id": EVIDENCE_BUNDLE_ID,
        "route_decision_id": ROUTE_DECISION_ID,
        "plan_id": PLAN_ID,
        "authorization_decision_id": AUTHORIZATION_DECISION_ID,
        "runtime_snapshot_id": RUNTIME_SNAPSHOT_ID,
        "correlation_id": CORRELATION_ID,
        "built_at": BUILT_AT,
        "decision": "answer",
        "answer_type": "direct",
        "sections": [section_payload()],
        "claims": [claim_payload()],
        "caveats": [],
        "citation_slots": [citation_payload()],
        "tone_constraints": tone_payload(),
        "prohibited_claim_codes": [],
        "prohibited_content_codes": ["content.prohibited.one"],
        "decision_reason_codes": ["reason.answer_ready"],
        "length_budget": budget_payload(),
        "answer_plan_builder_version": "1.0.0",
    }
    payload.update(overrides)
    return payload


def partial_plan_payload(**overrides: object) -> dict[str, object]:
    payload = answer_plan_payload(
        decision="partial_answer",
        answer_type="summary",
        sections=[
            section_payload(items=[item_payload("claim", "claim.one")]),
            section_payload(
                section_id="section.two",
                items=[item_payload("caveat", "caveat.one")],
            ),
        ],
        caveats=[caveat_payload()],
    )
    payload.update(overrides)
    return payload


def clarify_plan_payload(**overrides: object) -> dict[str, object]:
    payload = answer_plan_payload(
        decision="clarify",
        answer_type="clarification",
        claims=[],
        sections=[section_payload(items=[item_payload("caveat", "caveat.one")])],
        caveats=[caveat_payload(evidence_ids=[CAVEAT_EVIDENCE_ID])],
        citation_slots=[
            citation_payload(
                slot_id="citation.caveat",
                target_kind="caveat",
                target_id="caveat.one",
                evidence_ids=[CAVEAT_EVIDENCE_ID],
                placement="section_end",
            )
        ],
    )
    payload.update(overrides)
    return payload


def abstain_plan_payload(**overrides: object) -> dict[str, object]:
    payload = clarify_plan_payload(decision="abstain", answer_type="abstention")
    payload.update(overrides)
    return payload


ANSWER_TYPES = (
    "direct",
    "summary",
    "explanation",
    "comparison",
    "procedure",
    "status",
    "eligibility",
    "analytics",
    "composite",
)


class SchemaVersionTests(unittest.TestCase):
    def test_default_schema_version(self) -> None:
        plan = AnswerPlan(**answer_plan_payload())
        self.assertEqual(plan.schema_version, "1.0.0")
        self.assertEqual(ANSWER_PLAN_SCHEMA_VERSION, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(schema_version="2.0.0"))

    def test_schema_version_is_real_field(self) -> None:
        self.assertIn("schema_version", AnswerPlan.model_fields)

    def test_no_schema_version_warning(self) -> None:
        import ai_assistant.contracts  # noqa: F401
        from ai_assistant.contracts import answer_plan as warm_module  # noqa: F401

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            spec = importlib.util.spec_from_file_location("answer_plan_fresh_reload", MODULE_PATH)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        schema_version_warnings = [item for item in caught if "schema_version" in str(item.message)]
        self.assertEqual(schema_version_warnings, [])


class ToneConstraintTests(unittest.TestCase):
    def test_valid_locale_tags(self) -> None:
        for locale in ("en", "fa", "fa-IR", "en-US"):
            tone = AnswerToneConstraints(**tone_payload(response_locale=locale))
            self.assertEqual(tone.response_locale, locale)

    def test_invalid_locale_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerToneConstraints(**tone_payload(response_locale="e"))

    def test_padded_locale_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerToneConstraints(**tone_payload(response_locale=" en"))

    def test_response_locale_preserved(self) -> None:
        tone = AnswerToneConstraints(**tone_payload(response_locale="fa-IR"))
        self.assertEqual(tone.response_locale, "fa-IR")

    def test_tone_codes_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerToneConstraints(**tone_payload(tone_codes=[]))

    def test_duplicate_tone_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerToneConstraints(**tone_payload(tone_codes=["neutral", "neutral"]))

    def test_tone_code_order_preserved(self) -> None:
        tone = AnswerToneConstraints(**tone_payload(tone_codes=["formal", "concise", "direct"]))
        self.assertEqual(tone.tone_codes, ("formal", "concise", "direct"))

    def test_tone_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerToneConstraints(**tone_payload(persona="friendly"))


class LengthBudgetTests(unittest.TestCase):
    def test_valid_minimum_length_budget(self) -> None:
        budget = AnswerLengthBudget(
            max_characters=1, max_sections=1, max_claims=0, max_caveats=0, max_citations=0
        )
        self.assertEqual(budget.max_characters, 1)

    def test_valid_maximum_length_budget(self) -> None:
        budget = AnswerLengthBudget(**budget_payload())
        self.assertEqual(budget.max_citations, 64)

    def test_negative_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerLengthBudget(**budget_payload(max_claims=-1))

    def test_oversized_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerLengthBudget(**budget_payload(max_citations=65))

    def test_budget_floats_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerLengthBudget(**budget_payload(max_sections=1.5))

    def test_budget_booleans_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerLengthBudget(**budget_payload(max_sections=True))

    def test_budget_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerLengthBudget(**budget_payload(latency_budget_ms=100))


class LiteralCatalogTests(unittest.TestCase):
    def test_every_answer_type_accepted_with_matching_decision(self) -> None:
        for answer_type in ANSWER_TYPES:
            plan = AnswerPlan(**answer_plan_payload(answer_type=answer_type))
            self.assertEqual(plan.answer_type, answer_type)
        clarify = AnswerPlan(**clarify_plan_payload())
        self.assertEqual(clarify.answer_type, "clarification")
        abstain = AnswerPlan(**abstain_plan_payload())
        self.assertEqual(abstain.answer_type, "abstention")

    def test_unsupported_answer_type_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(answer_type="speculative"))

    def test_every_section_item_kind_accepted(self) -> None:
        for kind in ("claim", "caveat"):
            item = AnswerSectionItemRef(**item_payload(kind, "item.one"))
            self.assertEqual(item.item_kind, kind)

    def test_unsupported_item_kind_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSectionItemRef(**item_payload("fact", "item.one"))

    def test_every_citation_target_kind_accepted(self) -> None:
        for kind in ("claim", "caveat"):
            slot = CitationSlot(**citation_payload(target_kind=kind, target_id="item.one"))
            self.assertEqual(slot.target_kind, kind)

    def test_unsupported_citation_target_kind_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(target_kind="fact"))

    def test_every_citation_placement_accepted(self) -> None:
        for placement in ("inline", "section_end", "answer_end"):
            slot = CitationSlot(**citation_payload(placement=placement))
            self.assertEqual(slot.placement, placement)

    def test_unsupported_placement_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(placement="footnote"))


class SectionItemTests(unittest.TestCase):
    def test_valid_section_item(self) -> None:
        item = AnswerSectionItemRef(**item_payload("claim", "claim.one"))
        self.assertEqual(item.item_id, "claim.one")

    def test_invalid_item_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSectionItemRef(**item_payload("claim", "Claim-One"))

    def test_valid_section(self) -> None:
        section = AnswerSection(**section_payload())
        self.assertEqual(section.section_id, "section.one")

    def test_section_requires_at_least_one_item(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSection(**section_payload(items=[]))

    def test_duplicate_section_items_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSection(
                **section_payload(
                    items=[item_payload("claim", "claim.one"), item_payload("claim", "claim.one")]
                )
            )

    def test_32_section_items_accepted(self) -> None:
        items = [item_payload("claim", f"claim.{index}") for index in range(32)]
        section = AnswerSection(**section_payload(items=items))
        self.assertEqual(len(section.items), 32)

    def test_33_section_items_rejected(self) -> None:
        items = [item_payload("claim", f"claim.{index}") for index in range(33)]
        with self.assertRaises(ValidationError):
            AnswerSection(**section_payload(items=items))

    def test_section_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSection(**section_payload(), heading="Summary")

    def test_section_item_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerSectionItemRef(**item_payload("claim", "claim.one"), extra="x")


class ClaimTests(unittest.TestCase):
    def test_valid_planned_claim(self) -> None:
        claim = AnswerClaimPlan(**claim_payload())
        self.assertEqual(claim.claim_id, "claim.one")

    def test_claim_requires_facts(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(fact_ids=()))

    def test_claim_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(evidence_ids=()))

    def test_duplicate_claim_facts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(fact_ids=("fact.alpha", "fact.alpha")))

    def test_duplicate_claim_evidence_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(evidence_ids=(CLAIM_EVIDENCE_ID, CLAIM_EVIDENCE_ID)))

    def test_fact_order_preserved(self) -> None:
        claim = AnswerClaimPlan(**claim_payload(fact_ids=("fact.beta", "fact.alpha")))
        self.assertEqual(claim.supporting_fact_ids, ("fact.beta", "fact.alpha"))

    def test_evidence_order_preserved(self) -> None:
        claim = AnswerClaimPlan(
            **claim_payload(evidence_ids=(SECOND_CLAIM_EVIDENCE_ID, CLAIM_EVIDENCE_ID))
        )
        self.assertEqual(
            claim.evidence_ids, (UUID(SECOND_CLAIM_EVIDENCE_ID), UUID(CLAIM_EVIDENCE_ID))
        )

    def test_invalid_claim_code_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(claim_code="Claim Code"))

    def test_claim_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(), confidence=0.9)

    def test_claim_uuid4_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(evidence_ids=(NOT_UUID4,)))


class CaveatTests(unittest.TestCase):
    def test_valid_caveat_without_evidence(self) -> None:
        caveat = AnswerCaveat(**caveat_payload())
        self.assertEqual(caveat.evidence_ids, ())

    def test_valid_caveat_with_evidence(self) -> None:
        caveat = AnswerCaveat(**caveat_payload(evidence_ids=[CAVEAT_EVIDENCE_ID]))
        self.assertEqual(caveat.evidence_ids, (UUID(CAVEAT_EVIDENCE_ID),))

    def test_caveat_requires_reason_code(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerCaveat(**caveat_payload(reason_codes=[]))

    def test_duplicate_caveat_reasons_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerCaveat(
                **caveat_payload(reason_codes=["reason.missing_fact", "reason.missing_fact"])
            )

    def test_duplicate_related_claims_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerCaveat(**caveat_payload(related_claim_ids=["claim.one", "claim.one"]))

    def test_caveat_collection_order_preserved(self) -> None:
        caveat = AnswerCaveat(**caveat_payload(related_claim_ids=["claim.two", "claim.one"]))
        self.assertEqual(caveat.related_claim_ids, ("claim.two", "claim.one"))

    def test_caveat_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerCaveat(**caveat_payload(), caveat_text="missing data")


class CitationSlotTests(unittest.TestCase):
    def test_valid_claim_citation_slot(self) -> None:
        slot = CitationSlot(**citation_payload())
        self.assertEqual(slot.target_kind, "claim")

    def test_valid_caveat_citation_slot(self) -> None:
        slot = CitationSlot(
            **citation_payload(
                target_kind="caveat", target_id="caveat.one", evidence_ids=[CAVEAT_EVIDENCE_ID]
            )
        )
        self.assertEqual(slot.target_kind, "caveat")

    def test_citation_slot_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(evidence_ids=[]))

    def test_duplicate_citation_evidence_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(evidence_ids=[CLAIM_EVIDENCE_ID, CLAIM_EVIDENCE_ID]))

    def test_citation_evidence_order_preserved(self) -> None:
        slot = CitationSlot(
            **citation_payload(evidence_ids=[SECOND_CLAIM_EVIDENCE_ID, CLAIM_EVIDENCE_ID])
        )
        self.assertEqual(
            slot.evidence_ids, (UUID(SECOND_CLAIM_EVIDENCE_ID), UUID(CLAIM_EVIDENCE_ID))
        )

    def test_citation_slot_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(), locator="doc#1")


class AnswerPlanCoreTests(unittest.TestCase):
    def test_valid_answer_plan(self) -> None:
        plan = AnswerPlan(**answer_plan_payload())
        self.assertEqual(plan.decision, "answer")

    def test_valid_partial_answer_plan(self) -> None:
        plan = AnswerPlan(**partial_plan_payload())
        self.assertEqual(plan.decision, "partial_answer")

    def test_valid_clarification_plan(self) -> None:
        plan = AnswerPlan(**clarify_plan_payload())
        self.assertEqual(plan.decision, "clarify")

    def test_valid_abstention_plan(self) -> None:
        plan = AnswerPlan(**abstain_plan_payload())
        self.assertEqual(plan.decision, "abstain")

    def test_uuid4_enforcement_for_every_root_identifier(self) -> None:
        for field_name in (
            "answer_plan_id",
            "request_id",
            "evidence_bundle_id",
            "route_decision_id",
            "plan_id",
            "authorization_decision_id",
            "runtime_snapshot_id",
            "correlation_id",
        ):
            with self.assertRaises(ValidationError):
                AnswerPlan(**answer_plan_payload(**{field_name: NOT_UUID4}))

    def test_naive_built_at_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(built_at=NAIVE_BUILT_AT))

    def test_non_utc_built_at_normalized(self) -> None:
        plan = AnswerPlan(**answer_plan_payload(built_at=OFFSET_BUILT_AT))
        self.assertEqual(plan.built_at.utcoffset().total_seconds(), 0)
        self.assertEqual(plan.built_at.hour, EXPECTED_UTC_HOUR)

    def test_invalid_builder_version_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(answer_plan_builder_version="v1"))

    def test_duplicate_section_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    sections=[section_payload(), section_payload(section_id="section.one")]
                )
            )

    def test_duplicate_claim_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    claims=[claim_payload(), claim_payload(claim_code="claim.code.two")]
                )
            )

    def test_duplicate_claim_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    claims=[
                        claim_payload(),
                        claim_payload(claim_id="claim.two", claim_code="claim.code.one"),
                    ],
                    sections=[
                        section_payload(
                            items=[
                                item_payload("claim", "claim.one"),
                                item_payload("claim", "claim.two"),
                            ]
                        )
                    ],
                    citation_slots=[
                        citation_payload(),
                        citation_payload(slot_id="citation.two", target_id="claim.two"),
                    ],
                )
            )

    def test_duplicate_caveat_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    caveats=[caveat_payload(), caveat_payload(caveat_code="caveat.code.two")]
                )
            )

    def test_duplicate_citation_slot_ids_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    citation_slots=[citation_payload(), citation_payload(placement="answer_end")]
                )
            )


class SectionPartitionTests(unittest.TestCase):
    def test_unknown_claim_section_item_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    sections=[section_payload(items=[item_payload("claim", "claim.unknown")])]
                )
            )

    def test_unknown_caveat_section_item_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.unknown")],
                        ),
                    ]
                )
            )

    def test_claim_item_cannot_reference_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    sections=[
                        section_payload(items=[item_payload("claim", "caveat.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ]
                )
            )

    def test_caveat_item_cannot_reference_claim(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "claim.one")],
                        ),
                    ]
                )
            )

    def test_claim_missing_from_sections_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(sections=[section_payload(items=[])]))

    def test_caveat_missing_from_sections_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    sections=[section_payload(items=[item_payload("claim", "claim.one")])]
                )
            )

    def test_claim_appearing_twice_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("claim", "claim.one")],
                        ),
                    ]
                )
            )

    def test_caveat_appearing_twice_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                        section_payload(
                            section_id="section.three",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ]
                )
            )

    def test_exact_section_partition_accepted(self) -> None:
        plan = AnswerPlan(**partial_plan_payload())
        all_items = [item for section in plan.sections for item in section.items]
        self.assertEqual(len(all_items), len(plan.claims) + len(plan.caveats))


class ClaimProhibitionTests(unittest.TestCase):
    def test_related_caveat_claim_must_exist(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    caveats=[caveat_payload(related_claim_ids=["claim.unknown"])]
                )
            )

    def test_planned_and_prohibited_claim_code_overlap_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(prohibited_claim_codes=["claim.code.one"]))

    def test_prohibited_claim_code_order_preserved(self) -> None:
        plan = AnswerPlan(
            **answer_plan_payload(prohibited_claim_codes=["claim.code.z", "claim.code.a"])
        )
        self.assertEqual(plan.prohibited_claim_codes, ("claim.code.z", "claim.code.a"))

    def test_prohibited_content_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(prohibited_content_codes=[]))

    def test_duplicate_prohibited_content_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(prohibited_content_codes=["content.one", "content.one"])
            )

    def test_decision_reasons_cannot_be_empty(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(decision_reason_codes=[]))

    def test_duplicate_decision_reasons_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    decision_reason_codes=["reason.answer_ready", "reason.answer_ready"]
                )
            )


class CitationInvariantTests(unittest.TestCase):
    def test_citation_target_must_exist(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(citation_slots=[citation_payload(target_id="claim.unknown")])
            )

    def test_claim_citation_cannot_target_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    citation_slots=[citation_payload(target_kind="claim", target_id="caveat.one")]
                )
            )

    def test_caveat_citation_cannot_target_claim(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **partial_plan_payload(
                    citation_slots=[
                        citation_payload(
                            slot_id="citation.bad",
                            target_kind="caveat",
                            target_id="claim.one",
                            evidence_ids=[CLAIM_EVIDENCE_ID],
                        )
                    ]
                )
            )

    def test_claim_citation_evidence_must_belong_to_claim(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    citation_slots=[citation_payload(evidence_ids=[UNKNOWN_EVIDENCE_ID])]
                )
            )

    def test_caveat_citation_evidence_must_belong_to_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **clarify_plan_payload(
                    citation_slots=[
                        citation_payload(
                            slot_id="citation.caveat",
                            target_kind="caveat",
                            target_id="caveat.one",
                            evidence_ids=[UNKNOWN_EVIDENCE_ID],
                            placement="section_end",
                        )
                    ]
                )
            )

    def test_caveat_without_evidence_rejects_citation_slot(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **clarify_plan_payload(
                    caveats=[caveat_payload()],
                    citation_slots=[
                        citation_payload(
                            slot_id="citation.caveat",
                            target_kind="caveat",
                            target_id="caveat.one",
                            evidence_ids=[CAVEAT_EVIDENCE_ID],
                            placement="section_end",
                        )
                    ],
                )
            )

    def test_duplicate_semantic_citation_slot_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **answer_plan_payload(
                    citation_slots=[
                        citation_payload(),
                        citation_payload(slot_id="citation.two"),
                    ]
                )
            )

    def test_every_claim_requires_citation(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(citation_slots=[]))

    def test_multiple_citation_slots_for_one_claim_accepted(self) -> None:
        plan = AnswerPlan(
            **answer_plan_payload(
                claims=[claim_payload(evidence_ids=[CLAIM_EVIDENCE_ID, SECOND_CLAIM_EVIDENCE_ID])],
                citation_slots=[
                    citation_payload(),
                    citation_payload(
                        slot_id="citation.two",
                        evidence_ids=[SECOND_CLAIM_EVIDENCE_ID],
                        placement="section_end",
                    ),
                ],
            )
        )
        self.assertEqual(len(plan.citation_slots), 2)

    def test_claim_evidence_need_not_all_be_cited(self) -> None:
        plan = AnswerPlan(
            **answer_plan_payload(
                claims=[claim_payload(evidence_ids=[CLAIM_EVIDENCE_ID, SECOND_CLAIM_EVIDENCE_ID])],
                citation_slots=[citation_payload(evidence_ids=[CLAIM_EVIDENCE_ID])],
            )
        )
        self.assertEqual(len(plan.claims[0].evidence_ids), 2)
        self.assertEqual(len(plan.citation_slots[0].evidence_ids), 1)


class BudgetInvariantTests(unittest.TestCase):
    def test_section_count_within_budget_accepted(self) -> None:
        plan = AnswerPlan(**answer_plan_payload(length_budget=budget_payload(max_sections=1)))
        self.assertEqual(len(plan.sections), 1)

    def test_section_count_beyond_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**partial_plan_payload(length_budget=budget_payload(max_sections=1)))

    def test_claim_count_beyond_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(length_budget=budget_payload(max_claims=0)))

    def test_caveat_count_beyond_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**partial_plan_payload(length_budget=budget_payload(max_caveats=0)))

    def test_citation_count_beyond_budget_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(length_budget=budget_payload(max_citations=0)))


class DecisionShapeTests(unittest.TestCase):
    def test_answer_requires_at_least_one_claim(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**clarify_plan_payload(decision="answer", answer_type="direct"))

    def test_answer_rejects_clarification_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(answer_type="clarification"))

    def test_answer_rejects_abstention_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(answer_type="abstention"))

    def test_partial_requires_at_least_one_claim(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**clarify_plan_payload(decision="partial_answer", answer_type="summary"))

    def test_partial_requires_at_least_one_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(decision="partial_answer", answer_type="summary"))

    def test_partial_rejects_clarification_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**partial_plan_payload(answer_type="clarification"))

    def test_partial_rejects_abstention_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**partial_plan_payload(answer_type="abstention"))

    def test_clarify_requires_clarification_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**clarify_plan_payload(answer_type="direct"))

    def test_clarify_rejects_claims(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **clarify_plan_payload(
                    claims=[claim_payload()],
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ],
                    citation_slots=[
                        citation_payload(),
                        citation_payload(
                            slot_id="citation.caveat",
                            target_kind="caveat",
                            target_id="caveat.one",
                            evidence_ids=[CAVEAT_EVIDENCE_ID],
                            placement="section_end",
                        ),
                    ],
                )
            )

    def test_clarify_requires_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **clarify_plan_payload(
                    caveats=[],
                    sections=[section_payload(items=[item_payload("claim", "claim.one")])],
                    claims=[claim_payload()],
                    citation_slots=[citation_payload()],
                    decision="clarify",
                    answer_type="clarification",
                )
            )

    def test_clarify_citation_slots_may_target_caveats(self) -> None:
        plan = AnswerPlan(**clarify_plan_payload())
        self.assertEqual(plan.citation_slots[0].target_kind, "caveat")

    def test_clarify_rejects_claim_target_citation(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **clarify_plan_payload(
                    claims=[claim_payload()],
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ],
                    citation_slots=[
                        citation_payload(),
                    ],
                    decision="abstain",
                    answer_type="abstention",
                )
            )

    def test_abstain_requires_abstention_type(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**abstain_plan_payload(answer_type="clarification"))

    def test_abstain_rejects_claims(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **abstain_plan_payload(
                    claims=[claim_payload()],
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ],
                    citation_slots=[
                        citation_payload(),
                        citation_payload(
                            slot_id="citation.caveat",
                            target_kind="caveat",
                            target_id="caveat.one",
                            evidence_ids=[CAVEAT_EVIDENCE_ID],
                            placement="section_end",
                        ),
                    ],
                )
            )

    def test_abstain_requires_caveat(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **abstain_plan_payload(
                    caveats=[],
                    sections=[section_payload(items=[item_payload("claim", "claim.one")])],
                    claims=[claim_payload()],
                    citation_slots=[citation_payload()],
                )
            )

    def test_abstain_citation_slots_may_target_caveats(self) -> None:
        plan = AnswerPlan(**abstain_plan_payload())
        self.assertEqual(plan.citation_slots[0].target_kind, "caveat")

    def test_abstain_rejects_claim_target_citation(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(
                **abstain_plan_payload(
                    claims=[claim_payload()],
                    sections=[
                        section_payload(items=[item_payload("claim", "claim.one")]),
                        section_payload(
                            section_id="section.two",
                            items=[item_payload("caveat", "caveat.one")],
                        ),
                    ],
                    citation_slots=[citation_payload()],
                )
            )


class CollectionDefaultsAndOrderingTests(unittest.TestCase):
    def test_missing_collections_become_empty_tuples(self) -> None:
        payload = answer_plan_payload()
        del payload["caveats"]
        del payload["prohibited_claim_codes"]
        plan = AnswerPlan(**payload)
        self.assertEqual(plan.caveats, ())
        self.assertEqual(plan.prohibited_claim_codes, ())

    def test_explicit_null_collections_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(caveats=None))

    def test_section_order_preserved(self) -> None:
        plan = AnswerPlan(**partial_plan_payload())
        self.assertEqual(plan.sections[0].section_id, "section.one")
        self.assertEqual(plan.sections[1].section_id, "section.two")

    def test_claim_order_preserved(self) -> None:
        plan = AnswerPlan(
            **answer_plan_payload(
                claims=[
                    claim_payload(claim_id="claim.b", claim_code="claim.code.b"),
                    claim_payload(claim_id="claim.a", claim_code="claim.code.a"),
                ],
                sections=[
                    section_payload(
                        items=[
                            item_payload("claim", "claim.b"),
                            item_payload("claim", "claim.a"),
                        ]
                    )
                ],
                citation_slots=[
                    citation_payload(target_id="claim.b"),
                    citation_payload(slot_id="citation.two", target_id="claim.a"),
                ],
            )
        )
        self.assertEqual([claim.claim_id for claim in plan.claims], ["claim.b", "claim.a"])

    def test_caveat_order_preserved(self) -> None:
        plan = AnswerPlan(
            **partial_plan_payload(
                caveats=[
                    caveat_payload(caveat_id="caveat.b", caveat_code="caveat.code.b"),
                    caveat_payload(caveat_id="caveat.a", caveat_code="caveat.code.a"),
                ],
                sections=[
                    section_payload(items=[item_payload("claim", "claim.one")]),
                    section_payload(
                        section_id="section.two",
                        items=[
                            item_payload("caveat", "caveat.b"),
                            item_payload("caveat", "caveat.a"),
                        ],
                    ),
                ],
            )
        )
        self.assertEqual([caveat.caveat_id for caveat in plan.caveats], ["caveat.b", "caveat.a"])

    def test_citation_order_preserved(self) -> None:
        plan = AnswerPlan(
            **answer_plan_payload(
                claims=[claim_payload(evidence_ids=[CLAIM_EVIDENCE_ID, SECOND_CLAIM_EVIDENCE_ID])],
                citation_slots=[
                    citation_payload(slot_id="citation.b", evidence_ids=[SECOND_CLAIM_EVIDENCE_ID]),
                    citation_payload(slot_id="citation.a", evidence_ids=[CLAIM_EVIDENCE_ID]),
                ],
            )
        )
        self.assertEqual(
            [slot.slot_id for slot in plan.citation_slots], ["citation.b", "citation.a"]
        )


class RootUnknownFieldTests(unittest.TestCase):
    def test_root_unknown_field_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(), extra_field="unexpected")


class ForbiddenFieldTests(unittest.TestCase):
    def _assert_root_field_rejected(self, field_name: str) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(**{field_name: "unexpected"}))

    def _assert_claim_field_rejected(self, field_name: str) -> None:
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(**{field_name: "unexpected"}))

    def _assert_caveat_field_rejected(self, field_name: str) -> None:
        with self.assertRaises(ValidationError):
            AnswerCaveat(**caveat_payload(**{field_name: "unexpected"}))

    def _assert_section_field_rejected(self, field_name: str) -> None:
        with self.assertRaises(ValidationError):
            AnswerSection(**section_payload(**{field_name: "unexpected"}))

    def _assert_citation_field_rejected(self, field_name: str) -> None:
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(**{field_name: "unexpected"}))

    def test_forbidden_answer_text_fields_rejected(self) -> None:
        for field_name in ANSWER_TEXT_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)
            self._assert_claim_field_rejected(field_name)
            self._assert_caveat_field_rejected(field_name)
            self._assert_section_field_rejected(field_name)

    def test_forbidden_prompt_and_model_fields_rejected(self) -> None:
        for field_name in PROMPT_AND_MODEL_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)

    def test_forbidden_source_locator_fields_rejected(self) -> None:
        for field_name in SOURCE_LOCATOR_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)
            self._assert_citation_field_rejected(field_name)

    def test_forbidden_sql_and_tool_fields_rejected(self) -> None:
        for field_name in SQL_AND_TOOL_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)

    def test_forbidden_credential_fields_rejected(self) -> None:
        for field_name in CREDENTIAL_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)

    def test_forbidden_reasoning_fields_rejected(self) -> None:
        for field_name in REASONING_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)
            self._assert_claim_field_rejected(field_name)

    def test_forbidden_identity_fields_rejected(self) -> None:
        for field_name in IDENTITY_FORBIDDEN_FIELDS:
            self._assert_root_field_rejected(field_name)


class ImmutabilityTests(unittest.TestCase):
    def test_root_model_immutable(self) -> None:
        plan = AnswerPlan(**answer_plan_payload())
        with self.assertRaises(ValidationError):
            plan.answer_type = "summary"

    def test_nested_models_immutable(self) -> None:
        plan = AnswerPlan(**answer_plan_payload())
        with self.assertRaises(ValidationError):
            plan.claims[0].claim_code = "claim.code.other"
        with self.assertRaises(ValidationError):
            plan.tone_constraints.response_locale = "fa"


class SerializationRoundTripTests(unittest.TestCase):
    def test_json_serialization_round_trip(self) -> None:
        plan = AnswerPlan(**answer_plan_payload())
        restored = AnswerPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(plan, restored)


class SchemaArtifactTests(unittest.TestCase):
    def test_root_schema_identity(self) -> None:
        schema = AnswerPlan.model_json_schema()
        self.assertEqual(schema.get("$id"), ANSWER_PLAN_SCHEMA_ID)
        self.assertEqual(ANSWER_PLAN_SCHEMA_ID, "urn:ai-assistant:contracts:answer-plan:1.0.0")

    def test_root_schema_closed(self) -> None:
        schema = AnswerPlan.model_json_schema()
        self.assertFalse(schema.get("additionalProperties", True))

    def test_all_nested_schemas_closed(self) -> None:
        schema = AnswerPlan.model_json_schema()
        for definition in schema.get("$defs", {}).values():
            if definition.get("type") == "object":
                self.assertFalse(definition.get("additionalProperties", True))

    def test_exact_literal_catalogs_represented(self) -> None:
        schema = AnswerPlan.model_json_schema()
        answer_type_enum = schema["properties"]["answer_type"]["enum"]
        self.assertEqual(
            set(answer_type_enum),
            {
                "direct",
                "summary",
                "explanation",
                "comparison",
                "procedure",
                "status",
                "eligibility",
                "analytics",
                "composite",
                "clarification",
                "abstention",
            },
        )

    def test_committed_schema_matches_generated_schema(self) -> None:
        generated = (
            json.dumps(AnswerPlan.model_json_schema(), indent=2, sort_keys=True, ensure_ascii=False)
            + "\n"
        )
        committed = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.assertEqual(committed, generated)

    def test_schema_artifact_has_trailing_newline(self) -> None:
        committed = SCHEMA_ARTIFACT.read_text(encoding="utf-8")
        self.assertTrue(committed.endswith("\n"))
        self.assertFalse(committed.endswith("\n\n"))

    def test_forbidden_property_names_absent_from_schema(self) -> None:
        schema = AnswerPlan.model_json_schema()
        properties = set(schema.get("properties", {}).keys())
        for definition in schema.get("$defs", {}).values():
            properties.update(definition.get("properties", {}).keys())
        for field_name in ALL_FORBIDDEN_FIELDS:
            self.assertNotIn(field_name, properties)

    def test_nested_models_contain_no_schema_version(self) -> None:
        schema = AnswerPlan.model_json_schema()
        for name, definition in schema.get("$defs", {}).items():
            if name == "AnswerPlan":
                continue
            self.assertNotIn("schema_version", definition.get("properties", {}))


class PublicExportTests(unittest.TestCase):
    def test_public_exports_available_through_subset_assertion(self) -> None:
        expected = {
            "AnswerCaveat",
            "AnswerClaimPlan",
            "AnswerLengthBudget",
            "AnswerPlan",
            "AnswerSection",
            "AnswerSectionItemKind",
            "AnswerSectionItemRef",
            "AnswerToneConstraints",
            "AnswerType",
            "CitationPlacement",
            "CitationSlot",
            "CitationTargetKind",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            self.assertTrue(hasattr(contracts, name))

    def test_private_validation_aliases_are_not_exported(self) -> None:
        private_names = {
            "_CanonicalCode",
            "_LocaleTag",
            "_Uuid4",
            "_require_unique_values",
            "_ToneCodes",
            "_RequiredCodes16",
            "_OptionalCodes16",
            "_RequiredCodes32",
            "_OptionalCodes64",
            "_UuidTuple1To32",
            "_OptionalUuidTuple32",
            "_MaxCharactersBudget",
            "_MaxSectionsBudget",
            "_MaxClaimsBudget",
            "_MaxCaveatsBudget",
            "_MaxCitationsBudget",
        }
        for name in private_names:
            self.assertNotIn(name, contracts.__all__)
            self.assertFalse(hasattr(contracts, name))


def _synthetic_claim_id(index: int) -> str:
    return f"claim.p.{index}"


def _synthetic_claim_code(index: int) -> str:
    return f"claim.code.p.{index}"


def _synthetic_caveat_id(index: int) -> str:
    return f"caveat.p.{index}"


def _synthetic_caveat_code(index: int) -> str:
    return f"caveat.code.p.{index}"


def _synthetic_evidence_id(index: int) -> str:
    return f"c0000000-0000-4000-9000-{index:012d}"


def _distribute_round_robin(total: int, buckets: int) -> list[int]:
    sizes = [1] * buckets
    remaining = total - buckets
    cursor = 0
    while remaining > 0:
        target = cursor % buckets
        if sizes[target] < 8:
            sizes[target] += 1
            remaining -= 1
        cursor += 1
    return sizes


def _permutation(draw, count: int) -> list[int]:
    if count <= 1:
        return list(range(count))
    return draw(
        st.lists(
            st.integers(min_value=0, max_value=count - 1),
            min_size=count,
            max_size=count,
            unique=True,
        )
    )


@st.composite
def plan_component_counts(draw):
    section_count = draw(st.integers(min_value=1, max_value=4))
    claim_count = draw(st.integers(min_value=0, max_value=8))
    caveat_count = draw(st.integers(min_value=0, max_value=8))
    total_items = claim_count + caveat_count
    capacity = section_count * 8
    if total_items == 0:
        claim_count = 1
        total_items = 1
    if total_items > capacity:
        overflow = total_items - capacity
        caveat_reduction = min(overflow, caveat_count)
        caveat_count -= caveat_reduction
        overflow -= caveat_reduction
        if overflow > 0:
            claim_count = max(0, claim_count - overflow)
        total_items = claim_count + caveat_count
        if total_items == 0:
            claim_count = 1
            total_items = 1
    if section_count > total_items:
        section_count = total_items
    claim_order = _permutation(draw, claim_count)
    caveat_order = _permutation(draw, caveat_count)
    return claim_count, caveat_count, section_count, claim_order, caveat_order


def build_ordered_plan_payload(
    claim_count: int,
    caveat_count: int,
    section_count: int,
    claim_order: list[int],
    caveat_order: list[int],
) -> dict[str, object]:
    sizes = _distribute_round_robin(claim_count + caveat_count, section_count)
    all_refs = [item_payload("claim", _synthetic_claim_id(index)) for index in range(claim_count)]
    all_refs += [
        item_payload("caveat", _synthetic_caveat_id(index)) for index in range(caveat_count)
    ]
    sections: list[dict[str, object]] = []
    cursor = 0
    for section_index, size in enumerate(sizes):
        sections.append(
            section_payload(
                section_id=f"section.p.{section_index}",
                section_type="section.generated",
                items=all_refs[cursor : cursor + size],
            )
        )
        cursor += size
    claims = [
        claim_payload(
            claim_id=_synthetic_claim_id(index),
            claim_code=_synthetic_claim_code(index),
            evidence_ids=(_synthetic_evidence_id(index),),
        )
        for index in claim_order
    ]
    caveats = [
        caveat_payload(
            caveat_id=_synthetic_caveat_id(index),
            caveat_code=_synthetic_caveat_code(index),
            reason_codes=["reason.generated"],
        )
        for index in caveat_order
    ]
    citation_slots = [
        citation_payload(
            slot_id=f"citation.p.{index}",
            target_kind="claim",
            target_id=_synthetic_claim_id(index),
            evidence_ids=[_synthetic_evidence_id(index)],
            placement="inline",
        )
        for index in claim_order
    ]
    if claim_count >= 1 and caveat_count == 0:
        decision = "answer"
        answer_type = "direct"
    elif claim_count >= 1:
        decision = "partial_answer"
        answer_type = "summary"
    else:
        decision = "clarify"
        answer_type = "clarification"
    return answer_plan_payload(
        decision=decision,
        answer_type=answer_type,
        sections=sections,
        claims=claims,
        caveats=caveats,
        citation_slots=citation_slots,
        decision_reason_codes=["reason.generated"],
    )


@st.composite
def citation_subset_case(draw):
    evidence_total = draw(st.integers(min_value=1, max_value=8))
    slot_count = draw(st.integers(min_value=1, max_value=min(4, evidence_total)))
    return evidence_total, slot_count


class AnswerPlanPropertyTests(unittest.TestCase):
    """Bounded Hypothesis property tests for the AnswerPlan contract."""

    @given(plan_component_counts())
    def test_unique_collections_preserve_generated_order(self, components) -> None:
        claim_count, caveat_count, section_count, claim_order, caveat_order = components
        payload = build_ordered_plan_payload(
            claim_count, caveat_count, section_count, claim_order, caveat_order
        )
        plan = AnswerPlan(**payload)
        self.assertEqual(
            [claim.claim_id for claim in plan.claims],
            [_synthetic_claim_id(index) for index in claim_order],
        )
        self.assertEqual(
            [caveat.caveat_id for caveat in plan.caveats],
            [_synthetic_caveat_id(index) for index in caveat_order],
        )
        self.assertEqual(
            [slot.slot_id for slot in plan.citation_slots],
            [f"citation.p.{index}" for index in claim_order],
        )
        self.assertEqual(
            [section.section_id for section in plan.sections],
            [f"section.p.{index}" for index in range(section_count)],
        )

    @given(plan_component_counts())
    def test_valid_exact_partitions_round_trip_through_json(self, components) -> None:
        claim_count, caveat_count, section_count, claim_order, caveat_order = components
        payload = build_ordered_plan_payload(
            claim_count, caveat_count, section_count, claim_order, caveat_order
        )
        plan = AnswerPlan(**payload)
        restored = AnswerPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(plan, restored)
        seen_claims = {
            item.item_id
            for section in restored.sections
            for item in section.items
            if item.item_kind == "claim"
        }
        seen_caveats = {
            item.item_id
            for section in restored.sections
            for item in section.items
            if item.item_kind == "caveat"
        }
        self.assertEqual(seen_claims, {claim.claim_id for claim in restored.claims})
        self.assertEqual(seen_caveats, {caveat.caveat_id for caveat in restored.caveats})
        total_items = sum(len(section.items) for section in restored.sections)
        self.assertEqual(total_items, len(restored.claims) + len(restored.caveats))

    @given(plan_component_counts())
    def test_duplicate_item_or_global_occurrence_rejected(self, components) -> None:
        claim_count, caveat_count, section_count, claim_order, caveat_order = components
        payload = build_ordered_plan_payload(
            claim_count, caveat_count, section_count, claim_order, caveat_order
        )
        duplicated_within_section = copy.deepcopy(payload)
        first_section_items = list(duplicated_within_section["sections"][0]["items"])
        first_section_items.append(dict(first_section_items[0]))
        duplicated_within_section["sections"][0]["items"] = first_section_items
        with self.assertRaises(ValidationError):
            AnswerPlan(**duplicated_within_section)

        if len(payload["sections"]) > 1:
            duplicated_across_sections = copy.deepcopy(payload)
            duplicate_item = dict(duplicated_across_sections["sections"][0]["items"][0])
            second_section_items = list(duplicated_across_sections["sections"][1]["items"])
            second_section_items.append(duplicate_item)
            duplicated_across_sections["sections"][1]["items"] = second_section_items
            with self.assertRaises(ValidationError):
                AnswerPlan(**duplicated_across_sections)

    @given(citation_subset_case())
    def test_valid_citation_targets_with_evidence_subsets_round_trip(self, case) -> None:
        evidence_total, slot_count = case
        evidence_ids = [_synthetic_evidence_id(index) for index in range(evidence_total)]
        citation_slots = [
            citation_payload(
                slot_id=f"citation.subset.{index}",
                evidence_ids=[_synthetic_evidence_id(inner) for inner in range(index + 1)],
                placement="inline" if index % 2 == 0 else "section_end",
            )
            for index in range(slot_count)
        ]
        payload = answer_plan_payload(
            claims=[claim_payload(evidence_ids=evidence_ids)],
            citation_slots=citation_slots,
        )
        plan = AnswerPlan(**payload)
        claim_evidence = set(plan.claims[0].evidence_ids)
        for slot in plan.citation_slots:
            self.assertTrue(set(slot.evidence_ids).issubset(claim_evidence))
        restored = AnswerPlan.model_validate_json(plan.model_dump_json())
        self.assertEqual(plan, restored)
        self.assertEqual(len(restored.citation_slots), slot_count)

    @given(st.sampled_from(ALL_FORBIDDEN_FIELDS))
    def test_sampled_forbidden_fields_rejected_at_root_and_nested_boundaries(
        self, field_name
    ) -> None:
        with self.assertRaises(ValidationError):
            AnswerPlan(**answer_plan_payload(**{field_name: "unexpected"}))
        with self.assertRaises(ValidationError):
            AnswerClaimPlan(**claim_payload(**{field_name: "unexpected"}))
        with self.assertRaises(ValidationError):
            AnswerCaveat(**caveat_payload(**{field_name: "unexpected"}))
        with self.assertRaises(ValidationError):
            AnswerSection(**section_payload(**{field_name: "unexpected"}))
        with self.assertRaises(ValidationError):
            CitationSlot(**citation_payload(**{field_name: "unexpected"}))
