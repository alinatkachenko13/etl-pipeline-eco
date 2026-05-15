# Eco Doc AI

## О проекте

`Eco Doc AI` — это базовая платформа для интеллектуальной обработки экологической и природоохранной документации: парсинг файлов, разбиение текста, поиск релевантных фрагментов, формирование ответов и саммари.

Проект соответствует ключевой идее брифа, но в текущем виде это **MVP/демо-основа**, а не полный production-контур.

## Соответствие брифу

В репозитории уже есть:

- сбор и подготовка корпуса документов;
- парсинг неструктурированных и полуструктурированных форматов;
- RAG-подобный пайплайн: разбор → чанки → поиск → экстрактивный ответ/саммари;
- минимальный HTTP API для загрузки документа и запросов.

Пока **не реализованы** (как отдельные полноценные подсистемы):

- дообучение LLM;
- выделение требований как сущностей;
- интеграция в внешний UI-прототип;
- оценка эффекта в процентах по целевым KPI из брифа (для этого нужен пилот и замеры).

## Для кого

Экологи-проектировщики и специалисты, которым нужно быстро находить нужные фрагменты в документах заказчика и получать выжимки по содержимому.

## Что реализовано

### 1) Подготовка данных

- Сбор корпуса из `data/raw` в JSON-документы и `manifest.jsonl`.
- Конвертация train/test CSV в QA JSONL.
- Основной модуль: `src/utils.py`.

### 2) Парсинг документов и изображений

Поддерживаются:

- документы: **PDF, DOCX, TXT, RTF, DOC (macOS), XLS/XLSX**;
- изображения: **JPG, PNG, HEIC** (через OCR).

Особенности:

- для PDF/DOCX можно использовать **Docling** (лучше для сложной верстки и таблиц);
- fallback для PDF: **PyMuPDF + PaddleOCR**.

Основной модуль: `src/parsers.py`.

### 3) Чанки, саммари, поиск и ответы

- Разбиение на чанки и саммаризация без LLM (TextRank по TF-IDF предложений): `src/chunk_and_summarize.py`.
- Поиск по одному загруженному документу: TF-IDF по чанкам.
- Ответ: экстрактивная сборка релевантных предложений (без свободной генерации).
- Основной модуль: `src/memory_rag.py`.

### 4) API-прототип

- FastAPI-сервис для:
  - загрузки файла,
  - вопроса по документу,
  - получения саммари.
- Модули: `src/app.py`, запуск через `./run_api.sh`.
- Индекс хранится в памяти процесса (после перезапуска файл нужно загрузить заново).

### 5) Офлайн-артефакты по корпусу

Команда `python chunk_and_summarize.py` генерирует:

- `samples/corpus/chunks.jsonl`,
- `samples/corpus/summaries.jsonl`.

## Структура проекта

- `src/parsers.py` — извлечение текста и маршрутизация по форматам (Docling/PyMuPDF).
- `src/pdf_page_quality.py` — эвристики качества PDF-страниц (ветка PyMuPDF).
- `src/ocr.py` — обертка над PaddleOCR.
- `src/chunk_and_summarize.py` — чанки и TextRank-саммари.
- `src/memory_rag.py` — индекс и retrieval по одному документу.
- `src/app.py` — REST API.
- `src/utils.py`, `src/corpus_storage.py` — сбор корпуса и QA JSONL.
- `src/build_submission_answers.py` — сбор `answers.csv` для сдачи (RAG + fallback train).
- `src/generate_answers.py` — baseline для `answers.csv` только по train/test.
- `data/raw/` — исходные материалы.
- `samples/corpus/`, `samples/qa/` — артефакты обработки.
- `docs/mvp_definition.md`, `docs/architecture.md` — описание MVP и архитектуры.

## Быстрый старт API

```bash
cd eco-doc-ai
python3 -m pip install -r requirements.txt
./run_api.sh
```

Swagger UI:  
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Типовой сценарий:

1. загрузить файл;
2. получить `document_id`;
3. отправлять вопросы с `document_id`;
4. отдельно запрашивать summary.

### Выбор PDF-движка

По умолчанию:

```bash
ECO_DOC_PDF_ENGINE=pymupdf
```

Для сложной верстки можно переключиться на Docling:

```bash
export ECO_DOC_PDF_ENGINE=docling
```

## Офлайн-обработка корпуса

```bash
cd eco-doc-ai/src
python utils.py
python chunk_and_summarize.py
```

## Быстрая сборка `answers.csv`

Из каталога `eco-doc-ai/src` (нужны `train.csv`, `test.csv` и документы Word в `data/raw/.../Проект Word/`):

```bash
python build_submission_answers.py
```

Результат: `eco-doc-ai/answers.csv`.

Логика:

- для вопросов с указанным документом (например, «Книга 1/2 Эко Агро») — извлечение ответа из текста тома через RAG;
- для `Нет` и при ошибках парсинга — fallback на train (baseline).

Только baseline (без парсинга документов):

```bash
python generate_answers.py \
  --train "../data/raw/Хакатон_last/Данные для обучения/train.csv" \
  --test "../data/raw/Хакатон_last/Данные для тестирования/test.csv" \
  --out ../answers.csv
```
