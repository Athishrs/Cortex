from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.document_store import document_store

router = APIRouter(prefix="/query", tags=["query"])


@router.post("/")
async def run_query(payload: dict, session: AsyncSession = Depends(get_db)) -> dict:
    question = payload.get("question", "")
    return await document_store.generate_answer(session, question)