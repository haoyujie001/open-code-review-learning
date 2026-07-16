from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


SEVERITY_ORDER = ["Critical", "Warning", "Suggestion"]


def generate_markdown_report(
    review_data: dict[str, Any],
    changed_files: list[str] | None = None,
    trace: list[dict[str, Any]] | None = None,
) -> str:
    status = review_data.get("status", "unknown")
    message = review_data.get("message", "")
    summary = review_data.get("summary") or {}
    tool_calls = review_data.get("tool_calls") or {}
    comments = review_data.get("comments") or []
    warnings = review_data.get("warnings") or []
    project_summary = review_data.get("project_summary", "")
    risk_summary = normalized_risk_summary(review_data.get("risk_summary"), comments)

    lines: list[str] = [
        "# AI Code Review Report",
        "",
        f"- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Status: {status}",
    ]

    if message:
        lines.append(f"- Message: {message}")

    lines.extend(["", "## Summary", ""])
    if summary:
        lines.extend(
            [
                f"- Files reviewed: {summary.get('files_reviewed', 0)}",
                f"- Comments: {summary.get('comments', len(comments))}",
                f"- Total tokens: {summary.get('total_tokens', 0)}",
                f"- Input tokens: {summary.get('input_tokens', 0)}",
                f"- Output tokens: {summary.get('output_tokens', 0)}",
                f"- Cache read tokens: {summary.get('cache_read_tokens', 0)}",
                f"- Cache write tokens: {summary.get('cache_write_tokens', 0)}",
                f"- Elapsed: {summary.get('elapsed', 'unknown')}",
            ]
        )
    else:
        lines.append("- No summary returned.")

    lines.extend(["", "## Risk Summary", "", "| Severity | Count |", "|---|---:|"])
    for severity in SEVERITY_ORDER:
        lines.append(f"| {severity} | {risk_summary.get(severity, 0)} |")

    if changed_files:
        lines.extend(["", "## Changed Files", ""])
        lines.extend(f"- `{path}`" for path in changed_files)

    lines.extend(["", "## Tool Calls", ""])
    by_tool = tool_calls.get("by_tool") or {}
    if by_tool:
        lines.extend(["| Tool | Count |", "|---|---:|"])
        for name, count in sorted(by_tool.items(), key=lambda item: (-int(item[1]), item[0])):
            lines.append(f"| `{name}` | {count} |")
    else:
        lines.append("- No tool calls recorded.")

    if trace:
        lines.extend(["", "## Workflow Trace", "", "| Node | Message |", "|---|---|"])
        for event in trace:
            node = event.get("node", "")
            event_message = event.get("message", "")
            lines.append(f"| `{node}` | {event_message} |")

    if warnings:
        lines.extend(["", "## Warnings", ""])
        for warning in warnings:
            if isinstance(warning, dict):
                warning_type = warning.get("type", "warning")
                warning_file = warning.get("file", "")
                warning_message = warning.get("message", "")
                location = f" `{warning_file}`" if warning_file else ""
                lines.append(f"- **{warning_type}**{location}: {warning_message}")
            else:
                lines.append(f"- {warning}")

    if project_summary:
        lines.extend(["", "## Project Summary", "", str(project_summary)])

    lines.extend(["", "## Findings", ""])
    if not comments:
        lines.append("- No review comments.")
    else:
        for index, comment in enumerate(comments, start=1):
            lines.extend(render_comment(index, comment))

    lines.append("")
    return "\n".join(lines)


def normalized_risk_summary(
    risk_summary: dict[str, int] | None,
    comments: list[dict[str, Any]],
) -> dict[str, int]:
    if risk_summary:
        return {severity: int(risk_summary.get(severity, 0)) for severity in SEVERITY_ORDER}

    summary = {severity: 0 for severity in SEVERITY_ORDER}
    for comment in comments:
        severity = comment.get("severity", "Suggestion")
        if severity not in summary:
            severity = "Suggestion"
        summary[severity] += 1
    return summary


def render_comment(index: int, comment: dict[str, Any]) -> list[str]:
    path = comment.get("path", "unknown")
    start_line = comment.get("start_line", 0)
    end_line = comment.get("end_line", start_line)
    severity = comment.get("severity", "Suggestion")
    risk_reason = comment.get("risk_reason", "")
    matched_keywords = comment.get("matched_keywords") or []
    content = comment.get("content", "").strip() or "(empty comment)"
    existing_code = comment.get("existing_code", "")
    suggestion_code = comment.get("suggestion_code", "")

    lines = [
        f"### {index}. [{severity}] `{path}:{start_line}-{end_line}`",
        "",
    ]

    if risk_reason:
        lines.extend(["**Risk Reason**", "", risk_reason, ""])

    if matched_keywords:
        keyword_text = ", ".join(f"`{keyword}`" for keyword in matched_keywords[:8])
        lines.extend(["**Matched Keywords**", "", keyword_text, ""])

    lines.extend(["**Issue**", "", content, ""])

    if existing_code:
        lines.extend(["**Existing Code**", "", fenced_code(existing_code, language_for_path(path)), ""])

    if suggestion_code:
        lines.extend(["**Suggestion**", "", fenced_code(suggestion_code, language_for_path(path)), ""])

    return lines


def fenced_code(code: str, language: str = "") -> str:
    fence = "```"
    if "```" in code:
        fence = "````"
    return f"{fence}{language}\n{code.rstrip()}\n{fence}"


def language_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".js": "js",
        ".jsx": "jsx",
        ".ts": "ts",
        ".tsx": "tsx",
        ".py": "python",
        ".go": "go",
        ".java": "java",
        ".json": "json",
        ".md": "markdown",
        ".yml": "yaml",
        ".yaml": "yaml",
    }.get(suffix, "")


def save_markdown_report(markdown: str, output_path: str | Path) -> Path:
    path = Path(output_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return path
