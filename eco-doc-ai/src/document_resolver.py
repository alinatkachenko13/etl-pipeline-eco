"""
сопоставление колонки «Документ» из test.csv с файлами на диске.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOC_WORD_DIR = (
    ROOT
    / "data/raw/Хакатон_last/Данные для тестирования/Проект 2 (для QnA)/Проект Word"
)
DOC_SUMMARY_DIR = (
    ROOT
    / "data/raw/Хакатон_last/Данные для тестирования/Проект 3 (для суммаризации)/Био Агро Дон/Проект word"
)


def _norm(s: str) -> str:
    return " ".join(str(s).lower().replace("ё", "е").split())


def is_no_document(label: str | None) -> bool:
    return not (label or "").strip() or _norm(label) == "нет"


def resolve_hackathon_doc_path(doc_label: str) -> Path | None:
    """путь к word/pdf тома по подписи из test.csv."""
    label = (doc_label or "").strip()
    if is_no_document(label):
        return None

    low = label.lower()
    search_dirs: list[Path] = []
    if DOC_WORD_DIR.is_dir():
        search_dirs.append(DOC_WORD_DIR)
    if DOC_SUMMARY_DIR.is_dir():
        search_dirs.append(DOC_SUMMARY_DIR)

    patterns: list[str] = []
    if "книга 1" in low or "инвентаризация" in low:
        patterns.extend(["*Инвентаризация*Эко*Агро*", "*Инвентаризация*Био*Агро*"])
    if "книга 2" in low or re.search(r"\bпдв\b", low):
        patterns.extend(["*ПДВ*Эко*Агро*", "*ПДВ*Био*Агро*"])

    for base in search_dirs:
        for pat in patterns:
            for p in base.glob(pat + ".docx"):
                return p
            for p in base.glob(pat + ".pdf"):
                return p

    return None
