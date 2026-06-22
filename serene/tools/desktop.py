"""desktop.py — SERENE's native-app hands (tier 3: the Windows accessibility tree).

Most native Windows apps expose their buttons, menus, text fields, etc. through
the OS **UI Automation (UIA)** tree — the same data screen readers use. That
lets SERENE find and operate controls BY NAME, reliably, without the app having
an API and without guessing pixel coordinates.

THREADING: UIA is built on COM, which is thread-sensitive. The desktop GUI calls
tools from many worker threads, so — exactly like web.py — we funnel ALL UIA
work through ONE dedicated thread.

LIMITS: apps that draw their own UI (some Electron/games/canvas) expose a thin
or empty tree; for those you'd need the (unbuilt) vision fallback.
"""
import time
from concurrent.futures import ThreadPoolExecutor

import comtypes
import uiautomation as auto

from serene.tools.registry import tool
from serene.tools.confirm import confirm


def _init_com():
    """Runs once when the desktop thread is created. UIA is COM-based, and COM
    must be initialized on each thread that uses it — the pool worker thread
    isn't initialized automatically, so we do it here (multithreaded apartment,
    which UIA is happy with and which needs no message pump)."""
    try:
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    except OSError:
        pass   # already initialized on this thread


# One thread owns all UIA/COM calls for its whole life (see web.py for the why).
# `initializer` runs _init_com() once, before any task, on that worker thread.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="desktop",
                               initializer=_init_com)


def _run(fn, *args, **kwargs):
    """Run a UIA function on the dedicated desktop thread and return its result."""
    return _executor.submit(fn, *args, **kwargs).result()


# Control types worth showing/clicking (the things a user actually interacts with).
_INTERACTABLE = {
    "ButtonControl", "MenuItemControl", "EditControl", "CheckBoxControl",
    "RadioButtonControl", "ComboBoxControl", "ListItemControl", "TabItemControl",
    "HyperlinkControl", "TreeItemControl", "SplitButtonControl", "MenuControl",
    "DocumentControl",
}

_MODIFIERS = {"ctrl": "{Ctrl}", "control": "{Ctrl}", "alt": "{Alt}",
              "shift": "{Shift}", "win": "{Win}"}


# --- helpers (run only on the desktop thread) --------------------------------

def _find_window(name):
    """First top-level window whose title contains `name` (case-insensitive)."""
    root = auto.GetRootControl()
    name_l = name.lower()
    for w in root.GetChildren():
        if w.Name and name_l in w.Name.lower():
            return w
    return None


def _target_window(name):
    """The window to act on: matched by `name`, or the current foreground one."""
    if name:
        return _find_window(name)
    ctrl = auto.GetForegroundControl()
    while ctrl and ctrl.ControlTypeName not in ("WindowControl", "PaneControl"):
        ctrl = ctrl.GetParentControl()
    return ctrl


def _walk(ctrl, on_node, depth=0, max_depth=14):
    """Depth-first walk of the control tree, calling on_node(node) for each.
    on_node returns True to stop the whole walk early."""
    if depth > max_depth:
        return False
    for child in ctrl.GetChildren():
        if on_node(child):
            return True
        if _walk(child, on_node, depth + 1, max_depth):
            return True
    return False


# --- tool implementations ----------------------------------------------------

def _list_windows_impl():
    root = auto.GetRootControl()
    names = [w.Name for w in root.GetChildren()
             if w.Name and w.ControlTypeName == "WindowControl"]
    return "Open windows:\n" + "\n".join(f"- {n}" for n in names) if names \
        else "I don't see any normal app windows open."


def _focus_app_impl(name):
    w = _find_window(name)
    if w is None:
        return f"I don't see a window matching '{name}'."
    w.SwitchToThisWindow()       # bring it to the foreground
    return f"Switched to '{w.Name}'."


def _describe_window_impl(name=None):
    w = _target_window(name)
    if w is None:
        return f"I couldn't find a window matching '{name}'." if name \
            else "I couldn't tell which window is in front."
    items = []

    def collect(node):
        if node.ControlTypeName in _INTERACTABLE and node.Name:
            label = f"{node.ControlTypeName.replace('Control', '')}: {node.Name}"
            if label not in items:
                items.append(label)
        return len(items) >= 80

    _walk(w, collect)
    if not items:
        return (f"'{w.Name}' exposes no named controls — its UI is likely "
                f"custom-drawn, so a vision approach would be needed here.")
    return f"Controls in '{w.Name}':\n" + "\n".join(f"- {x}" for x in items)


def _click_element_impl(name, window=None):
    w = _target_window(window)
    if w is None:
        return "I couldn't find that window."
    name_l = name.lower()
    hit = []

    def match(node):
        if (node.Name and name_l in node.Name.lower()
                and node.ControlTypeName in _INTERACTABLE):
            hit.append(node)
            return True
        return False

    _walk(w, match)
    if not hit:
        return f"I couldn't find a control named '{name}' in '{w.Name}'."
    ctrl = hit[0]
    try:
        pattern = ctrl.GetInvokePattern()
        pattern.Invoke()                     # clean programmatic click
    except Exception:
        ctrl.Click()                         # fall back to a real mouse click
    return f"Clicked '{ctrl.Name}'."


