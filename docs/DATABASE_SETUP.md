# Настройка базы данных PostgreSQL

## Вариант 1: Установка Docker и запуск БД в контейнере (РЕКОМЕНДУЕТСЯ)

### Шаг 1: Установка Docker Desktop для Windows

1. Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Установите Docker Desktop
3. Запустите Docker Desktop
4. Дождитесь, пока Docker запустится (иконка в трее должна стать зеленой)

### Шаг 2: Запуск PostgreSQL

Откройте PowerShell в директории проекта и выполните:

```powershell
cd C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ
docker compose up -d db
```

### Шаг 3: Проверка

Проверьте, что контейнер запущен:

```powershell
docker ps
```

Вы должны увидеть контейнер `parsaz_db`.

### Шаг 4: Запуск приложения

```powershell
cd C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ
$env:PYTHONPATH=(Get-Location).Path
& "C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ\venv\Scripts\python.exe" website\app.py
```

Приложение теперь будет работать с базой данных.

---

## Вариант 2: Установка PostgreSQL напрямую в Windows

### Шаг 1: Установка PostgreSQL

1. Скачайте PostgreSQL 17: https://www.postgresql.org/download/windows/
2. Запустите установщик
3. В процессе установки укажите пароль для пользователя `postgres`
4. Запомните порт (по умолчанию 5432)

### Шаг 2: Создание базы данных и пользователя

Откройте SQL Shell (psql) из меню Пуск и выполните:

```sql
-- Подключитесь как postgres (оставьте все поля пустыми, нажимая Enter, кроме пароля)

-- Создайте базу данных
CREATE DATABASE newsdb;

-- Создайте пользователя
CREATE USER myuser WITH PASSWORD 'mypass';

-- Дайте права
GRANT ALL PRIVILEGES ON DATABASE newsdb TO myuser;

-- Подключитесь к базе
\c newsdb

-- Дайте права на схему
GRANT ALL ON SCHEMA public TO myuser;

-- Выход
\q
```

### Шаг 3: Настройка переменных окружения

Создайте файл `.env` в корне проекта:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=newsdb
DB_USER=myuser
DB_PASSWORD=mypass
```

### Шаг 4: Запуск приложения

```powershell
cd C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ
$env:PYTHONPATH=(Get-Location).Path
& "C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ\venv\Scripts\python.exe" website\app.py
```

---

## Вариант 3: Работа без базы данных

Приложение может работать без базы данных в режиме демонстрации.

В этом режиме:
- ✅ Обработка текста работает
- ✅ Извлечение сущностей работает
- ✅ Извлечение отношений работает
- ✅ Классификация рисков работает
- ✅ Поиск персон работает (из индекса)
- ❌ Сохранение в БД не работает
- ❌ Статистика показывает mock данные

Просто запустите приложение:

```powershell
cd C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ
$env:PYTHONPATH=(Get-Location).Path
& "C:\Users\admin\MIPT\Sem3\Hackathon\parsAZ\venv\Scripts\python.exe" website\app.py
```

Предупреждения о недоступности БД можно игнорировать.

---

## Параметры подключения

По умолчанию используются следующие параметры:

- **Host:** localhost
- **Port:** 5432
- **Database:** newsdb
- **User:** myuser (для Docker) / admin (по умолчанию)
- **Password:** mypass (для Docker) / secret (по умолчанию)

Эти параметры можно изменить через переменные окружения или файл `.env`.

---

## Схема базы данных

Схема создается автоматически при первом обращении к БД. Основные таблицы:

- `articles` - Обработанные статьи
- `entities` - Извлеченные сущности
- `relationships` - Связи между сущностями
- `risk_assessments` - Оценки рисков

Файл схемы: `data/database_schema.sql`

---

## Полезные команды

### Docker

```powershell
# Запустить БД
docker compose up -d db

# Остановить БД
docker compose down

# Посмотреть логи БД
docker logs parsaz_db

# Зайти в psql в контейнере
docker exec -it parsaz_db psql -U myuser -d newsdb
```

### PostgreSQL напрямую

```powershell
# Подключиться к БД
psql -U myuser -d newsdb -h localhost

# Проверить статус сервиса
Get-Service postgresql*
```
