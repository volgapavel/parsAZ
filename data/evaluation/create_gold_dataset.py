"""
evaluation/create_gold_dataset.py

Создаёт шаблон gold-датасета для ручной разметки:
- берёт по 10 статей из 01.csv, 02.csv, 03.csv (эвристика по длине)
- сохраняет JSON в evaluation/gold/gold_dataset.json

Запуск:
    python3 evaluation/create_gold_dataset.py
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


def project_root() -> Path:
    # evaluation/ -> корень проекта на 1 уровень выше
    return Path(__file__).resolve().parents[1]


def load_csv_articles(csv_file: Path, limit: int = 200) -> List[Dict[str, Any]]:
    """Загрузка статей из CSV (первые limit строк)."""
    df = pd.read_csv(csv_file, nrows=limit)
    articles: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        content = str(row.get("content", "") or "")
        title = str(row.get("title", "") or "")

        article = {
            "id": str(row.get("id", "")),
            "link": str(row.get("link", "") or ""),
            "pub_date": str(row.get("pub_date", "") or ""),
            "title": title,
            "content": content,
        }

        # фильтр «пустых»/слишком коротких
        if article["id"] and len(content) >= 200 and len(title) >= 5:
            articles.append(article)

    return articles


def select_diverse_articles(articles: List[Dict[str, Any]], n: int = 10) -> List[Dict[str, Any]]:
    """
    Выбор разнообразных статей: берём по длине из разных квантилей.
    Это НЕ gold-стратегия, но помогает получить разный текст.
    """
    if not articles:
        return []

    sorted_articles = sorted(articles, key=lambda x: len(x["content"]))
    m = len(sorted_articles)

    # 10 точек по шкале длины (если статей меньше - возьмём сколько есть)
    raw_positions = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    indices = [min(int(m * p), m - 1) for p in raw_positions]

    selected: List[Dict[str, Any]] = []
    seen_ids = set()
    for idx in indices[:n]:
        art = sorted_articles[idx]
        if art["id"] in seen_ids:
            continue
        selected.append(art)
        seen_ids.add(art["id"])

    # если из-за дублей/малого m не добрали - добираем случайно
    if len(selected) < min(n, m):
        pool = [a for a in sorted_articles if a["id"] not in seen_ids]
        need = min(n, m) - len(selected)
        if pool and need > 0:
            selected.extend(random.sample(pool, k=min(need, len(pool))))

    return selected[:n]


def create_gold_template(article: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Шаблон одной статьи для ручной разметки."""
    return {
        "article_id": str(article["id"]),
        "source": source,
        "link": article.get("link", ""),
        "pub_date": article.get("pub_date", ""),
        "title": article.get("title", ""),
        "content": (article.get("content", "") or "")[:4000],  # чтобы удобнее размечать
        "gold_entities": {
            "persons": [],
            "organizations": [],
            "locations": [],
            "positions": [],
            "dates": [],
        },
        "manually_verified": False,
        "annotator_notes": "",
    }


def ensure_dirs(base: Path) -> None:
    (base / "evaluation" / "gold").mkdir(parents=True, exist_ok=True)
    (base / "evaluation" / "reports").mkdir(parents=True, exist_ok=True)


def main() -> None:
    root = project_root()
    ensure_dirs(root)

    sources = {
        "report.az": root / "01.csv",
        "azerbaijan.az": root / "02.csv",
        "trend.az": root / "03.csv",
    }

    gold_dataset: List[Dict[str, Any]] = []

    print("=" * 70)
    print(" Создание шаблона gold dataset (30 статей)")
    print("=" * 70)

    for source_name, csv_path in sources.items():
        if not csv_path.exists():
            print(f" Не найден файл: {csv_path}")
            continue

        print(f"\n {source_name}: загрузка {csv_path.name} ...")
        articles = load_csv_articles(csv_path, limit=200)
        print(f"   Загружено (после фильтра): {len(articles)}")

        selected = select_diverse_articles(articles, n=10)
        print(f"   Выбрано: {len(selected)}")

        for article in selected:
            gold_dataset.append(create_gold_template(article, source_name))

    out_file = root / "evaluation" / "gold" / "gold_dataset.json"
    out_file.write_text(json.dumps(gold_dataset, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n Готово. Статей в шаблоне: {len(gold_dataset)}")
    print(f" Файл: {out_file}")
    print("\nДальше: откройте JSON, заполните gold_entities и поставьте manually_verified=true.")


if __name__ == "__main__":
    main()