def _read_window_impl(name=None):
    w = _target_window(name)
    if w is None:
        return (f"I couldn't find a window matching '{name}'." if name
                else "I couldn't tell which window is in front.")
    parts = []

    def collect(node):
        t = node.ControlTypeName
        if t in ("DocumentControl", "EditControl"):
            try:                                  # the body text of a doc/field
                val = node.GetValuePattern().Value
                if val:
                    parts.append(val)
            except Exception:
                pass
        elif t == "TextControl" and node.Name:    # labels, chat lines, etc.
            parts.append(node.Name)
        return sum(len(p) for p in parts) >= 6000  # stop once we have plenty

    _walk(w, collect)
    text = "\n".join(parts).strip()
    if not text:
        return (f"'{w.Name}' exposes no readable text — its UI may be "
                f"custom-drawn (that's where vision would be needed).")
    return f"Text in '{w.Name}':\n{text[:3000]}"


_EDIT_TYPES = ("EditControl", "DocumentControl", "ComboBoxControl")


def _type_text_impl(text, window, field=None):
    # The #1 failure was typing into SERENE's own window (it had focus). Fix:
    # bring the TARGET app to the front first, THEN focus its box and type.
    w = _find_window(window)
    if w is None:
        return f"I couldn't find a window matching '{window}'."
    w.SwitchToThisWindow()                 # target app to the foreground
    time.sleep(0.2)                        # let the focus change settle
    hits = []
    if field:
        _walk(w, lambda n: (hits.append(n) or True)
              if (n.Name and field.lower() in n.Name.lower()
                  and n.ControlTypeName in _EDIT_TYPES) else False)
        if not hits:
            return f"I couldn't find a field named '{field}' in '{w.Name}'."
    else:
        _walk(w, lambda n: (hits.append(n) or True)
              if n.ControlTypeName in _EDIT_TYPES else False)
    if hits:
        try:
            hits[0].SetFocus()             # put the cursor in the target box
        except Exception:
            try:
                hits[0].Click()
            except Exception:
                pass
    # Escape UIA SendKeys' only special chars (braces); plain text types as-is.
    safe = text.replace("{", "{{}").replace("}", "{}}")
    auto.SendKeys(safe, waitTime=0)
    return f"Typed into '{w.Name}': {text[:60]}"


def _press_keys_impl(keys, window=None):
    if window:                             # target a specific app: bring it forward
        w = _find_window(window)
        if w is None:
            return f"I couldn't find a window matching '{window}'."
        w.SwitchToThisWindow()
        time.sleep(0.2)
    seq = ""
    for part in (p.strip().lower() for p in keys.split("+") if p.strip()):
        if part in _MODIFIERS:
            seq += _MODIFIERS[part]
        elif len(part) == 1:
            seq += part
        else:
            seq += "{" + part.capitalize() + "}"   # named key: enter, tab, f5...
    if not seq:
        return "No keys to press."
    auto.SendKeys(seq, waitTime=0)
    return f"Pressed {keys}."


# --- tools: thin wrappers that run the impl on the desktop thread ------------

@tool("list_windows", "List the app windows currently open on the desktop.", {})
def list_windows():
    return _run(_list_windows_impl)


@tool("focus_app", "Bring an already-open app window to the foreground by name.",
      {"name": {"type": "string",
                "description": "Part of the window title, e.g. 'notepad' or 'spotify'."}},
      required=["name"])
def focus_app(name):
    return _run(_focus_app_impl, name)


@tool("describe_window",
      "List the clickable controls (buttons, menus, fields) of an app window, so "
      "you know what you can click. Defaults to the window in front.",
      {"name": {"type": "string",
                "description": "Part of the window title to inspect. Optional; "
                               "omit for the foreground window."}})
def describe_window(name=None):
    return _run(_describe_window_impl, name)


@tool("click_element",
      "Click a control (button, menu item, etc.) in an app window, found by its "
      "visible name. Use describe_window first if unsure of the name.",
      {"name": {"type": "string", "description": "The control's visible label, e.g. 'Save'."},
       "window": {"type": "string",
                  "description": "Part of the window title to look in. Optional; "
                                 "omit for the foreground window."}},
      required=["name"])
def click_element(name, window=None):
    return _run(_click_element_impl, name, window)


@tool("read_window",
      "Read the visible text of an app window (a chat, document, page, etc.). "
      "Defaults to the window in front.",
      {"name": {"type": "string",
                "description": "Part of the window title to read. Optional; omit "
                               "for the foreground window."}})
def read_window(name=None):
    return _run(_read_window_impl, name)


@tool("type_text",
      "Type text into a specific app. ALWAYS pass `window` (part of the target "
      "app's title) — it brings that app to the front so the text goes there and "
      "NOT into SERENE's own window. Add `field` if you know the box's name.",
      {"text": {"type": "string", "description": "The text to type."},
       "window": {"type": "string",
                  "description": "Part of the target app's window title, e.g. "
                                 "'Notepad', 'Untitled', 'Chrome'. Required."},
       "field": {"type": "string",
                 "description": "Name of the box to type into, e.g. 'Text editor' "
                                "or 'Message'. Optional."}},
      required=["text", "window"])
def type_text(text, window, field=None):
    if not confirm(f'type "{text[:80]}" into {window}'):
        return "Cancelled — I didn't type anything."
    return _run(_type_text_impl, text, window, field)


@tool("press_keys",
      "Send a keyboard shortcut, e.g. 'ctrl+s', 'alt+f4', 'enter'. Pass `window` "
      "to target a specific app (brings it to the front first).",
      {"keys": {"type": "string",
                "description": "Keys joined by '+', e.g. 'ctrl+s' or 'ctrl+shift+n'."},
       "window": {"type": "string",
                  "description": "Part of the target app's window title. Optional; "
                                 "omit for the current foreground app."}},
      required=["keys"])
def press_keys(keys, window=None):
    where = f" in {window}" if window else ""
    if not confirm(f"press {keys}{where}"):
        return "Cancelled — I didn't press anything."
    return _run(_press_keys_impl, keys, window)
