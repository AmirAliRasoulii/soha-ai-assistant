"""Architectural boundary tests for CP-001.

These tests are structural rather than behavioural: they read the committed
source of `src/ai_assistant/contracts/` and `src/ai_assistant/core/` and fail if
any framework, transport, persistence, provider, or secret concern leaks into
the AI purity boundary. They also guard the versioning policy by proving that
every previously published 1.0.0 schema artifact still matches its model.
"""

import ast
import json
import unittest
from pathlib import Path

import ai_assistant.contracts as contracts_package
from ai_assistant.core import ports

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "ai_assistant"
CONTRACTS_DIR = SRC_ROOT / "contracts"
CORE_DIR = SRC_ROOT / "core"
SCHEMAS_DIR = REPO_ROOT / "schemas"

FORBIDDEN_TOP_LEVEL_MODULES = frozenset(
    {
        # web frameworks and transports
        "django",
        "fastapi",
        "flask",
        "starlette",
        "requests",
        "httpx",
        "aiohttp",
        "urllib3",
        "http",
        "socket",
        "socketserver",
        "xmlrpc",
        "wsgiref",
        # queues, caches, brokers
        "redis",
        "celery",
        "kombu",
        "rq",
        "pika",
        "kafka",
        # persistence
        "sqlalchemy",
        "psycopg",
        "psycopg2",
        "asyncpg",
        "pymongo",
        "sqlite3",
        "alembic",
        # model providers and gateways
        "litellm",
        "openai",
        "anthropic",
        "cohere",
        "google",
        "vertexai",
        "transformers",
        "tiktoken",
        # cloud, secrets, storage, vectors
        "boto3",
        "botocore",
        "azure",
        "hvac",
        "minio",
        "qdrant_client",
        "pinecone",
        "weaviate",
        "chromadb",
        "elasticsearch",
        # process-level configuration and environment access
        "os",
        "subprocess",
        "multiprocessing",
        "threading",
        "logging",
    }
)

FORBIDDEN_SUBSTRINGS = (
    "litellm",
    "django",
    "redis",
    "fastapi",
    "psycopg",
    "sqlalchemy",
    "boto3",
    "secret_manager",
)

SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "secret_key",
        "secret_value",
        "client_secret",
        "password",
        "passphrase",
        "token",
        "access_token",
        "refresh_token",
        "bearer_token",
        "private_key",
        "credential_value",
        "authorization_header",
    }
)

CP001_MODULES = (
    "control_plane_base",
    "organization",
    "membership",
    "principal",
    "configuration",
    "source_registry",
    "model_gateway",
    "runtime_lineage",
    "visibility_isolation",
)

PUBLISHED_BEFORE_CP001 = {
    "turn-input": ("turn_input", "TurnInput"),
    "security-principal-context": ("security", "SecurityPrincipalContext"),
    "authorization-decision": ("security", "AuthorizationDecision"),
    "query-analysis": ("query_analysis", "QueryAnalysis"),
    "route-decision": ("route_decision", "RouteDecision"),
    "execution-plan": ("execution_plan", "ExecutionPlan"),
    "step-result": ("step_result", "StepResult"),
    "evidence": ("evidence", "EvidenceBundle"),
    "answer-plan": ("answer_plan", "AnswerPlan"),
    "final-answer": ("final_answer", "FinalAnswer"),
    "error-envelope": ("errors", "ErrorEnvelope"),
    "audit-event": ("audit", "AuditEvent"),
    "runtime-snapshot": ("runtime_snapshot", "RuntimeSnapshot"),
}

CP001_SCHEMA_NAMES = (
    "organization",
    "organizational-node",
    "node-membership",
    "scoped-role-assignment",
    "request-actor-context",
    "authorization-request",
    "configuration-release",
    "model-pool-policy",
    "knowledge-source",
    "source-revision",
    "source-relationship",
    "runtime-lineage",
    "model-invocation-request",
    "model-invocation-result",
    "visibility-policy-definition",
    "index-isolation-profile",
)


