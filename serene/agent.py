"""agent.py — the tool-using loop (SERENE's "hands" in action).

A normal chat is one round trip: you talk, the model talks back. A tool-using
agent is a LOOP, because the model might need several steps:

    you: "what's in my Downloads?"
      -> model: "call list_dir(path='Downloads')"      (a tool call, not text)
      -> we run it, feed the file list back
      -> model: "You've got 3 PDFs and an installer."   (final text answer)

So we keep looping: send messages -> if the model asked for tools, run them and
loop again -> if it gave a normal answer, we're done.

We use Groq here because tool-calling needs a capable model, and Groq's API
follows the OpenAI standard, which is the simplest to work with. The local 3B
model can't do this reliably.
"""
from groq import Groq

from serene.config import GROQ_API_KEY, AGENT_MODEL
from serene.tools.registry import TOOL_SCHEMAS, call_tool

_client = Groq(api_key=GROQ_API_KEY)
# gpt-oss uses proper structured function-calling (not Llama's text-tag format
# that Groq's parser sometimes rejects), so it's far more reliable for tools.
_MODEL = AGENT_MODEL
_MAX_STEPS = 5         # safety cap so a confused model can't loop forever
_TOOL_RETRIES = 2      # retry intermittent malformed tool calls before giving up


def _complete(messages):
    """Call the model, retrying if it emits a malformed tool call (an
    intermittent quirk). Raises if it keeps failing."""
    last = None
    for _ in range(_TOOL_RETRIES + 1):
        try:
            return _client.chat.completions.create(
                model=_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
        except Exception as e:
            last = e
            if "tool_use_failed" in str(e):
                continue
            raise
    raise last


def chat_with_tools(messages):
    """Run the agent loop over a message list and return SERENE's final reply.
    `messages` is the usual [{'role','content'}, ...] list."""
    for _ in range(_MAX_STEPS):
        try:
            response = _complete(messages)
        except Exception as e:
            # Even after retries the model couldn't format the call — recover
            # gracefully instead of crashing the whole app.
            if "tool_use_failed" in str(e):
                return ("I fumbled that action a little — could you rephrase "
                        "what you'd like me to do?")
            return f"Something went wrong with that action: {e}"

        msg = response.choices[0].message

        # No tool call => this is the final natural-language answer.
        if not msg.tool_calls:
            return msg.content

        # The model wants to use one or more tools. We must add ITS message
        # (the request) to the history, then add a result for each call —
        # a tool result whose tool_call_id has no matching assistant message
        # is a validation error.
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name,
                                 "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })

        for tc in msg.tool_calls:
            import json
            args = json.loads(tc.function.arguments or "{}")
            result = call_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
        # loop again so the model can use the tool results

    return "(I got stuck taking too many steps on that one.)"


class AgentProvider:
    """Wraps the tool loop so it plugs into the router like any other brain.
    Selected with /switch agent — this is SERENE's 'hands' mode."""
    name = "agent"

    def chat(self, messages):
        return chat_with_tools(messages)
