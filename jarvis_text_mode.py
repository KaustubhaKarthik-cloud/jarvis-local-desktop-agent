"""
Text-only mode for JARVIS â€” same brain (LLM tool-calling), memory,
automation, git, and self-modification. Type commands instead of speaking
them. Great for testing your Ollama setup and tool-calling before dealing
with microphone/voice setup.

Run: python jarvis_text_mode.py
"""

from modules.llm_engine import LLMEngine
from modules.memory import Memory
from modules.automation import Automation
from modules.git_manager import GitManager, SelfModifier
from modules.tools import ToolExecutor
from modules.training_mode import TrainingMode
from modules.screen_control import ScreenController
from jarvis import Jarvis


class JarvisText(Jarvis):
    def __init__(self):
        print("Booting JARVIS (text mode)...")
        self.memory = Memory()
        self.llm = LLMEngine()
        self.automation = Automation()
        self.training = TrainingMode(self.llm, self.memory)
        self.screen = ScreenController()
        self.self_mod = SelfModifier(self.llm)
        self.tools = ToolExecutor(self)
        self.last_generated_code_path = None
        self.last_opened_target = None

        try:
            self.git = GitManager()
        except EnvironmentError as e:
            print(f"[WARNING] Git unavailable: {e}")
            self.git = None

    def _respond(self, text: str):
        self.memory.add_turn("assistant", text)
        print(f"\nJARVIS: {text}\n")

    def run(self):
        print('\nJARVIS text mode ready.')
        print('Commands are understood by the local LLM directly â€” just type naturally.')
        print('Try: "open whatsapp app not the website"')
        print('     "can you open it again, I need to text someone"')
        print('     "create a git repo called my-project"')
        print('     "write a script that lists all files in the current folder"')
        print('Type "exit" to quit.\n')

        while True:
            try:
                text = input("You: ").strip()
                if not text:
                    continue
                if text.lower() in ("exit", "quit"):
                    print("JARVIS: Goodbye.")
                    break
                self.handle_command(text)
            except KeyboardInterrupt:
                print("\nJARVIS: Goodbye.")
                break


if __name__ == "__main__":
    JarvisText().run()
