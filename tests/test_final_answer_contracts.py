"""Contract tests for the FinalAnswer contract."""

import copy
import json
import unittest
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from ai_assistant.contracts.final_answer import (
    FINAL_ANSWER_SCHEMA_ID,
    FINAL_ANSWER_SCHEMA_VERSION,
    JSON_SCHEMA_DIALECT,
    FinalAnswer,
    FinalAnswerSection,
    FinalCaveatContent,
    FinalCitation,
    FinalCitationSource,
    FinalClaimContent,
    FinalFreshnessNote,
    FinalResponseMetadata,
    FinalValidatedContent,
)

Payload = dict[str, Any]

CLAIM_TEXT = "Your account balance is 1200."
CAVEAT_TEXT = "Data for July is unavailable."
CLARIFY_TEXT = "Which account should I check?"
ABSTAIN_TEXT = "I cannot answer this from approved sources."

PERMITTED_FAILURE_CODES = (
    "SCHEMA_INVALID",
    "DEPENDENCY_TIMEOUT",
    "TRANSIENT_DEPENDENCY",
    "BUDGET_EXCEEDED",
    "RATE_LIMITED",
    "CAPACITY_REJECTED",
    "INTERNAL_ERROR",
)

PROHIBITED_FAILURE_CODES = (
    "INVALID_INPUT",
    "UNAUTHENTICATED",
    "UNAUTHORIZED",
    "AMBIGUOUS_REQUEST",
    "POLICY_REJECTED",
    "NO_EVIDENCE",
    "CONFLICTING_EVIDENCE",
)

ROOT_IDENTIFIER_FIELDS = (
    "final_answer_id",
    "request_id",
    "answer_plan_id",
    "evidence_bundle_id",
    "route_decision_id",
    "plan_id",
    "authorization_decision_id",
    "runtime_snapshot_id",
    "correlation_id",
)

FORBIDDEN_FIELD_NAMES = (
    "answer_text",
    "raw_text",
    "prompt",
    "chain_of_thought",
    "model_name",
    "token_count",
    "cost",
    "latency_ms",
    "trace_id",
    "http_status",
    "url",
    "uri",
    "href",
    "path",
    "page_number",
    "quote",
    "excerpt",
    "snippet",
    "document_text",
    "raw_locator",
    "source_content",
    "embedding",
    "confidence",
    "user_email",
    "session_id",
    "api_key",
    "connection_string",
    "sql",
    "stack_trace",
    "metadata_extra",
)


def uuid_text(index: int) -> str:
    """Return a deterministic version 4 UUID string for the given index."""
    return f"{index:08x}-1111-4111-8111-{index:012x}"


def claim_item(item_id: str = "claim.balance", text: str = CLAIM_TEXT) -> Payload:
    return {
        "item_kind": "claim",
        "item_id": item_id,
        "rendered_text": text,
        "validation_status": "supported",
    }


def caveat_item(item_id: str = "caveat.july", text: str = CAVEAT_TEXT) -> Payload:
    return {
        "item_kind": "caveat",
        "item_id": item_id,
        "rendered_text": text,
        "validation_status": "authorized",
    }


def section_payload(
    section_id: str = "section.summary",
    section_type: str = "summary",
    items: list[Payload] | None = None,
) -> Payload:
    return {
        "section_id": section_id,
        "section_type": section_type,
        "items": [claim_item()] if items is None else items,
    }


def source_payload(index: int = 100, evidence_type: str = "sql") -> Payload:
    return {
        "evidence_id": uuid_text(index),
        "evidence_type": evidence_type,
        "display_label": "Ledger balance view",
        "source_version": "2026.08.01",
        "locator_ref": "ledger.balance.row-42",
    }


def citation_payload(
    index: int = 200,
    slot_id: str = "slot.balance",
    target_kind: str = "claim",
    target_id: str = "claim.balance",
    placement: str = "inline",
    sources: list[Payload] | None = None,
) -> Payload:
    return {
        "citation_id": uuid_text(index),
        "slot_id": slot_id,
        "target_kind": target_kind,
        "target_id": target_id,
        "placement": placement,
        "sources": [source_payload()] if sources is None else sources,
    }


def budget_payload(**overrides: int) -> Payload:
    budget: Payload = {
        "max_characters": 16000,
        "max_sections": 8,
        "max_claims": 32,
        "max_caveats": 32,
        "max_citations": 64,
    }
    budget.update(overrides)
    return budget


def metadata_payload(**overrides: Any) -> Payload:
    metadata: Payload = {
        "response_locale": "fa-IR",
        "answer_type": "direct",
        "generation_mode": "model_generated",
        "validation_status": "passed",
        "degraded": False,
        "section_count": 1,
        "claim_count": 1,
        "caveat_count": 0,
        "citation_count": 1,
        "character_count": len(CLAIM_TEXT),
    }
    metadata.update(overrides)
    return metadata


def freshness_payload(**overrides: Any) -> Payload:
    note: Payload = {
        "status": "current",
        "data_as_of": "2026-08-01T11:30:00Z",
        "reason_codes": [],
    }
    note.update(overrides)
    return note


def error_payload(code: str = "DEPENDENCY_TIMEOUT") -> Payload:
    retryable = code in {
        "DEPENDENCY_TIMEOUT",
        "TRANSIENT_DEPENDENCY",
        "RATE_LIMITED",
        "CAPACITY_REJECTED",
    }
    return {
        "code": code,
        "safe_message_key": f"error.{code.lower()}",
        "retryable": retryable,
        "internal_detail_ref": uuid_text(999),
    }


def recount(payload: Payload) -> Payload:
    """Recompute declared counts from the payload content and citations."""
    content = payload.get("validated_content")
    sections = content["sections"] if content else []
    items = [item for section in sections for item in section["items"]]
    metadata = payload["response_metadata"]
    metadata["section_count"] = len(sections)
    metadata["claim_count"] = sum(1 for item in items if item["item_kind"] == "claim")
    metadata["caveat_count"] = sum(1 for item in items if item["item_kind"] == "caveat")
    metadata["citation_count"] = len(payload["citations"])
    metadata["character_count"] = sum(len(item["rendered_text"]) for item in items)
    return payload


def answered_payload() -> Payload:
    return {
        "final_answer_id": uuid_text(1),
        "request_id": uuid_text(2),
        "answer_plan_id": uuid_text(3),
        "evidence_bundle_id": uuid_text(4),
        "route_decision_id": uuid_text(5),
        "plan_id": uuid_text(6),
        "authorization_decision_id": uuid_text(7),
        "runtime_snapshot_id": uuid_text(8),
        "correlation_id": uuid_text(9),
        "finalized_at": "2026-08-01T12:00:00Z",
        "outcome": "answered",
        "validated_content": {"sections": [section_payload()]},
        "citations": [citation_payload()],
        "outcome_reason_codes": [],
        "safe_error": None,
        "freshness_note": freshness_payload(),
        "applied_length_budget": budget_payload(),
        "response_metadata": metadata_payload(),
        "finalizer_version": "1.0.0",
    }


def partial_payload() -> Payload:
    payload = answered_payload()
    payload["outcome"] = "partially_answered"
    payload["validated_content"] = {
        "sections": [section_payload(items=[claim_item(), caveat_item()])]
    }
    payload["outcome_reason_codes"] = ["partial.missing_period"]
    payload["response_metadata"] = metadata_payload(degraded=True)
    return recount(payload)


def clarification_payload() -> Payload:
    payload = answered_payload()
    payload["outcome"] = "clarification_required"
    payload["validated_content"] = {
        "sections": [
            section_payload(
                section_id="section.clarify",
                section_type="clarification",
                items=[caveat_item("caveat.which_account", CLARIFY_TEXT)],
            )
        ]
    }
    payload["citations"] = []
    payload["outcome_reason_codes"] = ["clarify.ambiguous_account"]
    payload["freshness_note"] = freshness_payload(status="not_applicable", data_as_of=None)
    payload["response_metadata"] = metadata_payload(
        answer_type="clarification", generation_mode="deterministic_template"
    )
    return recount(payload)


def abstained_payload() -> Payload:
    payload = clarification_payload()
    payload["outcome"] = "abstained"
    payload["validated_content"] = {
        "sections": [
            section_payload(
                section_id="section.abstain",
                section_type="abstention",
                items=[caveat_item("caveat.no_authorized_source", ABSTAIN_TEXT)],
            )
        ]
    }
    payload["outcome_reason_codes"] = ["abstain.insufficient_evidence"]
    payload["response_metadata"] = metadata_payload(
        answer_type="abstention", generation_mode="safe_fallback", degraded=True
    )
    return recount(payload)


def failed_payload(code: str = "DEPENDENCY_TIMEOUT") -> Payload:
    payload = answered_payload()
    payload["outcome"] = "failed"
    payload["validated_content"] = None
    payload["citations"] = []
    payload["outcome_reason_codes"] = ["final.dependency_timeout"]
    payload["safe_error"] = error_payload(code)
    payload["freshness_note"] = freshness_payload(status="not_applicable", data_as_of=None)
    payload["response_metadata"] = metadata_payload(
        response_locale=None,
        answer_type=None,
        generation_mode="none",
        validation_status="not_applicable",
        degraded=True,
    )
    return recount(payload)


