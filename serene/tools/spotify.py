"""spotify.py — SERENE's Spotify control (tier 1: the official Web API).

Why the API and not clicking the Spotify window? Because it's exact and
reliable: we search for a track, get its unique URI, and tell Spotify to play
it — no guessing where a button is on screen.

It uses spotipy's Authorization-Code flow. The FIRST time a Spotify tool runs,
a browser tab opens once for you to log in and approve; after that the token is
cached in .spotify_cache and refreshed silently, so it never asks again.

Requirements:
  - A free Spotify "developer app" (https://developer.spotify.com/dashboard)
    for the client id/secret, with a Redirect URI of
    http://127.0.0.1:8888/callback added to its settings.
  - A Spotify PREMIUM account — Spotify only allows playback control on Premium.

Put these in your .env:
    SPOTIFY_CLIENT_ID=...
    SPOTIFY_CLIENT_SECRET=...
    SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback   (optional; this is the default)
"""
import os

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from serene.tools.registry import tool

# Scopes we need: see what's playing + control playback. (search needs none.)
_SCOPE = "user-read-playback-state user-modify-playback-state"

# Cache the login token next to the .env, at the project root.
_CACHE = os.path.join(os.path.dirname(__file__), "..", "..", ".spotify_cache")

_client = None


def _sp():
    """Build the Spotify client lazily, so importing this module never fails
    just because credentials aren't set yet — only USING a tool does."""
    global _client
    if _client is None:
        if not os.getenv("SPOTIFY_CLIENT_ID"):
            raise RuntimeError(
                "Spotify isn't set up yet — add SPOTIFY_CLIENT_ID and "
                "SPOTIFY_CLIENT_SECRET to your .env.")
        _client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI",
                                    "http://127.0.0.1:8888/callback"),
            scope=_SCOPE,
            cache_path=_CACHE,
            open_browser=True,
        ))
    return _client


def _active_device(sp):
    """Pick a device to play on: the currently-active one if any, else the
    first available. Returns a device id, or None if Spotify isn't open
    anywhere (the API can't start playback on thin air)."""
    devices = sp.devices().get("devices", [])
    if not devices:
        return None
    for d in devices:
        if d.get("is_active"):
            return d["id"]
    return devices[0]["id"]


_NO_DEVICE = ("I don't see an open Spotify anywhere — open Spotify on your "
              "phone or computer first, then ask me again.")


@tool("spotify_play_song",
      "Search Spotify for a song and play it. Include the artist if known, to "
      "get the right version.",
      {"song": {"type": "string", "description": "The song title to play."},
       "artist": {"type": "string",
                  "description": "Artist name, to pick the right song. Optional."}},
      required=["song"])
def play_song(song, artist=None):
    """Search for a track and start playing it on the active device."""
    sp = _sp()
    query = song if not artist else f"track:{song} artist:{artist}"
    items = sp.search(q=query, type="track", limit=1).get(
        "tracks", {}).get("items", [])
    if not items:
        return f"I couldn't find '{song}' on Spotify."
    track = items[0]
    device = _active_device(sp)
    if device is None:
        return _NO_DEVICE
    sp.start_playback(device_id=device, uris=[track["uri"]])
    who = ", ".join(a["name"] for a in track["artists"])
    return f"Now playing '{track['name']}' by {who}."


@tool("spotify_play_playlist",
      "Search Spotify for a playlist by name and start playing it.",
      {"name": {"type": "string", "description": "The playlist name to play."}},
      required=["name"])
def play_playlist(name):
    """Search for a playlist and start playing it (shuffled context)."""
    sp = _sp()
    items = sp.search(q=name, type="playlist", limit=1).get(
        "playlists", {}).get("items", [])
    if not items:
        return f"I couldn't find a playlist called '{name}'."
    playlist = items[0]
    device = _active_device(sp)
    if device is None:
        return _NO_DEVICE
    sp.start_playback(device_id=device, context_uri=playlist["uri"])
    return f"Playing the '{playlist['name']}' playlist."


@tool("spotify_pause", "Pause Spotify playback.")
def pause():
    sp = _sp()
    sp.pause_playback()
    return "Paused."


@tool("spotify_resume", "Resume Spotify playback.")
def resume():
    sp = _sp()
    device = _active_device(sp)
    if device is None:
        return _NO_DEVICE
    sp.start_playback(device_id=device)
    return "Resumed."


@tool("spotify_next", "Skip to the next song on Spotify.")
def next_track():
    sp = _sp()
    sp.next_track()
    return "Skipped to the next song."


@tool("spotify_previous", "Go back to the previous song on Spotify.")
def previous_track():
    sp = _sp()
    sp.previous_track()
    return "Went back to the previous song."


@tool("spotify_now_playing", "Say what song is currently playing on Spotify.")
def now_playing():
    sp = _sp()
    current = sp.current_playback()
    if not current or not current.get("item"):
        return "Nothing's playing right now."
    track = current["item"]
    who = ", ".join(a["name"] for a in track["artists"])
    state = "Playing" if current.get("is_playing") else "Paused on"
    return f"{state} '{track['name']}' by {who}."


@tool("spotify_set_volume",
      "Set the Spotify volume to a percentage from 0 to 100.",
      {"percent": {"type": "integer",
                   "description": "Volume level, 0 (mute) to 100 (max)."}},
      required=["percent"])
def set_volume(percent):
    sp = _sp()
    level = max(0, min(100, int(percent)))
    sp.volume(level)
    return f"Set the volume to {level}%."
