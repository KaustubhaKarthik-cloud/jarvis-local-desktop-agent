"""Dynamic Windows application discovery.

The finder uses the same Start Menu index exposed by Windows search, then falls
back to executables available on PATH. It does not maintain a hardcoded app list.
"""

import difflib
import json
import os
import shutil
import subprocess
import time

from config import DATA_DIR

APPS_CACHE_PATH = os.path.join(DATA_DIR, "installed_apps.json")
CACHE_SECONDS = 300


def _hidden_process_kwargs():
    kwargs = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return kwargs


class AppFinder:
    def __init__(self):
        self._apps = []
        self._loaded_at = 0.0
        self._load_cache()

    @staticmethod
    def _normalise(value):
        return " ".join(str(value).casefold().replace(".exe", "").split())

    def _load_cache(self):
        try:
            if os.path.exists(APPS_CACHE_PATH):
                age = time.time() - os.path.getmtime(APPS_CACHE_PATH)
                if age <= CACHE_SECONDS:
                    with open(APPS_CACHE_PATH, "r", encoding="utf-8") as handle:
                        data = json.load(handle)
                    if isinstance(data, list):
                        self._apps = data
                        self._loaded_at = time.time()
        except (OSError, ValueError, TypeError):
            self._apps = []

    def refresh(self):
        """Refresh the Windows Start Menu index and PATH executable cache."""
        apps = []
        command = "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json -Compress"
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                timeout=20,
                **_hidden_process_kwargs(),
            )
            if result.returncode == 0 and result.stdout.strip():
                payload = json.loads(result.stdout)
                if isinstance(payload, dict):
                    payload = [payload]
                for item in payload or []:
                    name = str(item.get("Name", "")).strip()
                    app_id = str(item.get("AppID", "")).strip()
                    if name and app_id:
                        apps.append({"name": name, "app_id": app_id, "kind": "startapp"})
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

        # Add executable names available through PATH without guessing install paths.
        seen = {self._normalise(item["name"]) for item in apps}
        for candidate in ("python", "python3", "git", "cmd", "powershell", "pwsh"):
            path = shutil.which(candidate)
            key = self._normalise(candidate)
            if path and key not in seen:
                apps.append({"name": candidate, "path": path, "kind": "path"})
                seen.add(key)

        self._apps = sorted(apps, key=lambda item: self._normalise(item.get("name", "")))
        self._loaded_at = time.time()
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(APPS_CACHE_PATH, "w", encoding="utf-8") as handle:
                json.dump(self._apps, handle, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return len(self._apps)

    def _ensure_loaded(self):
        if not self._apps or time.time() - self._loaded_at > CACHE_SECONDS:
            self.refresh()

    def find(self, query: str):
        """Return the best dynamic app match, or None when no match exists."""
        query_norm = self._normalise(query)
        if not query_norm:
            return None
        self._ensure_loaded()
        if not self._apps:
            self.refresh()
        exact = [item for item in self._apps if self._normalise(item.get("name", "")) == query_norm]
        if exact:
            return exact[0]
        contains = [item for item in self._apps if query_norm in self._normalise(item.get("name", ""))]
        if contains:
            return sorted(contains, key=lambda item: len(self._normalise(item.get("name", ""))))[0]
        names = [self._normalise(item.get("name", "")) for item in self._apps]
        close = difflib.get_close_matches(query_norm, names, n=1, cutoff=0.72)
        if close:
            index = names.index(close[0])
            return self._apps[index]
        return None

    def launch(self, query: str):
        match = self.find(query)
        if not match:
            return None
        try:
            if match.get("kind") == "startapp":
                subprocess.Popen(
                    ["explorer.exe", "shell:AppsFolder\\" + match["app_id"]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen([match["path"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return match["name"]
        except OSError:
            return None

    def list_names(self):
        self._ensure_loaded()
        return [item.get("name", "") for item in self._apps]
