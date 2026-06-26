"""
api: parse, question (как test.csv). запуск: ./run_api.sh
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from document_resolver import is_no_document, resolve_hackathon_doc_path
from document_store import (
    answer_from_text,
    get_record,
    list_document_ids,
    put_record,
)
from parsers import extract_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="eco-doc-ai",
    version="0.3.0",
    description="Парсинг и вопросы по документу. См. docs/TZ_API.md",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    document: str | None = Field(
        default=None,
        description="как в test.csv, напр. «Книга 1 Эко Агро» или «Нет»",
    )
    document_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class QuestionResponse(BaseModel):
    answer: str
    sources: list[dict]
    document_id: str | None = None
    document: str | None = None


class ParseResponse(BaseModel):
    document_id: str
    source_file: str
    file_type: str
    text_length: int
    page_count: int
    ocr_used: bool
    stored: bool


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="файл без имени")
    suffix = Path(file.filename).suffix.lower()
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="пустой файл")
    return suffix, raw


async def _parse_uploaded(file: UploadFile, *, store: bool) -> tuple[dict, str | None]:
    suffix, raw = await _read_upload(file)
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
    doc_id = None
    if store:
        doc_id = put_record(record, skip_if_empty=True)
        if doc_id is None:
            raise HTTPException(
                status_code=422,
                detail="из документа не извлечён текст",
            )
    return record, doc_id


def _sources(passages: list[tuple[str, float]], doc_id: str | None = None) -> list[dict]:
    out = []
    for p, s in passages:
        item = {"text": p[:1500], "score": round(s, 4)}
        if doc_id:
            item["document_id"] = doc_id
        out.append(item)
    return out


def _answer_for_record(question: str, record: dict, top_k: int) -> QuestionResponse:
    answer, passages = answer_from_text(record.get("text") or "", question, top_k=top_k)
    doc_id = str(record.get("document_id") or "")
    return QuestionResponse(
        answer=answer,
        sources=_sources(passages, doc_id or None),
        document_id=doc_id or None,
        document=record.get("source_file"),
    )


def _store_from_path(path: Path) -> str:
    record = extract_text(str(path))
    record["source_file"] = path.name
    doc_id = put_record(record, skip_if_empty=True)
    if not doc_id:
        raise HTTPException(status_code=422, detail=f"не удалось извлечь текст из {path.name}")
    return doc_id


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/documents")
def documents_list():
    ids = list_document_ids()
    return {"document_ids": ids, "count": len(ids)}


@app.post("/parse", response_model=ParseResponse)
async def parse_document(
    file: UploadFile = File(...),
    store: bool = Form(False, description="сохранить в сессии для /question без document"),
):
    record, doc_id = await _parse_uploaded(file, store=store)
    pages = record.get("pages") or []
    meta = record.get("metadata") or {}
    return ParseResponse(
        document_id=doc_id or str(record.get("document_id") or ""),
        source_file=str(record.get("source_file") or ""),
        file_type=str(record.get("file_type") or ""),
        text_length=len(record.get("text") or ""),
        page_count=len(pages),
        ocr_used=bool(meta.get("ocr_used")),
        stored=bool(doc_id),
    )


@app.post("/question", response_model=QuestionResponse)
def ask_question(req: QuestionRequest):
    q = (req.question or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="пустой вопрос")

    if req.document_id:
        rec = get_record(req.document_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="документ не найден")
        return _answer_for_record(q, rec, req.top_k)

    doc_label = (req.document or "").strip()
    if doc_label and not is_no_document(doc_label):
        path = resolve_hackathon_doc_path(doc_label)
        if path is None or not path.is_file():
            raise HTTPException(
                status_code=404,
                detail=f"файл для документа «{doc_label}» не найден на диске",
            )
        doc_id = _store_from_path(path)
        rec = get_record(doc_id)
        if rec is None:
            raise HTTPException(status_code=500, detail="документ сохранён, но не найден в хранилище")
        resp = _answer_for_record(q, rec, req.top_k)
        resp.document = doc_label
        return resp

    best: tuple[str, float, str] | None = None
    best_answer = ""
    all_sources: list[dict] = []
    for doc_id in list_document_ids():
        rec = get_record(doc_id)
        if not rec:
            continue
        answer, passages = answer_from_text(rec.get("text") or "", q, top_k=req.top_k)
        if passages and (best is None or passages[0][1] > best[1]):
            best = (passages[0][0], passages[0][1], doc_id)
            best_answer = answer
            all_sources = _sources(passages, doc_id)

    if best is None:
        raise HTTPException(
            status_code=404,
            detail="нет документов в сессии: укажите document или POST /parse с store=true",
        )

    return QuestionResponse(
        answer=best_answer,
        sources=all_sources,
        document_id=best[2],
        document=doc_label or "Нет",
    )
