"""web.py — SERENE's browser hands (tier 2), driving real Chrome via Playwright.

THREADING NOTE (important): Playwright's sync API is *thread-bound* — every call
must happen on the same thread that started it. But the desktop GUI hands each
chat message to a different worker thread, so calling the browser directly would
crash on the 2nd message ("cannot switch to a different thread").

Fix: we funnel ALL browser work through ONE dedicated thread — a single-worker
ThreadPoolExecutor. Each tool is a thin wrapper that ships its real work
(`*_impl`) to that thread via `_run()` and waits for the result. So no matter
which GUI thread calls a tool, Playwright is only ever touched from its owner
thread.
"""
import os
import atexit
from concurrent.futures import ThreadPoolExecutor

from playwright.sync_api import sync_playwright
from serene.tools.registry import tool

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".chrome_profile")

_pw = None
_ctx = None
_active = None        # the tab the tools currently act on

# The one thread that owns Playwright for its whole life. max_workers=1 means
# every task we submit runs on the SAME single thread, which is exactly what
# Playwright's sync API needs.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")


def _run(fn, *args, **kwargs):
    """Run a browser function on the dedicated browser thread and return its
    result (or re-raise its error) to the caller's thread."""
    return _executor.submit(fn, *args, **kwargs).result()


# --- raw implementations: these ONLY ever run on the browser thread ----------

def _browser():
    """Make sure the Chrome window exists, and return its context."""
    global _pw, _ctx
    if _ctx is None:
        _pw = sync_playwright().start()                        # the engine
        _ctx = _pw.chromium.launch_persistent_context(         # a real Chrome window
            USER_DATA_DIR,                              # folder to save cookies/logins
            headless=False,                             # visible so you can watch
            channel="chrome",                           # use your installed Chrome
            args=[                                      # skip Chrome's startup dialogs
                "--no-first-run",                       #  - no "welcome to Chrome"
                "--no-default-browser-check",           #  - no "make me default?"
                "--profile-directory=Default",          #  - use Default profile, skip the picker
                "--hide-crash-restore-bubble",          #  - no "restore pages?" after a hard exit
            ],
        )
    return _ctx


def _is_blank(page):
    """True if a tab has nothing real loaded yet (the startup/new-tab page)."""
    return page.url in ("", "about:blank") or page.url.startswith("chrome://")


def _page():
    """The ACTIVE tab — the one read/click act on. Adopt or open one if needed."""
    global _active
    ctx = _browser()
    if _active is None or _active.is_closed():
        _active = ctx.pages[0] if ctx.pages else ctx.new_page()
    return _active


def _open_impl(url):
    global _active
    ctx = _browser()
    if not url.startswith("http"):
        url = "https://" + url
    # If the active tab already has real content, open a NEW tab so we don't
    # clobber it (e.g. a song playing). If it's blank, just reuse it.
    if _active is not None and not _active.is_closed() and not _is_blank(_active):
        _active = ctx.new_page()
    else:
        _active = _page()
    _active.goto(url)
    _active.bring_to_front()       # show the tab we just opened
    return f"Opened {_active.title()}."


def _read_impl():
    p = _page()
    return p.inner_text("body")[:3000]


def _click_impl(selector):
    p = _page()
    p.click(selector)
    return f"Clicked {selector}."


def _youtube_impl(query):
    # Runs entirely on the browser thread, calling the impls directly (NOT the
    # wrapped tools) so it doesn't deadlock the single-worker pool.
    url = "https://www.youtube.com/results?search_query=" + query.replace(" ", "+")
    _open_impl(url)
    _click_impl("a#video-title")
    return f"Playing the top result for '{query}' on YouTube."


def _close_tab_impl(match=None):
    global _active
    ctx = _browser()
    pages = ctx.pages
    if not pages:
        return "There are no tabs open."
    # Pick which tab: one matching `match` in its title/URL, else the active one.
    if match:
        target = next((pg for pg in pages
                       if match.lower() in (pg.url + " " + (pg.title() or "")).lower()),
                      None)
        if target is None:
            return f"I couldn't find an open tab matching '{match}'."
    elif _active is not None and not _active.is_closed():
        target = _active
    else:
        target = pages[-1]
    try:
        label = target.title() or target.url
    except Exception:
        label = target.url
    target.close()                          # close ONLY this tab, not the browser
    remaining = ctx.pages
    _active = remaining[-1] if remaining else None   # move active to another tab
    return f"Closed the tab '{label}'."


# --- tools: thin wrappers that run the impl on the browser thread ------------

@tool("web_open", "Open a web page in the browser.",
      {"url": {"type": "string", "description": "The web address to open, e.g. youtube.com"}},
      required=["url"])
def web_open(url):
    return _run(_open_impl, url)


@tool("web_read", "Read the visible text of the current web page.", {})
def web_read():
    return _run(_read_impl)


@tool("web_click",
      "Click an element on the current web page, found by CSS selector or visible text.",
      {"selector": {"type": "string",
                    "description": "CSS selector or text= of the element to "
                                   "click, e.g. 'text=Sign in' or 'a#video-title'."}},
      required=["selector"])
def web_click(selector):
    return _run(_click_impl, selector)


@tool("youtube_play", "Search YouTube for a video and play the first result.",
      {"query": {"type": "string", "description": "what to search & play, e.g. 'lofi hip hop'"}},
      required=["query"])
def youtube_play(query):
    return _run(_youtube_impl, query)


@tool("web_close_tab",
      "Close a single browser tab WITHOUT closing the whole browser. Closes the "
      "current tab, or the tab matching a word from its title/URL.",
      {"match": {"type": "string",
                 "description": "Optional word from the tab's title or URL to "
                                "pick which tab to close, e.g. 'youtube'. Omit "
                                "to close the current tab."}})
def web_close_tab(match=None):
    return _run(_close_tab_impl, match)


# --- clean shutdown ----------------------------------------------------------

def _close_impl():
    global _ctx, _pw
    if _ctx is not None:
        try:
            _ctx.close()
        except Exception:
            pass
    if _pw is not None:
        try:
            _pw.stop()
        except Exception:
            pass


@atexit.register
def _shutdown():
    """On program exit, close the browser cleanly ON its owner thread, then stop
    the worker pool. Clean exit = Chrome won't try to restore old tabs."""
    try:
        if _ctx is not None:
            _run(_close_impl)
    except Exception:
        pass
    _executor.shutdown(wait=False)
