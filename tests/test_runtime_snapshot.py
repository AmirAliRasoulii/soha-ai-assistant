"""Tests for the RuntimeSnapshot contract, schema version 1.0.0."""

import json
import unittest
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

import ai_assistant.contracts as contracts
from ai_assistant.contracts import (
    RuntimeArtifactRef,
    RuntimeFeatureFlag,
    RuntimeSnapshot,
    RuntimeSnapshotContent,
    RuntimeSnapshotIntegrity,
)

TEHRAN = timezone(timedelta(hours=3, minutes=30))
SNAPSHOT_ID = "77777777-7777-4777-8777-777777777777"
UUID1_VALUE = "11111111-1111-1111-8111-111111111111"
CAPTURED_AT = "2026-01-01T12:00:00+03:30"
EXPECTED_UTC = datetime(2026, 1, 1, 8, 30, tzinfo=UTC)
HEX_16 = "0123456789abcdef"
REVISION_40 = HEX_16 * 2 + HEX_16[:8]
REVISION_64 = HEX_16 * 4
DIGEST = "sha256:" + HEX_16 * 4
SECOND_DIGEST = "sha256:" + "fedcba9876543210" * 4
NAMED_ARTIFACT_FIELDS = (
    "build_artifact",
    "config_bundle",
    "prompt_bundle",
    "model_policy",
    "structured_output_backend",
    "retrieval_profile",
    "embedding_artifact",
    "reranker_artifact",
    "index_snapshot",
    "semantic_catalog",
    "rule_bundle",
    "security_policy",
    "telemetry_schema",
)
FORBIDDEN_FIELDS = (
    "api_key",
    "access_token",
    "token",
    "secret",
    "password",
    "credentials",
    "endpoint_url",
    "provider_response",
    "raw_config",
    "environment_variables",
    "docker_registry",
    "kubernetes_namespace",
    "cloud_region",
    "database_url",
    "filesystem_path",
    "container_digest",
    "docker_image",
    "image_tag",
    "registry_url",
    "provider",
    "provider_object",
    "endpoint",
    "base_url",
    "deployment_name",
    "raw_model_config",
)
INVALID_FLAG_NAMES = (
    "Feature Flag",
    "UPPERCASE",
    " leading",
    "contains/slash",
    "contains@sign",
    "1leading.digit",
    "",
    "a" * 65,
)
INVALID_DIGESTS = (
    "sha256:" + (HEX_16 * 4).upper(),
    HEX_16 * 4,
    "md5:" + HEX_16 * 4,
    "sha512:" + HEX_16 * 8,
    "sha256:" + HEX_16 * 3,
    "sha256:" + HEX_16 * 4 + "ab",
    " sha256:" + HEX_16 * 4,
    "sha256:" + HEX_16 * 4 + " ",
    "prefix-sha256:" + HEX_16 * 4,
    "sha256:" + HEX_16 * 4 + "-suffix",
    "sha256:" + "g" * 64,
)
SCHEMA_ARTIFACT = Path(__file__).resolve().parents[1] / "schemas" / "runtime-snapshot"
SCHEMA_ARTIFACT = SCHEMA_ARTIFACT / "1.0.0.schema.json"


def artifact_payload(index: int = 0, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "artifact_id": f"artifact.{index}",
        "revision": f"revision.{index}",
        "digest": DIGEST,
    }
    values.update(overrides)
    return values


def flag_payload(index: int = 0, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {"name": f"flag.{index}", "enabled": index % 2 == 0}
    values.update(overrides)
    return values


def content_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "application_version": "1.4.2",
        "source_revision": REVISION_40,
        "model_artifacts": [artifact_payload(100)],
    }
    for position, field in enumerate(NAMED_ARTIFACT_FIELDS):
        values[field] = artifact_payload(position)
    values.update(overrides)
    return values


def integrity_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {"canonicalization": "rfc8785", "digest": SECOND_DIGEST}
    values.update(overrides)
    return values


def snapshot_payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "snapshot_id": SNAPSHOT_ID,
        "captured_at": CAPTURED_AT,
        "content": content_payload(),
        "integrity": integrity_payload(),
    }
    values.update(overrides)
    return values


