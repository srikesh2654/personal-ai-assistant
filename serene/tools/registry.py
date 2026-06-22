"""registry.py — collects every tool SERENE can use, from all tool modules.

Each tool module (files.py, spotify.py, ...) declares its tools with the
@tool decorator, which records two things in ONE place:
  1. the JSON schema we SEND to the model (so it knows the tool exists and how
     to call it — the OpenAI / Groq function-calling standard), and
  2. the real Python function we RUN when the model asks for that tool.

Adding a new capability is now just: write a function, decorate it, done — no
more editing a giant central list that drifts out of sync with the code.
"""

# Populated by the @tool decorators as each tool module is imported (bottom).
TOOL_SCHEMAS = []
TOOL_FUNCTIONS = {}


def tool(name, description, parameters=None, required=None):
    """Register the decorated function as a tool SERENE can call.

    `parameters` is a dict of {arg_name: {"type": ..., "description": ...}};
    `required` lists the argument names that are mandatory. The full
    OpenAI/Groq schema wrapper is built for you, so each tool just declares
    its own arguments.
    """
    parameters = parameters or {}
    required = required or []

    def decorator(fn):
        TOOL_SCHEMAS.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": required,
                },
            },
        })
        TOOL_FUNCTIONS[name] = fn
        return fn

    return decorator


def call_tool(name, arguments):
    """Run a tool by name with a dict of arguments. Always returns a string
    (errors included) so the agent loop never crashes."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}"
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Tool '{name}' failed: {e}"


# Importing the tool modules runs their @tool decorators, which fills in the
# dicts above. Keep these at the BOTTOM so `tool` is defined before the modules
# try to import it (avoids a circular-import error).
from serene.tools import files          # noqa: E402,F401
from serene.tools import spotify        # noqa: E402,F401
from serene.tools import web            # noqa: E402,F401
from serene.tools import desktop        # noqa: E402,F401
from serene.tools import memory         # noqa: E402,F401
