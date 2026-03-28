from __future__ import annotations

import json
import time
from functools import wraps
from pathlib import Path

import typer
from rich.live import Live

from cli.main import (
    MessageBuffer,
    classify_message_type,
    create_layout,
    get_retry_delay_seconds,
    update_analyst_statuses,
    update_display,
    update_research_team_status,
)
from cli.runtime import AnalysisRunRequest
from cli.stats_handler import StatsCallbackHandler
from tradingagents.graph.trading_graph import TradingAgentsGraph


app = typer.Typer(
    name="TradingAgentsWorker",
    help="Run one isolated TradingAgents analysis request.",
    add_completion=False,
)


def run_analysis_request(request: AnalysisRunRequest) -> dict:
    """Execute one analysis request in an isolated process."""
    request.ensure_directories()

    stats_handler = StatsCallbackHandler()
    message_buffer = MessageBuffer()
    message_buffer.init_for_analysis(request.analyst_keys)

    start_time = time.time()
    report_dir = request.report_dir
    log_file = request.log_file
    progress_log_file = request.run_dir / "progress_diagnostics.log"

    def append_progress_diagnostic(message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(progress_log_file, "a", encoding="utf-8") as file_handle:
            file_handle.write(f"{timestamp} {message}\n")

    def create_graph() -> TradingAgentsGraph:
        return TradingAgentsGraph(
            request.analyst_keys,
            config=request.config,
            debug=True,
            callbacks=[stats_handler],
        )

    def save_message_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, message_type, content = obj.messages[-1]
            content = str(content).replace("\n", " ")
            with open(log_file, "a", encoding="utf-8") as file_handle:
                file_handle.write(f"{timestamp} [{message_type}] {content}\n")

        return wrapper

    def save_tool_call_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, tool_name, args = obj.tool_calls[-1]
            args_str = ", ".join(f"{key}={value}" for key, value in args.items())
            with open(log_file, "a", encoding="utf-8") as file_handle:
                file_handle.write(
                    f"{timestamp} [Tool Call] {tool_name}({args_str})\n"
                )

        return wrapper

    def save_report_section_decorator(obj, func_name):
        func = getattr(obj, func_name)

        @wraps(func)
        def wrapper(section_name, content):
            func(section_name, content)
            if section_name in obj.report_sections:
                report_content = obj.report_sections[section_name]
                if report_content:
                    file_name = f"{section_name}.md"
                    if isinstance(report_content, list):
                        text = "\n".join(str(item) for item in report_content)
                    else:
                        text = str(report_content)
                    (report_dir / file_name).write_text(text, encoding="utf-8")

        return wrapper

    message_buffer.add_message = save_message_decorator(message_buffer, "add_message")
    message_buffer.add_tool_call = save_tool_call_decorator(
        message_buffer,
        "add_tool_call",
    )
    message_buffer.update_report_section = save_report_section_decorator(
        message_buffer,
        "update_report_section",
    )

    layout = create_layout()
    final_state = None

    with Live(layout, refresh_per_second=4):
        update_display(
            layout,
            message_buffer,
            stats_handler=stats_handler,
            start_time=start_time,
        )

        attempt = 0
        while True:
            attempt += 1
            message_buffer.init_for_analysis(request.analyst_keys)
            message_buffer.add_message("System", f"Run id: {request.run_id}")
            message_buffer.add_message("System", f"Selected ticker: {request.ticker}")
            message_buffer.add_message(
                "System",
                f"Analysis date: {request.analysis_date}",
            )
            message_buffer.add_message(
                "System",
                f"Selected analysts: {', '.join(request.analyst_labels)}",
            )
            message_buffer.add_message(
                "System",
                " ".join(
                    [
                        f"Run {request.run_id}",
                        f"attempt {attempt}",
                        f"using provider {request.llm_provider}",
                        f"@ {request.backend_url}",
                    ]
                ),
            )
            append_progress_diagnostic(
                " ".join(
                    [
                        f"attempt={attempt}",
                        f"ticker={request.ticker}",
                        f"provider={request.llm_provider}",
                        f"max_debate_rounds={request.config.get('max_debate_rounds')}",
                        "expected_research_turns="
                        f"{2 * request.config.get('max_debate_rounds', 0)}",
                        "max_risk_discuss_rounds="
                        f"{request.config.get('max_risk_discuss_rounds')}",
                        "expected_risk_turns="
                        f"{3 * request.config.get('max_risk_discuss_rounds', 0)}",
                    ]
                )
            )
            update_display(
                layout,
                message_buffer,
                stats_handler=stats_handler,
                start_time=start_time,
            )

            first_analyst = f"{request.analyst_labels[0].capitalize()} Analyst"
            message_buffer.update_agent_status(first_analyst, "in_progress")
            update_display(
                layout,
                message_buffer,
                f"Analyzing {request.ticker} on {request.analysis_date}...",
                stats_handler=stats_handler,
                start_time=start_time,
            )

            try:
                graph = create_graph()
                init_agent_state = graph.propagator.create_initial_state(
                    request.ticker,
                    request.analysis_date,
                )
                args = graph.propagator.get_graph_args(callbacks=[stats_handler])

                trace = []
                chunk_index = 0
                last_chunk_at = time.time()
                last_invest_count = 0
                last_risk_count = 0
                last_llm_calls = 0
                last_tool_calls = 0
                for chunk in graph.graph.stream(init_agent_state, **args):
                    chunk_index += 1
                    now = time.time()
                    seconds_since_last_chunk = now - last_chunk_at
                    last_chunk_at = now
                    invest_count = chunk.get("investment_debate_state", {}).get(
                        "count",
                        last_invest_count,
                    )
                    risk_count = chunk.get("risk_debate_state", {}).get(
                        "count",
                        last_risk_count,
                    )
                    llm_delta = stats_handler.llm_calls - last_llm_calls
                    tool_delta = stats_handler.tool_calls - last_tool_calls
                    append_progress_diagnostic(
                        " ".join(
                            [
                                f"chunk={chunk_index}",
                                f"dt={seconds_since_last_chunk:.1f}s",
                                f"llm_total={stats_handler.llm_calls}",
                                f"llm_delta={llm_delta}",
                                f"tool_total={stats_handler.tool_calls}",
                                f"tool_delta={tool_delta}",
                                f"invest_count={invest_count}",
                                f"risk_count={risk_count}",
                            ]
                        )
                    )
                    if (
                        invest_count != last_invest_count
                        or risk_count != last_risk_count
                        or seconds_since_last_chunk >= 20
                    ):
                        stage_bits = [f"chunk {chunk_index}"]
                        if invest_count != last_invest_count:
                            stage_bits.append(
                                "research debate turn "
                                f"{invest_count}/"
                                f"{2 * request.config.get('max_debate_rounds', 0)}"
                            )
                        if risk_count != last_risk_count:
                            stage_bits.append(
                                "risk debate turn "
                                f"{risk_count}/"
                                f"{3 * request.config.get('max_risk_discuss_rounds', 0)}"
                            )
                        if seconds_since_last_chunk >= 20:
                            stage_bits.append(
                                f"last graph step took {seconds_since_last_chunk:.1f}s"
                            )
                        stage_bits.append(
                            f"LLM {stats_handler.llm_calls}, tools {stats_handler.tool_calls}"
                        )
                        message_buffer.add_message(
                            "System",
                            "Progress checkpoint: " + ", ".join(stage_bits),
                        )
                    last_invest_count = invest_count
                    last_risk_count = risk_count
                    last_llm_calls = stats_handler.llm_calls
                    last_tool_calls = stats_handler.tool_calls
                    if len(chunk["messages"]) > 0:
                        last_message = chunk["messages"][-1]
                        msg_id = getattr(last_message, "id", None)
                        if msg_id != message_buffer._last_message_id:
                            message_buffer._last_message_id = msg_id
                            msg_type, content = classify_message_type(last_message)
                            if content and content.strip():
                                message_buffer.add_message(msg_type, content)
                            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                                for tool_call in last_message.tool_calls:
                                    if isinstance(tool_call, dict):
                                        message_buffer.add_tool_call(
                                            tool_call["name"],
                                            tool_call["args"],
                                        )
                                    else:
                                        message_buffer.add_tool_call(
                                            tool_call.name,
                                            tool_call.args,
                                        )

                    update_analyst_statuses(message_buffer, chunk)

                    if chunk.get("investment_debate_state"):
                        debate_state = chunk["investment_debate_state"]
                        bull_hist = debate_state.get("bull_history", "").strip()
                        bear_hist = debate_state.get("bear_history", "").strip()
                        judge = debate_state.get("judge_decision", "").strip()
                        if bull_hist or bear_hist:
                            update_research_team_status(message_buffer, "in_progress")
                        if bull_hist:
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"### Bull Researcher Analysis\n{bull_hist}",
                            )
                        if bear_hist:
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"### Bear Researcher Analysis\n{bear_hist}",
                            )
                        if judge:
                            message_buffer.update_report_section(
                                "investment_plan",
                                f"### Research Manager Decision\n{judge}",
                            )
                            update_research_team_status(
                                message_buffer,
                                "completed",
                            )
                            message_buffer.update_agent_status(
                                "Trader",
                                "in_progress",
                            )

                    if chunk.get("trader_investment_plan"):
                        message_buffer.update_report_section(
                            "trader_investment_plan",
                            chunk["trader_investment_plan"],
                        )
                        if message_buffer.agent_status.get("Trader") != "completed":
                            message_buffer.update_agent_status("Trader", "completed")
                            message_buffer.update_agent_status(
                                "Aggressive Analyst",
                                "in_progress",
                            )

                    if chunk.get("risk_debate_state"):
                        risk_state = chunk["risk_debate_state"]
                        agg_hist = risk_state.get("aggressive_history", "").strip()
                        con_hist = risk_state.get("conservative_history", "").strip()
                        neu_hist = risk_state.get("neutral_history", "").strip()
                        judge = risk_state.get("judge_decision", "").strip()
                        if agg_hist:
                            if (
                                message_buffer.agent_status.get(
                                    "Aggressive Analyst"
                                )
                                != "completed"
                            ):
                                message_buffer.update_agent_status(
                                    "Aggressive Analyst",
                                    "in_progress",
                                )
                            message_buffer.update_report_section(
                                "final_trade_decision",
                                f"### Aggressive Analyst Analysis\n{agg_hist}",
                            )
                        if con_hist:
                            if (
                                message_buffer.agent_status.get(
                                    "Conservative Analyst"
                                )
                                != "completed"
                            ):
                                message_buffer.update_agent_status(
                                    "Conservative Analyst",
                                    "in_progress",
                                )
                            message_buffer.update_report_section(
                                "final_trade_decision",
                                f"### Conservative Analyst Analysis\n{con_hist}",
                            )
                        if neu_hist:
                            if (
                                message_buffer.agent_status.get("Neutral Analyst")
                                != "completed"
                            ):
                                message_buffer.update_agent_status(
                                    "Neutral Analyst",
                                    "in_progress",
                                )
                            message_buffer.update_report_section(
                                "final_trade_decision",
                                f"### Neutral Analyst Analysis\n{neu_hist}",
                            )
                        if judge:
                            if (
                                message_buffer.agent_status.get("Portfolio Manager")
                                != "completed"
                            ):
                                message_buffer.update_agent_status(
                                    "Portfolio Manager",
                                    "in_progress",
                                )
                                message_buffer.update_report_section(
                                    "final_trade_decision",
                                    f"### Portfolio Manager Decision\n{judge}",
                                )
                                message_buffer.update_agent_status(
                                    "Aggressive Analyst",
                                    "completed",
                                )
                                message_buffer.update_agent_status(
                                    "Conservative Analyst",
                                    "completed",
                                )
                                message_buffer.update_agent_status(
                                    "Neutral Analyst",
                                    "completed",
                                )
                                message_buffer.update_agent_status(
                                    "Portfolio Manager",
                                    "completed",
                                )

                    update_display(
                        layout,
                        message_buffer,
                        stats_handler=stats_handler,
                        start_time=start_time,
                    )
                    trace.append(chunk)

                final_state = trace[-1]
                append_progress_diagnostic(
                    " ".join(
                        [
                            "completed",
                            f"chunks={chunk_index}",
                            f"llm_total={stats_handler.llm_calls}",
                            f"tool_total={stats_handler.tool_calls}",
                            f"elapsed={time.time() - start_time:.1f}s",
                        ]
                    )
                )
                graph.process_signal(final_state["final_trade_decision"])
                for agent in message_buffer.agent_status:
                    message_buffer.update_agent_status(agent, "completed")
                message_buffer.add_message(
                    "System",
                    f"Completed analysis for {request.analysis_date}",
                )
                for section in message_buffer.report_sections.keys():
                    if section in final_state:
                        message_buffer.update_report_section(
                            section,
                            final_state[section],
                        )
                update_display(
                    layout,
                    message_buffer,
                    stats_handler=stats_handler,
                    start_time=start_time,
                )
                break
            except KeyboardInterrupt:
                message_buffer.add_message(
                    "System",
                    "Analysis interrupted by user.",
                )
                update_display(
                    layout,
                    message_buffer,
                    stats_handler=stats_handler,
                    start_time=start_time,
                )
                raise
            except Exception as exc:
                for agent, status in message_buffer.agent_status.items():
                    if status == "in_progress":
                        message_buffer.update_agent_status(agent, "error")
                delay_seconds = get_retry_delay_seconds(attempt)
                message_buffer.add_message(
                    "Error",
                    " ".join(
                        [
                            f"Attempt {attempt} failed.",
                            f"Provider: {request.llm_provider}.",
                            f"Base URL: {request.backend_url}.",
                            f"Error: {exc}",
                        ]
                    ),
                )
                message_buffer.add_message(
                    "System",
                    f"Retrying in {delay_seconds}s. Press Ctrl+C to stop.",
                )
                update_display(
                    layout,
                    message_buffer,
                    stats_handler=stats_handler,
                    start_time=start_time,
                )
                time.sleep(delay_seconds)

    if final_state is None:
        raise RuntimeError("Analysis did not produce a final state.")

    request.final_state_file.write_text(
        json.dumps(final_state, indent=2, default=str),
        encoding="utf-8",
    )

    return final_state


@app.command()
def run_request(request_file: str) -> None:
    """Run one serialized analysis request file."""
    request = AnalysisRunRequest.from_file(request_file)
    run_analysis_request(request)


if __name__ == "__main__":
    app()
