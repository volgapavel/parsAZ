"""
evaluation/metrics_evaluator.py

Считает метрики качества NER на размеченном gold dataset.

Ожидаемые файлы:
 - evaluation/gold/gold_dataset.json (ручная разметка, manually_verified=true)
 - results_hybrid_final.json (предсказания пайплайна; должен содержать эти же article_id)

Запуск:
    python3 evaluation/metrics_evaluator.py

Вывод:
 - таблица precision/recall/F1
 - evaluation/reports/metrics_report.json
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


class NERMetricsEvaluator:
    def __init__(self) -> None:
        self.counts: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
        self.errors: List[Dict[str, Any]] = []

    @staticmethod
    def normalize(text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def extract_names(self, entities: List[Any]) -> Set[str]:
        names: Set[str] = set()
        for e in entities or []:
            if isinstance(e, str):
                raw = e
            elif isinstance(e, dict):
                raw = e.get("name") or e.get("text") or ""
            elif hasattr(e, "name"):
                raw = getattr(e, "name")
            else:
                raw = str(e)

            norm = self.normalize(str(raw))
            if norm and len(norm) > 1:
                names.add(norm)
        return names

    @staticmethod
    def _surname(word: str) -> str:
        parts = word.split()
        return parts[-1] if parts else ""

    def match_sets(self, pred: Set[str], gold: Set[str]) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Простое «fuzzy» сопоставление:
        - точное совпадение
        - включение (одна строка содержится в другой)
        - совпадение по фамилии (последнее слово), если фамилия достаточно длинная
        """
        tp: Set[str] = set()
        matched_gold: Set[str] = set()

        for p in pred:
            for g in gold:
                if g in matched_gold:
                    continue
                if p == g or (p and g and (p in g or g in p)):
                    tp.add(p)
                    matched_gold.add(g)
                    break
                sp, sg = self._surname(p), self._surname(g)
                if sp and sg and sp == sg and len(sp) >= 4:
                    tp.add(p)
                    matched_gold.add(g)
                    break

        fp = pred - tp
        fn = gold - matched_gold
        return tp, fp, fn

    def add_article(self, article_id: str, predicted: Dict[str, Any], gold: Dict[str, Any]) -> None:
        entity_types = ["persons", "organizations", "locations"]
        for et in entity_types:
            pred_set = self.extract_names(predicted.get(et, []))
            gold_set = self.extract_names(gold.get(et, []))

            tp, fp, fn = self.match_sets(pred_set, gold_set)

            key = et.rstrip("s")  # persons->person
            self.counts[key]["tp"] += len(tp)
            self.counts[key]["fp"] += len(fp)
            self.counts[key]["fn"] += len(fn)

            self.counts["overall"]["tp"] += len(tp)
            self.counts["overall"]["fp"] += len(fp)
            self.counts["overall"]["fn"] += len(fn)

            if fp or fn:
                self.errors.append(
                    {
                        "article_id": article_id,
                        "entity_type": et,
                        "false_positives": sorted(fp),
                        "false_negatives": sorted(fn),
                    }
                )

    def metrics(self) -> Dict[str, Dict[str, float]]:
        out: Dict[str, Dict[str, float]] = {}
        for k, c in self.counts.items():
            tp, fp, fn = c["tp"], c["fp"], c["fn"]
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
            out[k] = {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "support": tp + fn,
            }
        return out


def load_gold(path: Path) -> List[Dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_predictions(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Индексируем результаты пайплайна по article_id.
    Поддерживаем формат текущего results_hybrid_final.json (list of dict).
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    indexed: Dict[str, Dict[str, Any]] = {}
    for item in data:
        aid = str(item.get("article_id") or item.get("id") or "")
        if not aid:
            continue
        indexed[aid] = item.get("entities", {}) or {}
    return indexed


def print_table(m: Dict[str, Dict[str, float]]) -> None:
    def row(name: str) -> str:
        x = m.get(name, {})
        return f"{name:<15} {x.get('precision',0):>11.1%} {x.get('recall',0):>11.1%} {x.get('f1',0):>11.1%} {int(x.get('support',0)):>10}"

    print("\n" + "=" * 70)
    print(" NER METRICS REPORT")
    print("=" * 70)
    print(f"{'Entity Type':<15} {'Precision':>12} {'Recall':>12} {'F1':>12} {'Support':>10}")
    print("-" * 70)
    print(row("person"))
    print(row("organization"))
    print(row("location"))
    print("-" * 70)
    print(row("overall"))
    print("=" * 70)


def main() -> None:
    root = project_root()
    gold_path = root / "evaluation" / "gold" / "gold_dataset.json"
    # По умолчанию считаем метрики по предсказаниям, полученным на gold-статьях
    pred_path = root / "evaluation" / "reports" / "predictions_on_gold.json"
    report_path = root / "evaluation" / "reports" / "metrics_report.json"

    if not gold_path.exists():
        print(" Не найден gold dataset:", gold_path)
        print("   Сначала выполните: python3 evaluation/create_gold_dataset.py")
        return

    if not pred_path.exists():
        print(" Не найден файл предсказаний:", pred_path)
        print("   Сначала получите results_hybrid_final.json (пайплайн).")
        return

    gold = load_gold(gold_path)
    verified = [a for a in gold if a.get("manually_verified") is True]
    if not verified:
        print(" В gold dataset нет размеченных статей (manually_verified=true).")
        print("   Откройте evaluation/gold/gold_dataset.json и заполните gold_entities.")
        return

    preds = load_predictions(pred_path)

    ev = NERMetricsEvaluator()
    evaluated = 0
    missing = 0

    for a in verified:
        aid = str(a.get("article_id", ""))
        if not aid or aid not in preds:
            missing += 1
            continue
        ev.add_article(aid, preds[aid], a.get("gold_entities", {}) or {})
        evaluated += 1

    m = ev.metrics()
    print_table(m)

    report = {
        "evaluated_articles": evaluated,
        "missing_in_predictions": missing,
        "metrics": m,
        "errors_sample": ev.errors[:50],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n Отчёт сохранён: {report_path}")


if __name__ == "__main__":
    main()


