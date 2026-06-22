# SERENE — Progress & Errors Log

A running record of what we've built into SERENE's "hands" (app control), the
bugs we hit along the way, and how we fixed them. Newest work at the top.

---

## App-control architecture (the plan)

SERENE controls apps in **layered tiers** — always prefer the most structured,
reliable mechanism; fall back to pixels only as a last resort:

| Tier | Mechanism | Used for | Library |
|------|-----------|----------|---------|
| 1 | Official app API | Apps with one (Spotify) | `spotipy` |
| 2 | Browser DOM (real Chrome) | Anything on the web | **Playwright** |
| 3 | Windows accessibility tree | Native desktop apps | `pywinauto` *(planned)* |
| 4 | Vision + mouse | Last resort (canvas, games) | `pyautogui` + vision model *(planned)* |

**Why layered:** pixel-clicking is what makes automation brittle. Driving the
DOM / using APIs is reliable. Each tier degrades gracefully to the next.

**Build order:** (1) tool refactor ✅ → (2) Spotify ✅ → (3) Chrome/Playwright ✅
→ (4) native a11y → (5) vision fallback.

---

## Slice 1 — Tool registry refactor ✅

**Goal:** make adding new tools painless before piling on more.

**What changed:** `serene/tools/registry.py` now exposes a `@tool(name,
description, parameters, required)` **decorator**. Each tool declares its own
schema right above the function; the registry auto-collects them into
`TOOL_SCHEMAS` + `TOOL_FUNCTIONS`. Tools are split into modules
(`files.py`, `spotify.py`, `web.py`) and the registry imports each at the
bottom (which runs their decorators).

**Lesson learned:** keep the module imports at the *bottom* of `registry.py`,
after `tool` is defined, to avoid a circular-import error (the tool modules
import `tool` from the registry).

---

## Slice 2 — Spotify (tier 1) ✅

**Tools:** `spotify_play_song`, `spotify_play_playlist`, `spotify_pause`,
`spotify_resume`, `spotify_next`, `spotify_previous`, `spotify_now_playing`,
`spotify_set_volume`.

**How:** `spotipy` with the Authorization-Code flow. Lazy `_sp()` client so
importing the module never fails when creds are missing — only *using* a tool
does. Token cached in `.spotify_cache` (gitignored). Requires Spotify
**Premium** + a dev app with redirect `http://127.0.0.1:8888/callback`.

**Verified:** logged in, played "Blinding Lights" on the SRIKESH device,
now-playing + pause confirmed.

**Gotchas:**
- Playback control needs an **open Spotify device** somewhere (phone/PC) — the
  API can't play on nothing. We surface a friendly message if no device.
- `me()` returns `product: None` unless the `user-read-private` scope is
  requested — harmless, we don't need it.

---

## Slice 3 — Chrome via Playwright (tier 2) ✅

**Tools:** `web_open`, `web_read` (3000-char cap), `web_click`, `youtube_play`,
`web_close_tab`. `youtube_play` is **composed** from `web_open` + `web_click`
(reuse, not re-implementation).

**`web_close_tab`:** closes a SINGLE tab (by a word in its title/URL, or the
active tab) without killing the browser. Added because the only "close" option
SERENE had before was `close_app("chrome")`, which nuked all of Chrome. After
closing, `_active` moves to a remaining tab.

**How:** Playwright **sync** API (tools are synchronous). A per-process
singleton `_page()` lazily launches `launch_persistent_context` with
`channel="chrome"` (real installed Chrome) + a `.chrome_profile` dir
(gitignored) so logins persist. Headed so you can watch.

**Design note — dedicated vs general tools:** `youtube_play` is technically
redundant (the agent *could* chain `web_open`+`web_read`+`web_click`), but a
dedicated tool encodes the URL + selector knowledge once so it works reliably
every time and in one step. Rule of thumb: **general tools for the long tail,
dedicated tools for high-value workflows you want flawless.**

### Bugs hit & fixes

**1. `TargetClosedError: ...browser has been closed`**
- *Cause:* two short test processes launched Chrome on the **same profile dir**
  at overlapping times and fought over it; one instance closed the other's
  target.
- *Fix:* none needed in code — this is a test-only artifact of running many
  short `python -c` scripts. The real app is **one long-lived process with one
  browser**, so it never happens. (If running tests back-to-back, make sure no
  stale automation Chrome is still open.)

**2. `TimeoutError: waiting for locator("text=More information")`**
- *Cause:* **stale selector** — `example.com` was redesigned; its link text is
  now "Learn more", not "More information…". The code was fine; the selector
  pointed at content that no longer existed.
