from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from state import AgentState, add_trace


def save_history_node(state: AgentState) -> AgentState:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    history_root = Path(state["history_dir"])
    run_dir = history_root / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    review_json_path = Path(state["review_json_path"])
    review_report_path = Path(state["review_report_path"])
    history_json = run_dir / "review-result.json"
    history_report = run_dir / "review-report.md"
    metadata_path = run_dir / "run-metadata.json"

    if review_json_path.exists():
        shutil.copy2(review_json_path, history_json)
    if review_report_path.exists():
        shutil.copy2(review_report_path, history_report)

    history_files = {
        "directory": str(run_dir),
        "json": str(history_json),
        "report": str(history_report),
        "metadata": str(metadata_path),
    }
    trace = add_trace(state, "save_history", "Archived review outputs.", directory=str(run_dir))

    metadata = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repo_dir": state.get("repo_dir"),
        "changed_files": state.get("changed_files") or [],
        "raw_changed_files": state.get("raw_changed_files") or [],
        "risk_summary": state.get("risk_summary") or {},
        "history_files": history_files,
        "trace": trace,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "history_files": history_files,
        "trace": trace,
    }
