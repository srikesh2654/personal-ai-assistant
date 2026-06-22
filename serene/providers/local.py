import ollama
class LocalProvider:
    def __init__(self, model = "llama3.2"):
        self.model = model
    def chat(self,messages):
        responses = ollama.chat(model = self.model,messages = messages)
        reply = responses["message"]["content"]
        return reply