import uuid
from datetime import datetime

from pydantic import BaseModel, Field

class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    created_at: datetime

    