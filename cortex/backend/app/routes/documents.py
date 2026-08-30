from fastapi import APIRouter, Depends, HTTPException, status,UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.documents import  DocumentResponse
from app.services.document_store import document_store

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(session: AsyncSession = Depends(get_db)) -> list[DocumentResponse]:
    return await document_store.list_documents(session)


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(file: UploadFile, session: AsyncSession = Depends(get_db)) -> DocumentResponse:
    raw_bytes=await file.read()
    text=raw_bytes.decode('utf-8')
    return await document_store.create_document_with_chunks(session,file.filename, text)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, session: AsyncSession = Depends(get_db)) -> None:
    deleted = await document_store.delete_document(session, document_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")