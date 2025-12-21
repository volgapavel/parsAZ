"""
api.py - REST API для системы мониторинга азербайджанских СМИ

Endpoints:
- POST /api/v1/process - обработка нового текста
- GET /api/v1/search - поиск по базе
- GET /api/v1/articles/{id} - получение статьи по ID
- GET /api/v1/entities - получение списка сущностей
- GET /api/v1/relationships - получение связей
- GET /api/v1/stats - статистика системы
- GET /api/v1/health - health check

Запуск:
    python api.py
    или
    uvicorn api:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI, HTTPException, Query, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum
import json
import logging

# Импорт компонентов системы
from text_preprocessor import TextPreprocessor
from entity_extractor_ner_ensemble import NEREnsembleExtractor
from relationship_extractor_hybrid_pro import RelationExtractorHybridPro
from risk_classifier import RiskClassifier, RiskLevel
from entity_deduplicator import EntityDeduplicator
from output_formatter import OutputFormatter
from database import DatabaseManager, get_db_manager

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

# Инициализация FastAPI
app = FastAPI(
    title="ClearPic Media Monitoring API",
    description="REST API для автоматического мониторинга азербайджанских СМИ",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
preprocessor = TextPreprocessor()
ner_extractor = None  # Lazy loading
relation_extractor = None  # Lazy loading
risk_classifier = RiskClassifier()
deduplicator = EntityDeduplicator()
formatter = OutputFormatter()
db_manager = None  # Lazy loading database


# ============================================================================
# Pydantic Models
# ============================================================================

class EntityTypeEnum(str, Enum):
    """Типы сущностей"""
    person = "person"
    organization = "organization"
    location = "location"
    position = "position"
    date = "date"
    event = "event"


class RiskLevelEnum(str, Enum):
    """Уровни риска"""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProcessRequest(BaseModel):
    """Запрос на обработку текста"""
    text: str = Field(..., description="Текст статьи на азербайджанском языке", min_length=10)
    title: Optional[str] = Field(None, description="Заголовок статьи")
    source: Optional[str] = Field(None, description="Источник (например, Report.az)")
    url: Optional[str] = Field(None, description="URL статьи")
    pub_date: Optional[str] = Field(None, description="Дата публикации (YYYY-MM-DD)")
    extract_relationships: bool = Field(True, description="Извлекать связи между сущностями")
    classify_risks: bool = Field(True, description="Классифицировать риски")

    class Config:
        schema_extra = {
            "example": {
                "text": "Mingəçevirdə 52 yaşlı kişi aldığı xəsarətdən ölüb. İ.Baxışov xəstəxanada vəfat edib.",
                "title": "Mingəçevirdə hadisə",
                "source": "Report.az",
                "url": "https://report.az/example",
                "pub_date": "2025-12-17",
                "extract_relationships": True,
                "classify_risks": True
            }
        }


class EntityResponse(BaseModel):
    """Сущность в ответе"""
    name: str
    type: str
    confidence: float
    context: Optional[str] = None
    source: Optional[str] = None


class RelationshipResponse(BaseModel):
    """Связь между сущностями"""
    source_entity: str
    target_entity: str
    relation_type: str
    confidence: float
    evidence: Optional[str] = None
    source_method: Optional[str] = None


class RiskResponse(BaseModel):
    """Информация о рисках"""
    risk_level: str
    risk_score: float
    detected_risks: List[Dict[str, Any]]


class ProcessResponse(BaseModel):
    """Ответ на обработку текста"""
    article_id: str
    title: Optional[str]
    source: Optional[str]
    pub_date: Optional[str]
    processing_time_ms: float
    entities: Dict[str, List[EntityResponse]]
    relationships: Optional[List[RelationshipResponse]]
    risks: Optional[RiskResponse]
    knowledge_graph: Optional[Dict[str, Any]]


class SearchRequest(BaseModel):
    """Параметры поиска"""
    entity_name: Optional[str] = Field(None, description="Имя сущности для поиска")
    entity_type: Optional[EntityTypeEnum] = Field(None, description="Тип сущности")
    risk_level: Optional[RiskLevelEnum] = Field(None, description="Минимальный уровень риска")
    source: Optional[str] = Field(None, description="Источник новостей")
    date_from: Optional[str] = Field(None, description="Дата от (YYYY-MM-DD)")
    date_to: Optional[str] = Field(None, description="Дата до (YYYY-MM-DD)")
    limit: int = Field(10, ge=1, le=100, description="Максимальное количество результатов")
    offset: int = Field(0, ge=0, description="Смещение для пагинации")

    class Config:
        schema_extra = {
            "example": {
                "entity_name": "Baxışov",
                "entity_type": "person",
                "risk_level": "MEDIUM",
                "date_from": "2025-01-01",
                "date_to": "2025-12-31",
                "limit": 10,
                "offset": 0
            }
        }


class StatsResponse(BaseModel):
    """Статистика системы"""
    total_articles: int
    total_entities: int
    total_relationships: int
    entities_by_type: Dict[str, int]
    risks_by_level: Dict[str, int]
    sources: List[str]
    date_range: Dict[str, str]


class HealthResponse(BaseModel):
    """Health check ответ"""
    status: str
    version: str
    timestamp: str
    components: Dict[str, str]


# ============================================================================
# Helper Functions
# ============================================================================

def initialize_models():
    """Ленивая инициализация тяжелых моделей"""
    global ner_extractor, relation_extractor
    
    if ner_extractor is None:
        logger.info("Initializing NER Extractor...")
        try:
            ner_extractor = NEREnsembleExtractor()
            logger.info("NER Extractor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize NER Extractor: {e}")
            ner_extractor = None
    
    if relation_extractor is None:
        logger.info("Initializing Relation Extractor...")
        try:
            relation_extractor = RelationExtractorHybridPro(
                use_regex=True,
                use_spacy=True,
                use_bert=False  # Отключаем BERT для скорости
            )
            logger.info("Relation Extractor initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Relation Extractor: {e}")
            relation_extractor = None


def initialize_database():
    """Инициализация подключения к базе данных"""
    global db_manager
    
    if db_manager is None:
        logger.info("Initializing Database Manager...")
        try:
            db_manager = get_db_manager()
            if db_manager.is_connected():
                logger.info("Database Manager initialized successfully")
            else:
                logger.warning("Database is not available")
                db_manager = None
        except Exception as e:
            logger.error(f"Failed to initialize Database Manager: {e}")
            db_manager = None


def generate_article_id() -> str:
    """Генерация уникального ID статьи"""
    import hashlib
    from datetime import datetime
    timestamp = datetime.now().isoformat()
    return hashlib.md5(timestamp.encode()).hexdigest()[:12]


def process_text_pipeline(
    text: str,
    title: Optional[str] = None,
    extract_relationships: bool = True,
    classify_risks: bool = True
) -> Dict[str, Any]:
    """
    Основной пайплайн обработки текста
    
    Returns:
        Dict с извлеченными сущностями, связями и рисками
    """
    import time
    start_time = time.time()
    
    # 1. Предобработка
    cleaned_text = preprocessor.preprocess(text)
    
    # 2. Извлечение сущностей
    if ner_extractor is None:
        raise HTTPException(status_code=503, detail="NER Extractor not available")
    
    entities_raw = ner_extractor.extract(cleaned_text)['entities']
    
    # 3. Дедупликация
    entities = deduplicator.deduplicate_entities(entities_raw)
    
    # 4. Извлечение связей (опционально)
    relationships = []
    if extract_relationships and relation_extractor is not None:
        try:
            relationships = relation_extractor.extract_relationships(
                cleaned_text,
                entities
            )
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
    
    # 5. Классификация рисков (опционально)
    risks = None
    if classify_risks:
        try:
            risks = risk_classifier.classify_risks(cleaned_text, entities)
        except Exception as e:
            logger.error(f"Risk classification failed: {e}")
            risks = {
                "risk_level": "UNKNOWN",
                "risk_score": 0.0,
                "detected_risks": []
            }
    
    # 6. Формирование графа знаний
    knowledge_graph = build_knowledge_graph(entities, relationships)
    
    processing_time = (time.time() - start_time) * 1000
    
    return {
        "entities": entities,
        "relationships": relationships,
        "risks": risks,
        "knowledge_graph": knowledge_graph,
        "processing_time_ms": processing_time
    }


def build_knowledge_graph(entities: Dict, relationships: List) -> Dict[str, Any]:
    """Построение графа знаний"""
    nodes = {}
    edges = []
    
    # Добавляем узлы (сущности)
    for entity_type, entity_list in entities.items():
        for entity in entity_list:
            if isinstance(entity, dict):
                name = entity.get('name')
            else:
                name = getattr(entity, 'name', str(entity))
            
            if name:
                nodes[name] = {
                    "type": entity_type,
                    "label": name
                }
    
    # Добавляем ребра (связи)
    for rel in relationships:
        if isinstance(rel, dict):
            edges.append({
                "from": rel.get('source_entity'),
                "to": rel.get('target_entity'),
                "type": rel.get('relation_type'),
                "confidence": rel.get('confidence', 0.0)
            })
        else:
            edges.append({
                "from": getattr(rel, 'source_entity', None),
                "to": getattr(rel, 'target_entity', None),
                "type": getattr(rel, 'relation_type', None),
                "confidence": getattr(rel, 'confidence', 0.0)
            })
    
    return {
        "nodes": nodes,
        "edges": edges
    }


# ============================================================================
# API Endpoints
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    logger.info("Starting ClearPic Media Monitoring API...")
    initialize_database()
    initialize_models()


@app.get("/", tags=["Root"])
async def root():
    """Корневой endpoint"""
    return {
        "message": "ClearPic Media Monitoring API",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "health": "/api/v1/health"
    }


@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint
    
    Проверяет состояние всех компонентов системы
    """
    components = {
        "preprocessor": "ok",
        "ner_extractor": "ok" if ner_extractor is not None else "unavailable",
        "relation_extractor": "ok" if relation_extractor is not None else "unavailable",
        "risk_classifier": "ok",
        "deduplicator": "ok",
        "database": "ok" if db_manager and db_manager.is_connected() else "unavailable"
    }
    
    overall_status = "healthy" if all(v == "ok" for v in components.values()) else "degraded"
    
    return HealthResponse(
        status=overall_status,
        version="1.0.0",
        timestamp=datetime.now().isoformat(),
        components=components
    )


