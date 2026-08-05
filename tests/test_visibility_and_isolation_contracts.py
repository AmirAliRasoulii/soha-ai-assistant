"""Contract tests for the visibility policy and index isolation families (CP-001).

Every test names the architecture rule it proves: `ADR-CP-002` `V-*`/`C-*` for
visibility policy definitions and `ADR-CP-003` `T-*`/`P-*` for isolation
profiles. Structural absences are asserted explicitly, because an invariant that
is only unrepresentable today becomes representable the moment somebody adds a
field.
"""

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from ai_assistant import contracts as contracts_package
from ai_assistant.contracts.visibility_isolation import (
    INDEX_ISOLATION_PROFILE_SCHEMA_ID,
    MAX_ALLOW_CLAUSES,
    MAX_CLAUSE_PREDICATES,
    VISIBILITY_POLICY_DEFINITION_SCHEMA_ID,
    IndexIsolationProfile,
    VisibilityAllowClause,
    VisibilityPolicyDefinition,
    VisibilityPredicate,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"

ORGANIZATION_ID = UUID("11111111-1111-4111-8111-111111111111")
OTHER_ORGANIZATION_ID = UUID("22222222-2222-4222-8222-222222222222")
NODE_ID = UUID("33333333-3333-4333-8333-333333333333")
OTHER_NODE_ID = UUID("44444444-4444-4444-8444-444444444444")
PRINCIPAL_ID = UUID("66666666-6666-4666-8666-666666666666")
OTHER_PRINCIPAL_ID = UUID("77777777-7777-4777-8777-777777777777")

CREATED_AT = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
EARLIER = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
POLICY_DIGEST = "sha256:" + "a" * 64


def node_ref(node_id: UUID = NODE_ID, organization_id: UUID = ORGANIZATION_ID) -> dict[str, UUID]:
    return {"organization_id": organization_id, "node_id": node_id}


def staff_clause() -> VisibilityAllowClause:
    """The `computer-education-staff` example of `ADR-CP-002`."""
    return VisibilityAllowClause(
        predicates=(
            VisibilityPredicate(kind="exact_node_member", node_refs=(node_ref(),)),
            VisibilityPredicate(kind="scoped_role", role_code="education-staff"),
        )
    )


def policy_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "visibility_policy_id": "computer-education-staff",
        "policy_revision": "3",
        "policy_digest": POLICY_DIGEST,
        "organization_id": ORGANIZATION_ID,
        "display_name": "Computer education staff",
        "status": "active",
        "clauses": (staff_clause(),),
        "created_at": CREATED_AT,
        "approved_by_principal_id": PRINCIPAL_ID,
        "approved_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


def profile_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "isolation_profile_id": "university-shared",
        "profile_revision": "5",
        "organization_id": ORGANIZATION_ID,
        "logical_tenant_key": "tenant-university",
        "physical_isolation_tier": "shared_logical_partition",
        "effective_at": CREATED_AT,
        "recorded_at": CREATED_AT,
    }
    payload.update(overrides)
    return payload


