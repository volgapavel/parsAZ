"""
evaluation/create_gold_dataset.py

Создаёт шаблон gold-датасета для ручной разметки:
- берёт по N статей из 01.csv, 02.csv, 03.csv (эвристика по длине + добор)
- сохраняет JSON в evaluation/gold/gold_dataset.json

Запуск:
    python3 evaluation/create_gold_dataset.py --per-source 50 --read-limit 5000 --append
    python3 evaluation/create_gold_dataset.py --per-source 50 --read-limit 5000 --exclude-verified --strict --out evaluation/gold/gold_dataset_50x3_unlabeled.json
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


def select_diverse_articles(articles: List[Dict[str, Any]], n: int) -> List[Dict[str, Any]]:
    """
    Выбор разнообразных статей: равномерно по длине (квантили) + случайный добор.
    Это НЕ gold-стратегия, но помогает получить разный текст.
    """
    if not articles:
        return []

    sorted_articles = sorted(articles, key=lambda x: len(x["content"]))
    m = len(sorted_articles)

    if n <= 0:
        return []

    # Индексы равномерно по отсортированному списку
    if m == 1:
        return sorted_articles[:1]
    step = (m - 1) / max(1, (n - 1))
    indices = [min(int(round(i * step)), m - 1) for i in range(n)]

    selected: List[Dict[str, Any]] = []
    seen_ids = set()
    for idx in indices:
        art = sorted_articles[idx]
        if art["id"] in seen_ids:
            continue
        selected.append(art)
        seen_ids.add(art["id"])

    # если из-за дублей/малого m не добрали — добираем случайно
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


def load_existing_gold(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def key_for(item: Dict[str, Any]) -> Tuple[str, str]:
    # Уникальность в рамках источника
    return (str(item.get("source", "")).strip(), str(item.get("article_id", "")).strip())


def main() -> None:
    root = project_root()
    ensure_dirs(root)

    parser = argparse.ArgumentParser()
    parser.add_argument("--per-source", type=int, default=10, help="Сколько статей брать на каждый источник")
    parser.add_argument("--read-limit", type=int, default=200, help="Сколько строк читать из каждого CSV (первые N строк)")
    parser.add_argument("--append", action="store_true", help="Расширять существующий gold_dataset.json (не перезатирать)")
    parser.add_argument(
        "--exclude-verified",
        action="store_true",
        help="Исключать из выборки статьи, которые уже вручную размечены (manually_verified=true) в текущем gold_dataset.json",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Требовать строго per-source статей на источник (если не хватает — ошибка).",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Путь для выходного файла (по умолчанию evaluation/gold/gold_dataset.json).",
    )
    args = parser.parse_args()

    sources = {
        "report.az": root / "01.csv",
        "azerbaijan.az": root / "02.csv",
        "trend.az": root / "03.csv",
    }

    default_out = root / "evaluation" / "gold" / "gold_dataset.json"
    out_file = Path(args.out) if args.out else default_out
    if not out_file.is_absolute():
        out_file = root / out_file

    # Текущий gold (используем как источник исключений и/или как база для append)
    current_gold: List[Dict[str, Any]] = load_existing_gold(default_out)
    verified_exclude = {
        key_for(x)
        for x in current_gold
        if isinstance(x, dict) and x.get("manually_verified") is True
    }

    existing: List[Dict[str, Any]] = load_existing_gold(out_file) if (args.append and out_file.exists()) else []
    existing_map = {key_for(x): x for x in existing if isinstance(x, dict)}

    gold_dataset: List[Dict[str, Any]] = list(existing_map.values())

    print("=" * 70)
    target_total = args.per_source * len(sources)
    mode = "append" if args.append else "overwrite"
    print(f"🔧 Создание/расширение gold dataset ({mode})")
    print(f"   per-source={args.per_source} | read-limit={args.read_limit} | target~{target_total}")
    if args.exclude_verified:
        print(f"   exclude_verified: {len(verified_exclude)} articles")
    if args.strict:
        print("   strict: enabled")
    if out_file != default_out:
        print(f"   out: {out_file.relative_to(root) if str(out_file).startswith(str(root)) else out_file}")
    print("=" * 70)

    for source_name, csv_path in sources.items():
        if not csv_path.exists():
            print(f"⚠️ Не найден файл: {csv_path}")
            continue

        print(f"\n📰 {source_name}: загрузка {csv_path.name} ...")
        articles = load_csv_articles(csv_path, limit=args.read_limit)
        print(f"   Загружено (после фильтра): {len(articles)}")

        # Исключения: уже присутствующие в выходном файле (append) + вручную размеченные (если exclude-verified)
        excluded_keys = set(existing_map.keys())
        if args.exclude_verified:
            excluded_keys |= {k for k in verified_exclude if k[0] == source_name}

        # Предварительно фильтруем, чтобы строго добрать N
        candidates = [a for a in articles if (source_name, str(a["id"])) not in excluded_keys]
        if len(candidates) < args.per_source and args.strict:
            raise SystemExit(
                f"❌ Недостаточно кандидатов для {source_name}: нужно {args.per_source}, доступно {len(candidates)}. "
                f"Увеличьте --read-limit."
            )

        selected = select_diverse_articles(candidates, n=min(args.per_source, len(candidates)))
        # На всякий случай добор случайно, если квантильный отбор не дал N из-за дублей
        if len(selected) < min(args.per_source, len(candidates)):
            seen = {str(x['id']) for x in selected}
            pool = [a for a in candidates if str(a['id']) not in seen]
            need = min(args.per_source, len(candidates)) - len(selected)
            if need > 0 and pool:
                selected.extend(random.sample(pool, k=min(need, len(pool))))

        # В strict режиме добиваем до ровно per-source
        if args.strict and len(selected) != args.per_source:
            raise SystemExit(
                f"❌ Для {source_name} получилось {len(selected)} вместо {args.per_source}. "
                f"Увеличьте --read-limit."
            )

        print(f"   Выбрано: {len(selected)} (исключено ранее/verified: {len(articles) - len(candidates)})")

        for article in selected:
            gold_dataset.append(create_gold_template(article, source_name))

    # backup (если расширяем существующий)
    if args.append and out_file.exists():
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup = out_file.with_suffix(f".bak-{ts}.json")
        backup.write_text(out_file.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"\n🧷 Бэкап старого датасета: {backup.name}")

    out_file.write_text(json.dumps(gold_dataset, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Готово. Статей в шаблоне: {len(gold_dataset)}")
    print(f"📁 Файл: {out_file}")
    print("\nДальше: откройте JSON, заполните gold_entities и поставьте manually_verified=true.")


if __name__ == "__main__":
    main()


