"""
evaluation/run_pipeline_on_gold.py

Генерирует предсказания пайплайна для статей из gold-датасета
и сохраняет их в evaluation/reports/predictions_on_gold.json.

Зачем:
 - чтобы считать метрики на одинаковом наборе (gold vs predictions)

Запуск:
    . .venv/bin/activate
    python evaluation/run_pipeline_on_gold.py

По умолчанию читает:
 - evaluation/gold/gold_dataset.json
Пишет:
 - evaluation/reports/predictions_on_gold.json

Важно:
 - Для реальных предсказаний должны быть установлены зависимости NER:
   torch, transformers (и опционально spacy)
 - В проекте есть два варианта NER:
   1) legacy: entity_extractor_ner_ensemble.NEREnsembleExtractor (выдаёт dict entities)
   2) new: model/ner_module.NERModule (выдаёт list[dict] с полями name/type/...)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def to_serializable(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "__dict__") and not isinstance(obj, dict):
        return obj.__dict__
    if isinstance(obj, list):
        return [to_serializable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    return obj


def safe_import(module_name: str, class_name: str):
    try:
        module = __import__(module_name)
        return getattr(module, class_name)()
    except Exception as e:
        print(f"⚠️ Не удалось инициализировать {module_name}.{class_name}: {e}")
        return None


def load_gold_articles(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("gold_dataset.json должен быть списком объектов")
    return data


def ensure_dirs(root: Path) -> None:
    (root / "evaluation" / "reports").mkdir(parents=True, exist_ok=True)


def build_knowledge_graph(entities: Dict[str, Any], relations: List[Any]) -> Dict[str, Any]:
    kg = {"nodes": [], "edges": []}

    for ent in entities.get("all", []) or []:
        if isinstance(ent, dict):
            name = ent.get("name", "")
            etype = ent.get("type") or ent.get("entity_type") or "UNKNOWN"
        else:
            name = getattr(ent, "name", str(ent))
            etype = getattr(ent, "entity_type", getattr(ent, "type", "UNKNOWN"))

        if name:
            kg["nodes"].append({"id": name, "type": etype, "name": name})

    for r in relations or []:
        if hasattr(r, "to_dict"):
            kg["edges"].append(r.to_dict())
        elif isinstance(r, dict):
            kg["edges"].append(r)

    return kg


def normalize_model_entities_to_legacy(entities_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    model/ner_module.py возвращает плоский список:
      [{name,type,confidence,start,end}, ...]
    Приводим к формату evaluation/metrics_evaluator.py:
      {persons:[], organizations:[], locations:[], all:[...]}
    """
    persons = []
    orgs = []
    locs = []
    all_ = []
    for e in entities_list or []:
        if not isinstance(e, dict):
            continue
        et = (e.get("type") or "").lower()
        name = e.get("name")
        if not name:
            continue
        all_.append(e)
        if et == "person":
            persons.append(e)
        elif et == "organization":
            orgs.append(e)
        elif et == "location":
            locs.append(e)
    return {"persons": persons, "organizations": orgs, "locations": locs, "all": all_}


def check_dependencies() -> bool:
    """
    Мягкая проверка наличия torch/transformers.
    Без них NEREnsembleExtractor не поднимется.
    """
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


