# Open Code Review Agent - S10 LangGraph Workflow

This version upgrades the S09 sequential script into a LangGraph workflow.

Workflow:

```text
START
  -> check_git_changes
  -> route: run review or skip review
  -> run_ocr_review / build_skipped_review
  -> classify_risk
  -> generate_report
  -> save_history
  -> END
```

## What changed in S10

- Added `state.py` to define the shared `AgentState`.
- Added `nodes/` to split the workflow into small graph nodes.
- Added LangGraph orchestration in `agent_graph.py`.
- Kept deterministic tools in `tools/`.
- Added review history archiving under `outputs/history/<timestamp>/`.
- Kept `--use-existing-json` so the workflow can be tested without calling the LLM every time.

## Install

```powershell
pip install -r requirements.txt
```

If your default Python environment is old or shared, create a virtual environment first.

## Run with an existing OCR JSON

```powershell
python -B agent_graph.py `
  --repo D:\agent\open-code-review-main\ocr-practice-demo `
  --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

## Run real OCR review

```powershell
python -B agent_graph.py `
  --repo D:\agent\open-code-review-main\ocr-practice-demo `
  --ocr-bin C:\Users\ad\AppData\Roaming\npm\ocr.cmd `
  --exclude outputs/** `
  --exclude outputs-review-result.json `
  --exclude s09/** `
  --exclude s10/**
```

## Output

```text
outputs/
  review-result.json
  review-report.md
  history/
    20260708-153000/
      review-result.json
      review-report.md
      run-metadata.json
```
