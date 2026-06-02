# Eco Doc AI

Парсинг экологических документов (PDF, DOCX, сканы) и ответы на вопросы по тексту томов. FastAPI + офлайн-сбор `answers.csv`.

## Данные

В git нет папки `data/` — её кладёте локально. Ожидаемая структура:

```
eco-doc-ai/data/raw/Хакатон_last/
├── Данные для обучения/train.csv
└── Данные для тестирования/test.csv
    └── … тома проектов (Word/PDF)
```

Без `data/` скрипт сдачи не запустится; API не найдёт файл по названию из колонки «Документ».

## Установка

```bash
cd eco-doc-ai
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./run_api.sh          # http://127.0.0.1:8000/docs
```

Сбор ответов на весь test:

```bash
cd src && python build_submission_answers.py
```

→ `eco-doc-ai/answers.csv`

## Логика

1. **Парсер** — PDF, DOCX, TXT, Excel, изображения; OCR на страницах-сканах.
2. **Вопрос с томом** — по названию из «Документ» открывается файл, ответ из релевантных чанков текста.
3. **«Документ» = Нет** — в скрипте сдачи ответ берётся из **train.csv** (похожий вопрос, TF-IDF).

Ответы без LLM: текст режется на **чанки** (~2000 символов, с перекрытием), по вопросу выбираются самые релевантные куски.

## API

| Метод | Путь |
|-------|------|
| POST | `/parse` |
| POST | `/question` |

Подробнее: `docs/TZ_API.md`. Docker: `docker compose up --build`.

## Код

`parsers.py` · `text_chunks.py` · `document_store.py` · `document_resolver.py` · `app.py` · `build_submission_answers.py`
