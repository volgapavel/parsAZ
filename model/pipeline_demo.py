# file: pipeline_demo.py
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from config import PipelineConfig
from data_loader import DataLoader
from ner_module import NERModule
from person_graph_builder import build_person_index
from nli_relation_labeler import NLIRelationLabeler
from risk_classifier import RiskClassifier
from text_utils import normalize_text, split_sentences, contains_entity, normalize_key


def _collect_persons_in_article(ents: List[Dict[str, Any]], min_len: int) -> List[Tuple[str, str]]:
    """
    returns [(person_key, display)]
    """
    out: Dict[str, str] = {}
    for e in ents:
        if (e.get("type") or "").lower() != "person":
            continue
        name = (e.get("name") or "").strip()
        if len(normalize_text(name)) < min_len:
            continue
        out[normalize_key(name)] = name
    return list(out.items())


def run(
    csv_path: str = "sample.csv",
    out_path: str = "person_index.json",
    cfg: PipelineConfig | None = None,
) -> Dict[str, Any]:
    cfg = cfg or PipelineConfig()

    loader = DataLoader()
    articles = loader.load(csv_path, limit=cfg.max_articles)

    ner = NERModule(model_name=cfg.ner_model, device=cfg.device, max_chunk_chars=cfg.ner_max_chunk_chars)
    labeler = NLIRelationLabeler(cfg.nli_model, device=cfg.device, labels=cfg.relation_labels) if cfg.use_nli else None
    risk = RiskClassifier() if cfg.use_risk else None

    entities_by_article: List[List[Dict[str, Any]]] = []

    person_risk_agg: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "by_type": defaultdict(lambda: {"hits": 0, "score": 0.0, "support_articles_set": set(), "evidence": []}),
            "overall_scores": [],
        }
    )

    for a in articles:
        text = a.get("content", "") or ""
        ents = ner.extract(text)

        ents = [
            e
            for e in ents
            if e["type"] in ("person", "organization", "location")
            and len(normalize_text(e["name"])) >= cfg.min_entity_len
        ]
        entities_by_article.append(ents)

        if risk:
            persons = _collect_persons_in_article(ents, min_len=cfg.min_entity_len)
            if persons:
                sents = split_sentences(text, max_len=500)
                aid = a.get("id")

                for pk, pdisp in persons:
                    for sent in sents:
                        if not contains_entity(sent, pdisp):
                            continue

                        r = risk.classify_sentence(sent)
                        if not r["detected_risks"]:
                            continue

                        person_risk_agg[pk]["overall_scores"].append(float(r["overall_risk_score"] or 0.0))

                        for dr in r["detected_risks"]:
                            rt = dr["type"]
                            conf = float(dr["confidence"] or 0.0)
                            if conf < cfg.risk_min_score_to_store:
                                continue

                            bucket = person_risk_agg[pk]["by_type"][rt]
                            bucket["hits"] += 1
                            bucket["score"] = max(bucket["score"], conf)

                            if aid is not None:
                                bucket["support_articles_set"].add(aid)

                            if len(bucket["evidence"]) < cfg.risk_max_evidence_per_type:
                                bucket["evidence"].append(
                                    {
                                        "sentence": sent,
                                        "article_id": aid,
                                        "title": a.get("title"),
                                        "link": a.get("link"),
                                    }
                                )

    index = build_person_index(articles, entities_by_article, cfg)

    if labeler:
        for _, pdata in index["persons"].items():
            head = pdata["display"]
            for _, ndata in pdata["neighbors"].items():
                evs = ndata.get("evidence") or []
                if not evs:
                    continue

                sent = evs[0].get("sentence") or ""
                tail = ndata.get("display") or ""
                tail_type = (ndata.get("type") or "unknown")

                rel = labeler.label(
                    sentence=sent,
                    head=head,
                    tail=tail,
                    head_type="person",
                    tail_type=tail_type,
                )
                if rel and float(rel.get("score") or 0.0) >= cfg.nli_threshold:
                    ndata["nli_relation"] = rel

    if risk:
        for pk, pdata in index["persons"].items():
            pdata["risks"] = {"overall_risk_score": 0.0, "risk_level": "LOW", "by_type": {}}

            agg = person_risk_agg.get(pk)
            if not agg:
                continue

            overall = 0.0
            if agg["overall_scores"]:
                overall = sum(agg["overall_scores"]) / len(agg["overall_scores"])

            by_type_out: Dict[str, Any] = {}
            for rt, b in agg["by_type"].items():
                by_type_out[rt] = {
                    "hits": int(b["hits"]),
                    "score": float(b["score"]),
                    "support_articles": len(b["support_articles_set"]),
                    "evidence": b["evidence"],
                }

            if overall >= 0.75:
                level = "CRITICAL"
            elif overall >= 0.50:
                level = "HIGH"
            elif overall >= 0.25:
                level = "MEDIUM"
            else:
                level = "LOW"

            pdata["risks"] = {
                "overall_risk_score": float(overall),
                "risk_level": level,
                "by_type": by_type_out,
            }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Saved: {out_path}")
    print("Persons:", len(index["persons"]))
    return index


if __name__ == "__main__":
    run()
