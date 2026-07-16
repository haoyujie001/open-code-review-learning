from __future__ import annotations

from state import AgentState, add_trace
from tools.report_tools import generate_markdown_report, save_markdown_report


def generate_report_node(state: AgentState) -> AgentState:
    markdown = generate_markdown_report(
        state.get("review_data") or {},
        changed_files=state.get("changed_files") or [],
        trace=state.get("trace") or [],
    )
    report_path = save_markdown_report(markdown, state["review_report_path"])

    return {
        "report_markdown": markdown,
        "review_report_path": str(report_path),
        "trace": add_trace(
            state,
            "generate_report",
            "Generated Markdown review report.",
            path=str(report_path),
        ),
    }
