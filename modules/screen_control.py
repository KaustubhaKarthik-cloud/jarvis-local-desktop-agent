"""Explicit-consent Windows screen actions."""

import os
import time

from config import SCREEN_CONFIRMATION_REQUIRED


class ScreenController:
    def __init__(self):
        self.pending = None

    def has_pending(self):
        return self.pending is not None

    def request(self, action, x=None, y=None, text="", keys=None):
        action = str(action or "").strip().casefold()
        allowed = {"click", "double_click", "type", "press", "hotkey", "scroll"}
        if action not in allowed:
            return "Unsupported screen action. Allowed actions are click, double_click, type, press, hotkey, and scroll."
        pending = {"action": action, "x": x, "y": y, "text": text, "keys": keys or []}
        self.pending = pending
        details = action
        if x is not None and y is not None:
            details += f" at ({x}, {y})"
        if text:
            details += f" with text {text!r}"
        if keys:
            details += f" using keys {keys!r}"
        return f"Screen action pending: {details}. Say 'yes' or 'confirm' to execute it, or 'cancel' to discard it."

    def cancel(self):
        self.pending = None
        return "The pending screen action was cancelled."

    def confirm(self):
        if not self.pending:
            return "There is no pending screen action to confirm."
        if not SCREEN_CONFIRMATION_REQUIRED:
            return "Screen confirmation is disabled in configuration; refusing to execute for safety."
        pending = self.pending
        self.pending = None
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            action = pending["action"]
            x, y = pending["x"], pending["y"]
            if action == "click":
                pyautogui.click(x=x, y=y)
            elif action == "double_click":
                pyautogui.doubleClick(x=x, y=y)
            elif action == "type":
                pyautogui.write(str(pending["text"]), interval=0.01)
            elif action == "press":
                pyautogui.press(str(pending["text"]))
            elif action == "hotkey":
                pyautogui.hotkey(*(str(key) for key in pending["keys"]))
            elif action == "scroll":
                pyautogui.scroll(int(pending["text"] or 1))
            time.sleep(0.15)
            return f"Confirmed and completed the screen action: {action}."
        except Exception as exc:
            return f"The screen action was not completed: {exc}"
