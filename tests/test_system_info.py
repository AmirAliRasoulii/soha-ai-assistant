import unittest

from ai_assistant.system_info import get_system_info

SENSITIVE_KEYS = {
    "env",
    "environ",
    "environment",
    "path",
    "paths",
    "cwd",
    "home",
    "user",
    "username",
    "hostname",
    "host",
    "token",
    "secret",
    "password",
    "api_key",
    "credentials",
}


class SystemInfoTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.info = get_system_info()

    def test_app_name(self) -> None:
        self.assertEqual(self.info["app_name"], "ai-assistant")

    def test_app_version(self) -> None:
        self.assertEqual(self.info["app_version"], "0.1.0")

    def test_python_version_present(self) -> None:
        self.assertTrue(self.info["python_version"].strip())

    def test_no_sensitive_keys(self) -> None:
        self.assertEqual(set(self.info) & SENSITIVE_KEYS, set())

    def test_structure(self) -> None:
        self.assertIsInstance(self.info, dict)
        self.assertEqual(
            set(self.info), {"app_name", "app_version", "python_version"}
        )
        for key, value in self.info.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)


if __name__ == "__main__":
    unittest.main()
