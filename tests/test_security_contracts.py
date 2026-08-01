"""Tests for the security principal and authorization decision contracts 1.0.0."""

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import ai_assistant.contracts as contracts
from ai_assistant.contracts import (
    AuthorizationDecision,
    AuthorizationResourceRef,
    SecurityPrincipalContext,
)

TEHRAN = timezone(timedelta(hours=3, minutes=30))
CONTEXT_ID = "11111111-1111-4111-8111-111111111111"
PRINCIPAL_ID = "22222222-2222-4222-8222-222222222222"
DEPLOYMENT_ID = "33333333-3333-4333-8333-333333333333"
SESSION_ID = "44444444-4444-4444-8444-444444444444"
DECISION_ID = "55555555-5555-4555-8555-555555555555"
REQUEST_ID = "66666666-6666-4666-8666-666666666666"
UUID1_VALUE = "11111111-1111-1111-8111-111111111111"
AUTHENTICATED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN)
EVALUATED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN)
EXPECTED_UTC = datetime(2026, 1, 1, 8, 30, tzinfo=UTC)
INVALID_CODES = (
    "Finance Admin",
    "UPPERCASE",
    " leading",
    "contains/slash",
    "contains@sign",
    "1leading-digit",
    "",
    "a" * 65,
)
PRINCIPAL_COLLECTIONS = ("roles", "groups", "allowed_scopes", "data_classification_allowances")
COLLECTION_MAXIMUMS = {
    "roles": 64,
    "groups": 256,
    "allowed_scopes": 128,
    "data_classification_allowances": 32,
}
FORBIDDEN_PRINCIPAL_FIELDS = (
    "password",
    "token",
    "access_token",
    "cookie",
    "raw_claims",
    "headers",
    "email",
    "display_name",
    "permissions",
    "effect",
    "normalized_query",
    "provider_payload",
)
FORBIDDEN_DECISION_FIELDS = (
    "roles",
    "groups",
    "scopes",
    "policy_expression",
    "sql",
    "filter",
    "model_rationale",
    "access_token",
    "provider_response",
)
FORBIDDEN_RESOURCE_FIELDS = (
    "url",
    "filesystem_path",
    "sql",
    "filter_expression",
    "credentials",
)
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
PRINCIPAL_ARTIFACT = SCHEMA_DIR / "security-principal-context" / "1.0.0.schema.json"
DECISION_ARTIFACT = SCHEMA_DIR / "authorization-decision" / "1.0.0.schema.json"


def principal_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "context_id": CONTEXT_ID,
        "principal_id": PRINCIPAL_ID,
        "principal_type": "user",
        "deployment_id": DEPLOYMENT_ID,
        "issuer": "internal.identity.adapter",
        "authenticated_at": "2026-01-01T12:00:00+03:30",
        "authentication_methods": ["password", "mfa"],
        "assurance_level": "aal2",
    }
    values.update(overrides)
    return values


def resource_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "resource_type": "document",
        "resource_id": "doc-0001",
    }
    values.update(overrides)
    return values


def decision_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "decision_id": DECISION_ID,
        "request_id": REQUEST_ID,
        "security_context_id": CONTEXT_ID,
        "action": "document:read",
        "resource": resource_payload(classification="confidential"),
        "effect": "allow",
        "reason_codes": ["policy.allowed"],
        "policy_version": "1.2.3",
        "evaluated_at": "2026-01-01T12:00:00+03:30",
    }
    values.update(overrides)
    return values


def codes(count: int) -> list[str]:
    return [f"code.{index}" for index in range(count)]


def test_principal_schema_version_defaults_to_the_approved_value() -> None:
    assert SecurityPrincipalContext(**principal_payload()).schema_version == "1.0.0"


def test_principal_rejects_another_schema_version() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(schema_version="2.0.0"))


def test_valid_user_principal_is_constructed() -> None:
    context = SecurityPrincipalContext(
        **principal_payload(
            session_id=SESSION_ID,
            roles=["finance.reader"],
            groups=["finance"],
            allowed_scopes=["document:read"],
            data_classification_allowances=["confidential"],
        )
    )
    assert context.principal_type == "user"
    assert context.session_id == UUID(SESSION_ID)
    assert context.roles == ("finance.reader",)


