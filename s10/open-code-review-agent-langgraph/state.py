from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


DEFAULT_EXCLUDES = [
    "outputs/**",
    "*.review.json",
    "*.review.md",
    "outputs-review-result.json",
    "s09/**",
    "s10/**",
]

SEVERITY_ORDER = ["Critical", "Warning", "Suggestion"]


class AgentState(TypedDict, total=False):
    repo_dir: str
    output_dir: str
    review_json_path: str
    review_report_path: str
    history_dir: str
    ocr_bin: str
    excludes: list[str]
    timeout_seconds: int
    use_existing_json: str | None
    raw_changed_files: list[str]
    changed_files: list[str]
    has_changes: bool
    review_data: dict[str, Any]
    risk_summary: dict[str, int]
    report_markdown: str
    history_files: dict[str, str]
    trace: list[dict[str, Any]]


def add_trace(
    state: AgentState,
    node: str,
    message: str,
    **data: Any,
) -> list[dict[str, Any]]:
    trace = list(state.get("trace") or [])
    event: dict[str, Any] = {
        "node": node,
        "message": message,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if data:
        event["data"] = data
    trace.append(event)
    return trace