def artifacts(count: int) -> list[dict[str, object]]:
    return [artifact_payload(index) for index in range(count)]


def flags(count: int) -> list[dict[str, object]]:
    return [flag_payload(index) for index in range(count)]


class RuntimeArtifactRefTests(unittest.TestCase):
    def test_valid_artifact_reference(self) -> None:
        reference = RuntimeArtifactRef(**artifact_payload(3))
        self.assertEqual(reference.artifact_id, "artifact.3")
        self.assertEqual(reference.revision, "revision.3")
        self.assertEqual(reference.digest, DIGEST)

    def test_blank_artifact_id_rejected(self) -> None:
        for blank in ("", "   ", "\t\n"):
            with self.subTest(blank=blank), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(artifact_id=blank))

    def test_surrounding_artifact_id_whitespace_rejected(self) -> None:
        for value in (" artifact", "artifact ", "\tartifact", "artifact\n"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(artifact_id=value))

    def test_nul_artifact_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeArtifactRef(**artifact_payload(artifact_id="artifact\x00id"))

    def test_oversized_artifact_id_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeArtifactRef(**artifact_payload(artifact_id="a" * 257))

    def test_maximum_artifact_id_accepted(self) -> None:
        reference = RuntimeArtifactRef(**artifact_payload(artifact_id="a" * 256))
        self.assertEqual(len(reference.artifact_id), 256)

    def test_blank_revision_rejected(self) -> None:
        for blank in ("", "   ", "\t\n"):
            with self.subTest(blank=blank), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(revision=blank))

    def test_surrounding_revision_whitespace_rejected(self) -> None:
        for value in (" revision", "revision ", "\trevision", "revision\n"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(revision=value))

    def test_nul_revision_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeArtifactRef(**artifact_payload(revision="revision\x00"))

    def test_oversized_revision_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeArtifactRef(**artifact_payload(revision="r" * 129))

    def test_maximum_revision_accepted(self) -> None:
        reference = RuntimeArtifactRef(**artifact_payload(revision="r" * 128))
        self.assertEqual(len(reference.revision), 128)

    def test_accepted_values_preserved_exactly(self) -> None:
        identifier = "Prompt_Bundle:v2.MIXED-case"
        revision = "Release Candidate 3"
        reference = RuntimeArtifactRef(
            **artifact_payload(artifact_id=identifier, revision=revision)
        )
        self.assertEqual(reference.artifact_id, identifier)
        self.assertEqual(reference.revision, revision)

    def test_valid_digest_accepted(self) -> None:
        reference = RuntimeArtifactRef(**artifact_payload(digest=SECOND_DIGEST))
        self.assertEqual(reference.digest, SECOND_DIGEST)

    def test_invalid_digests_rejected(self) -> None:
        for digest in INVALID_DIGESTS:
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(digest=digest))

    def test_unknown_artifact_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RuntimeArtifactRef(**artifact_payload(**{field: "injected"}))

    def test_artifact_reference_immutable(self) -> None:
        reference = RuntimeArtifactRef(**artifact_payload())
        with self.assertRaises(ValidationError):
            reference.digest = SECOND_DIGEST


class RuntimeFeatureFlagTests(unittest.TestCase):
    def test_valid_feature_flag(self) -> None:
        flag = RuntimeFeatureFlag(name="retrieval.rerank", enabled=True)
        self.assertEqual(flag.name, "retrieval.rerank")
        self.assertIs(flag.enabled, True)

    def test_invalid_feature_flag_names_rejected(self) -> None:
        for name in INVALID_FLAG_NAMES:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                RuntimeFeatureFlag(name=name, enabled=True)

    def test_multivariate_value_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeFeatureFlag(name="routing.mode", enabled=True, variant="b")