def multi_claim_payload(section_count: int, claims_per_section: int = 1) -> Payload:
    """Build an answered payload with the requested number of cited claims."""
    payload = answered_payload()
    sections: list[Payload] = []
    citations: list[Payload] = []
    index = 0
    for section_index in range(section_count):
        items: list[Payload] = []
        for _ in range(claims_per_section):
            item_id = f"claim.item-{index}"
            items.append(claim_item(item_id, f"Fact number {index}."))
            citations.append(
                citation_payload(
                    index=1000 + index,
                    slot_id=f"slot.item-{index}",
                    target_id=item_id,
                    sources=[source_payload(2000 + index)],
                )
            )
            index += 1
        sections.append(section_payload(f"section.s{section_index}", "summary", items))
    payload["validated_content"] = {"sections": sections}
    payload["citations"] = citations
    return recount(payload)


class FinalAnswerTestCase(unittest.TestCase):
    """Shared helpers for building and rejecting FinalAnswer payloads."""

    def build(self, payload: Payload) -> FinalAnswer:
        return FinalAnswer.model_validate(payload)

    def reject(self, payload: Payload) -> None:
        with self.assertRaises(ValidationError):
            FinalAnswer.model_validate(payload)


class SchemaIdentityTests(FinalAnswerTestCase):
    """Schema version, schema identity, and closed-model configuration."""

    def test_schema_version_constant_is_the_declared_version(self) -> None:
        self.assertEqual(FINAL_ANSWER_SCHEMA_VERSION, "1.0.0")

    def test_schema_id_constant_is_the_declared_urn(self) -> None:
        self.assertEqual(FINAL_ANSWER_SCHEMA_ID, "urn:ai-assistant:contracts:final-answer:1.0.0")

    def test_dialect_constant_is_draft_2020_12(self) -> None:
        self.assertEqual(JSON_SCHEMA_DIALECT, "https://json-schema.org/draft/2020-12/schema")

    def test_schema_version_defaults_when_omitted(self) -> None:
        answer = self.build(answered_payload())
        self.assertEqual(answer.schema_version, "1.0.0")

    def test_explicit_matching_schema_version_is_accepted(self) -> None:
        payload = answered_payload()
        payload["schema_version"] = "1.0.0"
        self.assertEqual(self.build(payload).schema_version, "1.0.0")

    def test_future_schema_version_is_rejected(self) -> None:
        payload = answered_payload()
        payload["schema_version"] = "1.1.0"
        self.reject(payload)

    def test_empty_schema_version_is_rejected(self) -> None:
        payload = answered_payload()
        payload["schema_version"] = ""
        self.reject(payload)

    def test_generated_schema_declares_the_contract_id(self) -> None:
        self.assertEqual(FinalAnswer.model_json_schema()["$id"], FINAL_ANSWER_SCHEMA_ID)

    def test_generated_schema_declares_the_dialect(self) -> None:
        self.assertEqual(FinalAnswer.model_json_schema()["$schema"], JSON_SCHEMA_DIALECT)

    def test_generated_schema_matches_the_stored_artifact(self) -> None:
        with open("schemas/final-answer/1.0.0.schema.json", encoding="utf-8") as handle:
            stored = json.load(handle)
        self.assertEqual(stored, FinalAnswer.model_json_schema())

    def test_stored_artifact_ends_with_a_trailing_newline(self) -> None:
        with open("schemas/final-answer/1.0.0.schema.json", encoding="utf-8") as handle:
            self.assertTrue(handle.read().endswith("}\n"))

    def test_root_schema_forbids_additional_properties(self) -> None:
        self.assertFalse(FinalAnswer.model_json_schema()["additionalProperties"])

    def test_every_nested_schema_forbids_additional_properties(self) -> None:
        definitions = FinalAnswer.model_json_schema()["$defs"]
        self.assertTrue(
            all(entry["additionalProperties"] is False for entry in definitions.values())
        )

    def test_nested_models_do_not_declare_a_schema_version(self) -> None:
        definitions = FinalAnswer.model_json_schema()["$defs"]
        self.assertTrue(
            all("schema_version" not in entry["properties"] for entry in definitions.values())
        )

    def test_section_items_use_a_discriminated_union(self) -> None:
        definitions = FinalAnswer.model_json_schema()["$defs"]
        items = definitions["FinalAnswerSection"]["properties"]["items"]["items"]
        self.assertEqual(items["discriminator"]["propertyName"], "item_kind")

    def test_models_are_frozen(self) -> None:
        answer = self.build(answered_payload())
        with self.assertRaises(ValidationError):
            answer.outcome = "failed"

    def test_nested_models_are_frozen(self) -> None:
        answer = self.build(answered_payload())
        with self.assertRaises(ValidationError):
            answer.response_metadata.claim_count = 5


