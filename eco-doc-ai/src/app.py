"""
минимальный api: загрузка → чанки → tf-idf поиск → ответ и саммари.
запуск: из корня eco-doc-ai выполнить ./run_api.sh или:
  ECO_DOC_PDF_ENGINE=pymupdf python3 -m uvicorn app:app --app-dir src --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from memory_rag import (
    ensure_summary,
    extractive_answer,
    get_indexed,
    index_parsed_record,
    list_document_ids,
    retrieve,
)
from parsers import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="eco-doc-ai mvp", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    document_id: str
    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class QueryResponse(BaseModel):
    answer: str
    sources: list[dict]
    document_id: str


class SummaryResponse(BaseModel):
    document_id: str
    summary: str
    source_file: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def documents_list():
    return {"document_ids": list_document_ids(), "count": len(list_document_ids())}


@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="файл без имени")

    suffix = Path(file.filename).suffix.lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="пустой файл")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix or ".bin") as tmp:
        tmp.write(raw)
        tmp_path = tmp.name

    try:
        record = extract_text(tmp_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception("parse failed")
        raise HTTPException(status_code=500, detail=f"ошибка парсинга: {e}") from e
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    record["source_file"] = file.filename
    doc_id = index_parsed_record(record, skip_if_empty=True)
    if doc_id is None:
        raise HTTPException(
            status_code=422,
            detail="из документа не извлечён текст (проверьте формат или скан без ocr)",
        )

    idx = get_indexed(doc_id)
    n_chunks = len(idx.chunks) if idx else 0
    return {
        "document_id": doc_id,
        "source_file": file.filename,
        "file_type": record.get("file_type"),
        "chunk_count": n_chunks,
    }


@app.post("/query", response_model=QueryResponse)
def query_documents(req: QueryRequest):
    passages = retrieve(req.document_id, req.question, top_k=req.top_k)
    if not passages:
        if get_indexed(req.document_id) is None:
            raise HTTPException(status_code=404, detail="документ не найден, загрузите файл снова")

    answer = extractive_answer(req.question, passages)
    sources = [{"text": p[:1500], "score": round(s, 4)} for p, s in passages]
    return QueryResponse(
        answer=answer,
        sources=sources,
        document_id=req.document_id,
    )


@app.get("/documents/{document_id}/summary", response_model=SummaryResponse)
def document_summary(document_id: str):
    doc = get_indexed(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="документ не найден")

    s = ensure_summary(document_id) or ""
    return SummaryResponse(document_id=document_id, summary=s, source_file=doc.source_file)
