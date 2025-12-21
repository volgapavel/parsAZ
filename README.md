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

- **Web UI**: http://localhost:8000
- **Swagger API**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

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

### Найти связи Агаларова

```bash
curl "http://localhost:8000/api/v1/persons/by-name/Агаларов?top_neighbors=30" | jq
```

### Топ персон с рисками

```bash
curl "http://localhost:8000/api/v1/top-persons?sort_by=risk_score&limit=10" | jq
```

### Статистика индекса

```bash
curl "http://localhost:8000/api/v1/index/stats" | jq
```