- *Fix:* use the real text (`text=Learn more`). **Selectors are only as good as
  what's actually on the page** — verify with
  `page.locator('a').all_text_contents()` when in doubt.

**3. "Who's using Chrome?" profile picker on launch**
- *Cause:* launching **real Chrome** (`channel="chrome"`) while the everyday
  Chrome was already running triggered Chrome's first-run / profile-picker UI in
  the visible window (Playwright was driving a *background* tab the whole time —
  which is why test scripts still printed correct URLs).
- *Fix:* launch flags →
  `--no-first-run`, `--no-default-browser-check`, `--profile-directory=Default`.

**4. "It only opens YouTube" (never any other site)**
- *Cause:* the killed test process made Chrome think it **crashed**, so on the
  next launch it did **session restore** and reopened the old YouTube tab;
  navigations went to a background tab while the visible window stayed stuck on
  the restored YouTube.
- *Fix:* (a) `--hide-crash-restore-bubble` flag, and (b) an **`atexit`**
  shutdown handler `_close()` that closes the context + stops Playwright cleanly
  on program exit — so Chrome exits cleanly and has no "previous session" to
  restore.
- *Verified:* opened wikipedia → github → hacker news → youtube in sequence in
  one process, all in a single reused tab, clean shutdown.

**5. "Can't open a new tab when one is already open" (clobbering)**
- *Cause:* `_page()` always returned `pages[0]`, so every `web_open`
  re-navigated the *same* tab — opening a second site killed whatever was in the
  first (e.g. a playing video), and two pages could never coexist.
- *Fix:* track an **`_active`** tab pointer. Split `_browser()` (ensures the
  context) from `_page()` (returns `_active`). `web_open` now opens a **new tab**
  (reusing only a blank startup tab via `_is_blank()`), `bring_to_front()`s it,
  and sets it active. `web_read`/`web_click` act on `_active`.
- *Verified:* `youtube_play('lofi')` then `web_open('wikipedia')` → 2 tabs,
  YouTube keeps playing in tab 0 while Wikipedia opens in tab 1.

**6. Second web command crashes in the GUI ("can't open a second tab")**
- *Symptom:* in the desktop GUI, the first web command works but the next one
  fails; in CLI/tests it's fine.
- *Cause:* **Playwright's sync API is thread-bound** — it must be used from the
  thread that started it. pywebview runs each chat message on a *different*
  worker thread, so the 2nd call hit a dead thread →
  `Error: cannot switch to a different thread (which happens to have exited)`.
- *Fix:* funnel ALL browser work through ONE dedicated thread — a
  `ThreadPoolExecutor(max_workers=1)`. Each tool is now a thin wrapper that
  ships its real work (`_open_impl`, `_read_impl`, `_click_impl`,
  `_youtube_impl`) to that thread via `_run()`. Composed tools (`youtube_play`)
  call the `*_impl` functions **directly** (not the wrapped tools) to avoid
  deadlocking the single worker. `atexit` shutdown also runs `_close_impl` on
  the browser thread.
- *Verified:* 4 calls each on a different thread (wikipedia/github/youtube/HN)
  all succeed, 4 tabs, no thread error, no deadlock.

**Routing aside:** a separate confusion — SERENE replying "I can't launch
YouTube from this environment, here's a link" — was the **chat brain** (local
llama3.2) answering because the running app still had *stale code* (started
before the web tools were wired in). Always **restart SERENE** after code
changes; Python loads modules once at startup.

