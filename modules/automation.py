"""Windows desktop, browser, Spotify, and website automation."""

import datetime
import os
import re
import shutil
import subprocess
import urllib.parse
import webbrowser

from config import GENERATED_CODE_DIR
from modules.app_finder import AppFinder


class Automation:
    def __init__(self):
        os.makedirs(GENERATED_CODE_DIR, exist_ok=True)
        self.app_finder = AppFinder()
        self.browser_path = None
        self.browser_name = "system default"
        self.set_browser("system default", silent=True)

    @staticmethod
    def _clean_target(target):
        target = str(target or "").strip()
        target = re.sub(r"\b(?:the|an?)\s+(?:app|application|website|site)\b", "", target, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", target).strip()

    @staticmethod
    def _is_url(target):
        return bool(re.match(r"^(?:https?://|www\.)", target, re.IGNORECASE)) or bool(
            re.match(r"^[a-z0-9][a-z0-9.-]+\.[a-z]{2,}(?:/.*)?$", target, re.IGNORECASE)
        )

    @staticmethod
    def _browser_candidates(preferred):
        preferred = str(preferred or "").casefold()
        if preferred in ("system default", "default", ""):
            return []
        groups = {
            "edge": ["msedge", "msedge.exe"],
            "chrome": ["chrome", "chrome.exe"],
            "firefox": ["firefox", "firefox.exe"],
            "brave": ["brave", "brave.exe"],
            "opera": ["opera", "opera.exe"],
        }
        key = next((name for name in groups if name in preferred), preferred)
        names = groups.get(key, [preferred, preferred + ".exe"])
        paths = []
        for name in names:
            path = shutil.which(name)
            if path:
                paths.append(path)
        roots = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("LOCALAPPDATA", "")]
        locations = {
            "edge": ["Microsoft", "Edge", "Application", "msedge.exe"],
            "chrome": ["Google", "Chrome", "Application", "chrome.exe"],
            "firefox": ["Mozilla Firefox", "firefox.exe"],
            "brave": ["BraveSoftware", "Brave-Browser", "Application", "brave.exe"],
            "opera": ["Programs", "Opera", "opera.exe"],
        }
        relative = locations.get(key, [])
        if relative:
            for root in roots:
                candidate = os.path.join(root, *relative)
                if os.path.exists(candidate):
                    paths.append(candidate)
        return list(dict.fromkeys(paths))

    def set_browser(self, browser_name, silent=False):
        requested = self._clean_target(browser_name)
        if requested.casefold() in ("", "default", "system default"):
            self.browser_path = None
            self.browser_name = "system default"
            return "Using the Windows default browser." if not silent else True
        paths = self._browser_candidates(requested)
        if paths:
            self.browser_path = paths[0]
            self.browser_name = requested
            return f"I'll use {requested} for websites during this Jarvis session."

        # Store-installed browsers may not expose an exe through PATH or the usual folders.
        # Use their registered URL protocol after confirming the app exists in Windows search.
        app_match = self.app_finder.find(requested)
        protocol = next((value for key, value in {
            "edge": "microsoft-edge:",
            "chrome": "googlechrome:",
            "firefox": "firefox:",
            "brave": "brave:",
            "opera": "opera:",
        }.items() if key in requested.casefold()), None)
        if app_match and protocol:
            self.browser_path = "__protocol__:" + protocol
            self.browser_name = requested
            return f"I'll use {requested} for websites during this Jarvis session."

        message = f"I couldn't find {requested} installed. I left the current browser unchanged."
        return False if silent else message

    def browser_status(self):
        return f"Current Jarvis browser: {self.browser_name}."

    def _open_url(self, url):
        try:
            if self.browser_path and self.browser_path.startswith("__protocol__:"):
                protocol = self.browser_path.split(":", 1)[1]
                os.startfile(protocol + url)
            elif self.browser_path:
                subprocess.Popen([self.browser_path, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                webbrowser.open(url)
            return True
        except (OSError, webbrowser.Error):
            return False

    def open_app(self, spoken_name: str):
        target = self._clean_target(spoken_name)
        if not target:
            return "Tell me which application you want opened."
        if self._is_url(target):
            return self.open_website(target)
        launched = self.app_finder.launch(target)
        if launched:
            return f"Opening {launched}."
        return None

    def refresh_apps(self):
        count = self.app_finder.refresh()
        return f"Refreshed the Windows app index; found {count} launchable entries."

    def open_website(self, spoken_name_or_url: str):
        target = self._clean_target(spoken_name_or_url)
        if not target:
            return "Tell me which website you want opened."
        if self._is_url(target):
            url = target if re.match(r"^https?://", target, re.IGNORECASE) else "https://" + target
        else:
            query = urllib.parse.quote_plus(target)
            url = "https://www.google.com/search?q=" + query
        if self._open_url(url):
            return f"Opening {target} in {self.browser_name}."
        return f"I couldn't open {target}."

    def open_spotify(self, query=""):
        query = self._clean_target(query)
        url = "https://open.spotify.com"
        if query and query.casefold() not in ("music", "some music"):
            url += "/search/" + urllib.parse.quote(query)
        elif query:
            url += "/search/" + urllib.parse.quote(query)
        if self._open_url(url):
            return f"Opening Spotify in {self.browser_name}" + (f" and searching for {query}." if query else ".")
        return "I couldn't open Spotify."

    def save_code(self, code: str, filename: str = None) -> str:
        if not filename:
            filename = "generated_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
        if not filename.endswith(".py"):
            filename += ".py"
        path = os.path.join(GENERATED_CODE_DIR, os.path.basename(filename))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(code)
        return path

    def run_python_file(self, path: str) -> str:
        try:
            result = subprocess.run(["python", path], capture_output=True, text=True, timeout=30)
            output = result.stdout.strip() or result.stderr.strip()
            return output[:500] if output else "Ran with no output."
        except subprocess.TimeoutExpired:
            return "The script took too long and was stopped."
        except Exception as exc:
            return f"Error running the script: {exc}"

    def shutdown(self):
        os.system("shutdown /s /t 5")

    def restart(self):
        os.system("shutdown /r /t 5")

    def lock(self):
        os.system("rundll32.exe user32.dll,LockWorkStation")
