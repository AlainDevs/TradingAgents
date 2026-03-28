from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(slots=True)
class AnalysisRunRequest:
    """Serializable request payload for one isolated analysis run."""

    run_id: str
    ticker: str
    analysis_date: str
    analyst_keys: list[str]
    analyst_labels: list[str]
    research_depth: int
    llm_provider: str
    backend_url: str | None
    shallow_thinker: str
    deep_thinker: str
    google_thinking_level: str | None
    openai_reasoning_effort: str | None
    anthropic_effort: str | None
    config: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        ticker: str,
        analysis_date: str,
        analyst_keys: list[str],
        analyst_labels: list[str],
        research_depth: int,
        llm_provider: str,
        backend_url: str | None,
        shallow_thinker: str,
        deep_thinker: str,
        google_thinking_level: str | None,
        openai_reasoning_effort: str | None,
        anthropic_effort: str | None,
        config: dict[str, Any],
    ) -> "AnalysisRunRequest":
        run_id = uuid4().hex[:12]
        config_snapshot = copy.deepcopy(config)
        run_dir = Path(config_snapshot["results_dir"]) / "runs" / run_id

        config_snapshot["run_id"] = run_id
        config_snapshot["run_output_dir"] = str(run_dir)
        config_snapshot["graph_log_dir"] = str(run_dir / "graph_logs")
        config_snapshot["data_cache_dir"] = str(run_dir / "data_cache")

        return cls(
            run_id=run_id,
            ticker=ticker,
            analysis_date=analysis_date,
            analyst_keys=list(analyst_keys),
            analyst_labels=list(analyst_labels),
            research_depth=research_depth,
            llm_provider=llm_provider,
            backend_url=backend_url,
            shallow_thinker=shallow_thinker,
            deep_thinker=deep_thinker,
            google_thinking_level=google_thinking_level,
            openai_reasoning_effort=openai_reasoning_effort,
            anthropic_effort=anthropic_effort,
            config=config_snapshot,
        )

    @property
    def run_dir(self) -> Path:
        return Path(self.config["run_output_dir"])

    @property
    def report_dir(self) -> Path:
        return self.run_dir / "reports"

    @property
    def log_file(self) -> Path:
        return self.run_dir / "message_tool.log"

    @property
    def request_file(self) -> Path:
        return self.run_dir / "request.json"

    @property
    def final_state_file(self) -> Path:
        return self.run_dir / "final_state.json"

    def ensure_directories(self) -> None:
        self.report_dir.mkdir(parents=True, exist_ok=True)
        Path(self.config["graph_log_dir"]).mkdir(parents=True, exist_ok=True)
        Path(self.config["data_cache_dir"]).mkdir(parents=True, exist_ok=True)
        self.log_file.touch(exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "ticker": self.ticker,
            "analysis_date": self.analysis_date,
            "analyst_keys": self.analyst_keys,
            "analyst_labels": self.analyst_labels,
            "research_depth": self.research_depth,
            "llm_provider": self.llm_provider,
            "backend_url": self.backend_url,
            "shallow_thinker": self.shallow_thinker,
            "deep_thinker": self.deep_thinker,
            "google_thinking_level": self.google_thinking_level,
            "openai_reasoning_effort": self.openai_reasoning_effort,
            "anthropic_effort": self.anthropic_effort,
            "config": self.config,
        }

    def write(self) -> Path:
        self.ensure_directories()
        self.request_file.write_text(
            json.dumps(self.to_dict(), indent=2),
            encoding="utf-8",
        )
        return self.request_file

    @classmethod
    def from_file(cls, path: str | Path) -> "AnalysisRunRequest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**payload)
