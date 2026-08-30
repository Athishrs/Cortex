from google import genai

from app.config import get_settings

settings = get_settings()
client = genai.Client(api_key=settings.gemini_api_key)

response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello in one sentence.",
)

print(response.text)