#!/usr/bin/env bash
# запуск api из корня eco-doc-ai
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export ECO_DOC_PDF_ENGINE="${ECO_DOC_PDF_ENGINE:-pymupdf}"
cd "$ROOT"
exec python3 -m uvicorn app:app --app-dir src --host 127.0.0.1 --port 8000
