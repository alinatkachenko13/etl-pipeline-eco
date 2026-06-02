"""
Разбиение длинного текста на чанки для поиска ответа (абзацы → предложения → overlap по символам).
"""

from __future__ import annotations

import re


def normalize_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?…])\s+|(?<=;)\s+", text)
    return [p.strip() for p in parts if p and p.strip()]


def _chunk_by_chars(text: str, max_chars: int, overlap: int) -> list[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text.strip()]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def _flush_paragraph_buffer(buf: list[str]) -> str | None:
    if not buf:
        return None
    return "\n\n".join(buf)


def chunk_text(
    text: str,
    max_chars: int = 2000,
    overlap: int = 220,
) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush() -> None:
        nonlocal buf, buf_len
        merged = _flush_paragraph_buffer(buf)
        if merged:
            chunks.append(merged)
        buf = []
        buf_len = 0

    for para in paragraphs:
        if len(para) > max_chars:
            flush()
            sents = split_sentences(para)
            if len(sents) <= 1:
                chunks.extend(_chunk_by_chars(para, max_chars, overlap))
                continue
            sub: list[str] = []
            sub_len = 0
            for s in sents:
                if len(s) > max_chars:
                    if sub:
                        chunks.append(" ".join(sub))
                        sub = []
                        sub_len = 0
                    chunks.extend(_chunk_by_chars(s, max_chars, overlap))
                    continue
                add = len(s) + (1 if sub else 0)
                if sub_len + add <= max_chars:
                    sub.append(s)
                    sub_len += add
                else:
                    if sub:
                        chunks.append(" ".join(sub))
                    sub = [s]
                    sub_len = len(s)
            if sub:
                chunks.append(" ".join(sub))
            continue

        extra = len(para) + (2 if buf else 0)
        if buf_len + extra <= max_chars:
            buf.append(para)
            buf_len += extra
        else:
            flush()
            buf = [para]
            buf_len = len(para)

    flush()
    return [c for c in chunks if c]
