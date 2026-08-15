"""Local Ollama LLM engine with bounded context, connection reuse, and GPU hints."""
import json
import re
import requests

from config import (
    OLLAMA_URL,
    OLLAMA_CHAT_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_CODE_MODEL,
    CHAT_SYSTEM_PROMPT,
    CODE_SYSTEM_PROMPT,
    OLLAMA_NUM_GPU,
    OLLAMA_NUM_THREAD,
    OLLAMA_NUM_CTX,
    OLLAMA_CHAT_NUM_PREDICT,
    OLLAMA_CODE_NUM_PREDICT,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_TEMPERATURE,
)


class LLMEngine:
    def __init__(self):
        self.chat_model = OLLAMA_CHAT_MODEL
        self.code_model = OLLAMA_CODE_MODEL
        self.chat_system = CHAT_SYSTEM_PROMPT
        self.code_system = CODE_SYSTEM_PROMPT
        self.session = requests.Session()

    def ask(self, prompt: str, context_lines=None) -> str:
        return self._call(self.chat_model, self.chat_system, prompt, context_lines)

    def generate_code(self, request: str, context_lines=None) -> str:
        prompt = (
            "Write clean, working Python code for the following task.\n"
            "Return ONLY the final code. No explanation, no markdown fences.\n\n"
            f"Task: {request}"
        )
        return self._strip_fences(self._call(self.code_model, self.code_system, prompt, context_lines, code=True))

    def generate_code_in_language(self, request: str, language: str, context_lines=None) -> str:
        prompt = (
            f"Write clean, working {language} code for the following task.\n"
            "Return ONLY the code. No explanation, no markdown fences.\n\n"
            f"Task: {request}"
        )
        return self._strip_fences(self._call(self.code_model, self.code_system, prompt, context_lines, code=True))

    def explain_code(self, code: str) -> str:
        prompt = f"Explain the following code in plain English. Be concise and suitable for speaking aloud.\n\n{code}"
        return self._call(self.code_model, self.code_system, prompt, code=True)

    def debug_code(self, code: str, error: str) -> str:
        prompt = f"The following Python code produced this error:\nError: {error}\n\nCode:\n{code}\n\nReturn ONLY the fixed code. No explanation."
        return self._strip_fences(self._call(self.code_model, self.code_system, prompt, code=True))

    def switch_chat_model(self, model_name: str):
        self.chat_model = model_name
        return f"Chat model switched to {model_name}."

    def switch_code_model(self, model_name: str):
        self.code_model = model_name
        return f"Code model switched to {model_name}."

    def current_models(self) -> str:
        return f"Chat: {self.chat_model} | Code: {self.code_model}"

    def chat_with_tools(self, user_message: str, tools: list, context_lines=None) -> dict:
        messages = [{"role": "system", "content": self.chat_system}]
        if context_lines:
            for role, content in context_lines[-6:]:
                role = role if role in ("user", "assistant") else "user"
                messages.append({"role": role, "content": str(content)[-700:]})
        messages.append({"role": "user", "content": user_message})
        try:
            response = self.session.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "tools": tools,
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {
                        "num_gpu": OLLAMA_NUM_GPU,
                        "num_thread": OLLAMA_NUM_THREAD,
                        "num_ctx": OLLAMA_NUM_CTX,
                        "num_predict": OLLAMA_CHAT_NUM_PREDICT,
                        "temperature": OLLAMA_TEMPERATURE,
                    },
                },
                timeout=60,
            )
            response.raise_for_status()
            return response.json().get("message", {"content": ""})
        except requests.exceptions.ConnectionError:
            return {"content": "I can't reach Ollama. Make sure it is running."}
        except Exception as exc:
            return {"content": f"LLM error: {exc}"}

    def _call(self, model: str, system: str, prompt: str, context_lines=None, code=False) -> str:
        full_prompt = system + "\n\n"
        if context_lines:
            for role, content in context_lines[-4:]:
                full_prompt += f"{role}: {str(content)[-700:]}\n"
        full_prompt += f"user:\n{prompt}\nassistant:"
        try:
            response = self.session.post(
                OLLAMA_URL,
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "keep_alive": OLLAMA_KEEP_ALIVE,
                    "options": {
                        "num_gpu": OLLAMA_NUM_GPU,
                        "num_thread": OLLAMA_NUM_THREAD,
                        "num_ctx": OLLAMA_NUM_CTX,
                        "num_predict": OLLAMA_CODE_NUM_PREDICT if code else OLLAMA_CHAT_NUM_PREDICT,
                        "temperature": OLLAMA_TEMPERATURE,
                    },
                },
                timeout=120 if code else 60,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except requests.exceptions.ConnectionError:
            return "I can't reach Ollama. Make sure it is running."
        except Exception as exc:
            return f"LLM error: {exc}"

    @staticmethod
    def _strip_fences(text: str) -> str:
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()


if __name__ == "__main__":
    llm = LLMEngine()
    print("Models:", llm.current_models())
    print(llm.ask("Say hello in one sentence."))