class LiteralCatalogTests(FinalAnswerTestCase):
    """Every public literal catalog accepts only its declared members."""

    def test_answered_outcome_is_accepted(self) -> None:
        self.assertEqual(self.build(answered_payload()).outcome, "answered")

    def test_partially_answered_outcome_is_accepted(self) -> None:
        self.assertEqual(self.build(partial_payload()).outcome, "partially_answered")

    def test_clarification_required_outcome_is_accepted(self) -> None:
        self.assertEqual(self.build(clarification_payload()).outcome, "clarification_required")

    def test_abstained_outcome_is_accepted(self) -> None:
        self.assertEqual(self.build(abstained_payload()).outcome, "abstained")

    def test_failed_outcome_is_accepted(self) -> None:
        self.assertEqual(self.build(failed_payload()).outcome, "failed")

    def test_denied_outcome_does_not_exist(self) -> None:
        payload = answered_payload()
        payload["outcome"] = "denied"
        self.reject(payload)

    def test_unknown_outcome_is_rejected(self) -> None:
        payload = answered_payload()
        payload["outcome"] = "succeeded"
        self.reject(payload)

    def test_outcome_is_case_sensitive(self) -> None:
        payload = answered_payload()
        payload["outcome"] = "Answered"
        self.reject(payload)

    def test_deterministic_template_generation_mode_is_accepted(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["generation_mode"] = "deterministic_template"
        mode = self.build(payload).response_metadata.generation_mode
        self.assertEqual(mode, "deterministic_template")

    def test_model_generated_generation_mode_is_accepted(self) -> None:
        mode = self.build(answered_payload()).response_metadata.generation_mode
        self.assertEqual(mode, "model_generated")

    def test_model_repaired_generation_mode_is_accepted(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["generation_mode"] = "model_repaired"
        self.assertEqual(self.build(payload).response_metadata.generation_mode, "model_repaired")

    def test_safe_fallback_generation_mode_is_accepted(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["generation_mode"] = "safe_fallback"
        self.assertEqual(self.build(payload).response_metadata.generation_mode, "safe_fallback")

    def test_none_generation_mode_is_accepted_only_for_failure(self) -> None:
        self.assertEqual(self.build(failed_payload()).response_metadata.generation_mode, "none")

    def test_unknown_generation_mode_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["generation_mode"] = "streamed"
        self.reject(payload)

    def test_passed_validation_status_is_accepted(self) -> None:
        status = self.build(answered_payload()).response_metadata.validation_status
        self.assertEqual(status, "passed")

    def test_not_applicable_validation_status_is_accepted_for_failure(self) -> None:
        status = self.build(failed_payload()).response_metadata.validation_status
        self.assertEqual(status, "not_applicable")

    def test_failed_validation_status_does_not_exist(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["validation_status"] = "failed"
        self.reject(payload)

    def test_inline_placement_is_accepted(self) -> None:
        self.assertEqual(self.build(answered_payload()).citations[0].placement, "inline")

    def test_section_end_placement_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["placement"] = "section_end"
        self.assertEqual(self.build(payload).citations[0].placement, "section_end")

    def test_answer_end_placement_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["placement"] = "answer_end"
        self.assertEqual(self.build(payload).citations[0].placement, "answer_end")

    def test_unknown_placement_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["placement"] = "footnote"
        self.reject(payload)

    def test_unknown_target_kind_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["target_kind"] = "section"
        self.reject(payload)

    def test_unknown_item_kind_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_kind"] = "note"
        self.reject(payload)

    def test_document_evidence_type_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["evidence_type"] = "document"
        self.assertEqual(self.build(payload).citations[0].sources[0].evidence_type, "document")

    def test_sql_evidence_type_is_accepted(self) -> None:
        answer = self.build(answered_payload())
        self.assertEqual(answer.citations[0].sources[0].evidence_type, "sql")

    def test_selector_evidence_type_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["evidence_type"] = "selector"
        self.assertEqual(self.build(payload).citations[0].sources[0].evidence_type, "selector")

    def test_rule_evidence_type_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["evidence_type"] = "rule"
        self.assertEqual(self.build(payload).citations[0].sources[0].evidence_type, "rule")

    def test_web_evidence_type_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["evidence_type"] = "web"
        self.assertEqual(self.build(payload).citations[0].sources[0].evidence_type, "web")

    def test_unknown_evidence_type_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["evidence_type"] = "pdf"
        self.reject(payload)


class RenderedTextTests(FinalAnswerTestCase):
    """Rendered text is validated exactly and never repaired."""

    def _with_text(self, text: str) -> Payload:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = text
        return recount(payload)

    def test_plain_text_is_accepted(self) -> None:
        answer = self.build(answered_payload())
        self.assertEqual(answer.validated_content.sections[0].items[0].rendered_text, CLAIM_TEXT)

    def test_persian_text_is_accepted(self) -> None:
        text = "\u0645\u0648\u062c\u0648\u062f\u06cc \u0634\u0645\u0627 \u06f1\u06f2\u06f0\u06f0 \u0627\u0633\u062a."
        payload = self._with_text(text)
        self.assertEqual(self.build(payload).response_metadata.character_count, len(text))

    def test_emoji_text_is_accepted(self) -> None:
        text = "Balance updated \U0001f4c8"
        payload = self._with_text(text)
        self.assertEqual(self.build(payload).response_metadata.character_count, len(text))

    def test_embedded_newline_is_accepted(self) -> None:
        payload = self._with_text("First line.\nSecond line.")
        answer = self.build(payload)
        self.assertIn("\n", answer.validated_content.sections[0].items[0].rendered_text)

    def test_internal_double_space_is_preserved(self) -> None:
        payload = self._with_text("Spaced  text.")
        answer = self.build(payload)
        self.assertEqual(
            answer.validated_content.sections[0].items[0].rendered_text, "Spaced  text."
        )

    def test_maximum_length_text_is_accepted(self) -> None:
        payload = self._with_text("a" * 4000)
        self.assertEqual(self.build(payload).response_metadata.character_count, 4000)

    def test_text_above_maximum_length_is_rejected(self) -> None:
        self.reject(self._with_text("a" * 4001))

    def test_empty_text_is_rejected(self) -> None:
        self.reject(self._with_text(""))

    def test_leading_space_is_rejected(self) -> None:
        self.reject(self._with_text(" Leading space."))

    def test_trailing_space_is_rejected(self) -> None:
        self.reject(self._with_text("Trailing space. "))

    def test_leading_newline_is_rejected(self) -> None:
        self.reject(self._with_text("\nLeading newline."))

    def test_trailing_newline_is_rejected(self) -> None:
        self.reject(self._with_text("Trailing newline.\n"))

    def test_whitespace_only_text_is_rejected(self) -> None:
        self.reject(self._with_text("   "))

    def test_nul_character_is_rejected(self) -> None:
        self.reject(self._with_text("Broken\x00text."))

    def test_integer_text_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = 1200
        self.reject(payload)

    def test_null_text_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = None
        self.reject(payload)

    def test_list_text_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = [CLAIM_TEXT]
        self.reject(payload)

    def test_display_label_padding_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["display_label"] = " Ledger "
        self.reject(payload)

    def test_display_label_maximum_length_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["display_label"] = "L" * 256
        self.assertEqual(len(self.build(payload).citations[0].sources[0].display_label), 256)

    def test_display_label_above_maximum_length_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["display_label"] = "L" * 257
        self.reject(payload)


class ClaimAndCaveatContentTests(FinalAnswerTestCase):
    """Claim and caveat items expose only validated presentation data."""

    def test_claim_item_kind_defaults(self) -> None:
        item = FinalClaimContent(item_id="claim.a", rendered_text=CLAIM_TEXT)
        self.assertEqual(item.item_kind, "claim")

    def test_claim_validation_status_defaults_to_supported(self) -> None:
        item = FinalClaimContent(item_id="claim.a", rendered_text=CLAIM_TEXT)
        self.assertEqual(item.validation_status, "supported")

    def test_caveat_item_kind_defaults(self) -> None:
        item = FinalCaveatContent(item_id="caveat.a", rendered_text=CAVEAT_TEXT)
        self.assertEqual(item.item_kind, "caveat")

    def test_caveat_validation_status_defaults_to_authorized(self) -> None:
        item = FinalCaveatContent(item_id="caveat.a", rendered_text=CAVEAT_TEXT)
        self.assertEqual(item.validation_status, "authorized")

    def test_claim_cannot_be_marked_unsupported(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["validation_status"] = "unsupported"
        self.reject(payload)

    def test_claim_cannot_be_marked_authorized(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["validation_status"] = "authorized"
        self.reject(payload)

    def test_caveat_cannot_be_marked_supported(self) -> None:
        payload = partial_payload()
        payload["validated_content"]["sections"][0]["items"][1]["validation_status"] = "supported"
        self.reject(payload)

    def test_claim_rejects_evidence_ids(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["evidence_ids"] = [uuid_text(11)]
        self.reject(payload)

    def test_claim_rejects_claim_code(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["claim_code"] = "balance"
        self.reject(payload)

    def test_claim_rejects_claim_type(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["claim_type"] = "fact"
        self.reject(payload)

    def test_claim_rejects_subject(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["subject"] = "account"
        self.reject(payload)

    def test_claim_rejects_supporting_fact_ids(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["supporting_fact_ids"] = ["f1"]
        self.reject(payload)

    def test_claim_rejects_confidence(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["confidence"] = 0.9
        self.reject(payload)

    def test_claim_rejects_reasoning(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["reasoning"] = "because"
        self.reject(payload)

    def test_caveat_rejects_evidence_ids(self) -> None:
        payload = partial_payload()
        payload["validated_content"]["sections"][0]["items"][1]["evidence_ids"] = [uuid_text(11)]
        self.reject(payload)

    def test_uppercase_item_id_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = "Claim.balance"
        payload["citations"][0]["target_id"] = "Claim.balance"
        self.reject(payload)

    def test_item_id_starting_with_a_digit_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = "1claim"
        payload["citations"][0]["target_id"] = "1claim"
        self.reject(payload)

    def test_item_id_with_whitespace_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = "claim balance"
        payload["citations"][0]["target_id"] = "claim balance"
        self.reject(payload)

    def test_empty_item_id_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = ""
        payload["citations"][0]["target_id"] = ""
        self.reject(payload)

    def test_maximum_length_item_id_is_accepted(self) -> None:
        item_id = "c" + "a" * 127
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = item_id
        payload["citations"][0]["target_id"] = item_id
        answer = self.build(payload)
        self.assertEqual(answer.validated_content.sections[0].items[0].item_id, item_id)

    def test_item_id_above_maximum_length_is_rejected(self) -> None:
        item_id = "c" + "a" * 128
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"][0]["item_id"] = item_id
        payload["citations"][0]["target_id"] = item_id
        self.reject(payload)

    def test_claim_and_caveat_share_a_textual_identifier(self) -> None:
        payload = partial_payload()
        payload["validated_content"]["sections"][0]["items"] = [
            claim_item("shared.id"),
            caveat_item("shared.id"),
        ]
        payload["citations"][0]["target_id"] = "shared.id"
        answer = self.build(recount(payload))
        self.assertEqual(len(answer.validated_content.sections[0].items), 2)


class SectionStructureTests(FinalAnswerTestCase):
    """Sections are ordered, bounded, unique, and never empty."""

    def test_single_section_is_accepted(self) -> None:
        self.assertEqual(len(self.build(answered_payload()).validated_content.sections), 1)

    def test_eight_sections_are_accepted(self) -> None:
        self.assertEqual(len(self.build(multi_claim_payload(8)).validated_content.sections), 8)

    def test_nine_sections_are_rejected(self) -> None:
        self.reject(multi_claim_payload(9))

    def test_empty_section_list_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"] = []
        self.reject(recount(payload))

    def test_null_section_list_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"] = None
        self.reject(payload)

    def test_empty_item_list_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"] = []
        self.reject(recount(payload))

    def test_thirty_two_items_in_one_section_are_accepted(self) -> None:
        payload = answered_payload()
        items = [claim_item()] + [caveat_item(f"caveat.c{index}") for index in range(31)]
        payload["validated_content"]["sections"][0]["items"] = items
        answer = self.build(recount(payload))
        self.assertEqual(len(answer.validated_content.sections[0].items), 32)

    def test_thirty_three_items_in_one_section_are_rejected(self) -> None:
        payload = answered_payload()
        items = [claim_item()] + [caveat_item(f"caveat.c{index}") for index in range(32)]
        payload["validated_content"]["sections"][0]["items"] = items
        self.reject(recount(payload))

    def test_duplicate_item_inside_one_section_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"] = [claim_item(), claim_item()]
        self.reject(recount(payload))

    def test_duplicate_item_across_sections_is_rejected(self) -> None:
        payload = multi_claim_payload(2)
        payload["validated_content"]["sections"][1]["items"][0]["item_id"] = "claim.item-0"
        self.reject(recount(payload))

    def test_duplicate_section_id_is_rejected(self) -> None:
        payload = multi_claim_payload(2)
        payload["validated_content"]["sections"][1]["section_id"] = "section.s0"
        self.reject(payload)

    def test_section_order_is_preserved(self) -> None:
        payload = multi_claim_payload(3)
        payload["validated_content"]["sections"].reverse()
        answer = self.build(payload)
        ids = [section.section_id for section in answer.validated_content.sections]
        self.assertEqual(ids, ["section.s2", "section.s1", "section.s0"])

    def test_item_order_is_preserved(self) -> None:
        payload = partial_payload()
        payload["validated_content"]["sections"][0]["items"] = [caveat_item(), claim_item()]
        answer = self.build(recount(payload))
        kinds = [item.item_kind for item in answer.validated_content.sections[0].items]
        self.assertEqual(kinds, ["caveat", "claim"])

    def test_section_rejects_a_title_field(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["title"] = "Summary"
        self.reject(payload)

    def test_section_rejects_a_heading_field(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["heading"] = "Summary"
        self.reject(payload)

    def test_section_rejects_a_body_field(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["body"] = "text"
        self.reject(payload)

    def test_section_rejects_raw_text(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["raw_text"] = "text"
        self.reject(payload)

    def test_invalid_section_type_is_rejected(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["section_type"] = "Summary Section"
        self.reject(payload)

    def test_validated_content_rejects_unknown_fields(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["summary"] = "text"
        self.reject(payload)

    def test_section_model_can_be_built_directly(self) -> None:
        section = FinalAnswerSection.model_validate(section_payload())
        self.assertEqual(section.section_id, "section.summary")

    def test_validated_content_model_can_be_built_directly(self) -> None:
        content = FinalValidatedContent.model_validate({"sections": [section_payload()]})
        self.assertEqual(len(content.sections), 1)


class CitationSourceTests(FinalAnswerTestCase):
    """Compiled citation sources expose safe identification only."""

    def _with_source(self, **overrides: Any) -> Payload:
        payload = answered_payload()
        payload["citations"][0]["sources"][0].update(overrides)
        return payload

    def test_source_round_trips(self) -> None:
        source = FinalCitationSource.model_validate(source_payload())
        self.assertEqual(source.locator_ref, "ledger.balance.row-42")

    def test_non_uuid4_evidence_id_is_rejected(self) -> None:
        self.reject(self._with_source(evidence_id="00000064-1111-1111-8111-000000000064"))

    def test_malformed_evidence_id_is_rejected(self) -> None:
        self.reject(self._with_source(evidence_id="not-a-uuid"))

    def test_locator_with_a_url_scheme_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="https://example.test/doc"))

    def test_locator_with_a_slash_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="docs/page-1"))

    def test_locator_with_a_backslash_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="docs\\page-1"))

    def test_locator_with_a_question_mark_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="doc?page=1"))

    def test_locator_with_a_number_sign_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="doc#section-1"))

    def test_locator_with_whitespace_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="doc page"))

    def test_empty_locator_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref=""))

    def test_locator_maximum_length_is_accepted(self) -> None:
        payload = self._with_source(locator_ref="a" * 256)
        self.assertEqual(len(self.build(payload).citations[0].sources[0].locator_ref), 256)

    def test_locator_above_maximum_length_is_rejected(self) -> None:
        self.reject(self._with_source(locator_ref="a" * 257))

    def test_source_version_with_a_plus_is_accepted(self) -> None:
        payload = self._with_source(source_version="2026.08.01+build.7")
        version = self.build(payload).citations[0].sources[0].source_version
        self.assertEqual(version, "2026.08.01+build.7")

    def test_source_version_with_whitespace_is_rejected(self) -> None:
        self.reject(self._with_source(source_version="2026 08 01"))

    def test_empty_source_version_is_rejected(self) -> None:
        self.reject(self._with_source(source_version=""))

    def test_source_rejects_a_url_field(self) -> None:
        self.reject(self._with_source(url="https://example.test"))

    def test_source_rejects_a_page_number_field(self) -> None:
        self.reject(self._with_source(page_number=3))

    def test_source_rejects_a_quote_field(self) -> None:
        self.reject(self._with_source(quote="quoted text"))

    def test_source_rejects_a_snippet_field(self) -> None:
        self.reject(self._with_source(snippet="snippet text"))

    def test_source_rejects_document_text(self) -> None:
        self.reject(self._with_source(document_text="full document"))

    def test_missing_display_label_is_rejected(self) -> None:
        payload = answered_payload()
        del payload["citations"][0]["sources"][0]["display_label"]
        self.reject(payload)


class CitationTests(FinalAnswerTestCase):
    """Citations realize planned slots exactly once."""

    def test_citation_round_trips(self) -> None:
        citation = FinalCitation.model_validate(citation_payload())
        self.assertEqual(citation.slot_id, "slot.balance")

    def test_non_uuid4_citation_id_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["citation_id"] = "000000c8-1111-1111-8111-0000000000c8"
        self.reject(payload)

    def test_citation_with_no_sources_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"] = []
        self.reject(payload)

    def test_citation_with_thirty_two_sources_is_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"] = [source_payload(300 + index) for index in range(32)]
        self.assertEqual(len(self.build(payload).citations[0].sources), 32)

    def test_citation_with_thirty_three_sources_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"] = [source_payload(300 + index) for index in range(33)]
        self.reject(payload)

    def test_duplicate_evidence_in_one_citation_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"] = [source_payload(300), source_payload(300)]
        self.reject(payload)

    def test_source_order_is_preserved(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"] = [source_payload(301), source_payload(300)]
        answer = self.build(payload)
        self.assertEqual(str(answer.citations[0].sources[0].evidence_id), uuid_text(301))

    def test_duplicate_citation_id_is_rejected(self) -> None:
        payload = multi_claim_payload(1, 2)
        payload["citations"][1]["citation_id"] = payload["citations"][0]["citation_id"]
        self.reject(payload)

    def test_duplicate_slot_id_is_rejected(self) -> None:
        payload = multi_claim_payload(1, 2)
        payload["citations"][1]["slot_id"] = payload["citations"][0]["slot_id"]
        self.reject(payload)

    def test_duplicate_semantic_citation_is_rejected(self) -> None:
        payload = answered_payload()
        second = citation_payload(index=201, slot_id="slot.balance-2")
        payload["citations"].append(second)
        self.reject(recount(payload))

    def test_multiple_citations_for_one_claim_are_accepted(self) -> None:
        payload = answered_payload()
        payload["citations"].append(
            citation_payload(
                index=201,
                slot_id="slot.balance-2",
                placement="answer_end",
                sources=[source_payload(301)],
            )
        )
        self.assertEqual(len(self.build(recount(payload)).citations), 2)

    def test_one_evidence_may_support_several_slots(self) -> None:
        payload = multi_claim_payload(1, 2)
        payload["citations"][1]["sources"] = [source_payload(2000)]
        self.assertEqual(len(self.build(payload).citations), 2)

    def test_citation_order_is_preserved(self) -> None:
        payload = multi_claim_payload(1, 2)
        payload["citations"].reverse()
        answer = self.build(payload)
        self.assertEqual(answer.citations[0].slot_id, "slot.item-1")

    def test_sixty_five_citations_are_rejected(self) -> None:
        self.reject(multi_claim_payload(2, 33))

    def test_citation_rejects_a_url_field(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["url"] = "https://example.test"
        self.reject(payload)

    def test_citation_rejects_a_quote_field(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["quote"] = "quoted"
        self.reject(payload)

    def test_citation_rejects_a_page_field(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["page"] = 2
        self.reject(payload)

    def test_invalid_slot_id_is_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["slot_id"] = "Slot One"
        self.reject(payload)


class FreshnessNoteTests(FinalAnswerTestCase):
    """Freshness status controls the presence of dates and reason codes."""

    def _with_note(self, **overrides: Any) -> Payload:
        payload = answered_payload()
        payload["freshness_note"] = freshness_payload(**overrides)
        return payload

    def test_current_status_requires_a_date(self) -> None:
        self.assertEqual(self.build(answered_payload()).freshness_note.status, "current")

    def test_current_status_without_a_date_is_rejected(self) -> None:
        self.reject(self._with_note(data_as_of=None))

    def test_current_status_may_carry_reason_codes(self) -> None:
        payload = self._with_note(reason_codes=["freshness.recent_sync"])
        codes = self.build(payload).freshness_note.reason_codes
        self.assertEqual(codes, ("freshness.recent_sync",))

    def test_stale_status_with_date_and_reasons_is_accepted(self) -> None:
        payload = self._with_note(status="stale", reason_codes=["freshness.delayed_sync"])
        self.assertEqual(self.build(payload).freshness_note.status, "stale")

    def test_stale_status_without_reasons_is_rejected(self) -> None:
        self.reject(self._with_note(status="stale"))

    def test_stale_status_without_a_date_is_rejected(self) -> None:
        self.reject(
            self._with_note(
                status="stale", data_as_of=None, reason_codes=["freshness.delayed_sync"]
            )
        )

    def test_mixed_status_with_reasons_is_accepted(self) -> None:
        payload = self._with_note(status="mixed", reason_codes=["freshness.multiple_sources"])
        self.assertEqual(self.build(payload).freshness_note.status, "mixed")

    def test_mixed_status_without_reasons_is_rejected(self) -> None:
        self.reject(self._with_note(status="mixed", reason_codes=[]))

    def test_mixed_status_without_a_date_is_accepted(self) -> None:
        payload = self._with_note(
            status="mixed", data_as_of=None, reason_codes=["freshness.multiple_sources"]
        )
        self.assertIsNone(self.build(payload).freshness_note.data_as_of)

    def test_unknown_status_with_reasons_is_accepted(self) -> None:
        payload = self._with_note(
            status="unknown", data_as_of=None, reason_codes=["freshness.unreported"]
        )
        self.assertEqual(self.build(payload).freshness_note.status, "unknown")

    def test_unknown_status_with_a_date_is_rejected(self) -> None:
        self.reject(self._with_note(status="unknown", reason_codes=["freshness.unreported"]))

    def test_unknown_status_without_reasons_is_rejected(self) -> None:
        self.reject(self._with_note(status="unknown", data_as_of=None))

    def test_not_applicable_status_is_accepted(self) -> None:
        payload = self._with_note(status="not_applicable", data_as_of=None)
        self.assertEqual(self.build(payload).freshness_note.status, "not_applicable")

    def test_not_applicable_status_with_a_date_is_rejected(self) -> None:
        self.reject(self._with_note(status="not_applicable"))

    def test_not_applicable_status_with_reasons_is_rejected(self) -> None:
        self.reject(
            self._with_note(
                status="not_applicable", data_as_of=None, reason_codes=["freshness.none"]
            )
        )

    def test_eight_reason_codes_are_accepted(self) -> None:
        codes = [f"freshness.reason-{index}" for index in range(8)]
        payload = self._with_note(status="mixed", data_as_of=None, reason_codes=codes)
        self.assertEqual(len(self.build(payload).freshness_note.reason_codes), 8)

    def test_nine_reason_codes_are_rejected(self) -> None:
        codes = [f"freshness.reason-{index}" for index in range(9)]
        self.reject(self._with_note(status="mixed", data_as_of=None, reason_codes=codes))

    def test_duplicate_reason_codes_are_rejected(self) -> None:
        codes = ["freshness.delayed_sync", "freshness.delayed_sync"]
        self.reject(self._with_note(status="mixed", data_as_of=None, reason_codes=codes))

    def test_invalid_reason_code_is_rejected(self) -> None:
        self.reject(
            self._with_note(status="mixed", data_as_of=None, reason_codes=["Freshness Delayed"])
        )

    def test_naive_freshness_date_is_rejected(self) -> None:
        self.reject(self._with_note(data_as_of="2026-08-01T11:30:00"))

    def test_offset_freshness_date_is_normalized_to_utc(self) -> None:
        payload = self._with_note(data_as_of="2026-08-01T15:00:00+03:30")
        note = self.build(payload).freshness_note
        self.assertEqual(note.data_as_of, datetime(2026, 8, 1, 11, 30, tzinfo=UTC))

    def test_freshness_note_rejects_unknown_fields(self) -> None:
        payload = answered_payload()
        payload["freshness_note"]["source_url"] = "https://example.test"
        self.reject(payload)

    def test_freshness_note_model_can_be_built_directly(self) -> None:
        note = FinalFreshnessNote.model_validate(
            freshness_payload(status="not_applicable", data_as_of=None)
        )
        self.assertEqual(note.reason_codes, ())


class AppliedLengthBudgetTests(FinalAnswerTestCase):
    """The applied length budget bounds the finalized content."""

    def test_budget_is_recorded(self) -> None:
        self.assertEqual(self.build(answered_payload()).applied_length_budget.max_characters, 16000)

    def test_character_count_within_budget_is_accepted(self) -> None:
        payload = answered_payload()
        payload["applied_length_budget"] = budget_payload(max_characters=len(CLAIM_TEXT))
        self.assertEqual(self.build(payload).response_metadata.character_count, len(CLAIM_TEXT))

    def test_character_count_above_budget_is_rejected(self) -> None:
        payload = answered_payload()
        payload["applied_length_budget"] = budget_payload(max_characters=len(CLAIM_TEXT) - 1)
        self.reject(payload)

    def test_section_count_above_budget_is_rejected(self) -> None:
        payload = multi_claim_payload(3)
        payload["applied_length_budget"] = budget_payload(max_sections=2)
        self.reject(payload)

    def test_claim_count_above_budget_is_rejected(self) -> None:
        payload = multi_claim_payload(1, 3)
        payload["applied_length_budget"] = budget_payload(max_claims=2)
        self.reject(payload)

    def test_caveat_count_above_budget_is_rejected(self) -> None:
        payload = partial_payload()
        payload["applied_length_budget"] = budget_payload(max_caveats=0)
        self.reject(payload)

    def test_citation_count_above_budget_is_rejected(self) -> None:
        payload = multi_claim_payload(1, 3)
        payload["applied_length_budget"] = budget_payload(max_citations=2)
        self.reject(payload)

    def test_budget_at_exact_limits_is_accepted(self) -> None:
        payload = multi_claim_payload(2, 2)
        payload["applied_length_budget"] = budget_payload(
            max_characters=payload["response_metadata"]["character_count"],
            max_sections=2,
            max_claims=4,
            max_caveats=0,
            max_citations=4,
        )
        self.assertEqual(len(self.build(payload).citations), 4)

    def test_budget_is_required(self) -> None:
        payload = answered_payload()
        del payload["applied_length_budget"]
        self.reject(payload)

    def test_budget_rejects_unknown_fields(self) -> None:
        payload = answered_payload()
        payload["applied_length_budget"]["max_tokens"] = 500
        self.reject(payload)

    def test_failed_outcome_still_records_a_budget(self) -> None:
        self.assertEqual(self.build(failed_payload()).applied_length_budget.max_sections, 8)


class ResponseMetadataTests(FinalAnswerTestCase):
    """Trace-safe metadata must agree exactly with the finalized content."""

    def test_metadata_counts_match_content(self) -> None:
        metadata = self.build(partial_payload()).response_metadata
        self.assertEqual((metadata.claim_count, metadata.caveat_count), (1, 1))

    def test_wrong_section_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["section_count"] = 2
        self.reject(payload)

    def test_wrong_claim_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["claim_count"] = 2
        self.reject(payload)

    def test_wrong_caveat_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["caveat_count"] = 1
        self.reject(payload)

    def test_wrong_citation_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["citation_count"] = 0
        self.reject(payload)

    def test_wrong_character_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["character_count"] = len(CLAIM_TEXT) + 1
        self.reject(payload)

    def test_character_count_uses_unicode_code_points(self) -> None:
        payload = answered_payload()
        text = "\u0645\u0648\u062c\u0648\u062f\u06cc"
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = text
        answer = self.build(recount(payload))
        self.assertEqual(answer.response_metadata.character_count, 6)

    def test_character_count_excludes_citation_labels(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["sources"][0]["display_label"] = "A much longer citation label"
        self.assertEqual(self.build(payload).response_metadata.character_count, len(CLAIM_TEXT))

    def test_failure_counts_must_all_be_zero(self) -> None:
        metadata = self.build(failed_payload()).response_metadata
        self.assertEqual(metadata.section_count + metadata.character_count, 0)

    def test_failure_with_nonzero_counts_is_rejected(self) -> None:
        payload = failed_payload()
        payload["response_metadata"]["claim_count"] = 1
        self.reject(payload)

    def test_section_count_above_eight_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["section_count"] = 9
        self.reject(payload)

    def test_negative_counts_are_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["claim_count"] = -1
        self.reject(payload)

    def test_boolean_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["claim_count"] = True
        self.reject(payload)

    def test_float_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["claim_count"] = 1.0
        self.reject(payload)

    def test_string_count_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["claim_count"] = "1"
        self.reject(payload)

    def test_non_boolean_degraded_flag_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["degraded"] = "true"
        self.reject(payload)

    def test_locale_tag_is_accepted(self) -> None:
        self.assertEqual(self.build(answered_payload()).response_metadata.response_locale, "fa-IR")

    def test_bare_language_locale_is_accepted(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["response_locale"] = "fa"
        self.assertEqual(self.build(payload).response_metadata.response_locale, "fa")

    def test_malformed_locale_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["response_locale"] = "farsi_iran"
        self.reject(payload)

    def test_unknown_answer_type_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["answer_type"] = "chat"
        self.reject(payload)

    def test_metadata_rejects_model_name(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["model_name"] = "gpt"
        self.reject(payload)

    def test_metadata_rejects_token_count(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["token_count"] = 120
        self.reject(payload)

    def test_metadata_rejects_latency(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["latency_ms"] = 42
        self.reject(payload)

    def test_metadata_model_can_be_built_directly(self) -> None:
        metadata = FinalResponseMetadata.model_validate(metadata_payload())
        self.assertFalse(metadata.degraded)


class OutcomeShapeTests(FinalAnswerTestCase):
    """Each terminal outcome permits exactly one payload shape."""

    def test_answered_requires_validated_content(self) -> None:
        payload = answered_payload()
        payload["validated_content"] = None
        self.reject(recount(payload))

    def test_answered_requires_at_least_one_claim(self) -> None:
        payload = answered_payload()
        payload["validated_content"]["sections"][0]["items"] = [caveat_item()]
        payload["citations"] = []
        self.reject(recount(payload))

    def test_answered_rejects_a_safe_error(self) -> None:
        payload = answered_payload()
        payload["safe_error"] = error_payload()
        self.reject(payload)

    def test_answered_accepts_no_reason_codes(self) -> None:
        self.assertEqual(self.build(answered_payload()).outcome_reason_codes, ())

    def test_partially_answered_requires_reason_codes(self) -> None:
        payload = partial_payload()
        payload["outcome_reason_codes"] = []
        self.reject(payload)

    def test_partially_answered_requires_content(self) -> None:
        payload = partial_payload()
        payload["validated_content"] = None
        payload["citations"] = []
        self.reject(recount(payload))

    def test_partially_answered_rejects_a_safe_error(self) -> None:
        payload = partial_payload()
        payload["safe_error"] = error_payload()
        self.reject(payload)

    def test_clarification_requires_content(self) -> None:
        payload = clarification_payload()
        payload["validated_content"] = None
        self.reject(recount(payload))

    def test_clarification_rejects_claims(self) -> None:
        payload = clarification_payload()
        payload["validated_content"]["sections"][0]["items"].append(claim_item())
        payload["citations"] = [citation_payload()]
        self.reject(recount(payload))

    def test_clarification_citations_must_target_a_caveat(self) -> None:
        payload = clarification_payload()
        payload["citations"] = [
            citation_payload(target_kind="caveat", target_id="caveat.which_account")
        ]
        self.assertEqual(len(self.build(recount(payload)).citations), 1)

    def test_clarification_rejects_claim_targeted_citations(self) -> None:
        payload = clarification_payload()
        payload["citations"] = [citation_payload(target_id="caveat.which_account")]
        self.reject(recount(payload))

    def test_clarification_requires_reason_codes(self) -> None:
        payload = clarification_payload()
        payload["outcome_reason_codes"] = []
        self.reject(payload)

    def test_clarification_rejects_a_safe_error(self) -> None:
        payload = clarification_payload()
        payload["safe_error"] = error_payload()
        self.reject(payload)

    def test_abstention_requires_content(self) -> None:
        payload = abstained_payload()
        payload["validated_content"] = None
        self.reject(recount(payload))

    def test_abstention_rejects_claims(self) -> None:
        payload = abstained_payload()
        payload["validated_content"]["sections"][0]["items"].append(claim_item())
        payload["citations"] = [citation_payload()]
        self.reject(recount(payload))

    def test_abstention_citations_must_target_a_caveat(self) -> None:
        payload = abstained_payload()
        payload["citations"] = [
            citation_payload(target_kind="caveat", target_id="caveat.no_authorized_source")
        ]
        self.assertEqual(len(self.build(recount(payload)).citations), 1)

    def test_abstention_rejects_claim_targeted_citations(self) -> None:
        payload = abstained_payload()
        payload["citations"] = [citation_payload(target_id="caveat.no_authorized_source")]
        self.reject(recount(payload))

    def test_abstention_requires_reason_codes(self) -> None:
        payload = abstained_payload()
        payload["outcome_reason_codes"] = []
        self.reject(payload)

    def test_abstention_rejects_safe_error(self) -> None:
        payload = abstained_payload()
        payload["safe_error"] = error_payload()
        self.reject(payload)

    def test_failed_requires_a_safe_error(self) -> None:
        payload = failed_payload()
        payload["safe_error"] = None
        self.reject(payload)

    def test_failed_rejects_validated_content(self) -> None:
        payload = failed_payload()
        payload["validated_content"] = {"sections": [section_payload()]}
        self.reject(payload)

    def test_failed_rejects_citations(self) -> None:
        payload = failed_payload()
        payload["citations"] = [citation_payload()]
        self.reject(payload)

    def test_failed_requires_reason_codes(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = []
        self.reject(payload)

    def test_failed_requires_the_none_generation_mode(self) -> None:
        payload = failed_payload()
        payload["response_metadata"]["generation_mode"] = "model_generated"
        self.reject(payload)

    def test_failed_requires_not_applicable_validation_status(self) -> None:
        payload = failed_payload()
        payload["response_metadata"]["validation_status"] = "passed"
        self.reject(payload)

    def test_failed_requires_the_degraded_flag(self) -> None:
        payload = failed_payload()
        payload["response_metadata"]["degraded"] = False
        self.reject(payload)

    def test_failed_requires_not_applicable_freshness(self) -> None:
        payload = failed_payload()
        payload["freshness_note"] = freshness_payload()
        self.reject(payload)

    def test_failed_rejects_an_answer_type(self) -> None:
        payload = failed_payload()
        payload["response_metadata"]["answer_type"] = "direct"
        self.reject(payload)

    def test_content_outcomes_reject_the_none_generation_mode(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["generation_mode"] = "none"
        self.reject(payload)

    def test_content_outcomes_reject_not_applicable_validation_status(self) -> None:
        payload = answered_payload()
        payload["response_metadata"]["validation_status"] = "not_applicable"
        self.reject(payload)

    def test_every_claim_must_be_cited(self) -> None:
        payload = multi_claim_payload(1, 2)
        payload["citations"] = payload["citations"][:1]
        self.reject(recount(payload))

    def test_caveats_may_have_no_citation(self) -> None:
        answer = self.build(partial_payload())
        self.assertEqual(len(answer.citations), 1)

    def test_citation_target_must_exist_in_content(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["target_id"] = "claim.unknown"
        self.reject(payload)

    def test_citation_target_kind_must_match_the_item_kind(self) -> None:
        payload = answered_payload()
        payload["citations"][0]["target_kind"] = "caveat"
        self.reject(payload)

    def test_caveat_citation_is_accepted(self) -> None:
        payload = partial_payload()
        payload["citations"].append(
            citation_payload(
                index=205,
                slot_id="slot.july",
                target_kind="caveat",
                target_id="caveat.july",
                sources=[source_payload(305)],
            )
        )
        self.assertEqual(len(self.build(recount(payload)).citations), 2)

    def test_duplicate_outcome_reason_codes_are_rejected(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = [
            "final.dependency_timeout",
            "final.dependency_timeout",
        ]
        self.reject(payload)

    def test_sixteen_outcome_reason_codes_are_accepted(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = [f"final.reason-{index}" for index in range(16)]
        self.assertEqual(len(self.build(payload).outcome_reason_codes), 16)

    def test_seventeen_outcome_reason_codes_are_rejected(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = [f"final.reason-{index}" for index in range(17)]
        self.reject(payload)

    def test_invalid_outcome_reason_code_is_rejected(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = ["Final Timeout"]
        self.reject(payload)


class SafeErrorTests(FinalAnswerTestCase):
    """Failure carries the shared DomainError and nothing else."""

    def test_permitted_failure_codes_are_accepted(self) -> None:
        for code in PERMITTED_FAILURE_CODES:
            with self.subTest(code=code):
                self.assertEqual(self.build(failed_payload(code)).safe_error.code, code)

    def test_prohibited_failure_codes_are_rejected(self) -> None:
        for code in PROHIBITED_FAILURE_CODES:
            with self.subTest(code=code):
                self.reject(failed_payload(code))

    def test_safe_error_is_absent_for_content_outcomes(self) -> None:
        self.assertIsNone(self.build(answered_payload()).safe_error)

    def test_retryable_flag_must_match_the_code(self) -> None:
        payload = failed_payload("INTERNAL_ERROR")
        payload["safe_error"]["retryable"] = True
        self.reject(payload)

    def test_safe_message_key_must_match_the_code(self) -> None:
        payload = failed_payload()
        payload["safe_error"]["safe_message_key"] = "error.other"
        self.reject(payload)

    def test_safe_error_rejects_raw_message_text(self) -> None:
        payload = failed_payload()
        payload["safe_error"]["message"] = "Timeout contacting provider"
        self.reject(payload)

    def test_safe_error_rejects_a_stack_trace(self) -> None:
        payload = failed_payload()
        payload["safe_error"]["stack_trace"] = "Traceback ..."
        self.reject(payload)

    def test_safe_error_rejects_an_http_status(self) -> None:
        payload = failed_payload()
        payload["safe_error"]["http_status"] = 504
        self.reject(payload)

    def test_internal_detail_reference_is_preserved(self) -> None:
        reference = self.build(failed_payload()).safe_error.internal_detail_ref
        self.assertEqual(str(reference), uuid_text(999))

    def test_error_envelope_is_not_embedded(self) -> None:
        payload = failed_payload()
        payload["error_envelope"] = {"error": error_payload()}
        self.reject(payload)


class IdentifierAndTimestampTests(FinalAnswerTestCase):
    """Correlation identifiers and timestamps are strictly typed."""

    def test_all_identifier_fields_are_required(self) -> None:
        for field in ROOT_IDENTIFIER_FIELDS:
            with self.subTest(field=field):
                payload = answered_payload()
                del payload[field]
                self.reject(payload)

    def test_all_identifier_fields_reject_non_uuid_values(self) -> None:
        for field in ROOT_IDENTIFIER_FIELDS:
            with self.subTest(field=field):
                payload = answered_payload()
                payload[field] = "not-a-uuid"
                self.reject(payload)

    def test_all_identifier_fields_reject_non_version_four_uuids(self) -> None:
        for field in ROOT_IDENTIFIER_FIELDS:
            with self.subTest(field=field):
                payload = answered_payload()
                payload[field] = "11111111-1111-1111-8111-111111111111"
                self.reject(payload)

    def test_all_identifier_fields_reject_null(self) -> None:
        for field in ROOT_IDENTIFIER_FIELDS:
            with self.subTest(field=field):
                payload = answered_payload()
                payload[field] = None
                self.reject(payload)

    def test_answer_plan_id_is_mandatory_for_failure(self) -> None:
        payload = failed_payload()
        del payload["answer_plan_id"]
        self.reject(payload)

    def test_identifiers_may_repeat_across_fields(self) -> None:
        payload = answered_payload()
        payload["correlation_id"] = payload["request_id"]
        self.assertEqual(str(self.build(payload).correlation_id), payload["request_id"])

    def test_naive_finalized_at_is_rejected(self) -> None:
        payload = answered_payload()
        payload["finalized_at"] = "2026-08-01T12:00:00"
        self.reject(payload)

    def test_offset_finalized_at_is_normalized_to_utc(self) -> None:
        payload = answered_payload()
        payload["finalized_at"] = "2026-08-01T15:30:00+03:30"
        self.assertEqual(self.build(payload).finalized_at, datetime(2026, 8, 1, 12, 0, tzinfo=UTC))

    def test_negative_offset_finalized_at_is_normalized_to_utc(self) -> None:
        payload = answered_payload()
        payload["finalized_at"] = "2026-08-01T07:00:00-05:00"
        expected = datetime(2026, 8, 1, 7, 0, tzinfo=timezone(timedelta(hours=-5)))
        self.assertEqual(self.build(payload).finalized_at, expected)

    def test_finalized_at_is_required(self) -> None:
        payload = answered_payload()
        del payload["finalized_at"]
        self.reject(payload)

    def test_numeric_finalized_at_is_read_as_epoch_seconds(self) -> None:
        payload = answered_payload()
        payload["finalized_at"] = 1785000000
        self.assertEqual(self.build(payload).finalized_at.tzinfo, UTC)

    def test_finalizer_version_is_recorded(self) -> None:
        self.assertEqual(self.build(answered_payload()).finalizer_version, "1.0.0")

    def test_invalid_finalizer_version_is_rejected(self) -> None:
        payload = answered_payload()
        payload["finalizer_version"] = "v1"
        self.reject(payload)

    def test_finalizer_version_is_required(self) -> None:
        payload = answered_payload()
        del payload["finalizer_version"]
        self.reject(payload)


class DefaultsAndCollectionTests(FinalAnswerTestCase):
    """Optional collections default to empty tuples and reject explicit nulls."""

    def test_missing_citations_default_to_an_empty_tuple(self) -> None:
        payload = clarification_payload()
        del payload["citations"]
        self.assertEqual(self.build(payload).citations, ())

    def test_missing_outcome_reason_codes_default_to_an_empty_tuple(self) -> None:
        payload = answered_payload()
        del payload["outcome_reason_codes"]
        self.assertEqual(self.build(payload).outcome_reason_codes, ())

    def test_missing_safe_error_defaults_to_none(self) -> None:
        payload = answered_payload()
        del payload["safe_error"]
        self.assertIsNone(self.build(payload).safe_error)

    def test_missing_validated_content_defaults_to_none_for_failure(self) -> None:
        payload = failed_payload()
        del payload["validated_content"]
        self.assertIsNone(self.build(payload).validated_content)

    def test_explicit_null_citations_are_rejected(self) -> None:
        payload = answered_payload()
        payload["citations"] = None
        self.reject(payload)

    def test_explicit_null_outcome_reason_codes_are_rejected(self) -> None:
        payload = answered_payload()
        payload["outcome_reason_codes"] = None
        self.reject(payload)

    def test_explicit_null_freshness_note_is_rejected(self) -> None:
        payload = answered_payload()
        payload["freshness_note"] = None
        self.reject(payload)

    def test_explicit_null_metadata_is_rejected(self) -> None:
        payload = answered_payload()
        payload["response_metadata"] = None
        self.reject(payload)

    def test_collections_are_exposed_as_tuples(self) -> None:
        answer = self.build(answered_payload())
        self.assertIsInstance(answer.citations, tuple)

    def test_sections_are_exposed_as_tuples(self) -> None:
        answer = self.build(answered_payload())
        self.assertIsInstance(answer.validated_content.sections, tuple)

    def test_citations_are_not_sorted(self) -> None:
        payload = multi_claim_payload(1, 3)
        payload["citations"] = list(reversed(payload["citations"]))
        slots = [citation.slot_id for citation in self.build(payload).citations]
        self.assertEqual(slots, ["slot.item-2", "slot.item-1", "slot.item-0"])

    def test_reason_codes_are_not_sorted(self) -> None:
        payload = failed_payload()
        payload["outcome_reason_codes"] = ["final.zeta", "final.alpha"]
        self.assertEqual(self.build(payload).outcome_reason_codes, ("final.zeta", "final.alpha"))


class SerializationTests(FinalAnswerTestCase):
    """Finalized answers round-trip losslessly through JSON."""

    def _round_trip(self, payload: Payload) -> FinalAnswer:
        answer = self.build(payload)
        return FinalAnswer.model_validate_json(answer.model_dump_json())

    def test_answered_round_trips(self) -> None:
        self.assertEqual(self._round_trip(answered_payload()), self.build(answered_payload()))

    def test_partially_answered_round_trips(self) -> None:
        self.assertEqual(self._round_trip(partial_payload()), self.build(partial_payload()))

    def test_clarification_round_trips(self) -> None:
        expected = self.build(clarification_payload())
        self.assertEqual(self._round_trip(clarification_payload()), expected)

    def test_abstention_round_trips(self) -> None:
        self.assertEqual(self._round_trip(abstained_payload()), self.build(abstained_payload()))

    def test_failure_round_trips(self) -> None:
        self.assertEqual(self._round_trip(failed_payload()), self.build(failed_payload()))

    def test_dump_preserves_the_schema_version(self) -> None:
        dumped = self.build(answered_payload()).model_dump(mode="json")
        self.assertEqual(dumped["schema_version"], "1.0.0")

    def test_dump_preserves_persian_text(self) -> None:
        payload = answered_payload()
        text = "\u0645\u0648\u062c\u0648\u062f\u06cc"
        payload["validated_content"]["sections"][0]["items"][0]["rendered_text"] = text
        dumped = self.build(recount(payload)).model_dump(mode="json")
        self.assertEqual(
            dumped["validated_content"]["sections"][0]["items"][0]["rendered_text"], text
        )

    def test_dump_emits_utc_timestamps(self) -> None:
        payload = answered_payload()
        payload["finalized_at"] = "2026-08-01T15:30:00+03:30"
        dumped = self.build(payload).model_dump(mode="json")
        self.assertTrue(dumped["finalized_at"].startswith("2026-08-01T12:00:00"))

    def test_dumped_payload_revalidates(self) -> None:
        dumped = self.build(partial_payload()).model_dump(mode="json")
        self.assertEqual(self.build(dumped).outcome, "partially_answered")

    def test_deep_copied_payload_validates_identically(self) -> None:
        payload = answered_payload()
        self.assertEqual(self.build(copy.deepcopy(payload)), self.build(payload))

    def test_equality_is_structural(self) -> None:
        self.assertEqual(self.build(answered_payload()), self.build(answered_payload()))

    def test_different_outcomes_are_not_equal(self) -> None:
        self.assertNotEqual(self.build(answered_payload()), self.build(failed_payload()))


class ForbiddenFieldTests(FinalAnswerTestCase):
    """The contract is closed against unsafe or duplicated concepts."""

    def test_forbidden_root_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                payload = answered_payload()
                payload[name] = "value"
                self.reject(payload)

    def test_forbidden_metadata_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                payload = answered_payload()
                payload["response_metadata"][name] = "value"
                self.reject(payload)

    def test_forbidden_item_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                payload = answered_payload()
                payload["validated_content"]["sections"][0]["items"][0][name] = "value"
                self.reject(payload)

    def test_forbidden_citation_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                payload = answered_payload()
                payload["citations"][0][name] = "value"
                self.reject(payload)

    def test_forbidden_source_fields_are_rejected(self) -> None:
        for name in FORBIDDEN_FIELD_NAMES:
            with self.subTest(name=name):
                payload = answered_payload()
                payload["citations"][0]["sources"][0][name] = "value"
                self.reject(payload)

    def test_declared_root_property_names_avoid_forbidden_concepts(self) -> None:
        declared = set(FinalAnswer.model_json_schema()["properties"])
        self.assertEqual(declared.intersection(FORBIDDEN_FIELD_NAMES), set())

    def test_declared_nested_property_names_avoid_forbidden_concepts(self) -> None:
        definitions = FinalAnswer.model_json_schema()["$defs"]
        declared = {name for entry in definitions.values() for name in entry["properties"]}
        self.assertEqual(declared.intersection(FORBIDDEN_FIELD_NAMES), set())

    def test_answer_plan_is_not_embedded(self) -> None:
        payload = answered_payload()
        payload["answer_plan"] = {"plan": "value"}
        self.reject(payload)

    def test_evidence_bundle_is_not_embedded(self) -> None:
        payload = answered_payload()
        payload["evidence_bundle"] = {"bundle": "value"}
        self.reject(payload)

    def test_runtime_snapshot_is_not_embedded(self) -> None:
        payload = answered_payload()
        payload["runtime_snapshot"] = {"snapshot": "value"}
        self.reject(payload)

    def test_authorization_decision_is_not_embedded(self) -> None:
        payload = answered_payload()
        payload["authorization_decision"] = {"decision": "allow"}
        self.reject(payload)

    def test_generic_metadata_mapping_is_rejected(self) -> None:
        payload = answered_payload()
        payload["metadata"] = {"key": "value"}
        self.reject(payload)


class PublicExportTests(FinalAnswerTestCase):
    """The contracts package exports the new public names."""

    def test_new_names_are_exported(self) -> None:
        from ai_assistant import contracts

        expected = {
            "FinalAnswer",
            "FinalAnswerItem",
            "FinalAnswerSection",
            "FinalCaveatContent",
            "FinalCitation",
            "FinalCitationSource",
            "FinalClaimContent",
            "FinalContentValidationStatus",
            "FinalFreshnessNote",
            "FinalFreshnessStatus",
            "FinalGenerationMode",
            "FinalOutcome",
            "FinalResponseMetadata",
            "FinalValidatedContent",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))

    def test_exported_names_are_importable(self) -> None:
        from ai_assistant import contracts

        self.assertTrue(all(hasattr(contracts, name) for name in contracts.__all__))

    def test_exported_names_are_unique(self) -> None:
        from ai_assistant import contracts

        self.assertEqual(len(contracts.__all__), len(set(contracts.__all__)))

    def test_exported_names_are_sorted(self) -> None:
        from ai_assistant import contracts

        names = list(contracts.__all__)
        self.assertEqual(names, names[:1] + sorted(names[1:]))

    def test_earlier_contract_exports_are_preserved(self) -> None:
        from ai_assistant import contracts

        earlier = {"AnswerPlan", "DomainError", "ErrorCode", "ContractModel", "SchemaVersion"}
        self.assertTrue(earlier.issubset(set(contracts.__all__)))

    def test_final_answer_is_reachable_from_the_package(self) -> None:
        from ai_assistant import contracts

        self.assertIs(contracts.FinalAnswer, FinalAnswer)


class DocumentationExampleTests(FinalAnswerTestCase):
    """The specification document stays consistent with the contract."""

    def _document(self) -> str:
        with open("docs/contracts/final-answer-1.0.0.md", encoding="utf-8") as handle:
            return handle.read()

    def test_document_declares_the_schema_id(self) -> None:
        self.assertIn(FINAL_ANSWER_SCHEMA_ID, self._document())

    def test_document_declares_the_dialect(self) -> None:
        self.assertIn(JSON_SCHEMA_DIALECT, self._document())

    def test_document_mentions_every_outcome(self) -> None:
        document = self._document()
        outcomes = (
            "answered",
            "partially_answered",
            "clarification_required",
            "abstained",
            "failed",
        )
        self.assertTrue(all(outcome in document for outcome in outcomes))

    def test_document_does_not_declare_a_denied_outcome(self) -> None:
        self.assertNotIn('"outcome": "denied"', self._document())

    def test_document_examples_validate(self) -> None:
        document = self._document()
        blocks = document.split("```json")[1:]
        examples = [block.split("```")[0] for block in blocks]
        payloads = [json.loads(example) for example in examples]
        full = [item for item in payloads if "final_answer_id" in item and "outcome" in item]
        for index, payload in enumerate(full):
            with self.subTest(example=index):
                self.assertIsInstance(self.build(payload), FinalAnswer)

    def test_document_contains_all_five_outcome_examples(self) -> None:
        document = self._document()
        blocks = document.split("```json")[1:]
        examples = [json.loads(block.split("```")[0]) for block in blocks]
        outcomes = {
            item["outcome"] for item in examples if "final_answer_id" in item and "outcome" in item
        }
        self.assertEqual(len(outcomes), 5)


class FinalAnswerPropertyTests(FinalAnswerTestCase):
    """Bounded property tests for order, round-trips, duplicates, and closure."""

    @given(section_count=st.integers(1, 4), claims_per_section=st.integers(1, 3))
    def test_generated_order_is_preserved(
        self, section_count: int, claims_per_section: int
    ) -> None:
        payload = multi_claim_payload(section_count, claims_per_section)
        expected_sections = [
            section["section_id"] for section in payload["validated_content"]["sections"]
        ]
        expected_items = [
            item["item_id"]
            for section in payload["validated_content"]["sections"]
            for item in section["items"]
        ]
        expected_slots = [citation["slot_id"] for citation in payload["citations"]]
        answer = self.build(payload)
        actual_sections = [section.section_id for section in answer.validated_content.sections]
        actual_items = [
            item.item_id for section in answer.validated_content.sections for item in section.items
        ]
        actual_slots = [citation.slot_id for citation in answer.citations]
        self.assertEqual(actual_sections, expected_sections)
        self.assertEqual(actual_items, expected_items)
        self.assertEqual(actual_slots, expected_slots)

    @given(
        section_count=st.integers(1, 4),
        claims_per_section=st.integers(1, 3),
        text_length=st.integers(1, 120),
    )
    def test_valid_partitions_round_trip_through_json(
        self, section_count: int, claims_per_section: int, text_length: int
    ) -> None:
        payload = multi_claim_payload(section_count, claims_per_section)
        for section in payload["validated_content"]["sections"]:
            for item in section["items"]:
                item["rendered_text"] = "t" * text_length
        answer = self.build(recount(payload))
        restored = FinalAnswer.model_validate_json(answer.model_dump_json())
        self.assertEqual(restored, answer)

    @given(
        duplicate_kind=st.sampled_from(["section_item", "global_item", "caveat"]),
        section_count=st.integers(1, 4),
    )
    def test_duplicate_occurrences_are_rejected(
        self, duplicate_kind: str, section_count: int
    ) -> None:
        payload = multi_claim_payload(max(section_count, 2))
        sections = payload["validated_content"]["sections"]
        match duplicate_kind:
            case "section_item":
                sections[0]["items"].append(copy.deepcopy(sections[0]["items"][0]))
            case "global_item":
                sections[1]["items"].append(copy.deepcopy(sections[0]["items"][0]))
            case _:
                sections[0]["items"].append(caveat_item("caveat.shared"))
                sections[1]["items"].append(caveat_item("caveat.shared"))
        self.reject(recount(payload))

    @given(
        source_count=st.integers(1, 8),
        citation_count=st.integers(1, 16),
        placement=st.sampled_from(["inline", "section_end", "answer_end"]),
    )
    def test_citation_targets_with_evidence_subsets_round_trip(
        self, source_count: int, citation_count: int, placement: str
    ) -> None:
        payload = multi_claim_payload(1, citation_count)
        for index, citation in enumerate(payload["citations"]):
            citation["placement"] = placement
            citation["sources"] = [
                source_payload(5000 + index * 8 + offset) for offset in range(source_count)
            ]
        answer = self.build(recount(payload))
        item_ids = {
            item.item_id for section in answer.validated_content.sections for item in section.items
        }
        self.assertTrue(all(citation.target_id in item_ids for citation in answer.citations))
        restored = FinalAnswer.model_validate_json(answer.model_dump_json())
        self.assertEqual(restored, answer)

    @given(
        field_name=st.sampled_from(list(FORBIDDEN_FIELD_NAMES)),
        boundary=st.sampled_from(
            ["root", "content", "section", "item", "citation", "source", "metadata", "freshness"]
        ),
    )
    def test_sampled_forbidden_fields_are_rejected(self, field_name: str, boundary: str) -> None:
        payload = answered_payload()
        content = payload["validated_content"]
        match boundary:
            case "root":
                payload[field_name] = "value"
            case "content":
                content[field_name] = "value"
            case "section":
                content["sections"][0][field_name] = "value"
            case "item":
                content["sections"][0]["items"][0][field_name] = "value"
            case "citation":
                payload["citations"][0][field_name] = "value"
            case "source":
                payload["citations"][0]["sources"][0][field_name] = "value"
            case "metadata":
                payload["response_metadata"][field_name] = "value"
            case _:
                payload["freshness_note"][field_name] = "value"
        self.reject(payload)


if __name__ == "__main__":
    unittest.main()
