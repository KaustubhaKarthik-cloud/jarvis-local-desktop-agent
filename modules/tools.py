"""
Tool definitions + executor for JARVIS's LLM function-calling.

WHY THIS EXISTS:
The original design used hand-written regex to detect commands ("open X",
"remember that X is Y", etc). That works for exact phrasings but breaks
constantly on natural language: "can you open it again", "I didn't ask you
to open anything", "open spotify and roblox" all needed their own special
handling, and every fix risked breaking something else.

Instead, JARVIS now hands the user's message directly to the local LLM
along with a list of tools it's allowed to call (Ollama's native
function-calling, same OpenAI-compatible schema used by cloud assistants).
The model decides what the user wants and extracts the right arguments â€”
including resolving pronouns, ignoring negated mentions, and handling
multiple requests in one sentence â€” because that's what language models are
actually good at, instead of us re-deriving it with regex every time.

Every tool function below returns a short, human-readable string, which is
exactly what gets spoken back to the user.
"""

import re
import time
import urllib.parse

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": (
                "Opens an application, game, or website on the user's computer. "
                "Works for both installed desktop apps/games (Chrome, Spotify, "
                "Valorant, Minecraft, Discord...) and websites/online services "
                "(YouTube, Netflix, Crunchyroll, WhatsApp...) â€” just pass the "
                "plain name. By default this tries to launch the REAL installed "
                "app first and only opens a browser if nothing matching is "
                "installed â€” this is real desktop automation, not just a web "
                "search. Only set prefer_website to true if the user explicitly "
                "says they want the website/browser version instead of the app. "
                "ALWAYS call this tool when the user asks to open, launch, start, "
                "or go to something â€” never respond as if you opened it without "
                "actually calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Plain name of the app, game, or website, e.g. 'whatsapp', 'valorant', 'youtube'. If the user is referring back to something already discussed ('open it again'), use that same name.",
                    },
                    "prefer_website": {
                        "type": "boolean",
                        "description": "true ONLY if the user explicitly asked for the website/browser version rather than the installed app",
                    },
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Saves a fact the user wants JARVIS to remember long-term, for later recall in a future conversation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Short label for the fact, e.g. 'wifi password', 'favorite game'"},
                    "value": {"type": "string", "description": "The actual value to remember"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_fact",
            "description": "Looks up a previously remembered fact by its label.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The label of the fact to look up, e.g. 'wifi password'"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_code",
            "description": "Writes and saves a script based on a natural-language description. Use whenever the user asks JARVIS to write, create, or generate code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string", "description": "What the code should do"},
                    "language": {"type": "string", "description": "Programming language, defaults to python"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_last_code",
            "description": "Runs the most recently generated script and reports its output.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_last_code",
            "description": "Explains what the most recently generated script does, in plain English.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "debug_last_code",
            "description": "Fixes a bug in the most recently generated script.",
            "parameters": {
                "type": "object",
                "properties": {
                    "error": {"type": "string", "description": "The error message encountered, if known"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_create_repo",
            "description": "Creates a new local git repository with an initial commit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name for the new repo folder"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clones a git repository from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The repository URL to clone"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stages and commits all changes in the current git repo with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "The commit message"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {"name": "git_push", "description": "Pushes committed changes to the remote repository.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "git_pull", "description": "Pulls the latest changes from the remote repository.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "git_status", "description": "Shows the current git working tree status.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "git_log", "description": "Shows recent git commits.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {
            "name": "git_branch",
            "description": "Creates and switches to a new git branch.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Name for the new branch"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_installed_apps",
            "description": "Re-scans all applications installed on the computer. Use this if the user just installed something new and JARVIS can't find it yet.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "modify_own_code",
            "description": "Modifies one of JARVIS's own source code files per the user's instruction. Automatically backs up the original first. Use only when the user explicitly asks JARVIS to change/update/modify its own behavior or code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Which source file to modify, e.g. 'config', 'automation', 'jarvis'"},
                    "instruction": {"type": "string", "description": "What change to make"},
                },
                "required": ["file", "instruction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_self",
            "description": "Restarts the JARVIS process so recent self-modifications take effect.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_own_files",
            "description": "Lists JARVIS's own source code files.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_own_file",
            "description": "Prints the contents of one of JARVIS's own source files to the terminal.",
            "parameters": {
                "type": "object",
                "properties": {"file": {"type": "string", "description": "Which file to read, e.g. 'config', 'jarvis'"}},
                "required": ["file"],
            },
        },
    },
    {
        "type": "function",
        "function": {"name": "lock_computer", "description": "Locks the computer immediately.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "shutdown_computer", "description": "Shuts down the computer.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "restart_computer", "description": "Restarts the computer.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {
            "name": "switch_model",
            "description": "Switches which local LLM is used for chat and/or code generation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model_name": {"type": "string", "description": "Name of the Ollama model to switch to, e.g. 'deepseek-r1:7b'"},
                    "scope": {"type": "string", "description": "'chat', 'code', or 'everything' (default)"},
                },
                "required": ["model_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "which_models",
            "description": "Reports which local LLMs are currently being used for chat and code.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "play_on_youtube",
            "description": (
                "Opens YouTube search results for a song, video, or topic the user wants "
                "to watch or listen to. Use whenever the user asks to play, watch, or "
                "listen to something on YouTube. This opens real search results (not a "
                "guess) so the user can pick the right one â€” it does not guess and "
                "auto-play a specific video."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for, e.g. 'lofi hip hop radio' or the exact song/video name the user said",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_whatsapp_message",
            "description": (
                "Opens a WhatsApp chat with a specific contact and pre-fills a message, "
                "attempting to send it automatically. Requires the contact's phone number "
                "to already be saved via remember_fact (e.g. \"remember that Yash's phone "
                "number is +91XXXXXXXXXX\") â€” if no phone number is saved for this contact, "
                "this tool will say so and ask the user to save it first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "contact_name": {"type": "string", "description": "Name of the contact to message, e.g. 'Yash'"},
                    "message": {"type": "string", "description": "The message text to send"},
                },
                "required": ["contact_name", "message"],
            },
        },
    },
]



