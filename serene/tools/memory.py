"""memory.py — let SERENE pin something to PERMANENT (Core) memory on demand.

Normally facts are saved by the end-of-session reflection pass. This tool lets
the user say "remember my name is …" / "never forget …" and have it stored
immediately in the Core tier — always recalled, never decayed.
"""
from serene.tools.registry import tool
from serene.memory.store import pin_fact


@tool("remember",
      "Permanently remember an important fact about the user — their name, a key "
      "person, or anything they explicitly ask you to never forget. Stored in "
      "permanent (Core) memory.",
      {"key": {"type": "string",
               "description": "Short snake_case label, e.g. 'user_name'."},
       "value": {"type": "string",
                 "description": "The fact in third person, e.g. \"The user's name "
                                "is Srikesh.\""}},
      required=["key", "value"])
def remember(key, value):
    pin_fact(key, value)
    return f"Saved to permanent memory: {value}"
