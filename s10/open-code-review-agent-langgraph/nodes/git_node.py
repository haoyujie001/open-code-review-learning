from __future__ import annotations

from pathlib import Path

from state import AgentState, DEFAULT_EXCLUDES, add_trace
from tools.git_tools import ensure_git_repo, filter_paths, get_changed_files


def check_git_changes(state: AgentState) -> AgentState:
    repo_root = ensure_git_repo(state.get("repo_dir", "."))
    excludes = state.get("excludes") or list(DEFAULT_EXCLUDES)

    output_dir = Path(state.get("output_dir", "outputs"))
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_changed_files = get_changed_files(repo_root)
    changed_files = filter_paths(raw_changed_files, excludes)

    next_state: AgentState = {
        "repo_dir": str(repo_root),
        "output_dir": str(output_dir),
        "review_json_path": str(output_dir / "review-result.json"),
        "review_report_path": str(output_dir / "review-report.md"),
        "history_dir": str(output_dir / "history"),
        "raw_changed_files": raw_changed_files,
        "changed_files": changed_files,
        "has_changes": bool(changed_files),
        "trace": add_trace(
            state,
            "check_git_changes",
            "Collected Git changed files.",
            raw_count=len(raw_changed_files),
            reviewed_count=len(changed_files),
        ),
    }
    return next_state


def route_after_git_check(state: AgentState) -> str:
    if state.get("use_existing_json"):
        return "review"
    if state.get("has_changes"):
        return "review"
    return "skip"
