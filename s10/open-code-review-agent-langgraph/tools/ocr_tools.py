from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


class OcrCommandError(RuntimeError):
    """Raised when the OpenCodeReview CLI fails."""

    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = f"OpenCodeReview command failed ({returncode}): {' '.join(command)}"
        if stderr.strip():
            message += f"\n{stderr.strip()}"
        super().__init__(message)


def resolve_ocr_executable(ocr_bin: str = "ocr") -> str:
    candidate = Path(ocr_bin)
    if candidate.exists():
        return str(candidate)

    if os.name == "nt" and not Path(ocr_bin).suffix:
        cmd_path = shutil.which(f"{ocr_bin}.cmd")
        if cmd_path:
            return cmd_path

    resolved = shutil.which(ocr_bin)
    if resolved:
        return resolved

    raise RuntimeError(
        f"OpenCodeReview CLI '{ocr_bin}' was not found in PATH. "
        "Install it or pass --ocr-bin with the executable path."
    )


def build_ocr_review_command(
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [resolve_ocr_executable(ocr_bin), "review", "--format", "json"]

    normalized_excludes = [item for item in (excludes or []) if item]
    if normalized_excludes:
        command.extend(["--exclude", ",".join(normalized_excludes)])

    if extra_args:
        command.extend(extra_args)

    return command


def run_ocr_review(
    repo_dir: str | Path,
    output_path: str | Path,
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    timeout_seconds: int = 900,
    extra_args: list[str] | None = None,
) -> dict[str, Any]:
    repo_path = Path(repo_dir).resolve()
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    command = build_ocr_review_command(ocr_bin=ocr_bin, excludes=excludes, extra_args=extra_args)
    result = subprocess.run(
        command,
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )

    if result.returncode != 0:
        error_file = output_file.with_suffix(".stderr.txt")
        error_file.write_text(result.stderr, encoding="utf-8")
        raise OcrCommandError(command, result.returncode, result.stdout, result.stderr)

    output_file.write_text(result.stdout, encoding="utf-8")
    return parse_review_json_text(result.stdout)


def load_review_json(path: str | Path) -> dict[str, Any]:
    return parse_review_json_text(read_text_with_fallback(path))


def read_text_with_fallback(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", data, 0, min(len(data), 1), "unsupported text encoding")


def parse_review_json_text(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text.lstrip("\ufeff"))
    except json.JSONDecodeError as exc:
        snippet = text[:500].strip()
        raise ValueError(f"OCR output is not valid JSON: {exc}\nOutput starts with:\n{snippet}") from exc

    if not isinstance(data, dict):
        raise ValueError("OCR JSON output must be a JSON object")

    return data
