import tempfile
import unittest
from pathlib import Path

from cli.runtime import AnalysisRunRequest
from tradingagents.dataflows.config import get_config, reset_config, set_config
from tradingagents.default_config import DEFAULT_CONFIG


class RunIsolationTests(unittest.TestCase):
    def setUp(self):
        reset_config()

    def test_analysis_run_request_uses_unique_run_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = DEFAULT_CONFIG.copy()
            base_config["results_dir"] = temp_dir

            first_request = AnalysisRunRequest.create(
                ticker="SPY",
                analysis_date="2026-01-01",
                analyst_keys=["market"],
                analyst_labels=["market"],
                research_depth=1,
                llm_provider="openai",
                backend_url="https://api.openai.com/v1",
                shallow_thinker="gpt-5-mini",
                deep_thinker="gpt-5-mini",
                google_thinking_level=None,
                openai_reasoning_effort=None,
                anthropic_effort=None,
                config=base_config,
            )
            second_request = AnalysisRunRequest.create(
                ticker="SPY",
                analysis_date="2026-01-01",
                analyst_keys=["market"],
                analyst_labels=["market"],
                research_depth=1,
                llm_provider="openai",
                backend_url="https://api.openai.com/v1",
                shallow_thinker="gpt-5-mini",
                deep_thinker="gpt-5-mini",
                google_thinking_level=None,
                openai_reasoning_effort=None,
                anthropic_effort=None,
                config=base_config,
            )

            self.assertNotEqual(first_request.run_id, second_request.run_id)
            self.assertNotEqual(first_request.run_dir, second_request.run_dir)
            self.assertIn(first_request.run_id, str(first_request.run_dir))
            self.assertIn(second_request.run_id, str(second_request.run_dir))

    def test_analysis_run_request_writes_request_file_inside_run_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base_config = DEFAULT_CONFIG.copy()
            base_config["results_dir"] = temp_dir

            request = AnalysisRunRequest.create(
                ticker="NVDA",
                analysis_date="2026-01-02",
                analyst_keys=["market", "news"],
                analyst_labels=["market", "news"],
                research_depth=2,
                llm_provider="openai",
                backend_url="https://api.openai.com/v1",
                shallow_thinker="gpt-5-mini",
                deep_thinker="gpt-5-mini",
                google_thinking_level=None,
                openai_reasoning_effort="high",
                anthropic_effort=None,
                config=base_config,
            )

            request_file = request.write()

            self.assertTrue(request_file.exists())
            self.assertEqual(request_file.parent, request.run_dir)
            self.assertTrue(request.log_file.exists())
            self.assertTrue(request.report_dir.exists())

    def test_context_local_config_does_not_mutate_defaults(self):
        mutated_config = DEFAULT_CONFIG.copy()
        mutated_config["llm_provider"] = "anthropic"
        mutated_config["data_vendors"] = {
            **DEFAULT_CONFIG["data_vendors"],
            "news_data": "alpha_vantage",
        }

        set_config(mutated_config)
        scoped_config = get_config()

        self.assertEqual(scoped_config["llm_provider"], "anthropic")
        self.assertEqual(scoped_config["data_vendors"]["news_data"], "alpha_vantage")

        reset_config()
        reset_scoped_config = get_config()
        self.assertEqual(
            reset_scoped_config["llm_provider"],
            DEFAULT_CONFIG["llm_provider"],
        )
        self.assertEqual(
            reset_scoped_config["data_vendors"]["news_data"],
            DEFAULT_CONFIG["data_vendors"]["news_data"],
        )


if __name__ == "__main__":
    unittest.main()
