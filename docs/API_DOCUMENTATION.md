# API Documentation
## Media Monitoring System REST API

**Версия:** 1.0.0  
**Base URL:** `http://localhost:8000`  
**Дата:** 17 декабря 2025 г.

## Содержание

1. [Введение](#введение)
2. [Быстрый старт](#быстрый-старт)
3. [Аутентификация](#аутентификация)
4. [Endpoints](#endpoints)
5. [Модели данных](#модели-данных)
6. [Примеры использования](#примеры-использования)
7. [Коды ошибок](#коды-ошибок)
8. [Rate Limiting](#rate-limiting)
9. [Развертывание](#развертывание)

## Введение

Media Monitoring API предоставляет программный доступ к системе автоматического мониторинга азербайджанских СМИ для выявления рисков компаний и персон.

### Основные возможности

- **Обработка текстов** - автоматическое извлечение сущностей (NER)
- **Анализ связей** - выявление отношений между сущностями
- **Классификация рисков** - определение репутационных и compliance-рисков
- **Поиск** - гибкий поиск по базе данных
- **Статистика** - аналитика по обработанным данным

### Технологии

- **FastAPI** - современный Python фреймворк
- **Pydantic** - валидация данных
- **NER Models** - Davlan xlm-roberta + LocalDoc azerbaijani
- **PostgreSQL** - хранение данных (опционально)

## Быстрый старт

### Установка зависимостей

```bash
pip install -r requirements_api.txt
```

### Настройка PostgreSQL

API требует подключения к PostgreSQL для работы функций поиска и хранения данных.

1. Создайте базу данных:
```bash
createdb newsdb
```

2. Инициализируйте схему из файла database_schema.sql:
```bash
psql -d newsdb -f database_schema.sql
```

3. Настройте переменные окружения для подключения к БД:
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=newsdb
export DB_USER=postgres
export DB_PASSWORD=your_password
```

### Запуск сервера

```bash
# Вариант 1: Прямой запуск
python api.py

# Вариант 2: Через uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Вариант 3: С помощью Docker
docker build -t media-monitoring-api .
docker run -p 8000:8000 media-monitoring-api
```

### Проверка работоспособности

```bash
curl http://localhost:8000/api/v1/health
```

### Интерактивная документация

После запуска сервера откройте в браузере:
- **Swagger UI:** http://localhost:8000/api/v1/docs
- **ReDoc:** http://localhost:8000/api/v1/redoc

## Аутентификация

**Текущая версия:** Аутентификация не требуется (MVP версия)

**Планируется в версии 2.0:**
- JWT токены
- API ключи
- OAuth 2.0

## Endpoints

### 1. Health Check

**GET** `/api/v1/health`

Проверка состояния системы и всех компонентов.

#### Response

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-12-17T10:30:00",
  "components": {
    "preprocessor": "ok",
    "ner_extractor": "ok",
    "relation_extractor": "ok",
    "risk_classifier": "ok",
    "deduplicator": "ok"
  }
}
```

#### Status Codes

- `200` - Система работает
- `503` - Система недоступна

### 2. Обработка текста

**POST** `/api/v1/process`

Обработка нового текста статьи с извлечением сущностей, связей и рисков.

#### Request Body

```json
{
  "text": "Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb. İ.Baxışov ağır xəsarətdən müalicə aldığı xəstəxanada vəfat edib.",
  "title": "Mingəçevirdə hadisə",
  "source": "Report.az",
  "url": "https://report.az/example",
  "pub_date": "2025-12-17",
  "extract_relationships": true,
  "classify_risks": true
}
```

#### Parameters

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `text` | string | Да | Текст статьи (мин. 10 символов) |
| `title` | string | Нет | Заголовок статьи |
| `source` | string | Нет | Источник (Report.az, Trend.az и т.д.) |
| `url` | string | Нет | URL статьи |
| `pub_date` | string | Нет | Дата публикации (YYYY-MM-DD) |
| `extract_relationships` | boolean | Нет | Извлекать связи (по умолчанию: true) |
| `classify_risks` | boolean | Нет | Классифицировать риски (по умолчанию: true) |

#### Response

```json
{
  "article_id": "a1b2c3d4e5f6",
  "title": "Mingəçevirdə hadisə",
  "source": "Report.az",
  "pub_date": "2025-12-17",
  "processing_time_ms": 3245.67,
  "entities": {
    "persons": [
      {
        "name": "İ.Baxışov",
        "type": "person",
        "confidence": 0.9999,
        "context": "İ.Baxışov ağır xəsarətdən müalicə aldığı...",
        "source": "davlan"
      }
    ],
    "organizations": [],
    "locations": [
      {
        "name": "Mingəçevir",
        "type": "location",
        "confidence": 0.9410,
        "context": "Mingəçevir şəhərində bədbəxt hadisə...",
        "source": "localdoc"
      }
    ],
    "positions": [],
    "dates": [],
    "events": []
  },
  "relationships": [
    {
      "source_entity": "İ.Baxışov",
      "target_entity": "Mingəçevir",
      "relation_type": "located_in",
      "confidence": 0.75,
      "evidence": "İ.Baxışov Mingəçevir şəhərində...",
      "source_method": "regex"
    }
  ],
  "risks": {
    "risk_level": "MEDIUM",
    "risk_score": 0.25,
    "detected_risks": [
      {
        "type": "violations",
        "confidence": 0.85,
        "keyword_matches": 2
      }
    ]
  },
  "knowledge_graph": {
    "nodes": {
      "İ.Baxışov": {
        "type": "persons",
        "label": "İ.Baxışov"
      },
      "Mingəçevir": {
        "type": "locations",
        "label": "Mingəçevir"
      }
    },
    "edges": [
      {
        "from": "İ.Baxışov",
        "to": "Mingəçevir",
        "type": "located_in",
        "confidence": 0.75
      }
    ]
  }
}
```

#### Status Codes

- `200` - Успешная обработка
- `400` - Некорректный запрос
- `422` - Ошибка валидации
- `500` - Внутренняя ошибка сервера
- `503` - Сервис недоступен

#### Performance Notes

- **Первый запрос:** 5-10 секунд (загрузка моделей в память)
- **Последующие запросы:** 2-5 секунд
- **С GPU:** 1-2 секунды

### 3. Поиск по базе

**POST** `/api/v1/search`

Поиск статей по различным критериям.

#### Request Body

```json
{
  "entity_name": "Baxışov",
  "entity_type": "person",
  "risk_level": "MEDIUM",
  "source": "Report.az",
  "date_from": "2025-01-01",
  "date_to": "2025-12-31",
  "limit": 10,
  "offset": 0
}
```

#### Parameters

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `entity_name` | string | Нет | Имя сущности (частичное совпадение) |
| `entity_type` | enum | Нет | Тип: person, organization, location, position, date, event |
| `risk_level` | enum | Нет | Минимальный уровень: CRITICAL, HIGH, MEDIUM, LOW |
| `source` | string | Нет | Источник новостей |
| `date_from` | string | Нет | Дата от (YYYY-MM-DD) |
| `date_to` | string | Нет | Дата до (YYYY-MM-DD) |
| `limit` | integer | Нет | Макс. результатов (1-100, по умолчанию: 10) |
| `offset` | integer | Нет | Смещение для пагинации (по умолчанию: 0) |

#### Response

```json
{
  "total": 42,
  "limit": 10,
  "offset": 0,
  "results": [
    {
      "article_id": "abc123",
      "title": "Mingəçevirdə hadisə",
      "source": "Report.az",
      "pub_date": "2025-12-17",
      "entities": {
        "persons": [
          {
            "name": "İ.Baxışov",
            "confidence": 0.999
          }
        ],
        "organizations": [],
        "locations": [
          {
            "name": "Mingəçevir",
            "confidence": 0.94
          }
        ]
      },
      "risk_level": "MEDIUM",
      "risk_score": 0.25
    }
  ]
}
```

#### Status Codes

- `200` - Успешный поиск
- `400` - Некорректные параметры
- `422` - Ошибка валидации

### 4. Получение статьи по ID

**GET** `/api/v1/articles/{article_id}`

Получение полной информации о конкретной статье.

#### Path Parameters

- `article_id` (string, required) - Уникальный идентификатор статьи

#### Response

```json
{
  "article_id": "a1b2c3d4e5f6",
  "title": "Mingəçevirdə hadisə",
  "text": "Полный текст статьи...",
  "source": "Report.az",
  "url": "https://report.az/example",
  "pub_date": "2025-12-17",
  "created_at": "2025-12-17T10:30:00",
  "entities": {...},
  "relationships": [...],
  "risks": {...}
}
```

#### Status Codes

- `200` - Статья найдена
- `404` - Статья не найдена
- `501` - Не реализовано (MVP версия)

### 5. Список сущностей

**GET** `/api/v1/entities`

Получение списка всех уникальных сущностей из базы.

#### Query Parameters

| Параметр | Тип | Описание |
|----------|-----|----------|
| `entity_type` | enum | Фильтр по типу: person, organization, location и т.д. |
| `limit` | integer | Макс. результатов (1-1000, по умолчанию: 100) |
| `offset` | integer | Смещение (по умолчанию: 0) |

#### Response

```json
{
  "total": 1456,
  "limit": 100,
  "offset": 0,
  "entities": [
    {
      "entity_id": "ent_001",
      "name": "İ.Baxışov",
      "type": "person",
      "mention_count": 3,
      "first_seen": "2025-12-01",
      "last_seen": "2025-12-17"
    },
    {
      "entity_id": "ent_002",
      "name": "Mingəçevir",
      "type": "location",
      "mention_count": 45,
      "first_seen": "2025-06-01",
      "last_seen": "2025-12-17"
    }
  ]
}
```

#### Status Codes

- `200` - Успешно
- `501` - Не реализовано (MVP версия)

### 6. Связи между сущностями

**GET** `/api/v1/relationships`

Получение связей между сущностями.

#### Query Parameters

| Параметр | Тип | Описание |
|----------|-----|----------|
| `entity_name` | string | Имя сущности для поиска связей |
| `relation_type` | string | Тип связи: works_for, owns, manages и т.д. |
| `limit` | integer | Макс. результатов (1-1000, по умолчанию: 100) |
| `offset` | integer | Смещение (по умолчанию: 0) |

#### Response

```json
{
  "total": 342,
  "limit": 100,
  "offset": 0,
  "relationships": [
    {
      "relationship_id": "rel_001",
      "source_entity": "Polad Həşimov",
      "target_entity": "SOCAR",
      "relation_type": "works_for",
      "confidence": 0.85,
      "evidence": "Polad Həşimov SOCAR компанияsin директор...",
      "source_method": "regex",
      "article_count": 5
    }
  ]
}
```

#### Status Codes

- `200` - Успешно
- `501` - Не реализовано (MVP версия)

### 7. Статистика системы

**GET** `/api/v1/stats`

Получение общей статистики по обработанным данным.

#### Response

```json
{
  "total_articles": 237,
  "total_entities": 1456,
  "total_relationships": 342,
  "entities_by_type": {
    "person": 567,
    "organization": 234,
    "location": 445,
    "position": 89,
    "date": 78,
    "event": 43
  },
  "risks_by_level": {
    "CRITICAL": 12,
    "HIGH": 34,
    "MEDIUM": 89,
    "LOW": 102
  },
  "sources": [
    "Report.az",
    "Trend.az"
  ],
  "date_range": {
    "from": "2025-06-01",
    "to": "2025-12-17"
  }
}
```

#### Status Codes

- `200` - Успешно

## Модели данных

### EntityTypeEnum

Типы сущностей, которые система может извлекать:

```python
class EntityTypeEnum(str, Enum):
    person = "person"              # Персоны
    organization = "organization"  # Организации
    location = "location"          # Локации
    position = "position"          # Должности
    date = "date"                  # Даты
    event = "event"                # События
```

### RiskLevelEnum

Уровни риска:

```python
class RiskLevelEnum(str, Enum):
    CRITICAL = "CRITICAL"  # Критический
    HIGH = "HIGH"          # Высокий
    MEDIUM = "MEDIUM"      # Средний
    LOW = "LOW"            # Низкий
```

### Entity

Структура сущности:

```json
{
  "name": "string",         // Имя сущности
  "type": "string",         // Тип (person, organization и т.д.)
  "confidence": "float",    // Уверенность модели (0.0-1.0)
  "context": "string",      // Контекст упоминания
  "source": "string"        // Источник (davlan, localdoc, ensemble)
}
```

### Relationship

Структура связи:

```json
{
  "source_entity": "string",      // Исходная сущность
  "target_entity": "string",      // Целевая сущность
  "relation_type": "string",      // Тип связи (works_for, owns и т.д.)
  "confidence": "float",          // Уверенность (0.0-1.0)
  "evidence": "string",           // Текстовое подтверждение
  "source_method": "string"       // Метод извлечения (regex, spacy, bert)
}
```

### Risk

Структура информации о рисках:

```json
{
  "risk_level": "string",         // Уровень риска (CRITICAL, HIGH и т.д.)
  "risk_score": "float",          // Скор риска (0.0-1.0)
  "detected_risks": [             // Список обнаруженных рисков
    {
      "type": "string",           // Тип риска (corruption, fraud и т.д.)
      "confidence": "float",      // Уверенность (0.0-1.0)
      "keyword_matches": "int"    // Количество совпадений ключевых слов
    }
  ]
}
```

## Примеры использования

### Python (requests)

```python
import requests
import json

# 1. Проверка здоровья системы
response = requests.get("http://localhost:8000/api/v1/health")
print(response.json())

# 2. Обработка текста
data = {
    "text": "Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb.",
    "title": "Mingəçevirdə hadisə",
    "source": "Report.az"
}

response = requests.post(
    "http://localhost:8000/api/v1/process",
    json=data
)

result = response.json()
print(f"Article ID: {result['article_id']}")
print(f"Processing time: {result['processing_time_ms']}ms")
print(f"Entities: {result['entities']}")

# 3. Поиск
search_params = {
    "entity_name": "Baxışov",
    "entity_type": "person",
    "limit": 10
}

response = requests.post(
    "http://localhost:8000/api/v1/search",
    json=search_params
)

results = response.json()
print(f"Found {results['total']} articles")
```

### cURL

```bash
# Health check
curl -X GET http://localhost:8000/api/v1/health

# Обработка текста
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb.",
    "title": "Mingəçevirdə hadisə",
    "source": "Report.az"
  }'

# Поиск
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "entity_name": "Baxışov",
    "entity_type": "person",
    "limit": 10
  }'

# Статистика
curl -X GET http://localhost:8000/api/v1/stats
```

### JavaScript (fetch)

```javascript
// Health check
fetch('http://localhost:8000/api/v1/health')
  .then(response => response.json())
  .then(data => console.log(data));

// Обработка текста
const processText = async () => {
  const response = await fetch('http://localhost:8000/api/v1/process', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: 'Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb.',
      title: 'Mingəçevirdə hadisə',
      source: 'Report.az'
    })
  });
  
  const result = await response.json();
  console.log('Article ID:', result.article_id);
  console.log('Entities:', result.entities);
};

processText();
```

## Коды ошибок

### HTTP Status Codes

| Код | Название | Описание |
|-----|----------|----------|
| 200 | OK | Успешный запрос |
| 400 | Bad Request | Некорректный запрос |
| 404 | Not Found | Ресурс не найден |
| 422 | Unprocessable Entity | Ошибка валидации данных |
| 500 | Internal Server Error | Внутренняя ошибка сервера |
| 501 | Not Implemented | Функционал не реализован |
| 503 | Service Unavailable | Сервис недоступен |

### Формат ошибки

```json
{
  "detail": "Текст ошибки",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-12-17T10:30:00"
}
```

### Распространенные ошибки

#### 1. Текст слишком короткий

```json
{
  "detail": [
    {
      "loc": ["body", "text"],
      "msg": "ensure this value has at least 10 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

#### 2. NER модель не загружена

```json
{
  "detail": "NER Extractor not available",
  "error_code": "NER_UNAVAILABLE"
}
```

#### 3. Превышен лимит результатов

```json
{
  "detail": [
    {
      "loc": ["body", "limit"],
      "msg": "ensure this value is less than or equal to 100",
      "type": "value_error.number.not_le"
    }
  ]
}
```

## Rate Limiting

**Текущая версия:** Rate limiting не реализован

**Планируется в версии 2.0:**
- 100 запросов/минуту для /process
- 1000 запросов/минуту для /search и других GET endpoints
- Заголовки: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

## Развертывание

### Docker

Создайте `Dockerfile`:

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей
COPY requirements.txt requirements_api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements_api.txt

# Копирование кода
COPY . .

# Загрузка spaCy модели
RUN python -m spacy download en_core_web_sm

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

Сборка и запуск:

```bash
docker build -t clearpic-api .
docker run -p 8000:8000 clearpic-api
```

### Docker Compose

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=postgres
      - DB_PORT=5432
      - DB_NAME=newsdb
      - DB_USER=admin
      - DB_PASSWORD=secret
    depends_on:
      - postgres
    volumes:
      - ./models:/app/models

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=newsdb
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=secret
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database_schema.sql:/docker-entrypoint-initdb.d/schema.sql
    ports:
      - "5432:5432"

volumes:
  postgres_data:
```

Запуск:

```bash
docker-compose up -d
```

### Production рекомендации

1. **Используйте HTTPS** - настройте SSL/TLS сертификаты
2. **Добавьте аутентификацию** - JWT токены или API ключи
3. **Настройте rate limiting** - защита от злоупотреблений
4. **Мониторинг** - Prometheus + Grafana для метрик
5. **Логирование** - централизованное логирование (ELK stack)
6. **Кэширование** - Redis для частых запросов
7. **Load balancing** - nginx или AWS ALB
8. **Масштабирование** - несколько инстансов API за балансером

### Переменные окружения

```bash
# API настройки
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# База данных
DB_HOST=localhost
DB_PORT=5432
DB_NAME=newsdb
DB_USER=admin
DB_PASSWORD=secret

# Модели
MODEL_CACHE_DIR=/app/models
USE_GPU=false

# Логирование
LOG_LEVEL=INFO
LOG_FILE=/var/log/media-monitoring-api.log
```

## Версионирование

API использует семантическое версионирование (SemVer):

- **Текущая версия:** 1.0.0
- **Major версия** изменяется при несовместимых изменениях API
- **Minor версия** изменяется при добавлении новой функциональности с обратной совместимостью
- **Patch версия** изменяется при исправлении багов

## Поддержка и контакты

**Техническая поддержка:**  
Email: support@parsaz.com  
GitHub Issues: [ссылка на репозиторий]

**Документация:**  
- Swagger UI: http://localhost:8000/api/v1/docs
- ReDoc: http://localhost:8000/api/v1/redoc
- Этот документ: API_DOCUMENTATION.md

**Обратная связь:**  
Для вопросов и предложений обращайтесь через GitHub Issues

## Changelog

### Version 1.0.0 (2025-12-17)

**Добавлено:**
- POST /api/v1/process - обработка текста
- POST /api/v1/search - поиск по базе
- GET /api/v1/health - health check
- GET /api/v1/stats - статистика системы
- Pydantic модели для валидации
- Swagger/ReDoc документация
- CORS middleware
- Обработка ошибок

**Известные ограничения:**
- Нет аутентификации
- Нет rate limiting
- Endpoints для работы с БД возвращают 501 (не реализовано)
- Нет кэширования

### Roadmap

**Version 1.1.0 (Q1 2026):**
- Интеграция с PostgreSQL
- Реализация всех endpoints для работы с БД
- Кэширование через Redis
- Batch обработка текстов

**Version 2.0.0 (Q2 2026):**
- JWT аутентификация
- Rate limiting
- WebSocket для real-time обновлений
- Асинхронная обработка больших объемов
- GraphQL API (альтернатива REST)
