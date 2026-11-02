from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .db import session_factory
from .knowledge import answer_evaluation_questions, ingest_dataset, _eval_answer_for, init_db
from .models import Document


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "app": settings.app_name,
        "docs": "/docs",
        "health": "/health",
        "api": ["/api/ingest", "/api/evaluation", "/api/documents", "/api/query"],
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


@app.post("/api/ingest")
def ingest(payload: dict | None = None) -> dict:
    dataset_path = (payload or {}).get("dataset_path") if payload else None
    return ingest_dataset(dataset_path or settings.dataset_path)


@app.get("/api/evaluation")
def get_evaluation() -> dict:
    return {"questions": answer_evaluation_questions()}


@app.get("/api/documents")
def list_documents() -> list[dict]:
    with session_factory() as session:
        rows = session.query(Document).all()
        return [{
            "id": row.id,
            "filename": row.filename,
            "document_type": row.document_type,
            "revision": row.revision,
            "effective_date": row.effective_date,
            "trust_level": row.trust_level,
            "extraction_status": row.extraction_status,
            "source_path": row.source_path,
        } for row in rows]


@app.post("/api/query")
def query(payload: QueryRequest) -> dict:
    return {"question": payload.question, **_eval_answer_for(payload.question)}
