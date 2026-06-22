"""gui.py — SERENE's desktop face.

pywebview opens a native, frameless window that renders ui/index.html. The
frontend (HTML/CSS/JS) calls the methods on `Api` below via
    window.pywebview.api.<method>(...)
which returns a JS Promise. pywebview runs each call on a worker thread, so
slow LLM calls don't freeze the window.

The same Session that powers the CLI powers this — we just gave it a face.
"""
import os
import hashlib
import webview

import serene.router as router
from serene.config import SERENE_PASSWORD_HASH
from serene.session import Session
from serene.tools.confirm import set_confirm

_session = Session()
_window = None


class Api:
    """Every method here is callable from the frontend JS."""

    def lock_enabled(self):
        """True if a password is configured (so the frontend shows the lock)."""
        return bool(SERENE_PASSWORD_HASH)

    def unlock(self, password):
        """Check the entered password against the stored hash. Returns True/False."""
        return hashlib.sha256(password.encode()).hexdigest() == SERENE_PASSWORD_HASH

    def send(self, message):
        """User sent a message -> return SERENE's reply text."""
        return _session.send(message)

    def switch(self, brain):
        """Change the active brain; return the new active brain name."""
        router.switch(brain)
        return router.active_brain

    def current_brain(self):
        return router.active_brain

    def list_brains(self):
        # 'agent' is automatic now (auto-switch handles hands), so the dropdown
        # only offers chat brains.
        return [b for b in router.brains if b != "agent"]

    def set_memory(self, on):
        """Turn memory saving on/off; return the new state (True/False)."""
        return _session.set_memory(on)

    def memory_on(self):
        return _session.memory_on

    def end(self):
        """Run the memory-reflection pass; return a short report string."""
        return _session.end() or ""

    def minimize(self):
        _window.minimize()

    def close(self):
        _window.destroy()


def _gui_confirm(action):
    """The confirm gate, shown as a native dialog instead of a terminal y/n."""
    return _window.create_confirmation_dialog(
        "SERENE needs permission", f"Allow SERENE to {action}?")


def run_gui():
    global _window
    html = os.path.join(os.path.dirname(__file__), "ui", "index.html")
    _window = webview.create_window(
        "SERENE",
        html,
        js_api=Api(),
        width=920,
        height=700,
        min_size=(720, 540),
        background_color="#0a0e14",
        frameless=True,
        easy_drag=False,      # we define our own drag region in the title bar
    )
    set_confirm(_gui_confirm)
    webview.start()


if __name__ == "__main__":
    run_gui()
