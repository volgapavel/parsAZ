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
            f"host={os.getenv('DB_HOST', 'db')} "
            f"port={os.getenv('DB_PORT', '5432')} "
            f"dbname={os.getenv('DB_NAME', 'newsdb')} "
            f"user={os.getenv('DB_USER', 'myuser')} "
            f"password={os.getenv('DB_PASS', 'mypass')}"
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
        
        stats = {}
        tables = ["report", "azerbaijan", "trend"]
        
        for table in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                count = cur.fetchone()[0]
                
                cur.execute(f"SELECT MIN(pub_date), MAX(pub_date) FROM {table}")
                min_date, max_date = cur.fetchone()
                
                stats[table] = {
                    "count": count,
                    "min_date": str(min_date) if min_date else None,
                    "max_date": str(max_date) if max_date else None,
                }
            except Exception:
                stats[table] = {"count": 0, "error": "Table not found"}
        
        total = sum(s.get("count", 0) for s in stats.values())
        
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
        
        if source and source in ["report", "azerbaijan", "trend"]:
            query = f"""
                SELECT id, title, link, pub_date, '{source}' as source
                FROM {source}
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (limit,))
        else:
            # Union from all tables
            query = """
                (SELECT id, title, link, pub_date, 'report' as source FROM report ORDER BY pub_date DESC NULLS LAST LIMIT %s)
                UNION ALL
                (SELECT id, title, link, pub_date, 'azerbaijan' as source FROM azerbaijan ORDER BY pub_date DESC NULLS LAST LIMIT %s)
                UNION ALL
                (SELECT id, title, link, pub_date, 'trend' as source FROM trend ORDER BY pub_date DESC NULLS LAST LIMIT %s)
                ORDER BY pub_date DESC NULLS LAST
                LIMIT %s
            """
            cur.execute(query, (limit, limit, limit, limit))
        
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
        
        # Build date filter
        date_filter = ""
        params = [search_pattern, search_pattern]
        
        if date_from:
            date_filter += " AND pub_date >= %s"
            params.append(date_from)
        if date_to:
            date_filter += " AND pub_date <= %s"
            params.append(date_to)
        
        params.append(limit)
        
        # Search across all tables
        query_sql = f"""
            (SELECT id, title, link, pub_date, content, 'report' as source 
             FROM report WHERE (title ILIKE %s OR content ILIKE %s) {date_filter} LIMIT %s)
            UNION ALL
            (SELECT id, title, link, pub_date, content, 'azerbaijan' as source 
             FROM azerbaijan WHERE (title ILIKE %s OR content ILIKE %s) {date_filter} LIMIT %s)
            UNION ALL
            (SELECT id, title, link, pub_date, content, 'trend' as source 
             FROM trend WHERE (title ILIKE %s OR content ILIKE %s) {date_filter} LIMIT %s)
            ORDER BY pub_date DESC NULLS LAST
            LIMIT %s
        """
        
        # Build full params list (3 tables x params + final limit)
        full_params = params * 3 + [limit]
        cur.execute(query_sql, full_params)
        
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
                "entities": [],  # Would need NER processing
                "risks": [],     # Would need risk classification
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

