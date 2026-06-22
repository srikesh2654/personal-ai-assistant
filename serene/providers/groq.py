from groq import Groq
from serene.config import GROQ_API_KEY


class GroqProvider:
    def __init__(self, model="llama-3.3-70b-versatile"):
        self.model = model
        self.client = Groq(api_key=GROQ_API_KEY)

    def chat(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content
