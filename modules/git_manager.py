"""
Git operations and self-modification capability for JARVIS.

Git:
  - init, clone, add, commit, push, pull, create branch, status, log

Self-modification:
  - JARVIS can read its own source files
  - Ask the LLM to produce a modified version
  - Write the new version back to disk (with automatic backup)
  - Offer to restart itself so changes take effect

SAFETY: every self-modification makes a timestamped .bak backup first.
Nothing is ever applied without saving a rollback copy.
"""

import os
import subprocess
import datetime
import shutil
import sys

from config import BASE_DIR


# ─────────────────────────────────────────────
# Git helper
# ─────────────────────────────────────────────

class GitManager:
    def __init__(self):
        self._check_git_installed()

    def _check_git_installed(self):
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            raise EnvironmentError(
                "Git is not installed or not on PATH. "
                "Download it from https://git-scm.com/download/win"
            )

    def _run(self, args: list, cwd: str = None) -> str:
        """Run a git command and return its combined stdout+stderr."""
        cwd = cwd or os.getcwd()
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        out = (result.stdout + result.stderr).strip()
        return out or "(done)"

    # ── Repo creation ──────────────────────────────
    def init(self, path: str = ".") -> str:
        os.makedirs(path, exist_ok=True)
        return self._run(["init"], cwd=path)

    def create_repo(self, folder_name: str, base_path: str = None) -> str:
        """
        Creates a new local git repo in <base_path>/<folder_name>.
        base_path defaults to the user's home directory.
        """
        base = base_path or os.path.expanduser("~")
        repo_path = os.path.join(base, folder_name)
        os.makedirs(repo_path, exist_ok=True)
        out = self._run(["init"], cwd=repo_path)
        # write a starter README
        readme = os.path.join(repo_path, "README.md")
        if not os.path.exists(readme):
            with open(readme, "w") as f:
                f.write(f"# {folder_name}\n\nCreated by JARVIS.\n")
        self._run(["add", "."], cwd=repo_path)
        self._run(["commit", "-m", "Initial commit by JARVIS"], cwd=repo_path)
        return f"Created repo at {repo_path}.\n{out}"

    def clone(self, url: str, dest: str = None) -> str:
        args = ["clone", url]
        if dest:
            args.append(dest)
        return self._run(args)

    # ── Day-to-day operations ──────────────────────
    def status(self, cwd: str = ".") -> str:
        return self._run(["status", "--short"], cwd=cwd)

    def add_all(self, cwd: str = ".") -> str:
        return self._run(["add", "."], cwd=cwd)

    def commit(self, message: str, cwd: str = ".") -> str:
        self._run(["add", "."], cwd=cwd)
        return self._run(["commit", "-m", message], cwd=cwd)

    def push(self, remote: str = "origin", branch: str = "main", cwd: str = ".") -> str:
        return self._run(["push", remote, branch], cwd=cwd)

    def pull(self, cwd: str = ".") -> str:
        return self._run(["pull"], cwd=cwd)

    def create_branch(self, name: str, cwd: str = ".") -> str:
        self._run(["checkout", "-b", name], cwd=cwd)
        return f"Switched to new branch '{name}'."

    def log(self, n: int = 5, cwd: str = ".") -> str:
        return self._run(["log", f"--oneline", f"-{n}"], cwd=cwd)

    def diff(self, cwd: str = ".") -> str:
        return self._run(["diff"], cwd=cwd)


# ─────────────────────────────────────────────
# Self-modification
# ─────────────────────────────────────────────

JARVIS_FILES = {
    "jarvis":            os.path.join(BASE_DIR, "jarvis.py"),
    "config":            os.path.join(BASE_DIR, "config.py"),
    "memory":            os.path.join(BASE_DIR, "modules", "memory.py"),
    "automation":        os.path.join(BASE_DIR, "modules", "automation.py"),
    "llm":               os.path.join(BASE_DIR, "modules", "llm_engine.py"),
    "tts":               os.path.join(BASE_DIR, "modules", "tts_engine.py"),
    "stt":               os.path.join(BASE_DIR, "modules", "stt_engine.py"),
    "git":               os.path.join(BASE_DIR, "modules", "git_manager.py"),
}

BACKUP_DIR = os.path.join(BASE_DIR, "data", "backups")


class SelfModifier:
    def __init__(self, llm_engine):
        self.llm = llm_engine
        os.makedirs(BACKUP_DIR, exist_ok=True)

    def list_own_files(self) -> str:
        lines = [f"  {k}: {v}" for k, v in JARVIS_FILES.items()]
        return "My source files:\n" + "\n".join(lines)

    def read_own_file(self, name: str) -> str:
        path = JARVIS_FILES.get(name.lower())
        if not path:
            return f"Unknown file '{name}'. Known: {', '.join(JARVIS_FILES.keys())}"
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _backup(self, path: str) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(path)
        backup_path = os.path.join(BACKUP_DIR, f"{filename}.{ts}.bak")
        shutil.copy2(path, backup_path)
        return backup_path

    def modify_own_file(self, file_name: str, instruction: str) -> str:
        """
        Reads a JARVIS source file, asks the LLM to modify it per the instruction,
        backs up the original, then writes the new version.
        Returns a status message.
        """
        path = JARVIS_FILES.get(file_name.lower())
        if not path:
            return f"I don't know the file '{file_name}'. Known files: {', '.join(JARVIS_FILES.keys())}"

        current_code = self.read_own_file(file_name)

        prompt = (
            f"You are modifying a JARVIS source file. Here is the current content of {file_name}.py:\n\n"
            f"```python\n{current_code}\n```\n\n"
            f"Instruction: {instruction}\n\n"
            f"Return ONLY the complete modified Python file content. No explanation, no markdown fences."
        )

        new_code = self.llm.ask(prompt)
        # strip any accidental fences the model adds
        new_code = self._strip_fences(new_code)

        backup_path = self._backup(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_code)

        return (
            f"Done. I modified {file_name}.py and backed up the original to:\n"
            f"{backup_path}\n"
            f"Say 'restart yourself' to reload the changes."
        )

    def restart_self(self):
        """Restart the JARVIS process so code changes take effect."""
        print("Restarting JARVIS to apply changes...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()
