from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nodes.git_node import check_git_changes, route_after_git_check
from nodes.history_node import save_history_node
from nodes.ocr_node import build_skipped_review_node, run_ocr_review_node
from nodes.report_node import generate_report_node
from nodes.risk_node import classify_risk_node
from state import AgentState, DEFAULT_EXCLUDES

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:
    END = START = StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_IMPORT_ERROR = exc
else:
    LANGGRAPH_IMPORT_ERROR = None


def build_graph():
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed. Run `pip install -r requirements.txt` "
            "inside the S10 project directory."
        ) from LANGGRAPH_IMPORT_ERROR

    graph = StateGraph(AgentState)
    graph.add_node("check_git_changes", check_git_changes)
    graph.add_node("run_ocr_review", run_ocr_review_node)
    graph.add_node("build_skipped_review", build_skipped_review_node)
    graph.add_node("classify_risk", classify_risk_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("save_history", save_history_node)

    graph.add_edge(START, "check_git_changes")
    graph.add_conditional_edges(
        "check_git_changes",
        route_after_git_check,
        {
            "review": "run_ocr_review",
            "skip": "build_skipped_review",
        },
    )
    graph.add_edge("run_ocr_review", "classify_risk")
    graph.add_edge("build_skipped_review", "classify_risk")
    graph.add_edge("classify_risk", "generate_report")
    graph.add_edge("generate_report", "save_history")
    graph.add_edge("save_history", END)
    return graph.compile()


def run_workflow(
    repo_dir: str | Path,
    output_dir: str | Path = "outputs",
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    timeout_seconds: int = 900,
    use_existing_json: str | Path | None = None,
) -> AgentState:
    initial_state: AgentState = {
        "repo_dir": str(repo_dir),
        "output_dir": str(output_dir),
        "ocr_bin": ocr_bin,
        "excludes": excludes or list(DEFAULT_EXCLUDES),
        "timeout_seconds": timeout_seconds,
        "use_existing_json": str(use_existing_json) if use_existing_json else None,
        "trace": [],
    }
    app = build_graph()
    return app.invoke(initial_state)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the S10 LangGraph Code Review Agent workflow.")
    parser.add_argument("--repo", default=".", help="Target Git repository. Defaults to current directory.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for JSON and Markdown outputs.")
    parser.add_argument("--ocr-bin", default="ocr", help="OpenCodeReview executable name or path.")
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="Pattern passed to OCR --exclude. Can be repeated.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=900, help="OCR command timeout in seconds.")
    parser.add_argument(
        "--use-existing-json",
        help="Skip OCR and generate a report from an existing OCR JSON file.",
    )
    parser.add_argument("--print-trace", action="store_true", help="Print LangGraph node trace after running.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        state = run_workflow(
            repo_dir=args.repo,
            output_dir=args.output_dir,
            ocr_bin=args.ocr_bin,
            excludes=args.exclude,
            timeout_seconds=args.timeout_seconds,
            use_existing_json=args.use_existing_json,
        )
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    print("Code Review Agent LangGraph workflow finished.")
    print(f"Repo: {state.get('repo_dir')}")
    print(f"Changed files: {len(state.get('changed_files') or [])}")
    print(f"Risk summary: {state.get('risk_summary')}")
    print(f"JSON: {state.get('review_json_path')}")
    print(f"Report: {state.get('review_report_path')}")

    history_files = state.get("history_files") or {}
    if history_files:
        print(f"History: {history_files.get('directory')}")

    if args.print_trace:
        for event in state.get("trace") or []:
            print(f"- [{event.get('node')}] {event.get('message')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
