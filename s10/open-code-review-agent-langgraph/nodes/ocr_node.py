from __future__ import annotations

from state import AgentState, add_trace
from tools.ocr_tools import load_review_json, run_ocr_review


def run_ocr_review_node(state: AgentState) -> AgentState:
    use_existing_json = state.get("use_existing_json")
    if use_existing_json:
        review_data = load_review_json(use_existing_json)
        message = "Loaded existing OCR JSON."
    else:
        review_data = run_ocr_review(
            repo_dir=state["repo_dir"],
            output_path=state["review_json_path"],
            ocr_bin=state.get("ocr_bin", "ocr"),
            excludes=state.get("excludes"),
            timeout_seconds=int(state.get("timeout_seconds", 900)),
        )
        message = "Ran OpenCodeReview CLI."

    return {
        "review_data": review_data,
        "trace": add_trace(
            state,
            "run_ocr_review",
            message,
            comments=len(review_data.get("comments") or []),
        ),
    }


def build_skipped_review_node(state: AgentState) -> AgentState:
    review_data = {
        "status": "skipped",
        "message": "No Git changes detected by the LangGraph wrapper.",
        "summary": {
            "files_reviewed": 0,
            "comments": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "elapsed": "0s",
        },
        "tool_calls": {"total": 0, "by_tool": {}},
        "comments": [],
    }
    return {
        "review_data": review_data,
        "trace": add_trace(state, "build_skipped_review", "Built skipped review result."),
    }
