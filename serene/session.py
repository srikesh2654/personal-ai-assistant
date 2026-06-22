"""session.py — SERENE's conversation logic, independent of any interface.

The CLI and the GUI both just call session.send(text). Inside, SERENE decides
per-message whether you're CHATTING or asking for an ACTION:
  - CHAT   -> your selected brain (router) with the full warm persona
  - ACTION -> the tool-using agent (hands) with the lean tool persona
So you never switch modes manually — it just happens.
"""
import serene.router as router
from serene.persona import SYSTEM_PROMPT, TOOL_PROMPT
from serene.memory.recall import recall
from serene.reflection import reflect
from serene.classifier import needs_tools
from serene.agent import chat_with_tools


class Session:
    def __init__(self):
        self.history = []
        self.memory_on = True      # when False, this chat is never saved to the DB

    def set_memory(self, on):
        """Turn memory saving on/off for this session. Returns the new state."""
        self.memory_on = bool(on)
        return self.memory_on

    def _system(self, base, user_msg):
        """Persona + any relevant memories for this message."""
        memory = recall(user_msg)
        if memory:
            return base + "\n\n--- What you remember ---\n" + memory
        return base

    def send(self, user_msg):
        if needs_tools(user_msg, self.history):
            # ACTION: lean persona + hands (the agent loop with tools)
            system = self._system(TOOL_PROMPT, user_msg)
            brain = chat_with_tools
        else:
            # CHAT: full warm persona + the user's chosen brain
            system = self._system(SYSTEM_PROMPT, user_msg)
            brain = router.chat

        messages = [{"role": "system", "content": system}] + self.history + \
                   [{"role": "user", "content": user_msg}]
        reply = brain(messages)

        self.history.append({"role": "user", "content": user_msg})
        self.history.append({"role": "assistant", "content": reply})
        return reply

    def end(self):
        # In no-memory mode we never write this conversation to the database.
        if not self.memory_on:
            return "(private chat — nothing was saved to memory)"
        return reflect(self.history)
