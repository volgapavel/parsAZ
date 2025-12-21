# ClearPic Media Monitoring System
## Система автоматического мониторинга азербайджанских СМИ

### Описание

Автоматизированная система для выявления репутационных и compliance-рисков компаний и персон в азербайджанских новостных источниках. Использует передовые NLP технологии для извлечения именованных сущностей, анализа связей и классификации рисков.

### Основные возможности

- **NER Ensemble** - извлечение 25+ типов сущностей (персоны, организации, локации)
- **Hybrid Relationship Extraction** - 3 метода (Regex, spaCy, BERT) для выявления связей
- **Risk Classification** - 8 категорий рисков (fraud, corruption, etc.)
- **REST API** - программный доступ к функциям системы
- **PostgreSQL** - надежное хранение и быстрый поиск данных

## Установка

### 1. Системные требования

- Python 3.8+
- PostgreSQL 15+
- 8+ GB RAM (для NER моделей)
- 10+ GB свободного места (для моделей)

### 2. Клонирование и зависимости

```bash
# Установка Python зависимостей
pip install -r requirements.txt

# Для API
pip install -r requirements_api.txt
```

### 3. Настройка PostgreSQL

```bash
# Создание базы данных
createdb clearpic_media

# Инициализация схемы
psql -d clearpic_media -f database_schema.sql
```

### 4. Переменные окружения

Создайте файл `.env`:

```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=clearpic_media
DB_USER=postgres
DB_PASSWORD=your_password

# Optional
LOG_LEVEL=INFO
```

## Использование

### REST API

```bash
# Запуск API сервера
uvicorn api:app --reload --host 0.0.0.0 --port 8000

# API будет доступно на http://localhost:8000
# Документация: http://localhost:8000/docs
```

### Обработка одного текста

```python
from main import process_single_article

result = process_single_article(
    text="Mingəçevirdə İ.Baxışov həbs edildi...",
    article_id="abc123",
    source="Report.az",
    save_to_db=True
)

print(result['entities'])
print(result['relationships'])
print(result['risks'])
```

### Пакетная обработка

```python
from data_loader import DataLoader
from main import process_articles_batch

loader = DataLoader()
df = loader.load_csv("01.csv")

results = process_articles_batch(df, save_to_db=True)
```

### API Примеры

#### Обработка текста

```bash
curl -X POST "http://localhost:8000/api/v1/process" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mingəçevirdə İ.Baxışov həbs edildi",
    "article_id": "abc123",
    "source": "Report.az"
  }'
```

#### Поиск по базе

```bash
curl -X POST "http://localhost:8000/api/v1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_name": "Baxışov",
    "entity_type": "person",
    "limit": 10
  }'
```

#### Получение статьи

```bash
curl "http://localhost:8000/api/v1/articles/abc123"
```

#### Получение сущностей

```bash
curl "http://localhost:8000/api/v1/entities?entity_type=person&limit=100"
```

#### Статистика

```bash
curl "http://localhost:8000/api/v1/stats"
```

## Архитектура системы

```
┌─────────────────┐
│  Data Loader    │ <- CSV/JSON файлы
└────────┬────────┘
         │
         v
┌─────────────────────────────────────────┐
│      Text Preprocessor                  │
│  - Очистка текста                       │
│  - Нормализация                         │
└────────┬────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────┐
│   NER Ensemble Extractor                │
│  - Davlan xlm-roberta-large             │
│  - LocalDoc azerbaijani_v2              │
│  - Voting + Confidence                  │
└────────┬────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────┐
│   Entity Deduplicator                   │
│  - Levenshtein distance                 │
│  - Entity merging                       │
└────────┬────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────┐
│   Relationship Extractor (Hybrid)       │
│  - Regex patterns (85%)                 │
│  - spaCy dependency parsing (72%)       │
│  - BERT context (80-85%)                │
└────────┬────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────┐
│   Risk Classifier                       │
│  - 8 категорий рисков                   │
│  - Keyword + bigram matching            │
│  - Severity scoring                     │
└────────┬────────────────────────────────┘
         │
         v
┌─────────────────────────────────────────┐
│   Output Formatter + Database           │
│  - JSON formatting                      │
│  - PostgreSQL storage                   │
└─────────────────────────────────────────┘
```

## Структура проекта

```
.
├── api.py                                   # REST API
├── database.py                              # PostgreSQL интеграция
├── data_loader.py                           # Загрузка данных
├── text_preprocessor.py                     # Предобработка
├── entity_extractor_ner_ensemble.py         # NER ансамбль
├── entity_deduplicator.py                   # Дедупликация
├── relationship_extractor_hybrid_pro.py     # Извлечение связей
├── risk_classifier.py                       # Классификация рисков
├── output_formatter.py                      # Форматирование
├── translator.py                            # Перевод (опционально)
├── database_schema.sql                      # SQL схема
├── requirements.txt                         # Зависимости
├── requirements_api.txt                     # API зависимости
├── API_DOCUMENTATION.md                     # API документация
├── metrics_system.md                        # Система метрик
├── presentation.md                          # Презентация
├── presentation_script.md                   # Текст доклада
├── 01.csv, 02.csv, 03.csv                   # Тестовые данные
└── evaluation/                              # Оценка качества
    ├── create_gold_dataset.py
    ├── metrics_evaluator.py
    ├── run_pipeline_on_gold.py
    └── gold/
        └── gold_dataset.json
```

