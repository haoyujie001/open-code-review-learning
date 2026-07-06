from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.git_tools import ensure_git_repo, get_changed_files
from tools.ocr_tools import load_review_json, run_ocr_review
from tools.report_tools import generate_markdown_report, save_markdown_report


@dataclass
class AgentState:
    repo_dir: Path
    output_dir: Path
    review_json_path: Path
    review_report_path: Path
    changed_files: list[str] = field(default_factory=list)
    review_data: dict[str, Any] = field(default_factory=dict)


def run_workflow(
    repo_dir: str | Path,
    output_dir: str | Path = "outputs",
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    timeout_seconds: int = 900,
    use_existing_json: str | Path | None = None,
) -> AgentState:
    repo_root = ensure_git_repo(repo_dir)
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = repo_root / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    state = AgentState(
        repo_dir=repo_root,
        output_dir=out_dir,
        review_json_path=out_dir / "review-result.json",
        review_report_path=out_dir / "review-report.md",
    )

    state.changed_files = get_changed_files(repo_root)

    if use_existing_json:
        state.review_data = load_review_json(use_existing_json)
        state.review_json_path.write_text(
            json.dumps(state.review_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    elif not state.changed_files:
        state.review_data = {
            "status": "skipped",
            "message": "No Git changes detected by the wrapper.",
            "tool_calls": {"total": 0, "by_tool": {}},
            "comments": [],
        }
        state.review_json_path.write_text(
            "{\n"
            '  "status": "skipped",\n'
            '  "message": "No Git changes detected by the wrapper.",\n'
            '  "tool_calls": {"total": 0, "by_tool": {}},\n'
            '  "comments": []\n'
            "}\n",
            encoding="utf-8",
        )
    else:
        state.review_data = run_ocr_review(
            repo_dir=repo_root,
            output_path=state.review_json_path,
            ocr_bin=ocr_bin,
            excludes=excludes or ["outputs/**"],
            timeout_seconds=timeout_seconds,
        )

    markdown = generate_markdown_report(state.review_data, changed_files=state.changed_files)
    save_markdown_report(markdown, state.review_report_path)
    return state


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the OpenCodeReview Agent MVP workflow.")
    parser.add_argument("--repo", default=".", help="Target Git repository. Defaults to current directory.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for JSON and Markdown outputs.")
    parser.add_argument("--ocr-bin", default="ocr", help="OpenCodeReview executable name or path.")
    parser.add_argument(
        "--exclude",
        action="append",
        default=["outputs/**"],
        help="Pattern passed to OCR --exclude. Can be repeated.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=900, help="OCR command timeout in seconds.")
    parser.add_argument(
        "--use-existing-json",
        help="Skip OCR and generate a report from an existing OCR JSON file.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    state = run_workflow(
        repo_dir=args.repo,
        output_dir=args.output_dir,
        ocr_bin=args.ocr_bin,
        excludes=args.exclude,
        timeout_seconds=args.timeout_seconds,
        use_existing_json=args.use_existing_json,
    )

    print("Code Review Agent MVP finished.")
    print(f"Repo: {state.repo_dir}")
    print(f"Changed files: {len(state.changed_files)}")
    print(f"JSON: {state.review_json_path}")
    print(f"Report: {state.review_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
