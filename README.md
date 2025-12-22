#  parsAZ - Azerbaijan Media Monitoring System

Система мониторинга азербайджанских СМИ с извлечением именованных сущностей (NER), анализом рисков и построением графа связей между персонами.

##  Содержание

- [Описание проекта](#описание-проекта)
- [Возможности](#возможности)
- [Архитектура](#архитектура)
- [Быстрый старт](#быстрый-старт)
- [Web-интерфейс](#web-интерфейс)
- [API Reference](#api-reference)
- [Use Cases](#use-cases)
- [Конфигурация](#конфигурация)
- [Разработка](#разработка)
- [Troubleshooting](#troubleshooting)

---

## Описание проекта

**parsAZ** - это комплексная система для:

1. **Парсинга новостей** с азербайджанских медиа-порталов (report.az, azerbaijan.az, trend.az)
2. **Извлечения именованных сущностей** (NER) - персоны, организации, локации
3. **Анализа рисков** - классификация текстов по категориям рисков (коррупция, санкции, криминал)
4. **Построения графа связей** - кто с кем встречался, где работает, какие отношения
5. **Семантического анализа** - NLI-модели для определения типа связи (met_with, works_for)

### Целевая аудитория

- Аналитики compliance и due diligence
- Журналисты-расследователи
- Risk-менеджеры
- Исследователи медиа-пространства

---

## Возможности

###  Парсинг новостей

| Источник      | Статей  | Период    | Особенности         |
| ------------- | ------- | --------- | ------------------- |
| report.az     | 4,000+  | 2014-2025 | Архив по датам      |
| azerbaijan.az | 7,700+  | 2020-2025 | Официальный портал  |
| trend.az      | 73,000+ | 2014-2025 | AJAX-пагинация, RSS |

###  Поиск и анализ

- **713+ персон** в индексе с профилями
- **3,097 связей** между сущностями
- **85,000+ статей** для полнотекстового поиска
- **NLI-метки**: `met_with`, `works_for`, `appointed_to`, `related_to`

###  Уровни рисков

| Уровень     | Описание         | Количество |
| ----------- | ---------------- | ---------- |
|  LOW      | Минимальный риск | 685        |
|  MEDIUM   | Требует внимания | 27         |
|  HIGH     | Высокий риск     | 0          |
|  CRITICAL | Критический      | 1          |

---

## Архитектура

```

                         WEB UI                                   
         
    Home     Search   Entities    Stats    Process    
         

                               

                      FastAPI (REST API)                          
        
   /api/v1/persons    /api/v1/stats    /api/v1/process     
   /api/v1/search    /api/v1/index       /api/v1/top       
        

                               
        
                                                    
                                                    
        
  PostgreSQL         Person Index          ML Models     
                     (JSON Graph)                        
                             
   report         • 713 persons         NER Module   
       • 3,097 edges         (XLM-R)      
 azerbaijan       • NLI labels          
       • Risk scores         Risk Class.  
    trend         • Evidence            (Keywords)   
            
                           
        
        

                         SCRAPERS                                 
        
   report.az       azerbaijan.az         trend.az          
   (по датам)       (по страницам)   (AJAX + RSS)          
        

```

---

## Быстрый старт

### Требования

- Docker 24+
- Docker Compose 2.20+
- 4GB RAM (минимум)
- 10GB свободного места

### 1. Клонирование и запуск

```bash
# Клонировать репозиторий
git clone <repo-url>
cd parsAZ

# Запустить базу данных и API
docker compose up -d db api

# Проверить статус
docker compose ps
```

### 2. Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health
# {"status":"ok","service":"clearpic-api"}

# Статистика БД
curl http://localhost:8000/api/v1/stats/database
```

### 3. Открыть Web UI

Перейдите в браузере: **http://localhost:8000**

---

## Web-интерфейс

| Страница      | URL                            | Описание                            |
| ------------- | ------------------------------ | ----------------------------------- |
|  Главная    | http://localhost:8000          | Обзор системы                       |
|  Поиск      | http://localhost:8000/search   | Полнотекстовый поиск по статьям     |
|  Сущности   | http://localhost:8000/entities | **Карточки персон** с графом связей |
|  Статистика | http://localhost:8000/stats    | Статистика БД и индекса             |
|  Обработка  | http://localhost:8000/process  | NER + анализ рисков для текста      |
|  Swagger    | http://localhost:8000/docs     | Интерактивная API документация      |

### Карточки персон (`/entities`)

Ключевая функция системы:

1. **Поиск** - введите имя (например: `Ilham Aliyev`, `Agalarov`, `Ceyhun Bayramov`)
2. **Карточка** - отображает:
   - Уровень риска (LOW/MEDIUM/HIGH/CRITICAL)
   - Связи по типам (персоны, организации, локации)
   - NLI-метки (`met with`, `works for`) с confidence score
   - Цитаты из статей (evidence) со ссылками
3. **Семантические связи** - граф отношений

---

## API Reference

### Поиск персон

```bash
# Поиск по имени
GET /api/v1/persons/search?q=Алиев&limit=10

# Карточка по ключу
GET /api/v1/persons/{person_key}?top_neighbors=50&min_support=2

# Карточка по имени (удобный endpoint)
GET /api/v1/persons/by-name/{name}?top_neighbors=30
```

**Пример:**

```bash
curl "http://localhost:8000/api/v1/persons/by-name/Ceyhun+Bayramov" | jq
```

**Ответ:**

```json
{
  "status": "ok",
  "person": {
    "person_key": "ceyhun bayramov",
    "display": "Ceyhun Bayramov",
    "match_score": 1.0,
    "risk": {
      "risk_level": "LOW",
      "overall_risk_score": 0.0
    },
    "neighbors_count": 22,
    "neighbors": [
      {
        "display": "Hakan Fidan",
        "type": "person",
        "support_articles": 3,
        "score": 8.14,
        "nli_label": "met with",
        "nli_score": 1.0,
        "evidence": [
          {
            "sentence": "Fevralın 15-də Azərbaycanın xarici işlər naziri Ceyhun Bayramov Münxen Təhlükəsizlik Konfransı çərçivəsində Türkiyənin xarici işlər naziri Hakan Fidan ilə görüşüb.",
            "link": "https://report.az/..."
          }
        ]
      }
    ],
    "semantic_relations": [
      {
        "relation": "met_with",
        "target": "Hakan Fidan",
        "type": "person",
        "nli_score": 1.0
      }
    ]
  }
}
```

### Поиск по новостям

```bash
# Полнотекстовый поиск
GET /api/v1/search?query=Agalarov&limit=20

# Поиск с фильтрами
GET /api/v1/search?query=президент&date_from=2024-01-01&date_to=2024-12-31
```

### Статистика

```bash
# Статистика БД
GET /api/v1/stats/database

# Статистика индекса
GET /api/v1/index/stats

# Топ персон по связям
GET /api/v1/top-persons?limit=20&sort_by=neighbors_total

# Топ персон по рискам
GET /api/v1/top-persons?limit=10&sort_by=risk_score

# Последние статьи
GET /api/v1/stats/recent?limit=20&source=trend
```

### Обработка текста (NER)

```bash
POST /api/v1/process/text
Content-Type: application/json

{
  "text": "Президент Азербайджана İlham Əliyev встретился с министром экономики",
  "analyze_risk": true
}
```

---

## Use Cases

### 1. Due Diligence проверка персоны

**Сценарий:** Вам нужно проверить бизнес-партнёра перед сделкой.

```bash
# 1. Найти персону
curl "http://localhost:8000/api/v1/persons/search?q=Emin+Agalarov"

# 2. Получить полную карточку
curl "http://localhost:8000/api/v1/persons/by-name/Emin+Agalarov?top_neighbors=50" | jq

# 3. Проверить риски и связи
# - risk_level: LOW/MEDIUM/HIGH
# - neighbors: с кем связан
# - evidence: цитаты из статей
```

**Или через Web UI:**

1. Откройте http://localhost:8000/entities
2. Введите `Emin Agalarov`
3. Изучите карточку с рисками и связями

### 2. Мониторинг политических связей

**Сценарий:** Отслеживание встреч министра иностранных дел.

```bash
curl "http://localhost:8000/api/v1/persons/by-name/Ceyhun+Bayramov" | jq '.person.semantic_relations[] | select(.relation == "met_with")'
```

**Результат:**

```json
{"relation": "met_with", "target": "Abdullah bin Zayed Əl Nəhyan", "type": "person", "nli_score": 1.0}
{"relation": "met_with", "target": "Hakan Fidan", "type": "person", "nli_score": 1.0}
```

### 3. Поиск новостей по теме

**Сценарий:** Найти все статьи про инвестиции.

```bash
curl "http://localhost:8000/api/v1/search?query=investisiya&limit=50" | jq '.results[] | {title, source, date: .published_date}'
```

### 4. Анализ произвольного текста

**Сценарий:** Извлечь сущности из нового текста.

```bash
curl -X POST "http://localhost:8000/api/v1/process/text" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Prezident İlham Əliyev Bakıda Türkiyə Prezidenti Rəcəb Tayyib Ərdoğanla görüşüb.",
    "analyze_risk": true
  }' | jq
```

### 5. Экспорт топ-персон для отчёта

```bash
# Топ 20 персон с наибольшим количеством связей
curl "http://localhost:8000/api/v1/top-persons?limit=20" | jq '.persons[] | "\(.display): \(.neighbors_total) связей, риск: \(.risk_level)"'
```

---

## Конфигурация

### Переменные окружения

| Переменная | По умолчанию | Описание        |
| ---------- | ------------ | --------------- |
| `DB_HOST`  | `db`         | Хост PostgreSQL |
| `DB_PORT`  | `5432`       | Порт PostgreSQL |
| `DB_NAME`  | `newsdb`     | Имя базы данных |
| `DB_USER`  | `myuser`     | Пользователь    |
| `DB_PASS`  | `mypass`     | Пароль          |

### Запуск парсеров

```bash
# Все парсеры (в фоне)
docker compose --profile scraper up -d

# Отдельно report.az (с датами)
docker compose run --rm scraper_report python main.py --start-date 2024-01-01 --end-date 2024-12-31

# Отдельно trend.az (RSS - быстро)
docker compose run --rm scraper_trend python main_trend.py --mode rss

# Отдельно trend.az (полный архив - долго)
docker compose run --rm scraper_trend python main_trend.py --mode ajax --max-pages 1000
```

### Мониторинг парсеров

```bash
# Логи в реальном времени
docker logs -f trend_scraper

# Количество статей в БД
docker exec clearpic_db psql -U myuser -d newsdb -c "SELECT 'report' as source, COUNT(*) FROM report UNION ALL SELECT 'azerbaijan', COUNT(*) FROM azerbaijan UNION ALL SELECT 'trend', COUNT(*) FROM trend;"
```

---

## Структура проекта

```
parsAZ/
 api/                        # FastAPI приложение
    main.py                 # Точка входа, роуты страниц
    routers/                # API endpoints
        search.py           # /api/v1/persons/*, /api/v1/index/*
        stats.py            # /api/v1/stats/*, /api/v1/search
        process.py          # /api/v1/process/* (NER, Risk)

 app/                        # Парсеры новостей
    scraper/
       config.py           # Конфигурация (Pydantic)
       client.py           # HTTP клиент с ретраями
       parsers.py          # Парсер report.az
       parsers_azerbaijan.py
       parsers_trend.py
       pipeline.py         # Пайплайн report.az
       pipeline_azerbaijan.py
       pipeline_trend.py
    db/
        connection.py       # Подключение к PostgreSQL
        models.py           # Pydantic модели
        repository.py       # CRUD для report
        repository_azerbaijan.py
        repository_trend.py

 model/                      # ML модели и индексы
    person_index.json       # Граф персон (713 nodes, 3097 edges)
    person_search.py        # Поиск и навигация по графу
    ner_module.py           # NER (XLM-RoBERTa)
    risk_classifier.py      # Классификатор рисков
    nli_relation_labeler.py # NLI для связей
    text_utils.py           # Утилиты текста

 website/                    # Web UI
    templates/
       index.html          # Главная
       search.html         # Поиск по новостям
       entities.html       # Карточки персон
       stats.html          # Статистика
       process.html        # NER обработка
    static/
        css/style.css
        js/search.js

 docker/
    Dockerfile.api          # API + Web
    Dockerfile.scraper      # Парсеры

 docker-compose.yml          # Оркестрация
 requirements.txt            # Зависимости парсеров
 requirements-api.txt        # Зависимости API
 main.py                     # Entry point report.az
 main_azerbaijan.py          # Entry point azerbaijan.az
 main_trend.py               # Entry point trend.az
```

---

## Разработка

### Локальный запуск (без Docker)

```bash
# 1. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate

# 2. Установить зависимости
pip install -r requirements-api.txt

# 3. Запустить PostgreSQL (нужна своя БД)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=newsdb
export DB_USER=myuser
export DB_PASS=mypass

# 4. Запустить API
uvicorn api.main:app --reload --port 8000
```

### Добавление нового парсера

1. Создайте `app/scraper/parsers_<source>.py`
2. Создайте `app/db/repository_<source>.py`
3. Создайте `app/scraper/pipeline_<source>.py`
4. Создайте `main_<source>.py`
5. Добавьте сервис в `docker-compose.yml`

---

## Troubleshooting

### API не запускается

```bash
# Проверить логи
docker logs clearpic_api

# Проверить здоровье БД
docker exec clearpic_db pg_isready -U myuser -d newsdb
```

### Ошибка подключения к БД

```bash
# Перезапустить БД
docker compose restart db

# Подождать и перезапустить API
sleep 10
docker compose restart api
```

### Кодировка азербайджанских символов

Убедитесь, что БД создана с UTF-8:

```bash
docker exec clearpic_db psql -U myuser -d newsdb -c "SHOW client_encoding;"
# Должно быть: UTF8
```

### Парсер "застревает"

```bash
# Проверить логи
docker logs scraper_trend --tail 50

# Перезапустить с другими параметрами
docker compose run --rm scraper_trend python main_trend.py --mode rss
```

---

## Лицензия

MIT License

---

## Контакты

Для вопросов и предложений создавайте Issues в репозитории.
