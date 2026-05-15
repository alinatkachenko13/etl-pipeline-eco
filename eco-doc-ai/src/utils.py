import json
from pathlib import Path

import pandas as pd

from corpus_storage import append_to_manifest, save_document_json
from parsers import IMAGE_EXTENSIONS, extract_text

CORPUS_EXTENSIONS = {".pdf", ".docx", ".doc", ".rtf", ".txt", ".xls", ".xlsx"} | IMAGE_EXTENSIONS


def _resolve(project_root: Path, path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = project_root / path
    return path


def build_corpus(
    input_dir: str = "data/raw",
    corpus_root: str = "samples/corpus",
) -> None:
    """
    корпус знаний для rag:
    extract_text -> samples/corpus/documents/<document_id>.json
    + samples/corpus/manifest.jsonl
    """
    project_root = Path(__file__).resolve().parent.parent
    input_path = _resolve(project_root, input_dir)
    corpus_path = _resolve(project_root, corpus_root)

    documents_dir = corpus_path / "documents"
    manifest_path = corpus_path / "manifest.jsonl"

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_path}")

    documents_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text("", encoding="utf-8")
    corpus_rel = corpus_path.relative_to(project_root).as_posix()

    for file_path in input_path.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in CORPUS_EXTENSIONS:
            continue

        try:
            parsed = extract_text(str(file_path))
            save_document_json(parsed, documents_dir)
            doc_rel = f"{corpus_rel}/documents/{parsed['document_id']}.json"

            append_to_manifest(
                {
                    "document_id": parsed["document_id"],
                    "source_file": parsed["source_file"],
                    "file_type": parsed["file_type"],
                    "schema_name": parsed["schema_name"],
                    "schema_version": parsed["schema_version"],
                    "document_path": doc_rel,
                },
                manifest_path,
            )
            print(f"CORPUS OK: {file_path.relative_to(input_path)}")
        except Exception as e:
            print(f"CORPUS ERROR: {file_path.relative_to(input_path)} -> {e}")


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _read_qa_csv(path: Path) -> pd.DataFrame:
    # в данных встречаются tab-separated csv.
    return pd.read_csv(path, sep="\t", dtype=str).fillna("")


def _write_qa_jsonl(df: pd.DataFrame, out_path: Path, prefix: str) -> None:
    question_col = _first_existing_column(df, ["Вопрос", "question", "Question"])
    answer_col = _first_existing_column(df, ["Ответ", "answer", "Answer"])
    source_doc_col = _first_existing_column(df, ["Документ", "source_document", "document"])

    if question_col is None:
        raise ValueError(f"No question column in {out_path.name}")
    if answer_col is None:
        raise ValueError(f"No answer column in {out_path.name}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for i, row in enumerate(df.itertuples(index=False), start=1):
            row_dict = row._asdict()
            q = (row_dict.get(question_col, "") or "").strip()
            q = q if q else None
            answer_value = row_dict.get(answer_col, "") or ""
            rec = {
                "qa_id": f"{prefix}_{i:04d}",
                "question": q,
                "answer": answer_value.strip() if answer_value.strip() else None,
                "source_document": (row_dict.get(source_doc_col, "") or "").strip() if source_doc_col else "",
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def build_qa_data(
    raw_root: str = "data/raw",
    qa_root: str = "samples/qa",
) -> None:
    """
    qa-данные (train/test) хранятся отдельно от corpus.
    example.csv — шаблон ответов для сабмита, не qa-датасет; не конвертируем в jsonl.

    создаются файлы:
    - samples/qa/qa_train.jsonl
    - samples/qa/qa_test.jsonl
    """
    project_root = Path(__file__).resolve().parent.parent
    raw_path = _resolve(project_root, raw_root)
    qa_path = _resolve(project_root, qa_root)
    qa_path.mkdir(parents=True, exist_ok=True)

    mapping = {
        "train.csv": ("qa_train.jsonl", "train"),
        "test.csv": ("qa_test.jsonl", "test"),
    }

    found = {}
    for csv_path in raw_path.rglob("*.csv"):
        name = csv_path.name.lower()
        if name in mapping and name not in found:
            found[name] = csv_path

    for csv_name, (jsonl_name, prefix) in mapping.items():
        if csv_name not in found:
            print(f"QA SKIP: {csv_name} not found")
            continue
        df = _read_qa_csv(found[csv_name])
        out = qa_path / jsonl_name
        _write_qa_jsonl(df, out, prefix)
        print(f"QA OK: {found[csv_name].relative_to(raw_path)} -> {out.relative_to(project_root)}")


if __name__ == "__main__":
    build_corpus("data/raw", "samples/corpus")
    build_qa_data("data/raw", "samples/qa")
