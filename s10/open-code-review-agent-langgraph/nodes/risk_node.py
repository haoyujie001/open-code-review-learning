from __future__ import annotations

import json
from pathlib import Path

from state import AgentState, add_trace
from tools.risk_tools import classify_review_risks


def classify_risk_node(state: AgentState) -> AgentState:
    review_data = classify_review_risks(state.get("review_data") or {})
    risk_summary = review_data.get("risk_summary") or {}

    review_json_path = Path(state["review_json_path"])
    review_json_path.parent.mkdir(parents=True, exist_ok=True)
    review_json_path.write_text(
        json.dumps(review_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "review_data": review_data,
        "risk_summary": risk_summary,
        "trace": add_trace(
            state,
            "classify_risk",
            "Classified review comments by risk.",
            risk_summary=risk_summary,
        ),
    }
