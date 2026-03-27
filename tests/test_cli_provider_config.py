import os
import unittest
from unittest.mock import patch

from cli.main import get_retry_delay_seconds
from cli.utils import DEFAULT_OPENAI_BASE_URL, resolve_provider_backend_url


class CliProviderConfigTests(unittest.TestCase):
    def test_openai_backend_uses_env_when_no_explicit_url(self):
        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "https://example.com/custom/openai"},
            clear=False,
        ):
            resolved = resolve_provider_backend_url("openai")

        self.assertEqual(resolved, "https://example.com/custom/openai")

    def test_openai_backend_preserves_explicit_url(self):
        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "https://example.com/from-env"},
            clear=False,
        ):
            resolved = resolve_provider_backend_url(
                "openai",
                "https://example.com/from-selection",
            )

        self.assertEqual(resolved, "https://example.com/from-selection")

    def test_openai_backend_falls_back_to_native_default(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_BASE_URL", None)
            resolved = resolve_provider_backend_url("openai")

        self.assertEqual(resolved, DEFAULT_OPENAI_BASE_URL)

    def test_retry_delay_grows_with_cap(self):
        self.assertEqual(get_retry_delay_seconds(1), 1)
        self.assertEqual(get_retry_delay_seconds(2), 2)
        self.assertEqual(get_retry_delay_seconds(3), 4)
        self.assertEqual(get_retry_delay_seconds(10), 30)


if __name__ == "__main__":
    unittest.main()