class VisibilityPredicateTests(unittest.TestCase):
    def test_primitive_vocabulary_is_closed(self) -> None:
        # V-1 and V-3: administrators compose from Layer 1 and cannot introduce
        # a new primitive through data.
        with self.assertRaises(ValidationError):
            VisibilityPredicate(kind="custom_expression")

    def test_supported_primitives_construct(self) -> None:
        supported = (
            {"kind": "organization_member"},
            {"kind": "exact_node_member", "node_refs": (node_ref(),)},
            {"kind": "subtree_member", "node_refs": (node_ref(),)},
            {"kind": "scoped_role", "role_code": "education-staff"},
            {"kind": "trusted_group", "trusted_group_code": "clinical-staff"},
            {"kind": "explicit_principal", "principal_ids": (PRINCIPAL_ID,)},
            {"kind": "classification_condition", "classification_code": "public"},
        )
        for payload in supported:
            with self.subTest(kind=payload["kind"]):
                predicate = VisibilityPredicate(**payload)
                self.assertEqual(predicate.kind, payload["kind"])

    def test_operands_must_match_the_primitive(self) -> None:
        rejected = (
            ("node kind without nodes", {"kind": "exact_node_member"}),
            (
                "role kind carrying nodes",
                {"kind": "scoped_role", "role_code": "r", "node_refs": (node_ref(),)},
            ),
            ("role kind without role", {"kind": "scoped_role"}),
            ("group kind without group", {"kind": "trusted_group"}),
            ("principal kind without principal", {"kind": "explicit_principal"}),
            ("classification kind without code", {"kind": "classification_condition"}),
            (
                "organization member carrying a classification",
                {"kind": "organization_member", "classification_code": "public"},
            ),
            (
                "organization member carrying a group",
                {"kind": "organization_member", "trusted_group_code": "g"},
            ),
            (
                "organization member carrying principals",
                {"kind": "organization_member", "principal_ids": (PRINCIPAL_ID,)},
            ),
        )
        for label, payload in rejected:
            with self.subTest(case=label), self.assertRaises(ValidationError):
                VisibilityPredicate(**payload)

    def test_subtree_predicate_names_exactly_one_root(self) -> None:
        # Expanding a subtree is CP-002 evaluation; the contract only pins the root.
        with self.assertRaises(ValidationError):
            VisibilityPredicate(
                kind="subtree_member",
                node_refs=(node_ref(), node_ref(OTHER_NODE_ID)),
            )

    def test_repeated_operands_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityPredicate(kind="exact_node_member", node_refs=(node_ref(), node_ref()))
        with self.assertRaises(ValidationError):
            VisibilityPredicate(
                kind="explicit_principal",
                principal_ids=(PRINCIPAL_ID, PRINCIPAL_ID),
            )

    def test_no_expression_or_deny_field_exists(self) -> None:
        # C-3: there is no scripting, expression language, or administrator
        # authored deny language in this baseline.
        field_names = set(VisibilityPredicate.model_fields)
        forbidden = {
            "expression",
            "predicate_expression",
            "script",
            "deny",
            "deny_clauses",
            "negate",
        }
        self.assertEqual(field_names & forbidden, set())


