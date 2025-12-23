"""Statistics API router - database stats."""
import os
from typing import Any, Dict, List, Optional

import psycopg2
from fastapi import APIRouter, HTTPException

router = APIRouter()


def get_db_connection():
    """Create database connection."""
    try:
        dsn = (
            f"host={os.getenv('DB_HOST', 'localhost')} "
            f"port={os.getenv('DB_PORT', '5432')} "
            f"dbname={os.getenv('DB_NAME', 'newsdb')} "
            f"user={os.getenv('DB_USER', 'myuser')} "
            f"password={os.getenv('DB_PASSWORD', 'mypass')}"
        )
        conn = psycopg2.connect(dsn)
        conn.set_client_encoding('UTF8')
        return conn
    except Exception as e:
        return None


@router.get("/stats/database")
async def get_database_stats():
    """Get statistics from all news tables."""
    conn = get_db_connection()
    if not conn:
        return {
            "status": "database_unavailable",
            "message": "Database connection failed",
        }
    
    try:
        cur = conn.cursor()
        
        # Get overall stats
        cur.execute("SELECT COUNT(*) FROM articles")
        total = cur.fetchone()[0]
        
        cur.execute("SELECT MIN(published_date), MAX(published_date) FROM articles")
        min_date, max_date = cur.fetchone()
        
        # Get stats by source
        cur.execute("""
            SELECT source, COUNT(*) as count,
                   MIN(published_date) as min_date,
                   MAX(published_date) as max_date
            FROM articles
            GROUP BY source
        """)
        
        stats = {}
        for row in cur.fetchall():
            source, count, src_min_date, src_max_date = row
            stats[source] = {
                "count": count,
                "min_date": str(src_min_date) if src_min_date else None,
                "max_date": str(src_max_date) if src_max_date else None,
            }
        
        cur.close()
        conn.close()
        
        return {
            "status": "ok",
            "total_articles": total,
            "by_source": stats,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@router.get("/stats/recent")
async def get_recent_articles(
    limit: int = 20,
    source: Optional[str] = None,
):
    """Get recent articles from database."""
    conn = get_db_connection()
    if not conn:
        return {"status": "database_unavailable", "articles": []}
    
    try:
        cur = conn.cursor()
        
        if source:
            query = """
                SELECT id, title, link, pub_date, source
                FROM articles
                WHERE source = %s
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (source, limit))
        else:
            query = """
                SELECT id, title, link, pub_date, source
                FROM articles
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (limit,))
        
        rows = cur.fetchall()
        articles = []
        for row in rows:
            articles.append({
                "id": row[0],
                "title": row[1],
                "link": row[2],
                "pub_date": str(row[3]) if row[3] else None,
                "source": row[4],
            })
        
        cur.close()
        conn.close()
        
        return {"status": "ok", "articles": articles}
    except Exception as e:
        return {"status": "error", "message": str(e), "articles": []}


@router.get("/stats/search-articles")
async def search_articles(
    q: str,
    limit: int = 50,
    source: Optional[str] = None,
):
    """Search articles by text in title or content."""
    return await _search_articles_internal(q, limit, source)


@router.get("/search")
async def search_web(
    query: Optional[str] = None,
    entity_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    risk_category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    """
    Search endpoint for web UI.
    Searches articles by query text and/or entity name.
    """
    conn = get_db_connection()
    if not conn:
        return {"status": "database_unavailable", "results": [], "total": 0}
    
    # Use query or entity_name as search term
    search_term = query or entity_name
    if not search_term:
        return {"status": "ok", "results": [], "total": 0, "message": "No search term provided"}
    
    try:
        cur = conn.cursor()
        search_pattern = f"%{search_term}%"
        # Поиск по всем трём таблицам
        query = """
            (SELECT id, title, link, pub_date, content, 'report' as source FROM report WHERE title ILIKE %s OR content ILIKE %s)
            UNION ALL
            (SELECT id, title, link, pub_date, content, 'azerbaijan' as source FROM azerbaijan WHERE title ILIKE %s OR content ILIKE %s)
            UNION ALL
            (SELECT id, title, link, pub_date, content, 'trend' as source FROM trend WHERE title ILIKE %s OR content ILIKE %s)
            ORDER BY pub_date DESC NULLS LAST
            LIMIT %s
        """
        limit_val = limit
        cur.execute(query, (
            search_pattern, search_pattern,
            search_pattern, search_pattern,
            search_pattern, search_pattern,
            limit_val
        ))
        rows = cur.fetchall()
        results = []
        for row in rows:
            content = row[4] or ""
            snippet = content[:200] + "..." if len(content) > 200 else content
            results.append({
                "article_id": f"{row[5]}_{row[0]}",
                "title": row[1],
                "url": row[2],
                "published_date": str(row[3]) if row[3] else None,
                "text": snippet,
                "source": row[5],
                "entities": [],
                "risks": [],
            })
        cur.close()
        conn.close()
        return {"status": "ok", "total": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "error": str(e), "results": [], "total": 0}


async def _search_articles_internal(q: str, limit: int = 50, source: Optional[str] = None):
    """Internal search function."""
    conn = get_db_connection()
    if not conn:
        return {"status": "database_unavailable", "results": []}
    
    try:
        cur = conn.cursor()
        
        search_pattern = f"%{q}%"
        
        if source and source in ["report", "azerbaijan", "trend"]:
            query = f"""
                SELECT id, title, link, pub_date, content, '{source}' as source
                FROM {source}
                WHERE title ILIKE %s OR content ILIKE %s
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (search_pattern, search_pattern, limit))
        else:
            query = """
                (SELECT id, title, link, pub_date, content, 'report' as source FROM report WHERE title ILIKE %s OR content ILIKE %s LIMIT %s)
                UNION ALL
                (SELECT id, title, link, pub_date, content, 'azerbaijan' as source FROM azerbaijan WHERE title ILIKE %s OR content ILIKE %s LIMIT %s)
                UNION ALL
                (SELECT id, title, link, pub_date, content, 'trend' as source FROM trend WHERE title ILIKE %s OR content ILIKE %s LIMIT %s)
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (
                search_pattern, search_pattern, limit,
                search_pattern, search_pattern, limit,
                search_pattern, search_pattern, limit,
                limit
            ))
        
        rows = cur.fetchall()
        results = []
        for row in rows:
            content = row[4] or ""
            snippet = content[:300] + "..." if len(content) > 300 else content
            
            results.append({
                "id": row[0],
                "title": row[1],
                "link": row[2],
                "pub_date": str(row[3]) if row[3] else None,
                "snippet": snippet,
                "source": row[5],
            })
        
        cur.close()
        conn.close()
        
        return {"status": "ok", "query": q, "total": len(results), "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "results": []}

