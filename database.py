"""
database.py - Модуль для работы с PostgreSQL

Функции:
- Подключение к базе данных
- Сохранение обработанных статей
- Поиск по различным критериям
- Получение статистики
"""

import os
import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import SimpleConnectionPool

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Менеджер для работы с PostgreSQL"""
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        database: str = None,
        user: str = None,
        password: str = None,
        min_connections: int = 1,
        max_connections: int = 10
    ):
        """
        Инициализация подключения к БД
        
        Args:
            host: Хост базы данных (default: localhost)
            port: Порт (default: 5432)
            database: Имя базы данных (default: newsdb)
            user: Пользователь (default: admin)
            password: Пароль
            min_connections: Минимум соединений в пуле
            max_connections: Максимум соединений в пуле
        """
        self.host = host or os.getenv('DB_HOST', 'localhost')
        self.port = port or int(os.getenv('DB_PORT', '5432'))
        self.database = database or os.getenv('DB_NAME', 'newsdb')
        self.user = user or os.getenv('DB_USER', 'admin')
        self.password = password or os.getenv('DB_PASSWORD', 'secret')
        
        self.connection_pool = None
        self.min_connections = min_connections
        self.max_connections = max_connections
        
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Инициализация пула соединений"""
        try:
            self.connection_pool = SimpleConnectionPool(
                self.min_connections,
                self.max_connections,
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            logger.info(f"Database connection pool initialized: {self.database}@{self.host}")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            self.connection_pool = None
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для получения соединения из пула"""
        if self.connection_pool is None:
            raise Exception("Database connection pool not initialized")
        
        conn = self.connection_pool.getconn()
        try:
            yield conn
        finally:
            self.connection_pool.putconn(conn)
    
    def is_connected(self) -> bool:
        """Проверка доступности базы данных"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    # ========================================================================
    # Сохранение данных
    # ========================================================================
    
    def save_article(
        self,
        article_id: str,
        title: str,
        link: Optional[str],
        content: str,
        pub_date: Optional[date],
        source: Optional[str],
        processing_time_ms: float
    ) -> int:
        """
        Сохранение статьи в БД
        
        Returns:
            ID записи в таблице articles
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO articles 
                    (article_id, title, link, content, pub_date, source, processing_time_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (article_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        link = EXCLUDED.link,
                        content = EXCLUDED.content,
                        pub_date = EXCLUDED.pub_date,
                        source = EXCLUDED.source,
                        processing_time_ms = EXCLUDED.processing_time_ms
                    RETURNING id
                """, (article_id, title, link, content, pub_date, source, processing_time_ms))
                
                result = cur.fetchone()
                conn.commit()
                return result[0]
    
    def save_entity(
        self,
        name: str,
        entity_type: str,
        confidence: float,
        source_method: str,
        context: Optional[str] = None
    ) -> int:
        """
        Сохранение сущности в БД
        
        Returns:
            ID записи в таблице entities
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO entities 
                    (name, entity_type, confidence, source_method, context)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (name, entity_type) DO UPDATE SET
                        confidence = EXCLUDED.confidence,
                        source_method = EXCLUDED.source_method,
                        context = EXCLUDED.context
                    RETURNING id
                """, (name, entity_type, confidence, source_method, context))
                
                result = cur.fetchone()
                conn.commit()
                return result[0]
    
    def save_entity_mention(
        self,
        article_id: int,
        entity_id: int,
        mention_position: Optional[int] = None
    ):
        """Сохранение упоминания сущности в статье"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO entity_mentions (article_id, entity_id, mention_position)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (article_id, entity_id, mention_position))
                conn.commit()
    
    def save_relationship(
        self,
        article_id: int,
        source_entity_id: int,
        target_entity_id: int,
        relation_type: str,
        confidence: float,
        evidence: Optional[str] = None
    ):
        """Сохранение связи между сущностями"""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO relationships 
                    (article_id, source_entity_id, target_entity_id, relation_type, confidence, evidence)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (article_id, source_entity_id, target_entity_id, relation_type, confidence, evidence))
                conn.commit()
    
    # ========================================================================
    # Поиск и получение данных
    # ========================================================================
    
    def search_articles(
        self,
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        source: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 10,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """
        Поиск статей по различным критериям
        
        Returns:
            Tuple[List[Dict], int]: (список статей, общее количество)
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Построение WHERE условий
                where_clauses = []
                params = []
                
                if entity_name:
                    where_clauses.append("""
                        a.id IN (
                            SELECT DISTINCT em.article_id 
                            FROM entity_mentions em
                            JOIN entities e ON em.entity_id = e.id
                            WHERE LOWER(e.name) LIKE LOWER(%s)
                        )
                    """)
                    params.append(f"%{entity_name}%")
                
                if entity_type:
                    where_clauses.append("""
                        a.id IN (
                            SELECT DISTINCT em.article_id 
                            FROM entity_mentions em
                            JOIN entities e ON em.entity_id = e.id
                            WHERE e.entity_type = %s
                        )
                    """)
                    params.append(entity_type)
                
                if source:
                    where_clauses.append("a.source = %s")
                    params.append(source)
                
                if date_from:
                    where_clauses.append("a.pub_date >= %s")
                    params.append(date_from)
                
                if date_to:
                    where_clauses.append("a.pub_date <= %s")
                    params.append(date_to)
                
                where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # Подсчет общего количества
                count_query = f"SELECT COUNT(*) FROM articles a WHERE {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()['count']
                
                # Получение статей с пагинацией
                query = f"""
                    SELECT 
                        a.id,
                        a.article_id,
                        a.title,
                        a.link,
                        a.pub_date,
                        a.source,
                        a.created_at,
                        a.processing_time_ms
                    FROM articles a
                    WHERE {where_clause}
                    ORDER BY a.pub_date DESC, a.created_at DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])
                
                cur.execute(query, params)
                articles = cur.fetchall()
                
                # Получение сущностей для каждой статьи
                for article in articles:
                    article['entities'] = self._get_article_entities(article['id'])
                
                return [dict(a) for a in articles], total
    
    def _get_article_entities(self, article_id: int) -> Dict[str, List[Dict]]:
        """Получение всех сущностей для статьи"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e.name,
                        e.entity_type,
                        e.confidence,
                        e.source_method
                    FROM entities e
                    JOIN entity_mentions em ON e.id = em.entity_id
                    WHERE em.article_id = %s
                    ORDER BY e.entity_type, e.name
                """, (article_id,))
                
                entities = cur.fetchall()
                
                # Группировка по типам
                result = {
                    'persons': [],
                    'organizations': [],
                    'locations': [],
                    'positions': [],
                    'dates': [],
                    'events': []
                }
                
                type_mapping = {
                    'person': 'persons',
                    'organization': 'organizations',
                    'location': 'locations',
                    'position': 'positions',
                    'date': 'dates',
                    'event': 'events'
                }
                
                for entity in entities:
                    entity_dict = dict(entity)
                    entity_type = entity_dict.pop('entity_type')
                    key = type_mapping.get(entity_type, 'persons')
                    result[key].append(entity_dict)
                
                return result
    
    def get_article_by_id(self, article_id: str) -> Optional[Dict]:
        """Получение статьи по article_id"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        id,
                        article_id,
                        title,
                        link,
                        content,
                        pub_date,
                        source,
                        created_at,
                        processing_time_ms
                    FROM articles
                    WHERE article_id = %s
                """, (article_id,))
                
                article = cur.fetchone()
                if not article:
                    return None
                
                article = dict(article)
                article['entities'] = self._get_article_entities(article['id'])
                article['relationships'] = self._get_article_relationships(article['id'])
                
                return article
    
    def _get_article_relationships(self, article_id: int) -> List[Dict]:
        """Получение связей для статьи"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        e1.name as source_entity,
                        e2.name as target_entity,
                        r.relation_type,
                        r.confidence,
                        r.evidence
                    FROM relationships r
                    JOIN entities e1 ON r.source_entity_id = e1.id
                    JOIN entities e2 ON r.target_entity_id = e2.id
                    WHERE r.article_id = %s
                """, (article_id,))
                
                return [dict(r) for r in cur.fetchall()]
    
    def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """Получение списка сущностей"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                where_clause = "entity_type = %s" if entity_type else "TRUE"
                params = [entity_type] if entity_type else []
                
                # Подсчет
                count_query = f"SELECT COUNT(*) FROM entities WHERE {where_clause}"
                cur.execute(count_query, params)
                total = cur.fetchone()['count']
                
                # Получение сущностей
                query = f"""
                    SELECT 
                        e.id as entity_id,
                        e.name,
                        e.entity_type as type,
                        COUNT(DISTINCT em.article_id) as mention_count,
                        MIN(a.pub_date) as first_seen,
                        MAX(a.pub_date) as last_seen
                    FROM entities e
                    LEFT JOIN entity_mentions em ON e.id = em.entity_id
                    LEFT JOIN articles a ON em.article_id = a.id
                    WHERE {where_clause}
                    GROUP BY e.id, e.name, e.entity_type
                    ORDER BY mention_count DESC, e.name
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])
                
                cur.execute(query, params)
                entities = [dict(e) for e in cur.fetchall()]
                
                return entities, total
    
    def get_relationships(
        self,
        entity_name: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """Получение связей между сущностями"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                where_clauses = []
                params = []
                
                if entity_name:
                    where_clauses.append("""
                        (LOWER(e1.name) LIKE LOWER(%s) OR LOWER(e2.name) LIKE LOWER(%s))
                    """)
                    params.extend([f"%{entity_name}%", f"%{entity_name}%"])
                
                if relation_type:
                    where_clauses.append("r.relation_type = %s")
                    params.append(relation_type)
                
                where_clause = " AND ".join(where_clauses) if where_clauses else "TRUE"
                
                # Подсчет
                count_query = f"""
                    SELECT COUNT(DISTINCT r.id)
                    FROM relationships r
                    JOIN entities e1 ON r.source_entity_id = e1.id
                    JOIN entities e2 ON r.target_entity_id = e2.id
                    WHERE {where_clause}
                """
                cur.execute(count_query, params)
                total = cur.fetchone()['count']
                
                # Получение связей
                query = f"""
                    SELECT 
                        r.id as relationship_id,
                        e1.name as source_entity,
                        e2.name as target_entity,
                        r.relation_type,
                        AVG(r.confidence) as confidence,
                        COUNT(DISTINCT r.article_id) as article_count,
                        STRING_AGG(DISTINCT r.evidence, ' | ') as evidence_sample
                    FROM relationships r
                    JOIN entities e1 ON r.source_entity_id = e1.id
                    JOIN entities e2 ON r.target_entity_id = e2.id
                    WHERE {where_clause}
                    GROUP BY r.id, e1.name, e2.name, r.relation_type
                    ORDER BY article_count DESC
                    LIMIT %s OFFSET %s
                """
                params.extend([limit, offset])
                
                cur.execute(query, params)
                relationships = [dict(r) for r in cur.fetchall()]
                
                return relationships, total
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики системы"""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                stats = {}
                
                # Общее количество статей
                cur.execute("SELECT COUNT(*) as count FROM articles")
                stats['total_articles'] = cur.fetchone()['count']
                
                # Общее количество сущностей
                cur.execute("SELECT COUNT(*) as count FROM entities")
                stats['total_entities'] = cur.fetchone()['count']
                
                # Общее количество связей
                cur.execute("SELECT COUNT(*) as count FROM relationships")
                stats['total_relationships'] = cur.fetchone()['count']
                
                # Сущности по типам
                cur.execute("""
                    SELECT entity_type, COUNT(*) as count
                    FROM entities
                    GROUP BY entity_type
                """)
                stats['entities_by_type'] = {
                    row['entity_type']: row['count'] 
                    for row in cur.fetchall()
                }
                
                # Источники
                cur.execute("""
                    SELECT DISTINCT source
                    FROM articles
                    WHERE source IS NOT NULL
                    ORDER BY source
                """)
                stats['sources'] = [row['source'] for row in cur.fetchall()]
                
                # Диапазон дат
                cur.execute("""
                    SELECT 
                        MIN(pub_date) as date_from,
                        MAX(pub_date) as date_to
                    FROM articles
                    WHERE pub_date IS NOT NULL
                """)
                date_range = cur.fetchone()
                stats['date_range'] = {
                    'from': str(date_range['date_from']) if date_range['date_from'] else None,
                    'to': str(date_range['date_to']) if date_range['date_to'] else None
                }
                
                return stats
    
    def close(self):
        """Закрытие пула соединений"""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")


# Singleton instance
_db_manager = None


def get_db_manager() -> DatabaseManager:
    """Получение singleton instance DatabaseManager"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
