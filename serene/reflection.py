"""reflection.py — the "what should I remember?" pass.

After a conversation ends, we hand the transcript to a capable brain and ask
it to pull out (1) durable FACTS about the user and (2) a one-line EPISODE
summary. Those get saved through store.py, so memory fills itself over time.

We use Groq (llama-3.3-70b) for this: it's fast, free, and reliable at
producing strict JSON — which matters because we parse its output. The local
3B model is too weak for dependable structured extraction.
"""
import json
from datetime import date

from serene.providers.groq import GroqProvider
from serene.memory.store import save_fact, save_episode, decay

_extractor = GroqProvider()

_EXTRACTION_PROMPT = """You are SERENE's memory system. Read the conversation \
between the user and SERENE, and extract what is worth remembering long-term \
about the USER (never about SERENE).

Today's date is {today}.

Return ONLY valid JSON, no prose, in exactly this shape:
{{
  "facts": [
    {{"key": "snake_case_key", "value": "the fact, written in third person", "importance": 3}}
  ],
  "summary": "one sentence describing what happened, beginning with the date"
}}

Rules:
- Only DURABLE facts: preferences, relationships, goals, routines, important \
events, recurring feelings. Ignore small talk and one-off trivia.
- importance: 5 = CORE identity that must NEVER be forgotten — the user's NAME, \
key people/relationships, and defining facts about who they are. 3-4 = important \
ongoing things, 1-2 = minor preferences.
- If the user states their name or a key relationship, you MUST capture it at \
importance 5.
- If nothing is worth remembering, use an empty "facts" list.
- Keep each value short and specific.
- The summary should capture the emotional/topical gist in one sentence."""


def _to_transcript(history):
    """Turn the message list into a readable transcript for the extractor."""
    lines = []
    for msg in history:
        who = "User" if msg["role"] == "user" else "SERENE"
        lines.append(f"{who}: {msg['content']}")
    return "\n".join(lines)


def _parse_json(text):
    """LLMs sometimes wrap JSON in prose or code fences — grab the object
    between the first '{' and the last '}'."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None


def reflect(history):
    """Extract and save facts + an episode summary from a conversation.
    Returns a short report of what was saved (or None if nothing)."""
    if not history:
        return None

    messages = [
        {"role": "system", "content": _EXTRACTION_PROMPT.format(today=date.today())},
        {"role": "user", "content": _to_transcript(history)},
    ]

    try:
        raw = _extractor.chat(messages)
    except Exception as e:
        return f"(memory reflection failed: {e})"

    data = _parse_json(raw)
    if not data:
        return "(memory reflection produced no usable data)"

    saved_facts = 0
    for fact in data.get("facts", []):
        try:
            imp = fact.get("importance", 1)
            # importance 5 == permanent identity -> the Core tier.
            tier = "core" if imp >= 5 else "ambient"
            save_fact(fact["key"], fact["value"], imp, tier=tier)
            saved_facts += 1
        except (KeyError, TypeError):
            continue   # skip malformed entries

    summary = data.get("summary")
    if summary:
        save_episode(summary)

    decay()   # gentle forgetting of stale ambient memory (Core is untouched)

    return f"(remembered {saved_facts} fact(s)" + \
           (" and this session" if summary else "") + ")"
