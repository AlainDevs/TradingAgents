import importlib
import os
import unittest
from unittest.mock import patch


class DefaultConfigEnvTests(unittest.TestCase):
    def _reload_default_config(self):
        module = importlib.import_module("tradingagents.default_config")
        return importlib.reload(module)

    def test_openai_base_url_is_used_when_present(self):
        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "https://example.com/custom/openai"},
            clear=False,
        ):
            module = self._reload_default_config()

        self.assertEqual(
            module.DEFAULT_CONFIG["backend_url"],
            "https://example.com/custom/openai",
        )

    def test_default_openai_base_url_falls_back_to_native_openai(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_BASE_URL", None)
            module = self._reload_default_config()

        self.assertEqual(
            module.DEFAULT_CONFIG["backend_url"],
            "https://api.openai.com/v1",
        )


if __name__ == "__main__":
    unittest.main()
