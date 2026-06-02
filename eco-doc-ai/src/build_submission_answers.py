"""
Сбор answers.csv для сдачи: вопросы с документом — выдержка из текста тома;
остальные — подстановка ответа из train.

Запуск из eco-doc-ai/src:
  python build_submission_answers.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from document_resolver import resolve_hackathon_doc_path
from document_store import answer_from_text
from parsers import extract_text

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRAIN = ROOT / "data/raw/Хакатон_last/Данные для обучения/train.csv"
DEFAULT_TEST = ROOT / "data/raw/Хакатон_last/Данные для тестирования/test.csv"
DEFAULT_OUT = ROOT / "answers.csv"

_PARSE_CACHE: dict[str, dict] = {}


def _norm(s: str) -> str:
    return " ".join(str(s).lower().replace("ё", "е").split())


def _parsed(path: Path) -> dict:
    key = str(path.resolve())
    if key not in _PARSE_CACHE:
        _PARSE_CACHE[key] = extract_text(str(path))
    return _PARSE_CACHE[key]


def _answer_from_train(
    question: str,
    doc_label: str,
    train: pd.DataFrame,
    vectorizer: TfidfVectorizer,
    x_train,
    train_q,
    train_doc,
) -> str:
    qn = _norm(question)
    dn = _norm(doc_label)
    query_text = qn + (" [doc] " + dn if dn and dn != "нет" else "")
    qv = vectorizer.transform([query_text])
    scores = cosine_similarity(qv, x_train).ravel().copy()
    if dn and dn != "нет":
        mask = train_doc.map(_norm) == dn
        if mask.any():
            scores[~mask.to_numpy()] *= 0.65
    idx = int(scores.argmax())
    ans = str(train.iloc[idx]["Ответ"]).strip()
    return ans or "Требуется уточнение по документу и контексту вопроса."


def _answer_from_document(question: str, doc_path: Path) -> str | None:
    try:
        record = _parsed(doc_path)
        text = (record.get("text") or "").strip()
        if not text:
            return None
        answer, passages = answer_from_text(text, question)
        return answer.strip() if passages else None
    except Exception as e:
        print(f"doc skip {doc_path.name}: {e}", file=sys.stderr)
        return None


def build_answers(
    train_path: Path,
    test_path: Path,
    out_path: Path,
) -> None:
    train = pd.read_csv(train_path, sep="\t", dtype=str).fillna("")
    test = pd.read_csv(test_path, sep="\t", dtype=str).fillna("")

    train_q = train["Вопрос"].map(_norm)
    train_doc = train["Документ"].map(_norm)
    train_text = (train_q + " [doc] " + train_doc).tolist()
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
    x_train = vectorizer.fit_transform(train_text)

    answers: list[str] = []
    doc_n = 0
    train_n = 0

    for _, row in test.iterrows():
        question = str(row.get("Вопрос", "") or "").strip()
        doc_label = str(row.get("Документ", "") or "").strip()
        path = resolve_hackathon_doc_path(doc_label)
        ans: str | None = None
        if path and path.is_file():
            ans = _answer_from_document(question, path)
            if ans:
                doc_n += 1
        if not ans:
            ans = _answer_from_train(
                question, doc_label, train, vectorizer, x_train, train_q, train_doc
            )
            train_n += 1
        answers.append(ans)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"answers": answers}).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"Готово: {out_path} ({len(answers)} строк, из_документа={doc_n}, train={train_n})")


def main() -> None:
    p = argparse.ArgumentParser(description="answers.csv: текст тома + fallback train")
    p.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    p.add_argument("--test", type=Path, default=DEFAULT_TEST)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    if not args.train.is_file():
        raise SystemExit(f"нет train: {args.train}")
    if not args.test.is_file():
        raise SystemExit(f"нет test: {args.test}")
    build_answers(args.train.resolve(), args.test.resolve(), args.out.resolve())


if __name__ == "__main__":
    main()
