from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import get_settings
import voyageai

from app.db.models import Document, Chunk
from google import genai

from fastapi import HTTPException

settings=get_settings()
voyage_client=voyageai.Client(api_key=settings.voyage_api_key)
gemini_client = genai.Client(api_key=settings.gemini_api_key)




class DocumentStore:
    async def list_documents(self, session: AsyncSession) -> list[Document]:
        result = await session.execute(select(Document))
        return list(result.scalars().all())

    async def create_document_with_chunks(
        self, session: AsyncSession, filename: str, text: str
    ) -> Document:
        doc = Document(filename=filename)
        session.add(doc)
        await session.flush()

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        text_chunks = splitter.split_text(text)
        if not text_chunks:
         raise HTTPException(status_code=400, detail="Document content is empty")

        embedding_result = voyage_client.embed(
            texts=text_chunks,
            model="voyage-3",
            input_type="document",
        )

        for chunk_text, embedding in zip(text_chunks, embedding_result.embeddings):
            chunk = Chunk(document_id=doc.id, content=chunk_text, embedding=embedding)
            session.add(chunk)

        await session.commit()
        await session.refresh(doc)
        return doc

    async def delete_document(self, session: AsyncSession, doc_id: str) -> bool:
        doc = await session.get(Document, doc_id)
        if doc is None:
            return False
        await session.delete(doc)
        await session.commit()
        return True
    
    async def search_similar_chunks(self, session: AsyncSession, question: str, top_k: int = 5):
        query_embedding = voyage_client.embed(
            texts=[question],
            model="voyage-3",
            input_type="query",
        ).embeddings[0]

        result = await session.execute(
            select(Chunk)
            .order_by(Chunk.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
    async def generate_answer(self, session: AsyncSession, question: str, top_k: int = 5) -> dict:
        chunks = await self.search_similar_chunks(session, question, top_k)

        context = "\n\n---\n\n".join(chunk.content for chunk in chunks)

        prompt = f"""Answer the question using ONLY the context below. If the context doesn't contain the answer, say "I don't have enough information to answer that."

Context:
{context}

Question: {question}

Answer:"""

        response = gemini_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )

        return {
            "answer": response.text,
            "sources": [{"content": chunk.content[:100] + "..."} for chunk in chunks],
        }


document_store = DocumentStore()