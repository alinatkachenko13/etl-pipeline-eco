from pathlib import Path
import fitz
from docx import Document

# парсинг для pdf
def parse_pdf(path: str) -> dict:
    doc = fitz.open(path)
    pages = []
    full_text = []

    for i, page in enumerate(doc):
        page_text = page.get_text().strip()
        pages.append({
            "page_num": i + 1,
            "text": page_text
        })
        full_text.append(page_text)

    doc.close()

    return {
        "source_file": Path(path).name,
        "file_type": "pdf",
        "text": "\n".join(full_text).strip(),
        "pages": pages
    }

# парсинг для docx
def parse_docx(path: str) -> dict:
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return {
        "source_file": Path(path).name,
        "file_type": "docx",
        "text": "\n".join(paragraphs).strip(),
        "pages": None
    }

# парсинг для txt
def parse_txt(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8").strip()

    return {
        "source_file": Path(path).name,
        "file_type": "txt",
        "text": text,
        "pages": None
    }

# парсинг для текст
def parse_txt(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8").strip()

    return {
        "source_file": Path(path).name,
        "file_type": "txt",
        "text": text,
        "pages": None
    }

# единый вход для всех типов файлов
def extract_text(path: str) -> dict:
    ext = Path(path).suffix.lower()

    if ext == ".pdf":
        return parse_pdf(path)
    if ext == ".docx":
        return parse_docx(path)
    if ext == ".txt":
        return parse_txt(path)

    raise ValueError(f"Unsupported file type: {ext}")
