from groq import Groq
from serene.config import GROQ_API_KEY, GROQ_MODEL


class GroqProvider:
    def __init__(self, model=GROQ_MODEL):
        self.model = model
        self.client = Groq(api_key=GROQ_API_KEY)

    def chat(self, messages):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return response.choices[0].message.content
