"""confirm.py — the safety prompt before SERENE does anything destructive.

Destructive tools (delete, move, overwrite) call `confirm(action)` and only
proceed if it returns True.

The ASKING is pluggable on purpose. By default we ask in the terminal with
input(). Later the desktop UI will call set_confirm() to swap in a dialog box.
The tool code never changes — it just calls confirm() and trusts the answer.
This seam is what lets the same tools work in the CLI today and the GUI later.
"""


def _cli_confirm(action):
    answer = input(f"\n  [!] SERENE wants to: {action}\n      Allow? (y/n) ")
    return answer.strip().lower() in ("y", "yes")


_confirm_fn = _cli_confirm


def set_confirm(func):
    """Replace how confirmations are asked (e.g. a GUI dialog).
    `func` takes an action string and returns True/False."""
    global _confirm_fn
    _confirm_fn = func


def confirm(action):
    """Ask the user to approve a destructive action. Returns True if allowed."""
    return _confirm_fn(action)