### Wiring (so SERENE can use these from chat)
- `from serene.tools import web` added at the bottom of `registry.py` (runs the
  decorators → puts the tools on the model's menu).
- `classifier.py` got web examples ("open youtube", "what's on hacker news") so
  these route to ACTION → the agent.

---

## Slice 4 — Native apps via accessibility (tier 3) ✅

**Goal:** control native Windows apps with no API and no pixel-guessing, using
the OS **UI Automation (UIA)** tree.

**Tools (`serene/tools/desktop.py`):** `list_windows`, `focus_app`,
`describe_window` (lists an app's clickable controls by name), `read_window`
(reads an app's visible TEXT — chats, docs; works on Electron apps like Claude
via the a11y tree), `click_element` (Invoke pattern, falls back to a real
click), `type_text` (field-focused + `confirm()`-gated), `press_keys`
(`confirm()`-gated, e.g. `ctrl+s`). Library: `uiautomation`. Same
single-dedicated-thread pattern as web.py (COM is thread-sensitive).

**Hardening done:** `type_text` and `press_keys` gated through `confirm()` so
nothing types/keys blind.

**Targeting fix (the big one):** typing kept going into SERENE's OWN GUI window
because that window had keyboard focus when the agent acted, and the model often
omitted the target. Fix: **`window` is now REQUIRED** on `type_text`, and the
impl does `SwitchToThisWindow()` on the target app to bring it to the front
BEFORE focusing the box and typing. `press_keys` got an optional `window` that
foregrounds the app first too. Verified: with Calculator in front,
`type_text(window='Notepad')` still typed into Notepad, leaving Calculator
untouched.

**Verified:** Calculator — `focus_app` → `click_element('Seven'/'Plus'/'Eight'/
'Equals')` → read "Display is 15". Notepad — list/focus/describe worked.

### Bugs hit & fixes
**1. `CoInitialize has not been called` (UIA in a pool thread)**
- *Cause:* UIA is COM-based; COM must be initialized on each thread that uses
  it, and the executor's worker thread isn't initialized automatically. (An
  earlier ad-hoc test passed only by timing luck.)
- *Fix:* `ThreadPoolExecutor(..., initializer=_init_com)` where `_init_com`
  calls `comtypes.CoInitializeEx(COINIT_MULTITHREADED)` once on the worker
  thread (MTA needs no message pump).

### Known rough edges (expected for tier 3)
- **`type_text` focus** — FIXED: pass `field` and it focuses that box first.
  Without `field` it still types wherever the cursor is (caller's choice).
- **Sparse trees:** apps that draw their own UI expose few/no named controls →
  `describe_window`/`read_window` say so; those need the (unbuilt) tier-4 vision
  fallback.
- **Safety** — DONE: `type_text`/`press_keys` gated through `confirm()`.

**Classifier:** added native-control examples ("click the save button", "type …
in notepad", "press ctrl+s", "switch to spotify", "what windows do i have open").

## No-memory (private) mode ✅

A per-session toggle so a chat is never written to the database.
- `Session.memory_on` (default True) + `Session.set_memory(on)`. When False,
  `end()` skips `reflect()` entirely → no facts/episodes saved.
- **Recall stays ON** (she still knows you from existing memory); only *writing*
  is disabled. (To also disable recall for full incognito, gate `recall()` in
  `Session._system` on `self.memory_on`.)
- CLI: `/memory on|off`. GUI: 🧠 button in the title bar (bright = on, red/struck
  = off); status line shows `PRIVATE` when off. Backed by `Api.set_memory` /
  `Api.memory_on`.

## Packaging — SERENE.exe ✅

Built a Windows app with **PyInstaller** (onedir): `dist/SERENE/SERENE.exe`
(~86 MB exe, ~960 MB folder). Spec: `serene.spec` (run
`python -m PyInstaller serene.spec --noconfirm`). `collect_all` for the tricky
packages (torch, transformers, tokenizers, huggingface_hub, safetensors,
playwright, webview, comtypes, uiautomation, sklearn, scipy); `serene/ui/
index.html` bundled via `datas`. Windowed (`console=False`); custom icon
`icon.ico` (violet→cyan gradient "S", generated by `make_icon.py`).

- **NOT bundled (must run on the machine):** PostgreSQL+pgvector, Ollama (for the
  `local` brain), Chrome, WebView2 runtime. `.env` lives next to the exe (keys
  kept external).
- **`--noconfirm` wipes `dist/SERENE/`** on rebuild — re-copy `.env` +
  `READ_ME_FIRST.txt` afterward.
- Models are NOT bundled; loaded from the HF cache in the user profile on first
  run.

## Two-tier memory ✅

Problem: SERENE wasn't recalling the user's name. Root cause — the name was
never saved (reflection only runs on a clean exit, and we'd force-killed the app
a lot), AND nothing ever reached the old `PIN_IMPORTANCE>=4` "always inject"
threshold, so that mechanism was dead.

Redesigned memory into two explicit tiers via a `tier` column on `serene_facts`:
- **Core** (`tier='core'`): permanent identity — name, key people. **Always
  injected** into every prompt (no search), **never decayed/deleted**, and
  protected from dedup downgrades (once Core, stays Core).
- **Ambient** (`tier='ambient'`): everything else. Hybrid-searched (surfaced only
  when relevant) and **gently decayed** — `store.decay()` prunes importance≤2
  facts unused >45 days, caps ambient facts at 200 and episodes at 150. Runs at
  the end of every (memory-on) session.

How things reach Core:
- Reflection now assigns **importance 5** to identity (name/key people) →
  mapped to `tier='core'`. Prompt updated to require capturing the name.
- New **`remember` tool** (`serene/tools/memory.py`) pins a fact to Core on
  demand ("remember my name is …"). Classifier routes it to ACTION.

Files: `db.py` (ALTER ADD tier), `store.py` (tier-aware save + `pin_fact` +
`decay`), `recall.py` (core always-inject + ambient tier-filtered hybrid),
`reflection.py` (importance-5→core + calls decay), `tools/memory.py`, registry +
classifier. Verified: migration, core-always-injected on unrelated query, decay
keeps Core, importance-5→core.

## Dedup fix + seeded profile

- **Dedup bug fixed:** `save_fact` was merging distinct facts that merely shared
  a name (pinning "name is Srikesh" then "born on 30 May 2008" overwrote the
  name). Now it matches on **exact key first**, and only falls back to embedding
  similarity with a much stricter threshold (`DEDUP_DISTANCE` 0.2 → 0.10).
- **Seeded Srikesh's profile** (after the wipe): Core = name, date_of_birth
  (stored DOB not age, so it never goes stale). Ambient = education (IIT
  Tirupati, 2nd yr, Mech but branch unfinalised), calculus interest, F1, tennis.

## Memory reset + honesty rule

- **Memory wiped** on user request (`TRUNCATE serene_facts, serene_episodes
  RESTART IDENTITY`) — clean slate to re-teach from scratch.
- **Anti-fabrication rule** added to `persona.py` (both `SYSTEM_PROMPT` and
  `TOOL_PROMPT`): never invent facts/memories about the user; admit "I don't
  know / you haven't told me" instead of guessing; report only real tool
  results. NOTE: the `local` llama3.2-3B brain follows this less reliably than
  gemini/groq — for strict no-bluffing, prefer a bigger brain.

## Reactor lock screen ✅

A password gate on launch, styled as a glowing "reactor core" (concentric
spinning rings, type into the center) — not a plain form.
- Password stored **hashed** (sha256) in `.env` as `SERENE_PASSWORD_HASH`
  (`config.SERENE_PASSWORD_HASH`). Empty hash => no lock.
- `gui.Api.unlock(pw)` compares sha256(pw) to the hash; `Api.lock_enabled()`
  tells the frontend whether to show the lock.
- `ui/index.html`: `#lock` full-window overlay with the reactor SVG + a
  password input; correct → fades out to the chat, wrong → red shake. Has its
  own minimize/close buttons so you can exit while locked.
- Honest scope: a deterrent (gates the GUI), NOT real security — the DB and
  `.env` are still unencrypted on disk.

## Phone access — FastAPI server + PWA ✅

Her BRAIN runs on the PC; the phone is a chat client (Option A).
- `serene/server.py` — FastAPI wrapping the existing `Session`/router/memory.
  Endpoints: `/api/config` (public), `/api/unlock` (password → bearer token),
  `/api/state`, `/api/send`, `/api/switch`, `/api/memory`, `/api/end`. Serves the
  PWA from `serene/web_app/` at `/`. Run: `python -m serene.server` (port 8765,
  binds 0.0.0.0). `start_phone_server.bat` is a double-click launcher.
- `serene/web_app/` — installable PWA: `index.html` (mobile chat + reactor lock,
  uses `fetch`), `manifest.json`, `sw.js`, gradient-S `icon-192/512.png`.
- Auth reuses `SERENE_PASSWORD_HASH`; token stored in phone localStorage.
- Phone (same Wi-Fi) → `http://<pc-ip>:8765` (PC was 192.168.1.42). Outside home:
  Tailscale. Windows Firewall must allow Python on the private network.
- Confirmations auto-approve on the server (no GUI dialog) — TODO: route confirms
  to the phone. Tools still run on the PC (so you can drive the PC from the phone).
- Needs Postgres + Ollama running on the PC, same as the desktop app.

## Environment notes
- Python **3.14.5**, venv at `E:\jarvis\.venv`.
- Playwright **1.60.0**. Uses installed Chrome via `channel="chrome"` — no
  separate Chromium binary download needed.
- `requirements.txt` added at project root.
- Gitignored: `.env`, `.venv/`, `__pycache__/`, `.spotify_cache`,
  `.chrome_profile`.

## Next up
- Tier 4: vision + mouse fallback for sparse-tree apps. On this machine (RTX 3050
  6 GB, already running a local LLM) lean on **Gemini** for vision — local
  GUI-grounding models like OS-Atlas won't fit; Moondream/Florence-2 could.
