"""
website_app.py - FastAPI приложение для веб-интерфейса мониторинга СМИ

Предоставляет веб-интерфейс для тестирования и демонстрации системы.
Интегрируется с существующим API и компонентами обработки.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging
from datetime import datetime

# Импорт API компонентов
from api.app import app as api_app
from src.core.text_preprocessor import TextPreprocessor
from src.core.entity_extractor import NEREnsembleExtractor
from src.core.relationship_extractor import RelationExtractorHybridPro
from src.core.risk_classifier import RiskClassifier
from src.core.entity_deduplicator import EntityDeduplicator
from src.utils.output_formatter import OutputFormatter
from src.database.manager import DatabaseManager, get_db_manager

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_ORANGE = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"

# Custom formatter with colored log levels
class ColoredFormatter(logging.Formatter):
    def format(self, record):
        if record.levelno == logging.INFO:
            levelname_colored = f"{COLOR_GREEN}{record.levelname}{COLOR_RESET}"
        elif record.levelno == logging.WARNING:
            levelname_colored = f"{COLOR_ORANGE}{record.levelname}{COLOR_RESET}"
        elif record.levelno == logging.ERROR:
            levelname_colored = f"{COLOR_RED}{record.levelname}{COLOR_RESET}"
        else:
            levelname_colored = record.levelname
        
        record.levelname = levelname_colored
        return super().format(record)

# Настройка логирования
handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter('%(levelname)s:\t%(name)s:\t%(message)s'))
logging.basicConfig(
    level=logging.INFO,
    handlers=[handler]
)
logger = logging.getLogger(__name__)

# Инициализация FastAPI приложения
app = FastAPI(
    title="ClearPic Media Monitoring - Web Interface",
    description="Веб-интерфейс для системы мониторинга азербайджанских СМИ",
    version="1.0.0"
)

# Добавляем middleware для отключения кэширования статики
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Настройка путей
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "website" / "templates"
STATIC_DIR = BASE_DIR / "website" / "static"

# Создание директорий если их нет
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Монтирование статических файлов и шаблонов  
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Включение маршрутов API напрямую, кроме корневого "/"
for route in api_app.routes:
    # Пропускаем корневой маршрут из API, чтобы не конфликтовать с веб-интерфейсом
    if hasattr(route, 'path') and route.path == "/":
        continue
    app.routes.append(route)

# Инициализация компонентов системы (ленивая загрузка)
_components = {}

def get_components():
    """Получение или инициализация компонентов системы"""
    if not _components:
        logger.info("Инициализация компонентов системы...")
        _components['preprocessor'] = TextPreprocessor()
        _components['ner'] = NEREnsembleExtractor()
        _components['relation_extractor'] = RelationExtractorHybridPro()
        _components['risk_classifier'] = RiskClassifier()
        _components['deduplicator'] = EntityDeduplicator()
        _components['formatter'] = OutputFormatter()
        
        # Попытка подключения к БД (может не работать)
        try:
            _components['db'] = get_db_manager()
        except Exception as e:
            logger.warning(f"Database connection failed: {e}. Running without database.")
            _components['db'] = None
        
        logger.info("Компоненты инициализированы")
    return _components


# Маршруты для HTML страниц

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Главная страница"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/process", response_class=HTMLResponse)
async def process_page(request: Request):
    """Страница обработки текста"""
    return templates.TemplateResponse("process.html", {"request": request})


@app.get("/search", response_class=HTMLResponse)
async def search_page(request: Request):
    """Страница поиска"""
    return templates.TemplateResponse("search.html", {"request": request})


@app.get("/entities", response_class=HTMLResponse)
async def entities_page(request: Request):
    """Страница сущностей"""
    return templates.TemplateResponse("entities.html", {"request": request})


@app.get("/stats", response_class=HTMLResponse)
async def stats_page(request: Request):
    """Страница статистики"""
    return templates.TemplateResponse("stats.html", {"request": request})


@app.get("/docs", response_class=HTMLResponse)
async def docs_redirect():
    """Редирект на API документацию"""
    return HTMLResponse(
        content='<meta http-equiv="refresh" content="0; url=/api/v1/docs">',
        status_code=200
    )


# API эндпоинты для веб-интерфейса

@app.get("/web-api/health")
async def health_check():
    """Проверка работоспособности системы"""
    try:
        components = get_components()
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "preprocessor": True,
                "ner": True,
                "relation_extractor": True,
                "risk_classifier": True,
                "database": components['db'] is not None
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "unhealthy", "error": str(e)}
        )


@app.get("/web-api/quick-stats")
async def quick_stats():
    """Быстрая статистика для главной страницы"""
    try:
        # Возвращаем заглушку, т.к. БД не требуется для демонстрации
        return {
            "total_articles": 0,
            "total_entities": 0,
            "total_risks": 0,
            "status": "no_database"
        }
    except Exception as e:
        logger.error(f"Error getting quick stats: {e}")
        return {
            "total_articles": 0,
            "total_entities": 0,
            "total_risks": 0,
            "status": "error"
        }


@app.post("/web-api/fetch-article")
async def fetch_article_from_url(request: Request):
    """Извлечение заголовка и текста статьи из URL"""
    try:
        data = await request.json()
        url = data.get('url')
        
        if not url:
            raise HTTPException(status_code=400, detail="URL не указан")
        
        # Импорт парсеров
        from src.scrapers.client import HttpClient
        from src.scrapers.config import ScraperConfig
        from src.scrapers.parsers.azerbaijan import parse_article_page_az
        from bs4 import BeautifulSoup
        from urllib.parse import urlparse
        
        # Создаем HTTP клиент
        config = ScraperConfig()
        client = HttpClient(config)
        
        # Загружаем страницу
        html = client.fetch(url)
        if not html:
            raise HTTPException(status_code=404, detail="Не удалось загрузить страницу")
        
        # Пробуем специализированный парсер для азербайджанских сайтов
        result = parse_article_page_az(html)
        
        if result and result[0] and result[1]:
            title, text, pub_date = result
            source = urlparse(url).netloc
            
            return {
                "title": title,
                "text": text,
                "source": source,
                "published_date": pub_date.strftime("%Y-%m-%d") if pub_date else None,
                "url": url
            }
        
        # Fallback: универсальный парсинг с BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        # Ищем заголовок
        title = None
        for selector in ['h1', 'h2.title', '.article-title', 'meta[property="og:title"]']:
            if selector.startswith('meta'):
                tag = soup.select_one(selector)
                if tag:
                    title = tag.get('content')
            else:
                tag = soup.select_one(selector)
                if tag:
                    title = tag.get_text(strip=True)
            if title:
                break
        
        # Ищем текст статьи
        text = None
        for selector in ['.article-content', '.post-content', 'article', '.entry-content', 'main']:
            tag = soup.select_one(selector)
            if tag:
                # Удаляем скрипты и стили
                for script in tag(['script', 'style']):
                    script.decompose()
                text = tag.get_text(separator='\n', strip=True)
                if len(text) > 100:  # Минимальная длина текста
                    break
        
        if not title or not text:
            raise HTTPException(status_code=422, detail="Не удалось извлечь заголовок или текст статьи")
        
        source = urlparse(url).netloc
        
        return {
            "title": title,
            "text": text,
            "source": source,
            "published_date": None,
            "url": url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching article: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка обработки: {str(e)}")


# Обработка ошибок

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    """Обработчик 404 ошибки"""
    return templates.TemplateResponse(
        "index.html",
        {"request": request},
        status_code=404
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc: Exception):
    """Обработчик 500 ошибки"""
    logger.error(f"Server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Запуск веб-приложения ClearPic Media Monitoring")
    logger.info("Веб-интерфейс: http://localhost:8002")
    logger.info("API документация: http://localhost:8002/api/v1/docs")
    
    uvicorn.run(
        "website_app:app",
        host="0.0.0.0",
        port=8002,
        reload=False,
        log_level="info"
    )
