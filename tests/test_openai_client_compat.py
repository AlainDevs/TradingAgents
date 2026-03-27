import unittest
from unittest.mock import patch

from tradingagents.llm_clients.openai_client import OpenAIClient


class OpenAIClientCompatTests(unittest.TestCase):
    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_native_openai_keeps_responses_api(self, mock_chat_openai):
        client = OpenAIClient("gpt-5-mini", provider="openai")

        client.get_llm()

        kwargs = mock_chat_openai.call_args.kwargs
        self.assertTrue(kwargs["use_responses_api"])
        self.assertNotIn("streaming", kwargs)

    @patch("tradingagents.llm_clients.openai_client.NormalizedChatOpenAI")
    def test_custom_base_url_uses_streaming_chat_compat_mode(self, mock_chat_openai):
        client = OpenAIClient(
            "gpt-5-mini",
            base_url="https://example.com/openai",
            provider="openai",
            reasoning_effort="high",
        )

        client.get_llm()

        kwargs = mock_chat_openai.call_args.kwargs
        self.assertEqual(
            kwargs["base_url"],
            "https://example.com/openai/v1",
        )
        self.assertTrue(kwargs["streaming"])
        self.assertNotIn("use_responses_api", kwargs)
        self.assertEqual(kwargs["reasoning_effort"], "high")


if __name__ == "__main__":
    unittest.main()