def test_valid_service_principal_without_session_is_constructed() -> None:
    context = SecurityPrincipalContext(
        **principal_payload(principal_type="service", authentication_methods=["client.certificate"])
    )
    assert context.principal_type == "service"
    assert context.session_id is None


@pytest.mark.parametrize("field", ["context_id", "principal_id", "deployment_id", "session_id"])
def test_principal_identifiers_require_uuid_version_4(field: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: UUID1_VALUE}))


def test_naive_authenticated_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(authenticated_at=datetime(2026, 1, 1, 12)))


def test_non_utc_authenticated_at_is_normalized() -> None:
    context = SecurityPrincipalContext(**principal_payload(authenticated_at=AUTHENTICATED_AT))
    assert context.authenticated_at == EXPECTED_UTC
    assert context.authenticated_at.utcoffset() == timedelta(0)


def test_at_least_one_authentication_method_is_required() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(authentication_methods=[]))


def test_more_than_eight_authentication_methods_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(authentication_methods=codes(9)))


def test_duplicate_authentication_methods_are_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(authentication_methods=["mfa", "mfa"]))


def test_missing_collections_become_empty_tuples() -> None:
    context = SecurityPrincipalContext(**principal_payload())
    assert context.roles == ()
    assert context.groups == ()
    assert context.allowed_scopes == ()
    assert context.data_classification_allowances == ()


@pytest.mark.parametrize("field", PRINCIPAL_COLLECTIONS)
def test_explicit_null_collections_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: None}))


@pytest.mark.parametrize("field", PRINCIPAL_COLLECTIONS)
def test_duplicate_collection_values_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: ["duplicate", "duplicate"]}))


@pytest.mark.parametrize(("field", "maximum"), sorted(COLLECTION_MAXIMUMS.items()))
def test_collection_maximums_are_enforced(field: str, maximum: int) -> None:
    accepted = SecurityPrincipalContext(**principal_payload(**{field: codes(maximum)}))
    assert len(getattr(accepted, field)) == maximum
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: codes(maximum + 1)}))


def test_principal_tuple_order_is_preserved() -> None:
    ordered = ["gamma", "alpha", "beta"]
    context = SecurityPrincipalContext(**principal_payload(roles=ordered))
    assert list(context.roles) == ordered


def test_issuer_is_preserved_exactly() -> None:
    issuer = "  Internal Identity Provider \u06af\u0632\u0627\u0631\u0634  "
    assert SecurityPrincipalContext(**principal_payload(issuer=issuer)).issuer == issuer


def test_whitespace_only_issuer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(issuer="   \t "))


def test_issuer_with_nul_character_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(issuer="issuer\x00"))


def test_oversized_issuer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(issuer="a" * 513))


@pytest.mark.parametrize("code", INVALID_CODES)
def test_invalid_canonical_codes_are_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(assurance_level=code))


@pytest.mark.parametrize(
    "code",
    ["user", "service", "password", "mfa", "finance.reader", "document:read", "confidential"],
)
def test_valid_canonical_codes_are_accepted(code: str) -> None:
    assert SecurityPrincipalContext(**principal_payload(roles=[code])).roles == (code,)


@pytest.mark.parametrize("field", FORBIDDEN_PRINCIPAL_FIELDS)
def test_principal_rejects_sensitive_unknown_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: "injected"}))


def test_principal_is_immutable() -> None:
    context = SecurityPrincipalContext(**principal_payload(roles=["finance.reader"]))
    assert isinstance(context.roles, tuple)
    with pytest.raises(ValidationError):
        context.assurance_level = "aal3"


def test_principal_json_round_trip() -> None:
    context = SecurityPrincipalContext(**principal_payload(session_id=SESSION_ID, roles=["a.b"]))
    assert SecurityPrincipalContext.model_validate_json(context.model_dump_json()) == context


def test_principal_schema_identity_and_closure() -> None:
    schema = SecurityPrincipalContext.model_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ai-assistant:contracts:security-principal-context:1.0.0"
    assert schema["additionalProperties"] is False


