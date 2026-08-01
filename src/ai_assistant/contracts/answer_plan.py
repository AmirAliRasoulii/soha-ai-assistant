"""AnswerPlan contract: the deterministic semantic plan for one response."""

from collections.abc import Hashable
from typing import Annotated, Final, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from ai_assistant.contracts.base import ContractModel, SchemaVersion, UtcDateTime
from ai_assistant.contracts.evidence import EvidenceDecision, EvidenceSubjectRef

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
ANSWER_PLAN_SCHEMA_VERSION: Final[Literal["1.0.0"]] = "1.0.0"
ANSWER_PLAN_SCHEMA_ID = "urn:ai-assistant:contracts:answer-plan:1.0.0"

AnswerType = Literal[
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
]

AnswerSectionItemKind = Literal["claim", "caveat"]

CitationTargetKind = Literal["claim", "caveat"]

CitationPlacement = Literal["inline", "section_end", "answer_end"]

_CANONICAL_CODE_PATTERN = r"^[a-z][a-z0-9._:-]*$"
_LOCALE_TAG_PATTERN = r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$"

_CanonicalCode = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_CANONICAL_CODE_PATTERN),
]


def _require_exact_locale(value: str) -> str:
    # The pattern already excludes internal whitespace, but an explicit check
    # guards against a trailing newline slipping past the "$" anchor.
    if value != value.strip():
        raise ValueError("locale tag must not have leading or trailing whitespace")
    return value


_LocaleTag = Annotated[
    str,
    Field(min_length=2, max_length=35, pattern=_LOCALE_TAG_PATTERN),
    AfterValidator(_require_exact_locale),
]


def _require_uuid4(value: UUID) -> UUID:
    if value.version != 4:
        raise ValueError("identifier must be a version 4 UUID")
    return value


_Uuid4 = Annotated[UUID, AfterValidator(_require_uuid4)]


def _require_unique_values[T: Hashable](value: tuple[T, ...]) -> tuple[T, ...]:
    if len(set(value)) != len(value):
        raise ValueError("values must be unique")
    return value


_ToneCodes = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=8),
    AfterValidator(_require_unique_values),
]
_RequiredCodes16 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=16),
    AfterValidator(_require_unique_values),
]
_OptionalCodes16 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=16),
    AfterValidator(_require_unique_values),
]
_RequiredCodes32 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_values),
]
_OptionalCodes64 = Annotated[
    tuple[_CanonicalCode, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_values),
]
_UuidTuple1To32 = Annotated[
    tuple[_Uuid4, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_values),
]
_OptionalUuidTuple32 = Annotated[
    tuple[_Uuid4, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_values),
]

# Strict mode rejects bool and float for these integer budgets: a budget is a
# structural output limit, never a token, cost, or latency quota.
_MaxCharactersBudget = Annotated[int, Field(strict=True, ge=1, le=16000)]
_MaxSectionsBudget = Annotated[int, Field(strict=True, ge=1, le=8)]
_MaxClaimsBudget = Annotated[int, Field(strict=True, ge=0, le=32)]
_MaxCaveatsBudget = Annotated[int, Field(strict=True, ge=0, le=32)]
_MaxCitationsBudget = Annotated[int, Field(strict=True, ge=0, le=64)]


class AnswerToneConstraints(ContractModel):
    """Controlled linguistic presentation constraints for one response."""

    # Tone codes never carry free-form instructions or persona text: they are
    # open, controlled catalog codes resolved by a future presentation layer.
    response_locale: _LocaleTag
    tone_codes: _ToneCodes


class AnswerLengthBudget(ContractModel):
    """Hard structural output budget for one response."""

    max_characters: _MaxCharactersBudget
    max_sections: _MaxSectionsBudget
    max_claims: _MaxClaimsBudget
    max_caveats: _MaxCaveatsBudget
    max_citations: _MaxCitationsBudget


class AnswerSectionItemRef(ContractModel):
    """Reference to one planned claim or required caveat within a section."""

    item_kind: AnswerSectionItemKind
    item_id: _CanonicalCode


def _require_unique_section_items(
    value: tuple[AnswerSectionItemRef, ...],
) -> tuple[AnswerSectionItemRef, ...]:
    keys = [(item.item_kind, item.item_id) for item in value]
    if len(set(keys)) != len(keys):
        raise ValueError("section items must be unique by item kind and item identifier")
    return value


_SectionItems = Annotated[
    tuple[AnswerSectionItemRef, ...],
    Field(min_length=1, max_length=32),
    AfterValidator(_require_unique_section_items),
]


class AnswerSection(ContractModel):
    """One ordered presentation section referencing claims and caveats."""

    # No title, heading, or body text is stored: a future presentation catalog
    # maps section_type to localized rendering behavior.
    section_id: _CanonicalCode
    section_type: _CanonicalCode
    items: _SectionItems


