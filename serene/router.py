from serene.providers.local import LocalProvider
from serene.providers.gemini import GeminiProvider
from serene.providers.groq import GroqProvider
from serene.agent import AgentProvider
from serene.config import ACTIVE_BRAIN
brains = {
    "local": LocalProvider(),
    "gemini": GeminiProvider(),
    "groq": GroqProvider(),
    "agent": AgentProvider(),
}
active_brain = ACTIVE_BRAIN
def chat(messages):
    result = brains[active_brain].chat(messages)
    return result
def switch(name):
    global active_brain
    active_brain = name
    