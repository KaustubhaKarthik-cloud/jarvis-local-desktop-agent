"""
JARVIS - a fully local, offline voice assistant.

Wake phrase: "Wake up Jarvis"

ARCHITECTURE:
Command understanding is handled by the local LLM's native function-calling
(Ollama's tool-calling API), not regex pattern matching. Every user message
is sent to the chat model along with a list of tools it's allowed to call
(see modules/tools.py). The model decides whether to respond with plain
conversation or call one or more tools, and extracts the right arguments â€”
this handles natural phrasing, pronouns ("open it again"), negation ("I
didn't ask you to open anything"), and multi-part requests ("open spotify
and roblox") far more robustly than hand-written regex ever could.

Capabilities (all exposed as tools the LLM can call):
  - Desktop automation: open any installed app or website
  - Local LLM code generation, explanation, debugging
  - Persistent memory (SQLite)
  - Git: create repos, commit, push, branch, status, log
  - Self-modification: JARVIS can edit its own source code on request,
    auto-backing up before every change, then restart itself
"""

import re
import sys

from config import USE_WAKE_WORD, WAKE_WORD
from modules.stt_engine import STTEngine
from modules.tts_engine import TTSEngine
from modules.llm_engine import LLMEngine
from modules.memory import Memory
from modules.automation import Automation
from modules.git_manager import GitManager, SelfModifier
from modules.tools import TOOL_SCHEMAS, ToolExecutor
from modules.training_mode import TrainingMode
from modules.screen_control import ScreenController

# â”€â”€ Safety net â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Tool-calling on a local 7B model isn't 100% reliable â€” sometimes it responds
# with plain text describing an action instead of actually calling the tool
# (e.g. "Opening Roblox... enjoy!" with no real tool_calls). Since "open X" is
# the single most common and important action JARVIS performs, this lightweight
# fallback catches that specific case: if the model didn't call any tool, but
# the message clearly looks like an open request, JARVIS performs the real
# action directly and speaks the REAL result instead of trusting the model's
# possibly-fabricated text. This is deliberately narrow (just "open") rather
# than reintroducing regex for everything â€” tool-calling still handles all
# other commands.
_NEGATION_WORDS = {
    "not", "don't", "dont", "didn't", "didnt", "won't", "wont",
    "can't", "cant", "cannot", "never", "isn't", "isnt",
    "wasn't", "wasnt", "aren't", "arent", "doesn't", "doesnt",
    "wouldn't", "wouldnt", "shouldn't", "shouldnt",
}
_STOPWORDS = {"i", "because", "so", "and", "then", "please", "now", "to", "for", "again"}


def _detect_open_fallback(raw_text: str):
    """Returns a plain target name if raw_text looks like an unambiguous
    'open X' request not preceded by negation, else None."""
    text = re.sub(r"[?.!,]+$", "", raw_text.strip().lower()).strip()

    for m in re.finditer(r"\bopen (?:the )?(?:app |application )?([a-z0-9]+(?:\s+[a-z0-9]+){0,4}?)(?=\s+(?:i|because|so|and|then|please|now|to|for|again)\b|$)", text):
        preceding = text[:m.start()].split()[-4:]
        if any(w.strip(",.!?'\"") in _NEGATION_WORDS for w in preceding):
            continue
        # trim trailing stopwords from the captured target
        words = m.group(1).split()
        while words and words[-1] in _STOPWORDS:
            words.pop()
        target = " ".join(words).strip()
        if target:
            return target
    return None



# Tools it's safe to auto-recover via the leaked-JSON mechanism above: either
# read-only, or local-only and easily reversible (modify_own_code always
# backs up first). Deliberately EXCLUDED: send_whatsapp_message (sends a
# real message to a real person â€” a false-positive recovery must never
# fire this), git_push/pull/commit/clone, run_last_code, write_code,
# restart_self, lock/shutdown/restart_computer, switch_model, and open_app
# (which has its own dedicated, more conservative fallback below). If the
# model's real tool_calls mechanism doesn't fire for one of these, JARVIS
# will NOT guess â€” it responds conversationally and lets the user retry,
# because for these, doing nothing is much safer than doing the wrong thing.
_SAFE_FOR_LEAK_RECOVERY = {
    "remember_fact", "recall_fact", "which_models",
    "git_status", "git_log", "list_own_files", "read_own_file",
     "modify_own_code",
}


