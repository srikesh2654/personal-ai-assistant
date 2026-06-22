import ollama
from serene.config import LOCAL_MODEL
class LocalProvider:
    def __init__(self, model = LOCAL_MODEL):
        self.model = model
    def chat(self,messages):
        responses = ollama.chat(model = self.model,messages = messages)
        reply = responses["message"]["content"]
        return reply