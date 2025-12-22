# Структура проекта

## Карта перемещений файлов

### Документация → `docs/`

```
API_DOCUMENTATION.md                    → docs/API_DOCUMENTATION.md
WEBSITE_DOCUMENTATION.md                → docs/WEBSITE_DOCUMENTATION.md
metrics_system.md                       → docs/metrics_system.md
presentation.md                         → docs/presentation.md
presentation_script.md                  → docs/presentation_script.md
```

### Основной код → `src/`

#### Core NLP модули → `src/core/`

```
entity_extractor_ner_ensemble.py        → src/core/entity_extractor.py
entity_deduplicator.py                  → src/core/entity_deduplicator.py
relationship_extractor_hybrid_pro.py    → src/core/relationship_extractor.py
risk_classifier.py                      → src/core/risk_classifier.py
text_preprocessor.py                    → src/core/text_preprocessor.py
translator.py                           → src/core/translator.py
```

#### База данных → `src/database/`

```
database.py                             → src/database/manager.py
database_schema.sql                     → src/database/schema.sql
app/db/models.py                        → src/database/models.py (нужно переместить)
app/db/repository*.py                   → src/database/ (нужно переместить)
```

#### Парсеры → `src/scrapers/`

```
app/scraper/client.py                   → src/scrapers/client.py
app/scraper/config.py                   → src/scrapers/config.py
app/scraper/parsers.py                  → src/scrapers/parsers/base.py
app/scraper/parsers_azerbaijan.py       → src/scrapers/parsers/azerbaijan.py
app/scraper/parsers_trend.py            → src/scrapers/parsers/trend.py
app/scraper/pipeline.py                 → src/scrapers/pipelines/base.py
app/scraper/pipeline_azerbaijan.py      → src/scrapers/pipelines/azerbaijan.py
app/scraper/pipeline_trend.py           → src/scrapers/pipelines/trend.py
```

#### Граф персон → `src/graph/`

```
model/person_graph_builder.py           → src/graph/builder.py
model/person_search.py                   → src/graph/search.py
model/nli_relation_labeler.py            → src/graph/nli_labeler.py
```

#### Утилиты → `src/utils/`

```
output_formatter.py                      → src/utils/output_formatter.py
model/text_utils.py                      → src/utils/text_utils.py
```

### API → `api/`

```
api.py                                   → api/app.py
api/main.py                              → api/main.py (без изменений)
api/routers/*                            → api/routers/* (без изменений)
```

### Website → `website/`

```
website_app.py                           → website/app.py
website/static/*                         → website/static/* (без изменений)
website/templates/*                      → website/templates/* (без изменений)
```

### Скрипты → `scripts/`

```
main_azerbaijan.py                       → scripts/run_azerbaijan.py
main_trend.py                            → scripts/run_trend.py
main.py                                  → scripts/run_main.py
```

### Данные → `data/`

```
01.csv, 02.csv, 03.csv, sample.csv       → data/raw/
results_hybrid_final.json                → data/processed/
model/person_index.json                  → data/processed/
evaluation/                              → data/evaluation/
```

### Notebooks → `notebooks/`

```
data.ipynb                               → notebooks/data.ipynb
main.ipynb                               → notebooks/main.ipynb
model/hack.ipynb                         → notebooks/hack.ipynb
```

### Тесты → `tests/`

```
test_api_response.py                     → tests/test_api_response.py
test_normalize.py                        → tests/test_normalize.py
test_process.py                          → tests/test_process.py
```

### Зависимости → `requirements/`

```
requirements.txt                         → requirements/base.txt
requirements_api.txt                     → requirements/api.txt
requirements_website.txt                 → requirements/website.txt
```

## Как обновить импорты

### Старые импорты → Новые импорты

```python
# Было:
from entity_extractor_ner_ensemble import NEREnsembleExtractor
from entity_deduplicator import EntityDeduplicator
from relationship_extractor_hybrid_pro import RelationExtractorHybridPro
from risk_classifier import RiskClassifier
from text_preprocessor import TextPreprocessor
from database import DatabaseManager, get_db_manager

# Стало:
from src.core.entity_extractor import NEREnsembleExtractor
from src.core.entity_deduplicator import EntityDeduplicator
from src.core.relationship_extractor import RelationExtractorHybridPro
from src.core.risk_classifier import RiskClassifier
from src.core.text_preprocessor import TextPreprocessor
from src.database.manager import DatabaseManager, get_db_manager
```

```python
# Было:
from app.scraper.client import ScraperClient
from app.scraper.parsers_azerbaijan import AzerbaijanParser

# Стало:
from src.scrapers.client import ScraperClient
from src.scrapers.parsers.azerbaijan import AzerbaijanParser
```

## Запуск приложений

### API

```bash
# Было:
python api.py
uvicorn api:app --reload

# Стало:
python api/app.py
uvicorn api.app:app --reload
```

### Website

```bash
# Было:
python website_app.py

# Стало:
python website/app.py
```

### Скрипты парсинга

```bash
# Было:
python main_azerbaijan.py

# Стало:
python scripts/run_azerbaijan.py
```

## Docker

Обновите docker-compose.yml для новых путей:

- Проверьте пути к requirements файлам
- Обновите PYTHONPATH если нужно

## Что дальше

1. Обновите все импорты в файлах
2. Обновите docker-compose.yml
3. Обновите README.md с новой структурой
4. Протестируйте запуск всех компонентов
5. Удалите старые пустые папки (app/, model/)
