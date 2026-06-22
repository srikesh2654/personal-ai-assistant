"""classifier.py — the split-second 'is this an action or just chat?' decision.

This is what lets SERENE feel seamless: you never pick a mode. We ask a tiny,
very fast Groq model to label the LATEST message ACTION (needs to touch the
computer) or CHAT (just talking), and route accordingly.

It also sees the recent conversation, so follow-ups like "now write fibonacci
in it" are understood as actions on the file just created — not chatter.

We use llama-3.1-8b-instant: small and near-instant. On any failure we fall
back to CHAT (safer: don't reach for tools unless we're fairly sure).
"""
from groq import Groq

from serene.config import GROQ_API_KEY

_client = Groq(api_key=GROQ_API_KEY)
_MODEL = "llama-3.1-8b-instant"

_PROMPT = """Classify the LAST user message as ACTION or CHAT. Use the recent
conversation ONLY to resolve references like "it" or "that file".

ACTION = wants something DONE on the computer: open/launch/close an app;
list/show/browse/search/read/move/rename/delete files or folders; CREATE,
SAVE, or WRITE content/code/programs into a file on disk; or CONTROL music /
Spotify (play a song or playlist, pause/resume, skip, volume, what's playing).
CHAT = anything else: conversation, feelings, advice, opinions, or EXPLAINING
a topic without saving anything.

Examples:
"open spotify" -> ACTION
"what's in my downloads folder" -> ACTION
"find my resume file" -> ACTION
"delete that old screenshot" -> ACTION
"create a file notes.txt with my todo list" -> ACTION
"write a python program that prints hello" -> ACTION
"now write a program in it that prints fibonacci" -> ACTION
"put my todo list in that file" -> ACTION
"add a function to it" -> ACTION
"save that to a file on my desktop" -> ACTION
"play despacito on spotify" -> ACTION
"play some lofi" -> ACTION
"skip this song" -> ACTION
"what song is playing" -> ACTION
"turn the volume down" -> ACTION
"how are you?" -> CHAT
"i had a rough day" -> CHAT
"what do you remember about me" -> CHAT
"explain how recursion works" -> CHAT
"open youtube" -> ACTION
"go to wikipedia and tell me about cats" -> ACTION
"what's on hacker news" -> ACTION
"click the save button" -> ACTION
"type hello world in notepad" -> ACTION
"press ctrl+s" -> ACTION
"switch to spotify" -> ACTION
"what windows do i have open" -> ACTION
"remember my name is srikesh" -> ACTION
"never forget that my sister's name is anu" -> ACTION


Reply with one word only: ACTION or CHAT."""


def needs_tools(message, history=None):
    convo = ""
    if history:
        recent = history[-4:]   # last ~2 exchanges, for resolving "it"/"that"
        lines = []
        for m in recent:
            who = "User" if m["role"] == "user" else "Assistant"
            lines.append(f"{who}: {m['content'][:160]}")
        convo = "Recent conversation:\n" + "\n".join(lines) + "\n\n"

    try:
        resp = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _PROMPT},
                {"role": "user", "content": convo + f"LAST user message: {message}"},
            ],
            max_tokens=3,
            temperature=0,
        )
        return "ACTION" in resp.choices[0].message.content.upper()
    except Exception:
        return False
