"""server.py — SERENE as a small web server, so a phone can talk to her.

Her BRAIN runs here on the PC (same Session, memory, brains, and — because the
tools run on this machine — the same hands). The phone is just a chat client
(the PWA in web_app/) that calls these endpoints over your network.

Run:  .venv\\Scripts\\python.exe -m serene.server
Then open  http://<this-pc-ip>:8765  on your phone (same Wi-Fi, or via Tailscale).

Auth: if a password is set (SERENE_PASSWORD_HASH), /api/unlock exchanges it for a
token that every other call must carry. Single-user by design.
"""
import os
import hashlib
import secrets

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles

import serene.router as router
from serene.config import SERENE_PASSWORD_HASH
from serene.session import Session
from serene.tools.confirm import set_confirm

# Tools run on THIS PC with no GUI dialog available, so confirmations can't pop a
# window. For now we auto-approve so actions don't hang. TODO: route confirms to
# the phone as a yes/no message before doing anything destructive.
set_confirm(lambda action: True)

app = FastAPI(title="SERENE")
_session = Session()
_tokens = set()                      # valid bearer tokens (in-memory)

_WEB = os.path.join(os.path.dirname(__file__), "web_app")


def _auth(authorization: str = Header(None)):
    """Reject calls without a valid token (when a password is configured)."""
    if not SERENE_PASSWORD_HASH:
        return                       # no lock set -> open
    tok = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
    if tok not in _tokens:
        raise HTTPException(status_code=401, detail="locked")


@app.get("/api/config")
def config():
    """Public: tells the client whether a password is required."""
    return {"locked": bool(SERENE_PASSWORD_HASH)}


@app.post("/api/unlock")
def unlock(body: dict):
    pw = body.get("password", "")
    ok = (not SERENE_PASSWORD_HASH
          or hashlib.sha256(pw.encode()).hexdigest() == SERENE_PASSWORD_HASH)
    if not ok:
        return {"ok": False}
    token = secrets.token_urlsafe(24)
    _tokens.add(token)
    return {"ok": True, "token": token}


@app.get("/api/state", dependencies=[Depends(_auth)])
def state():
    return {
        "brain": router.active_brain,
        "brains": [b for b in router.brains if b != "agent"],
        "memory_on": _session.memory_on,
    }


@app.post("/api/send", dependencies=[Depends(_auth)])
def send(body: dict):
    return {"reply": _session.send(body.get("message", ""))}


@app.post("/api/switch", dependencies=[Depends(_auth)])
def switch(body: dict):
    router.switch(body.get("brain", "local"))
    return {"brain": router.active_brain}


@app.post("/api/memory", dependencies=[Depends(_auth)])
def memory(body: dict):
    return {"memory_on": _session.set_memory(bool(body.get("on", True)))}


@app.post("/api/end", dependencies=[Depends(_auth)])
def end(body: dict = None):
    return {"report": _session.end() or ""}


# Serve the phone PWA (index.html, manifest, service worker, icons) at the root.
# Mounted LAST so the /api/* routes above take priority.
app.mount("/", StaticFiles(directory=_WEB, html=True), name="web")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