class AnswerClaimPlan(ContractModel):
    """Planned claim shape that must exactly match an allowed evidence claim."""

    # No prose, value, or confidence is stored: the Generator realizes natural
    # language from this shape, and trusted validation binds it to the
    # referenced EvidenceBundle's allowed claims exactly.
    claim_id: _CanonicalCode
    claim_code: _CanonicalCode
    claim_type: _CanonicalCode
    subject: EvidenceSubjectRef
    supporting_fact_ids: _RequiredCodes16
    evidence_ids: _UuidTuple1To32


class AnswerCaveat(ContractModel):
    """Required semantic caveat represented by controlled codes only."""

    caveat_id: _CanonicalCode
    caveat_code: _CanonicalCode
    related_claim_ids: _OptionalCodes16 = ()
    evidence_ids: _OptionalUuidTuple32 = ()
    reason_codes: _RequiredCodes16


class CitationSlot(ContractModel):
    """Authorization to place a citation, without any rendered citation."""

    # Actual source labels and locators are compiled later by trusted
    # server-side code; this slot only authorizes placement and evidence.
    slot_id: _CanonicalCode
    target_kind: CitationTargetKind
    target_id: _CanonicalCode
    evidence_ids: _UuidTuple1To32
    placement: CitationPlacement


def _require_unique_sections(value: tuple[AnswerSection, ...]) -> tuple[AnswerSection, ...]:
    identifiers = [section.section_id for section in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("section identifiers must be unique")
    return value


def _require_unique_claims(value: tuple[AnswerClaimPlan, ...]) -> tuple[AnswerClaimPlan, ...]:
    identifiers = [claim.claim_id for claim in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("claim identifiers must be unique")
    return value


def _require_unique_caveats(value: tuple[AnswerCaveat, ...]) -> tuple[AnswerCaveat, ...]:
    identifiers = [caveat.caveat_id for caveat in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("caveat identifiers must be unique")
    return value


def _require_unique_slots(value: tuple[CitationSlot, ...]) -> tuple[CitationSlot, ...]:
    identifiers = [slot.slot_id for slot in value]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("citation slot identifiers must be unique")
    semantic = [
        (slot.target_kind, slot.target_id, slot.evidence_ids, slot.placement) for slot in value
    ]
    if len(set(semantic)) != len(semantic):
        raise ValueError("duplicate semantic citation slots are not permitted")
    return value


_Sections = Annotated[
    tuple[AnswerSection, ...],
    Field(min_length=1, max_length=8),
    AfterValidator(_require_unique_sections),
]
_Claims = Annotated[
    tuple[AnswerClaimPlan, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_claims),
]
_Caveats = Annotated[
    tuple[AnswerCaveat, ...],
    Field(max_length=32),
    AfterValidator(_require_unique_caveats),
]
_CitationSlots = Annotated[
    tuple[CitationSlot, ...],
    Field(max_length=64),
    AfterValidator(_require_unique_slots),
]


class AnswerPlan(ContractModel):
    """Deterministic, validated semantic plan for exactly one response."""

    model_config = ConfigDict(
        json_schema_extra={
            "$schema": JSON_SCHEMA_DIALECT,
            "$id": ANSWER_PLAN_SCHEMA_ID,
        }
    )

    schema_version: Literal["1.0.0"] = ANSWER_PLAN_SCHEMA_VERSION
    answer_plan_id: _Uuid4
    request_id: _Uuid4
    evidence_bundle_id: _Uuid4
    route_decision_id: _Uuid4
    plan_id: _Uuid4
    authorization_decision_id: _Uuid4
    runtime_snapshot_id: _Uuid4
    correlation_id: _Uuid4
    built_at: UtcDateTime
    decision: EvidenceDecision
    answer_type: AnswerType
    sections: _Sections
    claims: _Claims = ()
    caveats: _Caveats = ()
    citation_slots: _CitationSlots = ()
    tone_constraints: AnswerToneConstraints
    prohibited_claim_codes: _OptionalCodes64 = ()
    prohibited_content_codes: _RequiredCodes32
    decision_reason_codes: _RequiredCodes16
    length_budget: AnswerLengthBudget
    answer_plan_builder_version: SchemaVersion

    @model_validator(mode="after")
    def _require_consistent_plan(self) -> Self:
        self._require_valid_sections()
        self._require_valid_claims_and_prohibitions()
        self._require_valid_citations()
        self._require_within_budget()
        self._require_consistent_decision()
        return self

    def _require_valid_sections(self) -> None:
        # The section structure is an exact presentation partition: every
        # planned claim and caveat appears in exactly one section, never zero
        # and never more than one.
        claim_ids = {claim.claim_id for claim in self.claims}
        caveat_ids = {caveat.caveat_id for caveat in self.caveats}
        seen_claims: set[str] = set()
        seen_caveats: set[str] = set()
        for section in self.sections:
            for item in section.items:
                if item.item_kind == "claim":
                    if item.item_id not in claim_ids:
                        raise ValueError("a claim section item must reference a planned claim")
                    if item.item_id in seen_claims:
                        raise ValueError("a claim must not appear in multiple sections")
                    seen_claims.add(item.item_id)
                else:
                    if item.item_id not in caveat_ids:
                        raise ValueError("a caveat section item must reference a planned caveat")
                    if item.item_id in seen_caveats:
                        raise ValueError("a caveat must not appear in multiple sections")
                    seen_caveats.add(item.item_id)
        if seen_claims != claim_ids:
            raise ValueError("every planned claim must appear exactly once across sections")
        if seen_caveats != caveat_ids:
            raise ValueError("every planned caveat must appear exactly once across sections")

    def _require_valid_claims_and_prohibitions(self) -> None:
        claim_codes = [claim.claim_code for claim in self.claims]
        if len(set(claim_codes)) != len(claim_codes):
            raise ValueError("planned claim codes must be unique")
        prohibited = set(self.prohibited_claim_codes)
        if set(claim_codes).intersection(prohibited):
            raise ValueError("a planned claim code must not be prohibited")
        claim_ids = {claim.claim_id for claim in self.claims}
        for caveat in self.caveats:
            unknown = set(caveat.related_claim_ids).difference(claim_ids)
            if unknown:
                raise ValueError("a caveat's related claim ids must exist in claims")

    def _require_valid_citations(self) -> None:
        claims_by_id = {claim.claim_id: claim for claim in self.claims}
        caveats_by_id = {caveat.caveat_id: caveat for caveat in self.caveats}
        cited_claims: set[str] = set()
        for slot in self.citation_slots:
            if slot.target_kind == "claim":
                claim = claims_by_id.get(slot.target_id)
                if claim is None:
                    raise ValueError("a claim citation slot must target a planned claim")
                unknown = set(slot.evidence_ids).difference(claim.evidence_ids)
                if unknown:
                    raise ValueError("claim citation evidence must belong to the targeted claim")
                cited_claims.add(slot.target_id)
            else:
                caveat = caveats_by_id.get(slot.target_id)
                if caveat is None:
                    raise ValueError("a caveat citation slot must target a planned caveat")
                if not caveat.evidence_ids:
                    raise ValueError("a caveat citation slot requires the caveat to carry evidence")
                unknown = set(slot.evidence_ids).difference(caveat.evidence_ids)
                if unknown:
                    raise ValueError("caveat citation evidence must belong to the targeted caveat")
        missing = {claim.claim_id for claim in self.claims}.difference(cited_claims)
        if missing:
            raise ValueError("every planned claim requires at least one citation slot")

    def _require_within_budget(self) -> None:
        budget = self.length_budget
        if len(self.sections) > budget.max_sections:
            raise ValueError("section count must not exceed the length budget")
        if len(self.claims) > budget.max_claims:
            raise ValueError("claim count must not exceed the length budget")
        if len(self.caveats) > budget.max_caveats:
            raise ValueError("caveat count must not exceed the length budget")
        if len(self.citation_slots) > budget.max_citations:
            raise ValueError("citation count must not exceed the length budget")

    def _require_consistent_decision(self) -> None:
        if self.decision == "answer":
            self._require_answer_shape()
        elif self.decision == "partial_answer":
            self._require_partial_shape()
        elif self.decision == "clarify":
            self._require_clarify_shape()
        else:
            self._require_abstain_shape()

    def _require_answer_shape(self) -> None:
        if self.answer_type in ("clarification", "abstention"):
            raise ValueError("an answer decision must not use a clarification or abstention type")
        if not self.claims:
            raise ValueError("an answer decision requires at least one claim")

    def _require_partial_shape(self) -> None:
        if self.answer_type in ("clarification", "abstention"):
            raise ValueError("a partial answer must not use a clarification or abstention type")
        if not self.claims:
            raise ValueError("a partial answer requires at least one claim")
        if not self.caveats:
            raise ValueError("a partial answer requires at least one caveat")

    def _require_clarify_shape(self) -> None:
        if self.answer_type != "clarification":
            raise ValueError("a clarify decision requires the clarification answer type")
        if self.claims:
            raise ValueError("a clarify decision must not carry claims")
        if not self.caveats:
            raise ValueError("a clarify decision requires at least one caveat")
        for slot in self.citation_slots:
            if slot.target_kind != "caveat":
                raise ValueError("a clarify decision may only cite caveats")

    def _require_abstain_shape(self) -> None:
        if self.answer_type != "abstention":
            raise ValueError("an abstain decision requires the abstention answer type")
        if self.claims:
            raise ValueError("an abstain decision must not carry claims")
        if not self.caveats:
            raise ValueError("an abstain decision requires at least one caveat")
        for slot in self.citation_slots:
            if slot.target_kind != "caveat":
                raise ValueError("an abstain decision may only cite caveats")
