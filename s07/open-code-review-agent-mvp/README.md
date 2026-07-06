# Open Code Review Agent MVP

This project is a small agent workflow wrapper around Alibaba OpenCodeReview.

OpenCodeReview performs the AI code review. This project coordinates the workflow:

```text
Git changes
  -> run OpenCodeReview
  -> parse JSON
  -> generate Markdown report
```

## Features

- Detect whether the target directory is a Git repository.
- Detect changed files before running the LLM review.
- Run `ocr review --format json`.
- Save structured results to `outputs/review-result.json`.
- Generate a readable Markdown report at `outputs/review-report.md`.
- Preserve `stdout`, `stderr`, and exit-code handling around the OCR CLI.

## Requirements

- Python 3.10+
- Git
- OpenCodeReview CLI available as `ocr`
- A configured OpenCodeReview LLM provider

Check OCR first:

```powershell
ocr llm test
```

## Quick Start

Run the workflow in the current Git repository:

```powershell
python agent_graph.py
```

Run against another repository:

```powershell
python agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo
```

Use an existing JSON file and only generate the Markdown report:

```powershell
python agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

Exclude generated output from OCR:

```powershell
python agent_graph.py --exclude outputs/** --exclude *.review.json
```

## Project Structure

```text
open-code-review-agent-mvp
├── agent_graph.py
├── tools
│   ├── __init__.py
│   ├── git_tools.py
│   ├── ocr_tools.py
│   └── report_tools.py
├── outputs
│   ├── review-result.json
│   └── review-report.md
├── README.md
├── requirements.txt
└── .gitignore
```

## Design

The MVP keeps OpenCodeReview as the review backend.

```text
agent_graph.py
  -> git_tools.py
  -> ocr_tools.py
  -> report_tools.py
```

Later versions can replace the linear workflow with LangGraph, add risk classification, store history, and publish GitHub PR comments.

## Notes

Generated files should not be reviewed again. Keep `outputs/` in `.gitignore` or pass `--exclude outputs/**` when running OCR.
