"""
сессионное хранение распарсенных документов и ответы по чанкам текста (без rag/эмбеддингов).
"""

from __future__ import annotations

import re
import uuid

from text_chunks import chunk_text, normalize_text, split_sentences

_STORE: dict[str, dict] = {}

_WORD_RE = re.compile(r"\w+", flags=re.UNICODE)

# как в прежнем chunk_and_summarize
CHUNK_MAX_CHARS = 2000
CHUNK_OVERLAP = 220


def _words(s: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(s) if len(w) > 2}


def put_record(record: dict, *, skip_if_empty: bool = True) -> str | None:
    text = normalize_text(record.get("text") or "")
    if not text and skip_if_empty:
        return None
    doc_id = str(record.get("document_id") or uuid.uuid4())
    stored = {**record, "document_id": doc_id, "text": text}
    _STORE[doc_id] = stored
    return doc_id


def get_record(document_id: str) -> dict | None:
    return _STORE.get(document_id)


def list_document_ids() -> list[str]:
    return list(_STORE.keys())


def _search_blocks(
    blocks: list[str],
    qw: set[str],
    top_k: int,
) -> list[tuple[str, float]]:
    scored: list[tuple[str, float]] = []
    for block in blocks:
        bw = _words(block)
        if not bw:
            continue
        overlap = len(qw & bw) / len(qw)
        if overlap > 0:
            scored.append((block, float(overlap)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]


def answer_from_text(
    text: str,
    question: str,
    *,
    top_k: int = 5,
    max_answer_chars: int = 3500,
    chunk_max_chars: int = CHUNK_MAX_CHARS,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> tuple[str, list[tuple[str, float]]]:
    """ответ по чанкам (~2000 символов с overlap), релевантность — пересечение слов с вопросом."""
    q = (question or "").strip()
    if not q:
        return "пустой вопрос", []

    qw = _words(q)
    if not qw:
        return "не удалось выделить слова в вопросе", []

    norm = normalize_text(text)
    blocks = chunk_text(norm, max_chars=chunk_max_chars, overlap=chunk_overlap)
    if not blocks:
        blocks = [p.strip() for p in re.split(r"\n\s*\n", norm) if p.strip()]
    if not blocks:
        blocks = [s for s in split_sentences(norm) if s]

    top = _search_blocks(blocks, qw, top_k)

    if not top:
        sents = [s for s in split_sentences(norm) if len(s) >= 20][:4]
        if sents:
            joined = " ".join(sents)[:max_answer_chars]
            return joined, [(joined, 0.0)]
        return "релевантных фрагментов не найдено", []

    answer_parts: list[str] = []
    for block, _score in top[:3]:
        sents = split_sentences(block)
        if sents:
            best = max(
                sents,
                key=lambda s: len(_words(s) & qw) / max(len(qw), 1),
            )
            answer_parts.append(best)
        else:
            answer_parts.append(block[:800])

    seen: set[str] = set()
    unique: list[str] = []
    for p in answer_parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    answer = " ".join(unique)[:max_answer_chars]
    return answer, top