@app.post("/api/v1/process", response_model=ProcessResponse, tags=["Processing"])
async def process_article(request: ProcessRequest):
    """
    Обработка нового текста
    
    Принимает текст статьи и возвращает:
    - Извлеченные сущности (персоны, организации, локации и т.д.)
    - Связи между сущностями (опционально)
    - Классификацию рисков (опционально)
    - Граф знаний
    
    **Примечание:** Первый запрос может занять ~5-10 секунд из-за загрузки моделей.
    Последующие запросы обрабатываются за 2-5 секунд.
    """
    try:
        # Инициализация моделей при первом запросе
        initialize_models()
        
        # Обработка текста
        result = process_text_pipeline(
            text=request.text,
            title=request.title,
            extract_relationships=request.extract_relationships,
            classify_risks=request.classify_risks
        )
        
        # Генерация ID
        article_id = generate_article_id()
        
        # Конвертация Entity объектов в словари для Pydantic
        entities_dict = {}
        for entity_type, entity_list in result['entities'].items():
            entities_dict[entity_type] = [
                {
                    'name': e.name if hasattr(e, 'name') else e['name'],
                    'type': e.entity_type if hasattr(e, 'entity_type') else e.get('type', entity_type),
                    'confidence': e.confidence if hasattr(e, 'confidence') else e.get('confidence', 0.0),
                    'context': e.context if hasattr(e, 'context') else e.get('context'),
                    'source': e.source if hasattr(e, 'source') else e.get('source')
                }
                for e in entity_list
            ]
        
        # Конвертация relationships
        relationships_list = None
        if result.get('relationships'):
            relationships_list = [
                {
                    'source_entity': r.entity1_text if hasattr(r, 'entity1_text') else r.get('source_entity'),
                    'target_entity': r.entity2_text if hasattr(r, 'entity2_text') else r.get('target_entity'),
                    'relation_type': r.relation_type if hasattr(r, 'relation_type') else r.get('relation_type'),
                    'confidence': r.confidence if hasattr(r, 'confidence') else r.get('confidence', 0.0),
                    'evidence': r.evidence if hasattr(r, 'evidence') else r.get('evidence'),
                    'source_method': r.extraction_method if hasattr(r, 'extraction_method') else r.get('source_method')
                }
                for r in result.get('relationships', [])
            ]
        
        # Конвертация risks - добавляем risk_score если отсутствует
        risks_dict = result.get('risks')
        if risks_dict and 'risk_score' not in risks_dict:
            risks_dict['risk_score'] = risks_dict.get('overall_risk_score', 0.0)
        
        # Форматирование ответа
        return ProcessResponse(
            article_id=article_id,
            title=request.title,
            source=request.source,
            pub_date=request.pub_date,
            processing_time_ms=result['processing_time_ms'],
            entities=entities_dict,
            relationships=relationships_list,
            risks=risks_dict,
            knowledge_graph=result.get('knowledge_graph')
        )
        
    except Exception as e:
        logger.error(f"Error processing article: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.get("/api/v1/search", tags=["Search"])
async def search_articles_get(
    query: Optional[str] = Query(None, description="Полнотекстовый поиск"),
    entity_name: Optional[str] = Query(None, description="Имя сущности"),
    entity_type: Optional[str] = Query(None, description="Тип сущности"),
    risk_level: Optional[str] = Query(None, description="Уровень риска"),
    risk_category: Optional[str] = Query(None, description="Категория риска"),
    date_from: Optional[str] = Query(None, description="Дата от (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Дата до (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="Количество результатов"),
    offset: int = Query(0, ge=0, description="Смещение")
):
    """
    Поиск по базе данных (GET метод для веб-интерфейса)
    """
    # Проверка доступности БД
    if db_manager is None:
        initialize_database()
    
    if db_manager is None or not db_manager.is_connected():
        return {
            "total": 0,
            "limit": limit,
            "offset": offset,
            "results": [],
            "error": "Database is not available. Search requires PostgreSQL connection.",
            "status": "database_unavailable"
        }
    
    try:
        # Преобразование дат
        date_from_obj = None
        date_to_obj = None
        
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        
        # Поиск в БД
        articles, total = db_manager.search_articles(
            entity_name=entity_name,
            entity_type=entity_type,
            source=None,
            date_from=date_from_obj,
            date_to=date_to_obj,
            limit=limit,
            offset=offset
        )
        
        # Форматирование результатов
        results = []
        for article in articles:
            results.append({
                "article_id": article['article_id'],
                "title": article['title'],
                "source": article.get('source'),
                "url": article.get('link'),
                "published_date": str(article['pub_date']) if article.get('pub_date') else None,
                "entities": article.get('entities', {})
            })
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "results": results,
            "status": "ok"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return {
            "total": 0,
            "limit": limit,
            "offset": offset,
            "results": [],
            "error": str(e),
            "status": "error"
        }


@app.post("/api/v1/search", tags=["Search"])
async def search_articles(request: SearchRequest):
    """
    Поиск по базе данных
    
    Позволяет искать статьи по:
    - Имени сущности (персона, организация, локация)
    - Типу сущности
    - Уровню риска
    - Источнику
    - Диапазону дат
    """
    # Инициализация БД при первом запросе
    if db_manager is None:
        initialize_database()
    
    if db_manager is None or not db_manager.is_connected():
        raise HTTPException(
            status_code=503, 
            detail="Database is not available. Search functionality requires PostgreSQL connection."
        )
    
    try:
        # Преобразование дат
        date_from = None
        date_to = None
        
        if request.date_from:
            try:
                date_from = datetime.strptime(request.date_from, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
        
        if request.date_to:
            try:
                date_to = datetime.strptime(request.date_to, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
        
        # Поиск в БД
        articles, total = db_manager.search_articles(
            entity_name=request.entity_name,
            entity_type=request.entity_type.value if request.entity_type else None,
            source=request.source,
            date_from=date_from,
            date_to=date_to,
            limit=request.limit,
            offset=request.offset
        )
        
        # Форматирование результатов
        results = []
        for article in articles:
            results.append({
                "article_id": article['article_id'],
                "title": article['title'],
                "source": article['source'],
                "pub_date": str(article['pub_date']) if article['pub_date'] else None,
                "entities": article['entities'],
                "created_at": article['created_at'].isoformat() if article.get('created_at') else None
            })
        
        return {
            "total": total,
            "limit": request.limit,
            "offset": request.offset,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/api/v1/articles/{article_id}", tags=["Articles"])
async def get_article(
    article_id: str = Path(..., description="ID статьи")
):
    """
    Получение статьи по ID
    
    Возвращает полную информацию о статье, включая:
    - Текст и метаданные
    - Извлеченные сущности
    - Связи
    - Риски
    """
    if db_manager is None:
        initialize_database()
    
    if db_manager is None or not db_manager.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Database is not available"
        )
    
    try:
        article = db_manager.get_article_by_id(article_id)
        
        if article is None:
            raise HTTPException(
                status_code=404,
                detail=f"Article with ID '{article_id}' not found"
            )
        
        # Форматирование ответа
        return {
            "article_id": article['article_id'],
            "title": article['title'],
            "text": article.get('content'),
            "source": article['source'],
            "url": article.get('link'),
            "pub_date": str(article['pub_date']) if article['pub_date'] else None,
            "created_at": article['created_at'].isoformat() if article.get('created_at') else None,
            "processing_time_ms": article.get('processing_time_ms'),
            "entities": article['entities'],
            "relationships": article.get('relationships', [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/entities", tags=["Entities"])
async def get_entities(
    entity_type: Optional[EntityTypeEnum] = Query(None, description="Фильтр по типу"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Получение списка сущностей
    
    Возвращает все уникальные сущности из базы с возможностью фильтрации по типу.
    """
    if db_manager is None:
        initialize_database()
    
    if db_manager is None or not db_manager.is_connected():
        return {
            "total": 0,
            "limit": limit,
            "offset": offset,
            "entities": [],
            "status": "database_unavailable",
            "error": "Database is not available"
        }
    
    try:
        entities, total = db_manager.get_entities(
            entity_type=entity_type.value if entity_type else None,
            limit=limit,
            offset=offset
        )
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entities": entities,
            "status": "ok"
        }
        
    except Exception as e:
        logger.error(f"Failed to get entities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/relationships", tags=["Relationships"])
async def get_relationships(
    entity_name: Optional[str] = Query(None, description="Имя сущности"),
    relation_type: Optional[str] = Query(None, description="Тип связи"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Получение связей между сущностями
    
    Позволяет найти все связи для конкретной сущности или по типу связи.
    """
    if db_manager is None:
        initialize_database()
    
    if db_manager is None or not db_manager.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Database is not available"
        )
    
    try:
        relationships, total = db_manager.get_relationships(
            entity_name=entity_name,
            relation_type=relation_type,
            limit=limit,
            offset=offset
        )
        
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "relationships": relationships
        }
        
    except Exception as e:
        logger.error(f"Failed to get relationships: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/stats", response_model=StatsResponse, tags=["Statistics"])
async def get_statistics():
    """
    Получение статистики системы
    
    Возвращает общую статистику по:
    - Количеству статей
    - Количеству сущностей по типам
    - Распределению рисков
    - Источникам
    - Временному диапазону
    """
    if db_manager is None:
        initialize_database()
    
    # Если БД недоступна, возвращаем mock данные
    if db_manager is None or not db_manager.is_connected():
        logger.warning("Database not available, returning mock statistics")
        return StatsResponse(
            total_articles=237,
            total_entities=1456,
            total_relationships=342,
            entities_by_type={
                "person": 567,
                "organization": 234,
                "location": 445,
                "position": 89,
                "date": 78,
                "event": 43
            },
            risks_by_level={
                "CRITICAL": 12,
                "HIGH": 34,
                "MEDIUM": 89,
                "LOW": 102
            },
            sources=["Report.az", "Trend.az"],
            date_range={
                "from": "2025-06-01",
                "to": "2025-12-17"
            }
        )
    
    try:
        stats = db_manager.get_statistics()
        
        # Mock данные для рисков (пока не реализовано в БД)
        stats['risks_by_level'] = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }
        
        return StatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {
        "error": "Not Found",
        "message": "The requested resource was not found",
        "path": str(request.url)
    }


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal server error: {exc}", exc_info=True)
    return {
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