class VisibilityAllowClauseTests(unittest.TestCase):
    def test_a_clause_requires_at_least_one_predicate(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityAllowClause(predicates=())

    def test_a_clause_cannot_repeat_one_primitive_kind(self) -> None:
        # C-1: predicates inside a clause are conjunctive, so two occurrences of
        # one kind would need an implicit resolution rule.
        with self.assertRaises(ValidationError):
            VisibilityAllowClause(
                predicates=(
                    VisibilityPredicate(kind="scoped_role", role_code="a"),
                    VisibilityPredicate(kind="scoped_role", role_code="b"),
                )
            )

    def test_clause_predicates_are_bounded(self) -> None:
        self.assertEqual(MAX_CLAUSE_PREDICATES, 8)
        # Only seven primitive kinds exist and kinds are unique inside a clause,
        # so the ceiling can never be reached by valid data.
        self.assertGreater(MAX_CLAUSE_PREDICATES, 7)


class VisibilityPolicyDefinitionTests(unittest.TestCase):
    def test_valid_definition_constructs(self) -> None:
        definition = VisibilityPolicyDefinition(**policy_payload(previous_policy_revision="2"))
        self.assertEqual(definition.schema_version, "1.0.0")
        self.assertEqual(len(definition.clauses), 1)

    def test_definition_is_an_or_of_clauses(self) -> None:
        definition = VisibilityPolicyDefinition(
            **policy_payload(
                clauses=(
                    staff_clause(),
                    VisibilityAllowClause(
                        predicates=(
                            VisibilityPredicate(kind="subtree_member", node_refs=(node_ref(),)),
                        )
                    ),
                )
            )
        )
        self.assertEqual(len(definition.clauses), 2)

    def test_at_least_one_clause_is_required(self) -> None:
        # V-7: nothing in this contract may express a permissive default.
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(**policy_payload(clauses=()))

    def test_clauses_are_bounded(self) -> None:
        self.assertEqual(MAX_ALLOW_CLAUSES, 16)
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(
                **policy_payload(
                    clauses=tuple(staff_clause() for _ in range(MAX_ALLOW_CLAUSES + 1))
                )
            )

    def test_revision_ref_is_the_pinned_binding(self) -> None:
        # V-4: a source binds an exact immutable revision, never a policy
        # identity that follows whichever revision is active.
        definition = VisibilityPolicyDefinition(**policy_payload())
        reference = definition.revision_ref
        self.assertEqual(reference.visibility_policy_id, definition.visibility_policy_id)
        self.assertEqual(reference.policy_revision, definition.policy_revision)
        self.assertEqual(reference.policy_digest, definition.policy_digest)

    def test_approved_and_active_definitions_require_an_approval(self) -> None:
        for status in ("approved", "active", "retired"):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                VisibilityPolicyDefinition(
                    **policy_payload(
                        status=status,
                        approved_by_principal_id=None,
                        approved_at=None,
                    )
                )

    def test_a_draft_definition_must_not_record_an_approval(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(**policy_payload(status="draft"))

    def test_a_draft_definition_without_approval_constructs(self) -> None:
        definition = VisibilityPolicyDefinition(
            **policy_payload(status="draft", approved_by_principal_id=None, approved_at=None)
        )
        self.assertEqual(definition.status, "draft")

    def test_approval_must_not_precede_creation(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(**policy_payload(approved_at=EARLIER))

    def test_a_revision_must_differ_from_the_one_it_replaces(self) -> None:
        # V-5: activated revisions are never edited in place.
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(**policy_payload(previous_policy_revision="3"))

    def test_predicate_nodes_must_belong_to_the_policy_organization(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(
                **policy_payload(organization_id=OTHER_ORGANIZATION_ID),
            )

    def test_a_platform_wide_definition_needs_no_organization(self) -> None:
        # The `all-public-guests` example: anonymous public and a public class.
        definition = VisibilityPolicyDefinition(
            **policy_payload(
                visibility_policy_id="all-public-guests",
                organization_id=None,
                display_name="All public guests",
                clauses=(
                    VisibilityAllowClause(
                        predicates=(
                            VisibilityPredicate(
                                kind="classification_condition",
                                classification_code="public",
                            ),
                        )
                    ),
                ),
            )
        )
        self.assertIsNone(definition.organization_id)

    def test_definition_is_immutable(self) -> None:
        definition = VisibilityPolicyDefinition(**policy_payload())
        with self.assertRaises(ValidationError):
            definition.status = "draft"  # type: ignore[misc]

    def test_unknown_fields_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            VisibilityPolicyDefinition(**policy_payload(deny_clauses=()))

    def test_serialization_round_trip(self) -> None:
        definition = VisibilityPolicyDefinition(**policy_payload())
        restored = VisibilityPolicyDefinition.model_validate_json(definition.model_dump_json())
        self.assertEqual(restored, definition)

    def test_no_permission_or_deny_surface_exists(self) -> None:
        field_names = set(VisibilityPolicyDefinition.model_fields)
        forbidden = {
            "permissions",
            "permission_refs",
            "deny_clauses",
            "expression",
            "script",
            "follow_active_revision",
            "allow_all",
        }
        self.assertEqual(field_names & forbidden, set())


class IndexIsolationProfileTests(unittest.TestCase):
    def test_default_shared_tier_constructs(self) -> None:
        profile = IndexIsolationProfile(**profile_payload())
        self.assertEqual(profile.physical_isolation_tier, "shared_logical_partition")
        self.assertFalse(profile.is_promotion)

    def test_tier_vocabulary_is_closed(self) -> None:
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(**profile_payload(physical_isolation_tier="dedicated_planet"))

    def test_promotion_requires_a_reason_code_and_evidence(self) -> None:
        # P-2 and P-4: promotion is evidence-based and an informal sensitivity
        # label is insufficient.
        for tier in ("dedicated_shard", "dedicated_collection", "dedicated_deployment"):
            with self.subTest(tier=tier), self.assertRaises(ValidationError):
                IndexIsolationProfile(**profile_payload(physical_isolation_tier=tier))

    def test_recorded_promotion_constructs_and_is_detected(self) -> None:
        profile = IndexIsolationProfile(
            **profile_payload(
                physical_isolation_tier="dedicated_collection",
                promotion_reason="corpus-size",
                promotion_evidence_ref="promotion-evidence-1",
                previous_isolation_tier="shared_logical_partition",
                previous_profile_revision="4",
            )
        )
        self.assertTrue(profile.is_promotion)

    def test_recorded_demotion_is_not_a_promotion(self) -> None:
        profile = IndexIsolationProfile(
            **profile_payload(
                physical_isolation_tier="dedicated_shard",
                promotion_reason="capacity-rebalance",
                promotion_evidence_ref="promotion-evidence-2",
                previous_isolation_tier="dedicated_collection",
                previous_profile_revision="4",
            )
        )
        self.assertFalse(profile.is_promotion)

    def test_a_dedicated_deployment_requires_a_residency_or_encryption_policy(self) -> None:
        # P-4: legal isolation is grounded in an explicit policy, not a label.
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(
                **profile_payload(
                    physical_isolation_tier="dedicated_deployment",
                    promotion_reason="residency",
                    promotion_evidence_ref="promotion-evidence-3",
                )
            )
        profile = IndexIsolationProfile(
            **profile_payload(
                physical_isolation_tier="dedicated_deployment",
                promotion_reason="residency",
                promotion_evidence_ref="promotion-evidence-3",
                residency_policy_ref="residency-policy-eu",
            )
        )
        self.assertEqual(profile.physical_isolation_tier, "dedicated_deployment")

    def test_topology_lineage_is_recorded_as_a_pair(self) -> None:
        for overrides in (
            {"previous_isolation_tier": "dedicated_shard"},
            {"previous_profile_revision": "4"},
        ):
            with self.subTest(case=tuple(overrides)), self.assertRaises(ValidationError):
                IndexIsolationProfile(**profile_payload(**overrides))

    def test_a_topology_change_requires_a_new_revision(self) -> None:
        # P-1: a topology change is a new revision, never an edit.
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(
                **profile_payload(
                    physical_isolation_tier="dedicated_shard",
                    promotion_reason="corpus-size",
                    promotion_evidence_ref="promotion-evidence-4",
                    previous_isolation_tier="shared_logical_partition",
                    previous_profile_revision="5",
                )
            )

    def test_a_recorded_change_must_actually_change_the_tier(self) -> None:
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(
                **profile_payload(
                    previous_isolation_tier="shared_logical_partition",
                    previous_profile_revision="4",
                )
            )

    def test_recorded_at_must_not_precede_effective_at(self) -> None:
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(**profile_payload(recorded_at=EARLIER))

    def test_naive_timestamps_are_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            IndexIsolationProfile(**profile_payload(recorded_at=datetime(2026, 1, 1, 12, 0)))

    def test_profile_is_immutable(self) -> None:
        profile = IndexIsolationProfile(**profile_payload())
        with self.assertRaises(ValidationError):
            profile.logical_tenant_key = "tenant-other"  # type: ignore[misc]

    def test_serialization_round_trip(self) -> None:
        profile = IndexIsolationProfile(**profile_payload())
        restored = IndexIsolationProfile.model_validate_json(profile.model_dump_json())
        self.assertEqual(restored, profile)

    def test_a_tier_is_not_a_permission(self) -> None:
        # T-6: no tier grants broader read access, so no access surface exists.
        field_names = set(IndexIsolationProfile.model_fields)
        forbidden = {
            "permissions",
            "permission_refs",
            "role_code",
            "role_refs",
            "group_code",
            "membership_count",
            "role_count",
            "group_count",
            "hierarchy_depth",
            "grants_access",
            "bypass_filter",
        }
        self.assertEqual(field_names & forbidden, set())

    def test_no_physical_address_or_credential_surface_exists(self) -> None:
        # T-4: placement is resolved from trusted configuration only, and no
        # provider name, endpoint, or credential may appear in a contract.
        field_names = set(IndexIsolationProfile.model_fields)
        forbidden = {
            "endpoint",
            "endpoint_url",
            "connection_string",
            "host",
            "region",
            "provider",
            "provider_name",
            "api_key",
            "secret",
            "token",
            "password",
            "credential",
            "requested_tier",
        }
        self.assertEqual(field_names & forbidden, set())


class SchemaArtifactTests(unittest.TestCase):
    cases = (
        (
            "visibility-policy-definition",
            VisibilityPolicyDefinition,
            VISIBILITY_POLICY_DEFINITION_SCHEMA_ID,
        ),
        ("index-isolation-profile", IndexIsolationProfile, INDEX_ISOLATION_PROFILE_SCHEMA_ID),
    )

    def test_committed_schema_matches_the_python_contract(self) -> None:
        for name, model, _ in self.cases:
            with self.subTest(schema=name):
                path = SCHEMAS_DIR / name / "1.0.0.schema.json"
                committed = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(committed, model.model_json_schema())

    def test_schema_identity_is_stable(self) -> None:
        for name, model, schema_id in self.cases:
            with self.subTest(schema=name):
                path = SCHEMAS_DIR / name / "1.0.0.schema.json"
                committed = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(committed["$id"], schema_id)
                self.assertTrue(schema_id.endswith(":1.0.0"))
                self.assertEqual(model.model_fields["schema_version"].default, "1.0.0")

    def test_public_exports_cover_both_families(self) -> None:
        exported = set(contracts_package.__all__)
        expected = {
            "IndexIsolationProfile",
            "PhysicalIsolationTier",
            "VisibilityAllowClause",
            "VisibilityPolicyDefinition",
            "VisibilityPolicyStatus",
            "VisibilityPredicate",
            "VisibilityPredicateKind",
        }
        self.assertEqual(expected - exported, set())


if __name__ == "__main__":
    unittest.main()