def test_committed_principal_schema_matches_the_model() -> None:
    committed = json.loads(PRINCIPAL_ARTIFACT.read_text(encoding="utf-8"))
    assert committed == SecurityPrincipalContext.model_json_schema()


def test_valid_resource_reference() -> None:
    resource = AuthorizationResourceRef(**resource_payload(classification="confidential"))
    assert resource.resource_type == "document"
    assert resource.classification == "confidential"


def test_resource_classification_may_be_absent() -> None:
    assert AuthorizationResourceRef(**resource_payload()).classification is None


def test_whitespace_only_resource_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationResourceRef(**resource_payload(resource_id="   "))


def test_resource_id_with_nul_character_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationResourceRef(**resource_payload(resource_id="doc\x00"))


def test_resource_id_is_preserved_exactly() -> None:
    resource_id = "  Doc/2026 \u06f1\u06f2  "
    assert AuthorizationResourceRef(**resource_payload(resource_id=resource_id)).resource_id == (
        resource_id
    )


@pytest.mark.parametrize("field", FORBIDDEN_RESOURCE_FIELDS)
def test_resource_rejects_location_and_query_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationResourceRef(**resource_payload(**{field: "value"}))


def test_resource_schema_is_closed() -> None:
    assert AuthorizationResourceRef.model_json_schema()["additionalProperties"] is False


def test_decision_schema_version_defaults_to_the_approved_value() -> None:
    assert AuthorizationDecision(**decision_payload()).schema_version == "1.0.0"


def test_valid_allow_decision() -> None:
    decision = AuthorizationDecision(**decision_payload(obligations=["audit.write"]))
    assert decision.effect == "allow"
    assert decision.obligations == ("audit.write",)
    assert decision.expires_at is None


def test_valid_deny_decision() -> None:
    decision = AuthorizationDecision(
        **decision_payload(effect="deny", reason_codes=["policy.denied"])
    )
    assert decision.effect == "deny"
    assert decision.reason_codes == ("policy.denied",)


@pytest.mark.parametrize("field", ["decision_id", "request_id", "security_context_id"])
def test_decision_identifiers_require_uuid_version_4(field: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(**{field: UUID1_VALUE}))


def test_unsupported_effect_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(effect="maybe"))


@pytest.mark.parametrize("code", INVALID_CODES)
def test_invalid_action_codes_are_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(action=code))


def test_empty_reason_codes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(reason_codes=[]))


def test_missing_reason_codes_are_rejected() -> None:
    payload = decision_payload()
    del payload["reason_codes"]
    with pytest.raises(ValidationError):
        AuthorizationDecision(**payload)


@pytest.mark.parametrize("field", ["reason_codes", "obligations", "constraint_references"])
def test_duplicate_decision_collection_values_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(**{field: ["duplicate", "duplicate"]}))


@pytest.mark.parametrize("field", ["reason_codes", "obligations", "constraint_references"])
def test_decision_collection_maximums_are_enforced(field: str) -> None:
    accepted = AuthorizationDecision(**decision_payload(**{field: codes(16)}))
    assert len(getattr(accepted, field)) == 16
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(**{field: codes(17)}))


def test_decision_tuple_order_is_preserved() -> None:
    ordered = ["gamma", "alpha", "beta"]
    decision = AuthorizationDecision(**decision_payload(reason_codes=ordered))
    assert list(decision.reason_codes) == ordered


@pytest.mark.parametrize("version", ["1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0", "1.0.0+build"])
def test_invalid_policy_versions_are_rejected(version: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(policy_version=version))


def test_naive_evaluated_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(evaluated_at=datetime(2026, 1, 1, 12)))


def test_non_utc_evaluated_at_is_normalized() -> None:
    decision = AuthorizationDecision(**decision_payload(evaluated_at=EVALUATED_AT))
    assert decision.evaluated_at == EXPECTED_UTC
    assert decision.evaluated_at.utcoffset() == timedelta(0)


def test_non_utc_expires_at_is_normalized() -> None:
    decision = AuthorizationDecision(
        **decision_payload(expires_at=EVALUATED_AT + timedelta(minutes=5))
    )
    assert decision.expires_at == EXPECTED_UTC + timedelta(minutes=5)
    assert decision.expires_at is not None
    assert decision.expires_at.utcoffset() == timedelta(0)


