# ClearPic - Azerbaijan Media Monitoring System

Система мониторинга азербайджанских СМИ с NER, анализом рисков и поиском связей между персонами.

## Компоненты

| Компонент | Описание |
|-----------|----------|
| **PostgreSQL** | Хранение спарсенных новостей |
| **API (FastAPI)** | REST API + Web UI |
| **Парсеры** | report.az, azerbaijan.az, trend.az |
| **ML модели** | NER, Risk Classification |

## Быстрый старт

### 1. Запуск базы данных и API

```bash
# Запуск БД + API
docker compose up -d db api

# Проверка статуса
docker compose ps
```

### 2. Открыть в браузере

| URL | Описание |
|-----|----------|
| http://localhost:8000 | Главная страница |
| http://localhost:8000/search | Поиск по новостям в БД |
| http://localhost:8000/entities | **Карточки персон** (связи, риски, NLI) |
| http://localhost:8000/stats | Статистика БД |
| http://localhost:8000/docs | Swagger API |
| http://localhost:8000/redoc | ReDoc API |

### Функции Web UI

#### Карточки персон (`/entities`)
- Поиск персон по имени (713+ персон в индексе)
- Отображение связей (персоны, организации, локации)
- Семантические связи (met_with, works_for, related_to)
- NLI-метки с confidence score
- Цитаты из статей (evidence) со ссылками на источники
- Уровень риска (LOW, MEDIUM, HIGH, CRITICAL)

#### Поиск по БД (`/search`)
- Полнотекстовый поиск по 85,000+ статей
- Фильтрация по дате, источнику, типу сущности

### 3. Запуск парсеров (опционально)

```bash
# Запуск всех парсеров
docker compose --profile scraper up -d

# Или отдельно:
docker compose run --rm scraper_report
docker compose run --rm scraper_azerbaijan
docker compose run --rm scraper_trend
```

## API Endpoints

### Поиск персон

```bash
# Поиск по имени
curl "http://localhost:8000/api/v1/persons/search?q=Агаларов&limit=5"

# Получить карточку персоны
curl "http://localhost:8000/api/v1/persons/by-name/Агаларов"

# Топ персон по связям
curl "http://localhost:8000/api/v1/top-persons?limit=20"
```

### Статистика БД

```bash
# Статистика по таблицам
curl "http://localhost:8000/api/v1/stats/database"

# Поиск по статьям
curl "http://localhost:8000/api/v1/stats/search-articles?q=президент"

# Последние статьи
curl "http://localhost:8000/api/v1/stats/recent?limit=10"
```

### Обработка текста (NER + Риски)

```bash
curl -X POST "http://localhost:8000/api/v1/process/text" \
  -H "Content-Type: application/json" \
  -d '{"text": "Президент İlham Əliyev встретился с министром экономики", "analyze_risk": true}'
```

## Структура проекта

```
parsAZ/
├── api/                    # FastAPI приложение
│   ├── main.py            # Точка входа
│   └── routers/           # API роуты
│       ├── search.py      # Поиск персон
│       ├── stats.py       # Статистика БД
│       └── process.py     # NER + Риски
├── app/                    # Парсеры
│   ├── scraper/           # Логика парсинга
│   └── db/                # Работа с БД
├── model/                  # ML модели
│   ├── person_index.json  # Индекс персон
│   ├── ner_module.py      # NER модуль
│   └── risk_classifier.py # Классификатор рисков
├── website/               # Web UI
│   ├── templates/         # HTML шаблоны
│   └── static/            # CSS, JS
├── docker/                # Dockerfiles
├── docker-compose.yml     # Оркестрация
└── requirements*.txt      # Зависимости
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| DB_HOST | db | Хост PostgreSQL |
| DB_PORT | 5432 | Порт PostgreSQL |
| DB_NAME | newsdb | Имя базы данных |
| DB_USER | myuser | Пользователь |
| DB_PASS | mypass | Пароль |

## Разработка

```bash
# Локальный запуск API (без Docker)
cd parsAZ
pip install -r requirements-api.txt
uvicorn api.main:app --reload --port 8000

# Логи парсеров
docker logs -f scraper_trend
```

## Таблицы БД

```sql
-- Новости report.az
CREATE TABLE report (
    id SERIAL PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    pub_date TIMESTAMP,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Аналогично для azerbaijan, trend
```

## Примеры запросов

### Карточка персоны (API)

```bash
# Поиск персоны по имени
curl "http://localhost:8000/api/v1/persons/search?q=Ceyhun+Bayramov" | jq

# Полная карточка с соседями и связями
curl "http://localhost:8000/api/v1/persons/ceyhun%20bayramov?top_neighbors=50" | jq

# Карточка по имени (удобный endpoint)
curl "http://localhost:8000/api/v1/persons/by-name/Ilham+Aliyev?top_neighbors=30" | jq
```

### Пример ответа карточки

```json
{
  "status": "ok",
  "person": {
    "person_key": "ceyhun bayramov",
    "display": "Ceyhun Bayramov",
    "risk": {"risk_level": "LOW", "overall_risk_score": 0.0},
    "neighbors_count": 22,
    "neighbors": [
      {
        "display": "Hakan Fidan",
        "type": "person",
        "nli_label": "met with",
        "nli_score": 1.0,
        "evidence": [{"sentence": "...görüş...", "link": "https://..."}]
      }
    ],
    "semantic_relations": [
      {"relation": "met_with", "target": "Abdullah bin Zayed", "nli_score": 1.0}
    ]
  }
}
```

### Топ персон с рисками

```bash
curl "http://localhost:8000/api/v1/top-persons?sort_by=risk_score&limit=10" | jq
```

### Статистика индекса

```bash
curl "http://localhost:8000/api/v1/index/stats" | jq
# {"total_persons": 713, "total_neighbors": 3097, "risk_levels": {...}}
```

### Поиск по новостям

```bash
# Поиск статей про Агаларова
curl "http://localhost:8000/api/v1/search?query=Agalarov&limit=20" | jq
```
