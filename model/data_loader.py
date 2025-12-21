# file: data_loader.py
from __future__ import annotations

import csv
import os
from typing import Any, Dict, List, Optional


def _guess_col(row: Dict[str, Any], *candidates: str, default: str = "") -> str:
    for c in candidates:
        if c in row and row[c] not in (None, ""):
            return str(row[c])
    return default


class DataLoader:
    """
    Универсальный загрузчик CSV.
    Возвращает list[dict] со стандартными ключами:
    id, title, link, pub_date, content
    """

    def load(self, path: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        if not os.path.exists(path):
            raise FileNotFoundError(path)

        try:
            import pandas as pd  

            df = pd.read_csv(path)
            if limit is not None:
                df = df.head(int(limit))

            raw = df.to_dict(orient="records")
            rows: List[Dict[str, Any]] = []
            for i, r in enumerate(raw):
                rid = r.get("id", r.get("article_id", i))
                rows.append(
                    {
                        "id": rid,
                        "title": _guess_col(r, "title", "headline", "name", default=""),
                        "link": _guess_col(r, "link", "url", "source_url", default=""),
                        "pub_date": _guess_col(r, "pub_date", "pubdate", "date", "datetime", default=""),
                        "content": _guess_col(r, "content", "text", "body", "description", default=""),
                    }
                )
            return rows
        except Exception:
            pass

        rows2: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            for i, r in enumerate(reader):
                if limit is not None and i >= int(limit):
                    break
                rid = r.get("id", r.get("article_id", i))
                rows2.append(
                    {
                        "id": rid,
                        "title": _guess_col(r, "title", "headline", "name", default=""),
                        "link": _guess_col(r, "link", "url", "source_url", default=""),
                        "pub_date": _guess_col(r, "pub_date", "pubdate", "date", "datetime", default=""),
                        "content": _guess_col(r, "content", "text", "body", "description", default=""),
                    }
                )
        return rows2