def main() -> int:
    root = project_root()
    # Чтобы импорты вида `import text_preprocessor` работали при запуске
    # `python evaluation/run_pipeline_on_gold.py`
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    # У некоторых сетей/провайдеров загрузка через Xet может «висеть» на 0%.
    # Отключаем Xet по умолчанию, чтобы форсировать обычную HTTP-загрузку.
    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    ensure_dirs(root)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--gold",
        default=str(root / "evaluation" / "gold" / "gold_dataset.json"),
        help="Путь к gold_dataset.json",
    )
    parser.add_argument(
        "--out",
        default=str(root / "evaluation" / "reports" / "predictions_on_gold.json"),
        help="Куда сохранить предсказания",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Ограничить число статей (0 = все)",
    )
    parser.add_argument(
        "--engine",
        choices=["ensemble", "model"],
        default="ensemble",
        help="Какой NER-пайплайн использовать: ensemble (старый) или model (NERModule из model/).",
    )
    parser.add_argument(
        "--model-ner-name",
        default="Davlan/xlm-roberta-large-ner-hrl",
        help="HF model name для engine=model (model/NERModule).",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Устройство для engine=model (cpu/cuda). Для ensemble определяется внутри модели.",
    )
    parser.add_argument(
        "--extract-relationships",
        action="store_true",
        help="Извлекать отношения (тяжёлая операция; по умолчанию выключено, т.к. для NER-метрик не нужно).",
    )
    parser.add_argument(
        "--disable-davlan",
        action="store_true",
        help="Не использовать модель Davlan (обход проблем скачивания через cas-bridge.xethub.hf.co)",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Не скачивать модели из интернета (только из кеша).",
    )
    args = parser.parse_args()

    gold_path = Path(args.gold)
    out_path = Path(args.out)
    if not gold_path.is_absolute():
        gold_path = root / gold_path
    if not out_path.is_absolute():
        out_path = root / out_path

    if not gold_path.exists():
        print(f"❌ Не найден gold dataset: {gold_path}")
        print("   Сначала запустите: python evaluation/create_gold_dataset.py")
        return 2

    # Инициализация модулей проекта
    text_preprocessor = safe_import("text_preprocessor", "TextPreprocessor")
    entity_deduplicator = safe_import("entity_deduplicator", "EntityDeduplicator")
    relation_extractor = safe_import("relationship_extractor_hybrid_pro", "RelationExtractorHybridPro") if args.extract_relationships else None

    ner_extractor = None
    model_ner = None
    if args.engine == "ensemble":
        try:
            from entity_extractor_ner_ensemble import NEREnsembleExtractor
            ner_extractor = NEREnsembleExtractor(
                use_davlan=not args.disable_davlan,
                use_localdoc=True,
                local_files_only=args.local_files_only,
            )
        except Exception as e:
            print(f"⚠️ Не удалось инициализировать NEREnsembleExtractor: {e}")
    else:
        try:
            # model/ner_module.py использует relative imports внутри model/, поэтому добавим model/ в sys.path
            model_dir = root / "model"
            if str(model_dir) not in sys.path:
                sys.path.insert(0, str(model_dir))
            from ner_module import NERModule  # type: ignore
            model_ner = NERModule(
                model_name=args.model_ner_name,
                device=args.device,
                local_files_only=args.local_files_only,
                use_fast_tokenizer=False,
            )
        except Exception as e:
            print(f"⚠️ Не удалось инициализировать model.NERModule: {e}")

    if ner_extractor is None and model_ner is None:
        print("\n❌ NER модуль не инициализировался.")
        if not check_dependencies():
            print("Похоже, в venv не установлены зависимости NER.")
            print("Установите минимум:")
            print("  python -m pip install torch transformers")
            print("Опционально для связей (spaCy слой):")
            print("  python -m pip install spacy && python -m spacy download en_core_web_sm")
        print("\nПосле установки повторите запуск скрипта.")
        return 3

    gold_articles = load_gold_articles(gold_path)
    if args.max and args.max > 0:
        gold_articles = gold_articles[: args.max]

    results: List[Dict[str, Any]] = []

    print("=" * 70)
    print(f"🚀 Генерация предсказаний на gold-статьях: {len(gold_articles)}")
    print("=" * 70)

    for idx, a in enumerate(gold_articles, 1):
        article_id = str(a.get("article_id", ""))
        title = str(a.get("title", ""))[:80]
        text = a.get("content", "") or ""

        cleaned_text = text
        if text_preprocessor:
            try:
                cleaned_text = text_preprocessor.preprocess(text) or text
            except Exception:
                cleaned_text = text

        # NER
        if args.engine == "ensemble":
            ner_out = ner_extractor.extract(cleaned_text) or {}
            entities = ner_out.get("entities", {}) if isinstance(ner_out, dict) else {}
        else:
            ents_list = model_ner.extract(cleaned_text) if model_ner else []
            entities = normalize_model_entities_to_legacy(ents_list)

        # Дедупликация (ожидает ключи persons/organizations)
        if entity_deduplicator and isinstance(entities, dict):
            entities.setdefault("persons", [])
            entities.setdefault("organizations", [])
            try:
                entities = entity_deduplicator.deduplicate_entities(entities) or entities
            except Exception:
                pass

        # Связи
        relations: List[Any] = []
        if relation_extractor and isinstance(entities, dict) and entities.get("all"):
            try:
                relations = relation_extractor.extract_relationships(cleaned_text, entities) or []
            except Exception:
                relations = []

        kg = build_knowledge_graph(entities if isinstance(entities, dict) else {}, relations)

        results.append(
            {
                "article_id": article_id,
                "source": a.get("source", ""),
                "title": title,
                "entities": to_serializable(entities),
                "knowledge_graph": kg,
                "success": True,
            }
        )

        if idx % 5 == 0 or idx == len(gold_articles):
            print(f"[{idx}/{len(gold_articles)}] ✅ {article_id} {title}")

    out_path.write_text(json.dumps(to_serializable(results), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📁 Предсказания сохранены в: {out_path}")
    print("Дальше: запустите подсчёт метрик командой:")
    print("  python evaluation/metrics_evaluator.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