TOOL_SCHEMAS.extend([
    {
        "type": "function",
        "function": {
            "name": "start_training_mode",
            "description": "Starts opt-in Training Mode only when the user explicitly asks JARVIS to research, learn about, study, or enter Training Mode. It searches public sources, summarizes them, and saves a visible local knowledge note.",
            "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screen_action",
            "description": "Prepares one screen action such as click, type, press, hotkey, or scroll. It NEVER executes immediately; JARVIS must show the exact action and wait for a separate user confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["click", "double_click", "type", "press", "hotkey", "scroll"]},
                    "x": {"type": "integer"},
                    "y": {"type": "integer"},
                    "text": {"type": "string"},
                    "keys": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action"],
            },
        },
    },
])

class ToolExecutor:
    """
    Executes a tool call by name, dispatching to the right module
    (automation, memory, git, self-mod, llm) and returning a short spoken
    response. Holds a back-reference to the running Jarvis instance so it
    can read/update shared state like last_opened_target.
    """

    def __init__(self, jarvis):
        self.jarvis = jarvis

    # â”€â”€ Apps / websites â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def open_app(self, name, prefer_website=False):
        automation = self.jarvis.automation
        target = str(name).strip().lower()

        if prefer_website:
            result = automation.open_website(target)
        else:
            result = automation.open_app(target)
            if result is None:
                result = automation.open_website(target)

        self.jarvis.last_opened_target = target
        return result

    # â”€â”€ Memory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def remember_fact(self, key, value):
        self.jarvis.memory.remember_fact(key, value)
        return f"Got it, I'll remember that {key} is {value}."

    def recall_fact(self, key):
        value = self.jarvis.memory.recall_fact(key)
        if value:
            return f"You told me {key} is {value}."
        return f"I don't have anything saved about {key} yet."

    # â”€â”€ Code â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def write_code(self, description, language="python"):
        llm = self.jarvis.llm
        if language.lower() == "python":
            code = llm.generate_code(description)
        else:
            code = llm.generate_code_in_language(description, language)
        path = self.jarvis.automation.save_code(code)
        self.jarvis.last_generated_code_path = path
        return f"Done. Saved to {path}. Say 'run it' if you'd like me to run it."

    def run_last_code(self):
        path = self.jarvis.last_generated_code_path
        if not path:
            return "I don't have any code saved yet to run."
        output = self.jarvis.automation.run_python_file(path)
        return f"Output: {output}"

    def explain_last_code(self):
        path = self.jarvis.last_generated_code_path
        if not path:
            return "I don't have any generated code to explain yet."
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        return self.jarvis.llm.explain_code(code)

    def debug_last_code(self, error="unknown error"):
        path = self.jarvis.last_generated_code_path
        if not path:
            return "No script to debug yet."
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        fixed = self.jarvis.llm.debug_code(code, error)
        new_path = self.jarvis.automation.save_code(fixed, "fixed_script.py")
        self.jarvis.last_generated_code_path = new_path
        return "Debugged and saved the fixed script. Say 'run it' to test."

    # â”€â”€ Git â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def git_create_repo(self, name="my-jarvis-project"):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.create_repo(str(name).replace(" ", "-"))

    def git_clone(self, url):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.clone(url)

    def git_commit(self, message):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.commit(message)

    def git_push(self):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.push()

    def git_pull(self):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.pull()

    def git_status(self):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.status() or "Working tree is clean."

    def git_log(self):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.log()

    def git_branch(self, name):
        if not self.jarvis.git:
            return "Git isn't available on this machine."
        return self.jarvis.git.create_branch(name)

    # â”€â”€ Apps index / self-modification â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def refresh_installed_apps(self):
        return self.jarvis.automation.refresh_apps()

    def modify_own_code(self, file, instruction):
        return self.jarvis.self_mod.modify_own_file(file, instruction)

    def restart_self(self):
        self.jarvis.self_mod.restart_self()
        return "Restarting now."

    def list_own_files(self):
        return self.jarvis.self_mod.list_own_files()

    def read_own_file(self, file):
        content = self.jarvis.self_mod.read_own_file(file)
        print(content)
        return f"Printed my {file} file to the terminal."

    # â”€â”€ System â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def lock_computer(self):
        self.jarvis.automation.lock()
        return "Locking now."

    def shutdown_computer(self):
        self.jarvis.automation.shutdown()
        return "Shutting down in 5 seconds."

    def restart_computer(self):
        self.jarvis.automation.restart()
        return "Restarting in 5 seconds."

    # â”€â”€ Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def switch_model(self, model_name, scope="everything"):
        if scope in ("code", "everything"):
            self.jarvis.llm.switch_code_model(model_name)
        if scope in ("chat", "everything"):
            self.jarvis.llm.switch_chat_model(model_name)
        return f"Switched {scope} model to {model_name}."

    def which_models(self):
        return self.jarvis.llm.current_models()

    # â”€â”€ YouTube / WhatsApp â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def play_on_youtube(self, query):
        """Opens real YouTube search results â€” reliable and API-key-free,
        since it just uses YouTube's own search URL rather than guessing
        or scraping for a specific video to auto-play."""
        encoded = urllib.parse.quote_plus(str(query))
        url = f"https://www.youtube.com/results?search_query={encoded}"
        self.jarvis.automation.open_website(url)
        self.jarvis.last_opened_target = "youtube"
        return f'Opened YouTube search results for "{query}" â€” go ahead and pick one.'

    def send_whatsapp_message(self, contact_name, message):
        """
        Uses WhatsApp's official click-to-chat link (wa.me/<phone>?text=...)
        rather than simulating clicks around the WhatsApp UI â€” this is far
        more reliable since it doesn't depend on screen resolution, window
        state, or WhatsApp's UI layout. Looks up the contact's phone number
        from remembered facts; asks the user to save it if not found.

        Best-effort auto-send: after the chat opens with the message
        pre-filled, JARVIS waits a few seconds then presses Enter to send
        it. This step can fail silently if another window steals focus
        during the wait, or if WhatsApp Web isn't already logged in on this
        browser (it'll show a QR code screen instead of the chat) â€” if so,
        the message is still sitting there pre-filled and ready, just not
        auto-sent.
        """
        memory = self.jarvis.memory
        contact_lower = str(contact_name).strip().lower()
        if contact_lower in ("him", "her", "them", "that person", "this person"):
            for key, value in memory.all_facts():
                match = re.match(r"^([a-z][a-z0-9_-]*)\b.*\b(phone|number|whatsapp)\b", key, re.IGNORECASE)
                if match:
                    contact_name = match.group(1).title()
                    contact_lower = match.group(1).lower()
                    break

        phone = None
        for key, value in memory.all_facts():
            if contact_lower in key and any(w in key for w in ("phone", "number", "whatsapp")):
                phone = value
                break

        if not phone:
            return (
                f"I don't have a phone number saved for {contact_name}. Say something like "
                f'"remember that {contact_name}\'s phone number is +91XXXXXXXXXX" '
                f"and I'll be able to message them directly next time."
            )

        digits = re.sub(r"[^\d+]", "", phone).lstrip("+")
        encoded_message = urllib.parse.quote_plus(str(message))
        # web.whatsapp.com/send goes straight to the chat with the message
        # pre-filled. wa.me/<number> looks similar but redirects through an
        # "Open WhatsApp?" confirmation page on desktop browsers first,
        # which breaks the auto-send timing below â€” this avoids that.
        url = f"https://web.whatsapp.com/send?phone={digits}&text={encoded_message}"

        self.jarvis.automation.open_website(url)
        self.jarvis.last_opened_target = "whatsapp"

        try:
            import pyautogui
            time.sleep(5)  # give WhatsApp Web time to load the chat and pre-fill the message
            pyautogui.press("enter")
            return f'Sent to {contact_name}: "{message}"'
        except Exception:
            return (
                f'Opened a chat with {contact_name} with your message pre-filled: "{message}". '
                f"Just hit Enter to send it â€” I wasn't able to confirm auto-send worked."
            )

    # â”€â”€ Dispatch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    def start_training_mode(self, topic):
        return self.jarvis.training.start(topic)

    def screen_action(self, action, x=None, y=None, text="", keys=None):
        return self.jarvis.screen.request(action, x=x, y=y, text=text, keys=keys)

    def screen_status(self):
        if self.jarvis.screen.has_pending():
            return "A screen action is waiting for your explicit confirmation."
        return "No screen action is pending."
    def execute(self, tool_name: str, arguments: dict) -> str:
        method = getattr(self, tool_name, None)
        if method is None:
            return f"Unknown tool: {tool_name}"
        try:
            return method(**(arguments or {}))
        except TypeError as e:
            return f"I tried to use {tool_name} but got the arguments wrong: {e}"
        except Exception as e:
            return f"Error running {tool_name}: {e}"
