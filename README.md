# Report.az News Parser

Парсер новостей с сайта report.az (азербайджанский язык) с сохранением в PostgreSQL.

## Структура проекта

```
parsAZ/
├── app/
│   ├── scraper/
│   │   ├── config.py      # Конфигурация
│   │   ├── client.py      # HTTP клиент с retry
│   │   ├── parsers.py     # HTML парсеры
│   │   └── pipeline.py    # Основной пайплайн
│   └── db/
│       ├── models.py      # Модели данных
│       ├── connection.py  # Подключение к БД
│       └── repository.py  # CRUD операции
├── docker/
│   └── Dockerfile.scraper
├── docker-compose.yml
├── main.py
└── requirements.txt
```

## Быстрый старт (Docker)

```bash
# Запуск PostgreSQL + парсер
docker compose up -d

# Только БД (для локальной разработки)
docker compose up -d db

# Логи парсера
docker compose logs -f scraper
```

## Локальный запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Экспорт переменных (или создайте .env)
export DB_HOST=localhost
export DB_NAME=newsdb
export DB_USER=myuser
export DB_PASS=mypass

# Запуск парсера
python main.py

# С параметрами
python main.py --start-date 2024-01-01 --end-date 2024-12-01 --log-level DEBUG
```

## Параметры командной строки

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--start-date` | Начальная дата (YYYY-MM-DD) | 2014-01-01 |
| `--end-date` | Конечная дата (YYYY-MM-DD) | сегодня |
| `--log-level` | Уровень логирования | INFO |
| `--batch-size` | Размер батча для вставки | 50 |

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `DB_HOST` | Хост PostgreSQL | db |
| `DB_PORT` | Порт PostgreSQL | 5432 |
| `DB_NAME` | Имя базы данных | newsdb |
| `DB_USER` | Пользователь БД | myuser |
| `DB_PASS` | Пароль БД | mypass |

## Схема таблицы

```sql
CREATE TABLE IF NOT EXISTS report (
    id BIGSERIAL PRIMARY KEY,
    link TEXT UNIQUE NOT NULL,
    pub_date TIMESTAMP,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

## Возможности

- ✅ Парсинг архива новостей с 2014 года
- ✅ Retry логика с exponential backoff
- ✅ Random delays для избежания блокировки
- ✅ Batch insert в БД
- ✅ Дедупликация по URL (ON CONFLICT DO NOTHING)
- ✅ Структурированное логирование
- ✅ Docker-ready