def _extract_leaked_tool_calls(content: str):
    """
    Second safety net, more general than _detect_open_fallback: sometimes
    the model correctly DECIDES to call a tool and forms the right JSON
    arguments, but Ollama's chat template fails to structure that into the
    proper tool_calls field for this model â€” it leaks out as a JSON-looking
    blob sitting inside the plain text response instead (e.g. the model says
    something like 'Storing fact {"key": "wifi password", "value": "abc123"}'
    as if that were normal conversation, when it actually meant to invoke a
    real tool with those exact arguments).

    This scans the text for {...} blobs, parses any that are valid JSON
    objects, and matches each one's keys against every known tool's REQUIRED
    parameters. A match is only accepted if it's unambiguous (exactly one
    tool's required-parameter set fits) AND that tool is in
    _SAFE_FOR_LEAK_RECOVERY â€” ambiguous, unrecognized, or consequential
    blobs are ignored rather than guessed at, since a wrong automatic action
    (like resending stale message content) is worse than no action.
    """
    import json as _json
    from modules.tools import TOOL_SCHEMAS

    found = []
    for m in re.finditer(r"\{[^{}]*\}", content):
        try:
            data = _json.loads(m.group(0))
        except Exception:
            continue
        if not isinstance(data, dict) or not data:
            continue

        data_keys = set(data.keys())
        candidates = []
        for tool in TOOL_SCHEMAS:
            fn = tool["function"]
            if fn["name"] not in _SAFE_FOR_LEAK_RECOVERY:
                continue
            required = set(fn["parameters"].get("required", []))
            all_props = set(fn["parameters"].get("properties", {}).keys())
            if required and required.issubset(data_keys) and data_keys.issubset(all_props):
                candidates.append(fn["name"])

        if len(candidates) == 1:
            found.append((candidates[0], data))

    return found


