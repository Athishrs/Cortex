from fastapi import FastAPI
from app.routes import documents
from app.routes import query

app = FastAPI()


app.include_router(documents.router)
app.include_router(query.router)