def test_expiry_equal_to_evaluation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(expires_at="2026-01-01T12:00:00+03:30"))


def test_expiry_before_evaluation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(expires_at="2026-01-01T11:00:00+03:30"))


def test_expiry_after_evaluation_is_accepted() -> None:
    decision = AuthorizationDecision(**decision_payload(expires_at="2026-01-01T13:00:00+03:30"))
    assert decision.expires_at == EXPECTED_UTC + timedelta(hours=1)


@pytest.mark.parametrize("field", FORBIDDEN_DECISION_FIELDS)
def test_decision_rejects_sensitive_unknown_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        AuthorizationDecision(**decision_payload(**{field: "injected"}))


def test_decision_is_immutable() -> None:
    decision = AuthorizationDecision(**decision_payload())
    assert isinstance(decision.reason_codes, tuple)
    with pytest.raises(ValidationError):
        decision.effect = "deny"


def test_decision_json_round_trip() -> None:
    decision = AuthorizationDecision(
        **decision_payload(
            obligations=["audit.write"],
            constraint_references=["policy.constraint.1"],
            expires_at="2026-01-01T13:00:00+03:30",
        )
    )
    assert AuthorizationDecision.model_validate_json(decision.model_dump_json()) == decision


def test_decision_schema_identity_and_closure() -> None:
    schema = AuthorizationDecision.model_json_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == "urn:ai-assistant:contracts:authorization-decision:1.0.0"
    assert schema["additionalProperties"] is False


def test_nested_resource_schema_is_closed_inside_the_decision_schema() -> None:
    schema = AuthorizationDecision.model_json_schema()
    assert schema["$defs"]["AuthorizationResourceRef"]["additionalProperties"] is False


def test_committed_decision_schema_matches_the_model() -> None:
    committed = json.loads(DECISION_ARTIFACT.read_text(encoding="utf-8"))
    assert committed == AuthorizationDecision.model_json_schema()


def test_public_exports_are_correct() -> None:
    assert contracts.__all__ == [
        "SCHEMA_VERSION_PATTERN",
        "AttachmentRef",
        "AuthorizationDecision",
        "AuthorizationResourceRef",
        "ContractModel",
        "SchemaVersion",
        "SecurityPrincipalContext",
        "TurnInput",
        "UtcDateTime",
    ]


def test_generated_schemas_contain_no_forbidden_fields() -> None:
    principal_schema = json.dumps(SecurityPrincipalContext.model_json_schema())
    decision_schema = json.dumps(AuthorizationDecision.model_json_schema())
    assert all(f'"{field}"' not in principal_schema for field in FORBIDDEN_PRINCIPAL_FIELDS)
    assert all(f'"{field}"' not in decision_schema for field in FORBIDDEN_DECISION_FIELDS)


@given(
    st.lists(
        st.from_regex(r"\Aa[a-z0-9._:-]{0,8}\Z"),
        min_size=1,
        max_size=8,
        unique=True,
    )
)
def test_property_unique_code_tuples_preserve_order(values: list[str]) -> None:
    context = SecurityPrincipalContext(**principal_payload(authentication_methods=values))
    assert list(context.authentication_methods) == values


@given(st.sampled_from(PRINCIPAL_COLLECTIONS), st.from_regex(r"\Aa[a-z0-9._:-]{0,8}\Z"))
def test_property_duplicate_collection_values_are_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: [value, value]}))


@given(st.sampled_from(FORBIDDEN_PRINCIPAL_FIELDS + FORBIDDEN_DECISION_FIELDS))
def test_property_unknown_security_fields_are_rejected(field: str) -> None:
    with pytest.raises(ValidationError):
        SecurityPrincipalContext(**principal_payload(**{field: "injected"}))


@given(st.integers(min_value=1, max_value=86400))
def test_property_expiry_after_evaluation_is_accepted(seconds: int) -> None:
    expires_at = EVALUATED_AT + timedelta(seconds=seconds)
    decision = AuthorizationDecision(**decision_payload(expires_at=expires_at))
    assert decision.expires_at == EXPECTED_UTC + timedelta(seconds=seconds)