class RuntimeSnapshotIntegrityTests(unittest.TestCase):
    def test_valid_integrity_metadata(self) -> None:
        integrity = RuntimeSnapshotIntegrity(**integrity_payload())
        self.assertEqual(integrity.canonicalization, "rfc8785")
        self.assertEqual(integrity.digest, SECOND_DIGEST)

    def test_unsupported_canonicalization_rejected(self) -> None:
        for value in ("jcs", "rfc7159", "RFC8785", "none"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RuntimeSnapshotIntegrity(**integrity_payload(canonicalization=value))

    def test_invalid_integrity_digest_rejected(self) -> None:
        for digest in INVALID_DIGESTS:
            with self.subTest(digest=digest), self.assertRaises(ValidationError):
                RuntimeSnapshotIntegrity(**integrity_payload(digest=digest))


class RuntimeSnapshotContentTests(unittest.TestCase):
    def test_valid_content(self) -> None:
        content = RuntimeSnapshotContent(**content_payload())
        self.assertEqual(content.application_version, "1.4.2")
        self.assertEqual(content.source_revision, REVISION_40)
        self.assertEqual(content.feature_flags, ())

    def test_forty_character_source_revision_accepted(self) -> None:
        content = RuntimeSnapshotContent(**content_payload(source_revision=REVISION_40))
        self.assertEqual(len(content.source_revision), 40)

    def test_sixty_four_character_source_revision_accepted(self) -> None:
        content = RuntimeSnapshotContent(**content_payload(source_revision=REVISION_64))
        self.assertEqual(len(content.source_revision), 64)

    def test_short_source_revision_rejected(self) -> None:
        for revision in (HEX_16, HEX_16 * 2 + "0123456", HEX_16 * 3):
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                RuntimeSnapshotContent(**content_payload(source_revision=revision))

    def test_uppercase_source_revision_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(source_revision=REVISION_40.upper()))

    def test_non_hexadecimal_source_revision_rejected(self) -> None:
        for revision in ("g" * 40, REVISION_40[:39] + "z", REVISION_40[:39] + " "):
            with self.subTest(revision=revision), self.assertRaises(ValidationError):
                RuntimeSnapshotContent(**content_payload(source_revision=revision))

    def test_invalid_application_version_rejected(self) -> None:
        for version in ("1", "1.0", "01.0.0", "1.0.0-beta", "v1.0.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                RuntimeSnapshotContent(**content_payload(application_version=version))

    def test_missing_required_artifact_rejected(self) -> None:
        for field in NAMED_ARTIFACT_FIELDS:
            payload = content_payload()
            del payload[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RuntimeSnapshotContent(**payload)

    def test_one_model_artifact_accepted(self) -> None:
        content = RuntimeSnapshotContent(**content_payload(model_artifacts=artifacts(1)))
        self.assertEqual(len(content.model_artifacts), 1)

    def test_sixteen_model_artifacts_accepted(self) -> None:
        content = RuntimeSnapshotContent(**content_payload(model_artifacts=artifacts(16)))
        self.assertEqual(len(content.model_artifacts), 16)

    def test_zero_model_artifacts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(model_artifacts=[]))

    def test_seventeen_model_artifacts_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(model_artifacts=artifacts(17)))

    def test_missing_model_artifacts_rejected(self) -> None:
        payload = content_payload()
        del payload["model_artifacts"]
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**payload)

    def test_duplicate_model_artifact_identifiers_rejected(self) -> None:
        duplicated = [artifact_payload(1), artifact_payload(1, revision="other")]
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(model_artifacts=duplicated))

    def test_model_artifact_order_preserved(self) -> None:
        ordered = [artifact_payload(index) for index in (5, 1, 9)]
        content = RuntimeSnapshotContent(**content_payload(model_artifacts=ordered))
        self.assertEqual(
            [item.artifact_id for item in content.model_artifacts],
            ["artifact.5", "artifact.1", "artifact.9"],
        )

    def test_missing_feature_flags_becomes_empty_tuple(self) -> None:
        content = RuntimeSnapshotContent(**content_payload())
        self.assertEqual(content.feature_flags, ())
        self.assertIsInstance(content.feature_flags, tuple)

    def test_explicit_null_feature_flags_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(feature_flags=None))

    def test_sixty_four_feature_flags_accepted(self) -> None:
        content = RuntimeSnapshotContent(**content_payload(feature_flags=flags(64)))
        self.assertEqual(len(content.feature_flags), 64)

    def test_sixty_five_feature_flags_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(feature_flags=flags(65)))

    def test_duplicate_feature_flag_names_rejected(self) -> None:
        duplicated = [flag_payload(2), flag_payload(2, enabled=False)]
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**content_payload(feature_flags=duplicated))

    def test_feature_flag_order_preserved(self) -> None:
        ordered = [flag_payload(index) for index in (7, 2, 4)]
        content = RuntimeSnapshotContent(**content_payload(feature_flags=ordered))
        self.assertEqual(
            [item.name for item in content.feature_flags],
            ["flag.7", "flag.2", "flag.4"],
        )

    def test_content_immutable(self) -> None:
        content = RuntimeSnapshotContent(**content_payload())
        with self.assertRaises(ValidationError):
            content.source_revision = REVISION_64