def python_sources(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*.py"))


def imported_root_modules(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
    return roots


class ImportBoundaryTests(unittest.TestCase):
    def test_boundary_scan_covers_the_expected_surface(self) -> None:
        scanned = python_sources(CONTRACTS_DIR) + python_sources(CORE_DIR)
        self.assertGreater(len(scanned), 20)
        names = {path.stem for path in python_sources(CONTRACTS_DIR)}
        for module in CP001_MODULES:
            self.assertIn(module, names)

    def test_no_forbidden_imports_in_contracts_or_core(self) -> None:
        offenders: list[str] = []
        for path in python_sources(CONTRACTS_DIR) + python_sources(CORE_DIR):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            forbidden = imported_root_modules(tree) & FORBIDDEN_TOP_LEVEL_MODULES
            if forbidden:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {sorted(forbidden)}")
        self.assertEqual(offenders, [])

    def test_only_the_allowed_third_party_dependency_is_used(self) -> None:
        allowed_external = {"pydantic"}
        stdlib_allowed = {
            "__future__",
            "abc",
            "asyncio",
            "collections",
            "contextlib",
            "dataclasses",
            "datetime",
            "enum",
            "functools",
            "hashlib",
            "json",
            "math",
            "re",
            "types",
            "typing",
            "unicodedata",
            "uuid",
        }
        internal = {"ai_assistant"}
        unexpected: dict[str, list[str]] = {}
        for path in python_sources(CONTRACTS_DIR) + python_sources(CORE_DIR):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            roots = imported_root_modules(tree)
            leftover = roots - allowed_external - stdlib_allowed - internal
            if leftover:
                unexpected[str(path.relative_to(REPO_ROOT))] = sorted(leftover)
        self.assertEqual(unexpected, {})

    def test_no_vendor_or_framework_token_appears_in_the_boundary(self) -> None:
        offenders: list[str] = []
        for path in python_sources(CONTRACTS_DIR) + python_sources(CORE_DIR):
            lowered = path.read_text(encoding="utf-8").lower()
            for token in FORBIDDEN_SUBSTRINGS:
                if token in lowered:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {token}")
        self.assertEqual(offenders, [])

    def test_no_mutable_module_level_state(self) -> None:
        offenders: list[str] = []
        for path in python_sources(CONTRACTS_DIR) + python_sources(CORE_DIR):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                targets: list[ast.expr] = []
                if isinstance(node, ast.Assign):
                    targets = list(node.targets)
                elif isinstance(node, ast.AnnAssign):
                    targets = [node.target]
                if not targets:
                    continue
                value = node.value
                if isinstance(
                    value, ast.Dict | ast.List | ast.Set | ast.DictComp | ast.ListComp | ast.SetComp
                ):
                    names = [
                        target.id
                        for target in targets
                        if isinstance(target, ast.Name) and not target.id.startswith("__")
                    ]
                    if names:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {names}")
        self.assertEqual(offenders, [])

    def test_model_gateway_port_stays_provider_neutral(self) -> None:
        source = (CORE_DIR / "ports.py").read_text(encoding="utf-8").lower()
        for token in ("litellm", "openai", "anthropic", "base_url", "api_key"):
            self.assertNotIn(token, source)
        self.assertTrue(hasattr(ports, "ModelGatewayPort"))
        annotations = ports.ModelGatewayPort.invoke.__annotations__
        self.assertEqual(
            annotations["request"].__name__
            if hasattr(annotations["request"], "__name__")
            else str(annotations["request"]),
            "ModelInvocationRequest",
        )


class SecretExclusionTests(unittest.TestCase):
    def test_no_contract_field_name_looks_like_a_secret(self) -> None:
        offenders: list[str] = []
        for name in contracts_package.__all__:
            candidate = getattr(contracts_package, name)
            fields = getattr(candidate, "model_fields", None)
            if not isinstance(fields, dict):
                continue
            for field_name in fields:
                if field_name.lower() in SECRET_FIELD_NAMES:
                    offenders.append(f"{name}.{field_name}")
        self.assertEqual(offenders, [])

    def test_no_schema_property_name_looks_like_a_secret(self) -> None:
        offenders: list[str] = []
        for artifact in sorted(SCHEMAS_DIR.glob("*/1.0.0.schema.json")):
            document = json.loads(artifact.read_text(encoding="utf-8"))
            for node in _walk_json(document):
                if isinstance(node, dict) and isinstance(node.get("properties"), dict):
                    for property_name in node["properties"]:
                        if property_name.lower() in SECRET_FIELD_NAMES:
                            offenders.append(f"{artifact.parent.name}:{property_name}")
        self.assertEqual(offenders, [])


def _walk_json(node: object) -> list[object]:
    found: list[object] = [node]
    if isinstance(node, dict):
        for value in node.values():
            found.extend(_walk_json(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_walk_json(value))
    return found


class ExportCoverageTests(unittest.TestCase):
    def test_every_public_cp001_symbol_is_exported(self) -> None:
        exported = set(contracts_package.__all__)
        missing: list[str] = []
        for module_name in CP001_MODULES:
            module_path = CONTRACTS_DIR / f"{module_name}.py"
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    if node.name not in exported:
                        missing.append(f"{module_name}.{node.name}")
                elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                    name = node.target.id
                    if name.startswith("_") or name.isupper():
                        continue
                    if name not in exported:
                        missing.append(f"{module_name}.{name}")
        self.assertEqual(missing, [])

    def test_all_exports_resolve_and_are_sorted_and_unique(self) -> None:
        exported = list(contracts_package.__all__)
        self.assertEqual(len(exported), len(set(exported)))
        for name in exported:
            self.assertTrue(hasattr(contracts_package, name), name)

    def test_previously_exported_symbols_are_still_exported(self) -> None:
        # Deleting or renaming a published export would be a breaking change.
        for _module_name, symbol in PUBLISHED_BEFORE_CP001.values():
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, contracts_package.__all__)
                self.assertTrue(hasattr(contracts_package, symbol))


class VersioningStabilityTests(unittest.TestCase):
    def test_published_schema_artifacts_still_match_their_models(self) -> None:
        import importlib

        for artifact_name, (module_name, symbol) in PUBLISHED_BEFORE_CP001.items():
            with self.subTest(artifact=artifact_name):
                module = importlib.import_module(f"ai_assistant.contracts.{module_name}")
                model = getattr(module, symbol)
                committed = json.loads(
                    (SCHEMAS_DIR / artifact_name / "1.0.0.schema.json").read_text(encoding="utf-8")
                )
                self.assertEqual(committed, model.model_json_schema())
                self.assertEqual(
                    committed["$id"], f"urn:ai-assistant:contracts:{artifact_name}:1.0.0"
                )

    def test_cp001_artifacts_are_new_schema_identifiers(self) -> None:
        published = set(PUBLISHED_BEFORE_CP001)
        for name in CP001_SCHEMA_NAMES:
            with self.subTest(name=name):
                self.assertNotIn(name, published)
                artifact = SCHEMAS_DIR / name / "1.0.0.schema.json"
                self.assertTrue(artifact.is_file())

    def test_only_one_version_directory_exists_per_schema_family(self) -> None:
        for directory in sorted(SCHEMAS_DIR.iterdir()):
            if not directory.is_dir():
                continue
            versions = sorted(path.name for path in directory.glob("*.schema.json"))
            with self.subTest(family=directory.name):
                self.assertEqual(versions, ["1.0.0.schema.json"])

    def test_every_schema_artifact_is_canonically_formatted(self) -> None:
        for artifact in sorted(SCHEMAS_DIR.glob("*/1.0.0.schema.json")):
            raw = artifact.read_text(encoding="utf-8")
            document = json.loads(raw)
            expected = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
            with self.subTest(artifact=artifact.parent.name):
                self.assertEqual(raw, expected)
                self.assertEqual(
                    document["$schema"], "https://json-schema.org/draft/2020-12/schema"
                )

    def test_runtime_snapshot_1_0_0_is_untouched_by_cp001(self) -> None:
        from ai_assistant.contracts.runtime_snapshot import RuntimeSnapshot

        schema = RuntimeSnapshot.model_json_schema()
        committed = json.loads(
            (SCHEMAS_DIR / "runtime-snapshot" / "1.0.0.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(committed, schema)
        self.assertNotIn("configuration_release", set(RuntimeSnapshot.model_fields))


if __name__ == "__main__":
    unittest.main()