## Модели и производительность

### NER Models

1. **Davlan/xlm-roberta-large-ner-hrl**
   - Multilingual (40+ languages)
   - Person: 73.7% (precision), 50.1% (recall)
   - Location: 23.3% / 28.7%
   - Organization: 0% / 0%

2. **LocalDoc/private_ner_azerbaijani_v2**
   - Специализирован для азербайджанского
   - 25+ типов сущностей
   - Person: 38.1% / 51.1%
   - Location: 21.5% / 25.6%
   - Organization: 0% / 0%

3. **Ensemble (Weighted Voting)**
   - Person: **47.5% / 60.9%** -> F1 = 53.3%
   - Location: 23.1% / 28.6% -> F1 = 24.1%
   - Organization: 0% / 0% -> F1 = 0%
   - **Overall F1: 23.5%**

### Relationship Extraction

- **Regex**: 85% precision
- **spaCy**: 72% precision
- **BERT**: 80-85% precision (медленно)
- **Hybrid**: Комбинирует все три метода

### Производительность

- **Обработка**: <10 сек на статью
- **Memory**: ~2GB (с моделями)
- **Batch**: 200+ статей в час

## Метрики качества

Полное описание системы метрик в [metrics_system.md](metrics_system.md)

### Ключевые метрики

1. **NER.PREC** - Precision NER (целевое значение: >60%)
2. **NER.REC** - Recall NER (целевое значение: >50%)
3. **NER.F1** - F1-score NER (целевое значение: >55%)
4. **REL.PREC** - Precision связей (целевое значение: >70%)
5. **PERF.LAT** - Latency обработки (целевое значение: <10 сек)

### Текущие результаты (30 статей gold dataset)

- Person F1: 53.3%
- Location F1: 24.1%
- Organization F1: 0%
- Overall F1: 23.5%
- Latency: 8.2 сек (avg)

## API Endpoints

Полная документация в [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

### Основные endpoints

- `POST /api/v1/process` - Обработка текста
- `POST /api/v1/search` - Поиск статей
- `GET /api/v1/articles/{id}` - Получение статьи
- `GET /api/v1/entities` - Список сущностей
- `GET /api/v1/relationships` - Список связей
- `GET /api/v1/stats` - Статистика
- `GET /health` - Проверка состояния

## Развертывание

### Docker

```bash
# Build
docker build -t clearpic-api .

# Run
docker run -d \
  -p 8000:8000 \
  -e DB_HOST=postgres \
  -e DB_NAME=clearpic_media \
  -e DB_USER=postgres \
  -e DB_PASSWORD=password \
  clearpic-api
```

### Production рекомендации

1. **Nginx** - reverse proxy перед API
2. **Gunicorn** - WSGI сервер (4+ workers)
3. **PostgreSQL** - connection pooling (10-20)
4. **Monitoring** - Prometheus + Grafana
5. **Backup** - ежедневные бэкапы БД
6. **Scaling** - горизонтальное масштабирование API

## Roadmap

### Краткосрочные планы (1-3 месяца)

- [ ] Улучшение NER для организаций (F1 > 40%)
- [ ] Добавление новых источников (5+ сайтов)
- [ ] Real-time мониторинг с Kafka
- [ ] Веб интерфейс для анализа

### Среднесрочные планы (3-6 месяцев)

- [ ] Fine-tuning NER моделей на азербайджанском корпусе
- [ ] Sentiment analysis для текстов
- [ ] Automatic summarization
- [ ] Email alerts для критических рисков

### Долгосрочные планы (6-12 месяцев)

- [ ] Knowledge graph для связей
- [ ] Predictive risk modeling
- [ ] Multi-language support (русский, английский)
- [ ] Mobile приложение

## Тестирование

```bash
# Запуск тестов
pytest evaluation/

# Оценка на gold dataset
python evaluation/run_pipeline_on_gold.py

# Генерация метрик
python evaluation/metrics_evaluator.py
```

## Лицензия

Проект разработан для ClearPic (финансовая организация).  
Все права защищены (c) 2025.

## Контакты

- **Email**: info@clearpic.az
- **Техподдержка**: support@clearpic.az
- **Документация**: http://docs.clearpic.az

## Благодарности

- HuggingFace Transformers
- spaCy
- FastAPI
- PostgreSQL Community
