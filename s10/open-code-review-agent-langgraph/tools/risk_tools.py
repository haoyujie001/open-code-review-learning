from __future__ import annotations

from copy import deepcopy
from typing import Any


SEVERITY_ORDER = ["Critical", "Warning", "Suggestion"]

CRITICAL_KEYWORDS = [
    "sql injection",
    "command injection",
    "remote code execution",
    "rce",
    "xss",
    "csrf",
    "hardcoded secret",
    "secret key",
    "api key",
    "password",
    "token",
    "authentication",
    "authorization",
    "permission",
    "privilege",
    "prepared statement",
    "parameterized",
    "drop table",
]

WARNING_KEYWORDS = [
    "error handling",
    "exception",
    "null",
    "undefined",
    "validation",
    "not exported",
    "missing",
    "async",
    "timeout",
    "resource leak",
    "race condition",
]

SUGGESTION_KEYWORDS = [
    "style",
    "readability",
    "naming",
    "comment",
    "documentation",
    "refactor",
    "simplify",
]


def classify_review_risks(review_data: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(review_data)
    comments = result.get("comments") or []
    classified_comments = [classify_comment(comment) for comment in comments]
    result["comments"] = classified_comments
    result["risk_summary"] = summarize_risks(classified_comments)
    return result


def classify_comment(comment: dict[str, Any]) -> dict[str, Any]:
    result = dict(comment)
    text = build_comment_text(comment)

    severity, reason, matched_keywords = match_severity(text)
    result["severity"] = severity
    result["risk_reason"] = reason
    result["matched_keywords"] = matched_keywords
    return result


def build_comment_text(comment: dict[str, Any]) -> str:
    parts = [
        str(comment.get("content", "")),
        str(comment.get("existing_code", "")),
        str(comment.get("suggestion_code", "")),
    ]
    return " ".join(parts).lower()


def match_severity(text: str) -> tuple[str, str, list[str]]:
    matched = find_keywords(text, CRITICAL_KEYWORDS)
    if matched:
        return "Critical", "Security-sensitive or data-risk keyword matched.", matched

    matched = find_keywords(text, WARNING_KEYWORDS)
    if matched:
        return "Warning", "Reliability, correctness, or maintainability keyword matched.", matched

    matched = find_keywords(text, SUGGESTION_KEYWORDS)
    if matched:
        return "Suggestion", "Code quality or readability keyword matched.", matched

    return "Suggestion", "No high-risk keyword matched; treat as a general suggestion.", []


def find_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def summarize_risks(comments: list[dict[str, Any]]) -> dict[str, int]:
    summary = {severity: 0 for severity in SEVERITY_ORDER}
    for comment in comments:
        severity = comment.get("severity", "Suggestion")
        if severity not in summary:
            severity = "Suggestion"
        summary[severity] += 1
    return summary