class RuntimeSnapshotTests(unittest.TestCase):
    def test_default_schema_version(self) -> None:
        snapshot = RuntimeSnapshot(**snapshot_payload())
        self.assertEqual(snapshot.schema_version, "1.0.0")

    def test_other_schema_version_rejected(self) -> None:
        for version in ("1.0.1", "2.0.0", "0.1.0", "1.0"):
            with self.subTest(version=version), self.assertRaises(ValidationError):
                RuntimeSnapshot(**snapshot_payload(schema_version=version))

    def test_valid_full_snapshot(self) -> None:
        payload = snapshot_payload(
            content=content_payload(
                model_artifacts=artifacts(3),
                feature_flags=flags(2),
                source_revision=REVISION_64,
            )
        )
        snapshot = RuntimeSnapshot(**payload)
        self.assertEqual(snapshot.snapshot_id, UUID(SNAPSHOT_ID))
        self.assertEqual(snapshot.captured_at, EXPECTED_UTC)
        self.assertEqual(len(snapshot.content.model_artifacts), 3)
        self.assertEqual(len(snapshot.content.feature_flags), 2)
        self.assertEqual(snapshot.integrity.canonicalization, "rfc8785")

    def test_snapshot_id_must_be_uuid4(self) -> None:
        for value in (UUID1_VALUE, "not-a-uuid", ""):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                RuntimeSnapshot(**snapshot_payload(snapshot_id=value))

    def test_naive_captured_at_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshot(**snapshot_payload(captured_at=datetime(2026, 1, 1, 12, 0, 0)))

    def test_non_utc_captured_at_normalized(self) -> None:
        snapshot = RuntimeSnapshot(
            **snapshot_payload(captured_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=TEHRAN))
        )
        self.assertEqual(snapshot.captured_at, EXPECTED_UTC)
        self.assertEqual(snapshot.captured_at.utcoffset(), timedelta(0))

    def test_missing_integrity_rejected(self) -> None:
        payload = snapshot_payload()
        del payload["integrity"]
        with self.assertRaises(ValidationError):
            RuntimeSnapshot(**payload)

    def test_snapshot_and_nested_models_immutable(self) -> None:
        snapshot = RuntimeSnapshot(**snapshot_payload())
        with self.assertRaises(ValidationError):
            snapshot.snapshot_id = UUID(SNAPSHOT_ID)
        with self.assertRaises(ValidationError):
            snapshot.content.application_version = "2.0.0"
        with self.assertRaises(ValidationError):
            snapshot.integrity.digest = DIGEST
        with self.assertRaises(ValidationError):
            snapshot.content.build_artifact.revision = "other"
        self.assertIsInstance(snapshot.content.model_artifacts, tuple)
        self.assertIsInstance(snapshot.content.feature_flags, tuple)

    def test_json_round_trip(self) -> None:
        payload = snapshot_payload(
            content=content_payload(model_artifacts=artifacts(2), feature_flags=flags(3))
        )
        snapshot = RuntimeSnapshot(**payload)
        restored = RuntimeSnapshot.model_validate_json(snapshot.model_dump_json())
        self.assertEqual(restored, snapshot)

    def test_forbidden_fields_rejected(self) -> None:
        for field in FORBIDDEN_FIELDS + ("run_id",):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                RuntimeSnapshot(**snapshot_payload(**{field: "injected"}))
            with self.subTest(field=field, level="content"), self.assertRaises(ValidationError):
                RuntimeSnapshot(**snapshot_payload(content=content_payload(**{field: "x"})))


class RuntimeSnapshotSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = RuntimeSnapshot.model_json_schema()

    def test_root_schema_identity(self) -> None:
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(self.schema["$id"], "urn:ai-assistant:contracts:runtime-snapshot:1.0.0")

    def test_root_schema_closed(self) -> None:
        self.assertIs(self.schema["additionalProperties"], False)

    def test_nested_schemas_closed(self) -> None:
        definitions = self.schema["$defs"]
        for name in (
            "RuntimeArtifactRef",
            "RuntimeFeatureFlag",
            "RuntimeSnapshotContent",
            "RuntimeSnapshotIntegrity",
        ):
            with self.subTest(definition=name):
                self.assertIs(definitions[name]["additionalProperties"], False)

    def test_committed_schema_matches_generated_schema(self) -> None:
        committed = json.loads(SCHEMA_ARTIFACT.read_text(encoding="utf-8"))
        self.assertEqual(committed, self.schema)

    def test_committed_schema_ends_with_newline(self) -> None:
        self.assertTrue(SCHEMA_ARTIFACT.read_text(encoding="utf-8").endswith("}\n"))

    def test_forbidden_field_names_absent_from_schema(self) -> None:
        serialized = json.dumps(self.schema)
        for field in FORBIDDEN_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(f'"{field}"', serialized)

    def test_run_id_absent_from_schema(self) -> None:
        self.assertNotIn('"run_id"', json.dumps(self.schema))

    def test_public_exports_available(self) -> None:
        expected = {
            "RuntimeArtifactRef",
            "RuntimeFeatureFlag",
            "RuntimeSnapshot",
            "RuntimeSnapshotContent",
            "RuntimeSnapshotIntegrity",
        }
        self.assertTrue(expected.issubset(set(contracts.__all__)))
        for name in expected:
            with self.subTest(name=name):
                self.assertTrue(hasattr(contracts, name))


artifact_ids = st.lists(
    st.from_regex(r"\Aartifact\.[a-z0-9]{1,6}\Z"),
    min_size=1,
    max_size=6,
    unique=True,
)
flag_names = st.lists(
    st.from_regex(r"\Aflag\.[a-z0-9]{1,6}\Z"),
    min_size=1,
    max_size=6,
    unique=True,
)
forbidden_field_names = st.sampled_from(FORBIDDEN_FIELDS)


class RuntimeSnapshotPropertyTests(unittest.TestCase):
    @given(identifiers=artifact_ids)
    def test_unique_model_artifacts_preserve_order(self, identifiers: list[str]) -> None:
        payload = content_payload(
            model_artifacts=[artifact_payload(artifact_id=value) for value in identifiers]
        )
        content = RuntimeSnapshotContent(**payload)
        self.assertEqual([item.artifact_id for item in content.model_artifacts], identifiers)

    @given(identifiers=artifact_ids)
    def test_duplicate_model_artifact_rejected(self, identifiers: list[str]) -> None:
        duplicated = [*identifiers, identifiers[0]]
        payload = content_payload(
            model_artifacts=[artifact_payload(artifact_id=value) for value in duplicated]
        )
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**payload)

    @given(names=flag_names)
    def test_unique_feature_flags_preserve_order(self, names: list[str]) -> None:
        payload = content_payload(
            feature_flags=[{"name": value, "enabled": True} for value in names]
        )
        content = RuntimeSnapshotContent(**payload)
        self.assertEqual([item.name for item in content.feature_flags], names)

    @given(names=flag_names)
    def test_duplicate_feature_flag_rejected(self, names: list[str]) -> None:
        duplicated = [*names, names[0]]
        payload = content_payload(
            feature_flags=[{"name": value, "enabled": False} for value in duplicated]
        )
        with self.assertRaises(ValidationError):
            RuntimeSnapshotContent(**payload)

    @given(field=forbidden_field_names, value=st.text(min_size=1, max_size=8))
    def test_unknown_infrastructure_fields_rejected(self, field: str, value: str) -> None:
        with self.assertRaises(ValidationError):
            RuntimeSnapshot(**snapshot_payload(**{field: value}))


if __name__ == "__main__":
    unittest.main()
