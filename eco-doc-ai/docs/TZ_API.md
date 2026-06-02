# HTTP API

| Метод | Путь | Назначение |
|--------|------|------------|
| GET | `/health` | Проверка |
| POST | `/parse` | `file`, опционально `store=true` |
| POST | `/question` | JSON: `question`, опционально `document` или `document_id` |
| GET | `/documents` | id документов в сессии |

## Примеры

```bash
curl -F "file=@doc.pdf" http://127.0.0.1:8000/parse

curl -X POST http://127.0.0.1:8000/question \
  -H "Content-Type: application/json" \
  -d '{"question": "…", "document": "Книга 1 Эко Агро"}'
```

Сдача test: `cd src && python build_submission_answers.py` → `answers.csv`.