class Jarvis:
    def __init__(self):
        print("Booting JARVIS...")
        self.tts = TTSEngine()
        self.memory = Memory()
        self.llm = LLMEngine()
        self.automation = Automation()
        self.training = TrainingMode(self.llm, self.memory)
        self.screen = ScreenController()
        self.self_mod = SelfModifier(self.llm)
        self.tools = ToolExecutor(self)

        try:
            self.git = GitManager()
        except EnvironmentError as e:
            print(f"[WARNING] Git unavailable: {e}")
            self.git = None

        try:
            self.stt = STTEngine()
        except FileNotFoundError as e:
            print(str(e))
            sys.exit(1)

        self.last_generated_code_path = None
        self.last_opened_target = None

    # â”€â”€â”€ Main loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def run(self):
        self.tts.say("JARVIS online. How can I help?")
        while True:
            try:
                if USE_WAKE_WORD:
                    heard = self.stt.listen_once(timeout_seconds=6)
                    if WAKE_WORD not in heard:
                        continue
                    self.tts.say("I'm awake. What do you need?")
                    command_text = heard.replace(WAKE_WORD, "", 1).strip()
                    if not command_text:
                        command_text = self.stt.listen_once()
                else:
                    command_text = self.stt.listen_once()

                if not command_text:
                    continue

                print(f"You: {command_text}")
                self.handle_command(command_text)

            except KeyboardInterrupt:
                self.tts.say("Shutting down. Goodbye.")
                break
            except Exception as e:
                print(f"Error: {e}")
                self.tts.say("Sorry, something went wrong there.")

    # â”€â”€â”€ Intent routing (LLM tool-calling based) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def handle_command(self, raw_text: str):
        self.memory.add_turn("user", raw_text)

        # Only two things are handled outside the LLM, deliberately: exiting
        # the program (must be instant and 100% reliable, no model call
        # needed) and nothing else â€” everything else goes through tool-calling.
        if re.match(r"^\s*(exit|quit|goodbye)\s*[.!]?\s*$", raw_text.strip(), re.IGNORECASE):
            self.tts.say("Goodbye.")
            sys.exit(0)

        remember_match = re.match(r"^\s*remember(?: that)?\s+(.+?)\s+(?:is|=)\s+(.+?)\s*[.!]?\s*$", raw_text, re.IGNORECASE)
        if remember_match:
            self.memory.remember_fact(remember_match.group(1), remember_match.group(2))
            self._respond(f"Fact stored: {remember_match.group(1)} is {remember_match.group(2)}.")
            return

        browser_request = re.match(r"^\s*(?:use|select|switch to|open with)\s+(microsoft edge|edge|google chrome|chrome|mozilla firefox|firefox|brave|opera)(?:\s+as\s+(?:the\s+)?(?:default\s+)?browser)?\s*[.!]?\s*$", raw_text, re.IGNORECASE)
        if browser_request:
            self._respond(self.automation.set_browser(browser_request.group(1)))
            return

        if re.search(r"\bspotify\b", raw_text, re.IGNORECASE):
            play_match = re.search(r"\b(?:play|listen to)\s+(.+?)(?:\s+on\s+spotify)?\s*[.!]?\s*$", raw_text, re.IGNORECASE)
            spotify_query = play_match.group(1).strip() if play_match else ""
            self._respond(self.automation.open_spotify(spotify_query))
            return

        if self.screen.has_pending():
            if re.match(r"^\s*(yes|yes please|confirm|do it|go ahead)\s*[.!]?\s*$", raw_text, re.IGNORECASE):
                self._respond(self.screen.confirm())
                return
            if re.match(r"^\s*(no|cancel|stop|never mind)\s*[.!]?\s*$", raw_text, re.IGNORECASE):
                self._respond(self.screen.cancel())
                return
            self._respond("A screen action is waiting for confirmation. Say yes to execute it or cancel to discard it.")
            return

        training_match = re.match(r"^\s*(?:enter\s+training\s+mode|training\s+mode|research|learn about|study)\s*(.*)$", raw_text, re.IGNORECASE)
        if training_match:
            topic = training_match.group(1).strip()
            if topic.casefold().startswith("on "):
                topic = topic[3:].strip()
            if not topic:
                self._respond("Training Mode is ready. Tell me what topic you want me to research.")
            else:
                self._respond("Entering Training Mode. I will research " + topic + " and return a sourced summary.")
                self._respond(self.training.start(topic))
            return

        history = self.memory.recent_history(limit=6)
        message = self.llm.chat_with_tools(raw_text, TOOL_SCHEMAS, context_lines=history)

        tool_calls = message.get("tool_calls") or []

        if tool_calls:
            responses = []
            for call in tool_calls:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments", {})
                # Ollama sometimes returns arguments as a JSON string instead
                # of a dict, depending on model â€” handle both.
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                result = self.tools.execute(name, args)
                if result:
                    responses.append(str(result))

            combined = " ".join(responses).strip()
            self._respond(combined or "Done.")
            return

        # No real tool_calls came back. Before trusting the model's text as
        # genuine conversation, try two safety nets in order:
        content = (message.get("content") or "").strip()

        # 1) General recovery: did the model leak an attempted tool call as
        # garbled JSON inside its text response? If so, actually run it.
        leaked_calls = _extract_leaked_tool_calls(content)
        if leaked_calls:
            responses = []
            for name, args in leaked_calls:
                print(f"[safety net] Recovered a leaked '{name}' tool call from model output â€” executing for real.")
                result = self.tools.execute(name, args)
                if result:
                    responses.append(str(result))
            if responses:
                self._respond(" ".join(responses).strip())
                return

        # 2) Narrow recovery: does the raw user request look like an
        # unambiguous "open X" that the model just talked about instead of
        # doing? (Covers cases where the model didn't even attempt a tool
        # call, e.g. "Opening Roblox... enjoy!" with nothing to recover.)
        fallback_target = _detect_open_fallback(raw_text)
        if fallback_target:
            print(f"[safety net] Model didn't call a tool for an apparent 'open {fallback_target}' request â€” executing directly.")
            result = self.tools.execute("open_app", {"name": fallback_target})
            self._respond(result)
            return

        if not content:
            content = "I'm not sure how to help with that â€” could you rephrase?"
        self._respond(content)

    def _respond(self, text: str):
        self.memory.add_turn("assistant", text)
        self.tts.say(text)


if __name__ == "__main__":
    jarvis = Jarvis()
    jarvis.run()
