from __future__ import annotations

import subprocess
from pathlib import Path


class GitCommandError(RuntimeError):
    """Raised when a Git command fails."""

    def __init__(self, command: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = f"git command failed ({returncode}): {' '.join(command)}"
        if stderr.strip():
            message += f"\n{stderr.strip()}"
        super().__init__(message)


def run_git(repo_dir: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    repo_path = Path(repo_dir).resolve()
    command = ["git", "-C", str(repo_path), *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitCommandError(command, result.returncode, result.stdout, result.stderr)
    return result


def ensure_git_repo(repo_dir: str | Path) -> Path:
    repo_path = Path(repo_dir).resolve()
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if result.stdout.strip() != "true":
        raise RuntimeError(f"{repo_path} is not inside a Git work tree")
    root = run_git(repo_path, ["rev-parse", "--show-toplevel"]).stdout.strip()
    return Path(root).resolve()


def get_changed_files(repo_dir: str | Path) -> list[str]:
    result = run_git(repo_dir, ["status", "--porcelain"])
    files: list[str] = []

    for raw_line in result.stdout.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue

        # Porcelain format uses two status columns followed by a path.
        path = line[3:] if len(line) > 3 else ""
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        path = path.strip().strip('"')
        if path:
            files.append(path)

    return sorted(dict.fromkeys(files))


def has_changes(repo_dir: str | Path) -> bool:
    return bool(get_changed_files(repo_dir))


def get_diff_name_only(repo_dir: str | Path) -> list[str]:
    result = run_git(repo_dir, ["diff", "--name-only"])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
