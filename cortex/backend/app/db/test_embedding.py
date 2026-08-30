import voyageai

from app.config import get_settings

settings = get_settings()
client = voyageai.Client(api_key=settings.voyage_api_key)

result = client.embed(
    texts=["Employees receive 15 days of paid vacation per year."],
    model="voyage-3",
    input_type="document",
)

embedding = result.embeddings[0]
print(f"Embedding length: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")