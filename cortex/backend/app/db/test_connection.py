import asyncio

from app.db.session import async_session_maker
from app.db.models import Document


async def main():
    async with async_session_maker() as session:
        doc = Document(filename="test_from_sqlalchemy.pdf")
        session.add(doc)
        await session.commit()
        print(f"Created document with id: {doc.id}")


asyncio.run(main())