from google import genai
from serene.config import GEMINI_API_KEY

def _to_gemini_format(messages):
    system = ""
    history = []
    for msg in messages:
        if msg["role"] == "system":
            system = msg["content"]
        elif msg["role"] == "user":
            history.append({"role": "user", "parts": [{"text": msg["content"]}]})
        elif msg["role"] == "assistant":
            history.append({"role": "model", "parts": [{"text": msg["content"]}]})
    return system, history

class GeminiProvider:
    def __init__(self,model = "gemini-3.5-flash"):
        self.model = model
        self.client = genai.Client(api_key = GEMINI_API_KEY)
    def chat(self,messages):
        system,history = _to_gemini_format(messages)
        response = self.client.models.generate_content(
            model = self.model,
            contents = history,
            config = {"system_instruction":system}
        )
        return response.text
    