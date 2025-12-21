# file: person_search.py
from __future__ import annotations

import json
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from text_utils import normalize_key


@dataclass
class NeighborView:
    neighbor_key: str
    display: str
    type: str
    support_articles: int
    support_mentions: int
    score: float
    nli_label: Optional[str] = None
    nli_score: Optional[float] = None
    evidence: Optional[List[Dict[str, Any]]] = None


@dataclass
class SemanticRelation:
    relation: str 
    target_display: str
    target_type: str
    support_articles: int
    score: float
    nli_score: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class PersonIndexSearch:
    def __init__(self, index: Dict[str, Any]):
        self.index = index
        self.persons: Dict[str, Dict[str, Any]] = index.get("persons", {}) or {}

        self._display_to_keys: Dict[str, List[str]] = {}
        for pk, pdata in self.persons.items():
            disp = (pdata.get("display") or "").strip()
            if disp:
                self._display_to_keys.setdefault(normalize_key(disp), []).append(pk)

    @staticmethod
    def load(path: str) -> "PersonIndexSearch":
        with open(path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        return PersonIndexSearch(idx)

    @staticmethod
    def _sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    def find_person(self, query: str, top_k: int = 10) -> List[Tuple[str, str, float]]:
        q = normalize_key(query)
        if not q:
            return []

        if q in self._display_to_keys:
            out = [(pk, self.persons[pk].get("display", ""), 1.0) for pk in self._display_to_keys[q]]
            return out[:top_k]

        candidates = []
        for pk, pdata in self.persons.items():
            disp = (pdata.get("display") or "").strip()
            d = normalize_key(disp)
            if d and q in d:
                candidates.append((pk, disp, 0.95))
        if candidates:
            return candidates[:top_k]

        scored = []
        for pk, pdata in self.persons.items():
            disp = (pdata.get("display") or "").strip()
            d = normalize_key(disp)
            if not d:
                continue
            s = self._sim(q, d)
            if s >= 0.60:
                scored.append((pk, disp, s))
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:top_k]

    def get_neighbors(
        self,
        person_key: str,
        sort_by: str = "score",
        top_n: Optional[int] = None,
        types: Optional[List[str]] = None,
        min_support_articles: int = 1,
    ) -> List[NeighborView]:
        pdata = self.persons.get(person_key)
        if not pdata:
            return []

        neigh = pdata.get("neighbors") or {}
        out: List[NeighborView] = []

        types_l = [t.lower() for t in types] if types else None

        for nk, nd in neigh.items():
            ntype = (nd.get("type") or "unknown").lower()
            if types_l and ntype not in types_l:
                continue

            sa = int(nd.get("support_articles") or 0)
            if sa < min_support_articles:
                continue

            nli = nd.get("nli_relation") if isinstance(nd.get("nli_relation"), dict) else None

            out.append(
                NeighborView(
                    neighbor_key=nk,
                    display=nd.get("display") or nk,
                    type=ntype,
                    support_articles=sa,
                    support_mentions=int(nd.get("support_mentions") or 0),
                    score=float(nd.get("score") or 0.0),
                    nli_label=(nli.get("label") if nli else None),
                    nli_score=(float(nli.get("score")) if nli and nli.get("score") is not None else None),
                    evidence=nd.get("evidence") or [],
                )
            )

        if sort_by == "score":
            out.sort(key=lambda x: x.score, reverse=True)
        elif sort_by == "support_articles":
            out.sort(key=lambda x: x.support_articles, reverse=True)
        elif sort_by == "support_mentions":
            out.sort(key=lambda x: x.support_mentions, reverse=True)

        if top_n is not None:
            out = out[:top_n]
        return out

    # --------- stats ----------
    def stats_global(self) -> Dict[str, Any]:
        persons_total = len(self.persons)
        neighbors_total = 0
        by_type = {"person": 0, "organization": 0, "location": 0, "unknown": 0}
        nli_labels: Dict[str, int] = {}

        for _, pdata in self.persons.items():
            neigh = pdata.get("neighbors") or {}
            neighbors_total += len(neigh)
            for _, nd in neigh.items():
                t = (nd.get("type") or "unknown").lower()
                by_type[t] = by_type.get(t, 0) + 1

                nli = nd.get("nli_relation") if isinstance(nd.get("nli_relation"), dict) else None
                if nli and nli.get("label"):
                    nli_labels[nli["label"]] = nli_labels.get(nli["label"], 0) + 1

        return {
            "persons_total": persons_total,
            "neighbors_total": neighbors_total,
            "neighbors_by_type": by_type,
            "nli_labels": dict(sorted(nli_labels.items(), key=lambda x: x[1], reverse=True)),
        }

    def print_stats_global(self) -> None:
        st = self.stats_global()
        print("=" * 90)
        print("GLOBAL STATS")
        print("=" * 90)
        print("persons_total:", st["persons_total"])
        print("neighbors_total:", st["neighbors_total"])
        print("neighbors_by_type:", st["neighbors_by_type"])
        if st["nli_labels"]:
            print("nli_labels:", st["nli_labels"])

    def top_persons(self, top_k: int = 20, sort_by: str = "neighbors_total") -> List[Dict[str, Any]]:
        rows = []
        for pk, pdata in self.persons.items():
            neigh = pdata.get("neighbors") or {}
            cnt_by_type = {"person": 0, "organization": 0, "location": 0, "unknown": 0}
            for _, nd in neigh.items():
                t = (nd.get("type") or "unknown").lower()
                cnt_by_type[t] = cnt_by_type.get(t, 0) + 1

            risks = pdata.get("risks") or {}

            rows.append(
                {
                    "person_key": pk,
                    "display": pdata.get("display") or pk,
                    "neighbors_total": len(neigh),
                    "neighbors_person": cnt_by_type.get("person", 0),
                    "neighbors_org": cnt_by_type.get("organization", 0),
                    "neighbors_loc": cnt_by_type.get("location", 0),
                    "risk_level": risks.get("risk_level") or "LOW",
                    "risk_score": float(risks.get("overall_risk_score", 0.0) or 0.0),
                }
            )

        rows.sort(key=lambda r: r.get(sort_by, 0), reverse=True)
        return rows[:top_k]

    def print_top_persons(self, top_k: int = 20) -> None:
        top = self.top_persons(top_k=top_k)
        print("=" * 90)
        print(f"TOP PERSONS BY NEIGHBORS (top_k={top_k})")
        print("=" * 90)
        for i, r in enumerate(top, 1):
            print(
                f"{i:02d}. {r['display']} | total={r['neighbors_total']} "
                f"(PER={r['neighbors_person']}, ORG={r['neighbors_org']}, LOC={r['neighbors_loc']}) "
                f"| risk={r['risk_level']} ({r['risk_score']:.2f})"
            )

    # --------- semantic relations ----------
    def get_semantic_relations(self, person_key: str, min_nli: float = 0.82, top_n: int = 30) -> List[SemanticRelation]:
        pdata = self.persons.get(person_key)
        if not pdata:
            return []

        neigh = self.get_neighbors(person_key, top_n=None, min_support_articles=1)

        rels: List[SemanticRelation] = []
        for n in neigh:
            rel = "related_to"
            if n.nli_label and (n.nli_score or 0.0) >= min_nli:
                if n.nli_label == "met with" and n.type == "person":
                    rel = "met_with"
                elif n.nli_label == "works for" and n.type == "organization":
                    rel = "works_for"
                elif n.nli_label == "was appointed to" and n.type == "organization":
                    rel = "appointed_to"

            ev0 = (n.evidence[0] if n.evidence else None)
            rels.append(
                SemanticRelation(
                    relation=rel,
                    target_display=n.display,
                    target_type=n.type,
                    support_articles=n.support_articles,
                    score=n.score,
                    nli_score=n.nli_score,
                    evidence=ev0,
                )
            )

        rels.sort(key=lambda x: (x.relation != "related_to", x.nli_score or 0.0, x.score), reverse=True)
        return rels[:top_n]

    def print_semantic_relations(self, query: str, min_nli: float = 0.82, top_n: int = 30) -> None:
        cands = self.find_person(query, top_k=5)
        if not cands:
            print("No person found for:", query)
            return

        pk, disp, match = cands[0]
        rels = self.get_semantic_relations(pk, min_nli=min_nli, top_n=top_n)

        print("=" * 90)
        print(f"RELATIONS: {disp} (key={pk}, match={match:.2f})")
        print("=" * 90)

        if not rels:
            print("No relations.")
            return

        for i, r in enumerate(rels, 1):
            nli_part = f" | nli={r.nli_score:.2f}" if r.nli_score is not None else ""
            print(
                f"{i:02d}. {r.relation} -> {r.target_display} [{r.target_type}] "
                f"| support={r.support_articles} | score={r.score:.2f}{nli_part}"
            )
            if r.evidence and r.evidence.get("sentence"):
                print(f" - evidence: {(r.evidence.get('sentence') or '')[:220]}")
            if r.evidence and r.evidence.get("link"):
                print(f" - link: {r.evidence['link']}")

    def print_person_card(
        self,
        query: str,
        top_n_each_type: int = 10,
        min_support_articles: int = 2,
        show_evidence: bool = True,
        min_nli: float = 0.82,
        show_risk_types: bool = True,
        top_risk_types: int = 10,
        show_risk_evidence: bool = True,
    ) -> None:
        cands = self.find_person(query, top_k=5)
        if not cands:
            print("No person found for:", query)
            return

        pk, disp, match = cands[0]
        pdata = self.persons.get(pk) or {}
        risks = pdata.get("risks") or {}

        print("=" * 90)
        print(f"PERSON CARD: {disp} (key={pk}, match={match:.2f})")
        print("=" * 90)

        # --- risks ---
        overall = float(risks.get("overall_risk_score") or 0.0)
        level = risks.get("risk_level") or "LOW"
        print(f"RISK: {level} ({overall:.2f})")

        if show_risk_types:
            by_type = (risks.get("by_type") or {})
            if not by_type:
                print("RISK TYPES: none")
            else:
                rows = []
                for rt, b in by_type.items():
                    rows.append(
                        (
                            rt,
                            int(b.get("hits") or 0),
                            float(b.get("score") or 0.0),
                            int(b.get("support_articles") or 0),
                            b.get("evidence") or [],
                        )
                    )
                rows.sort(key=lambda x: (x[2], x[1], x[3]), reverse=True)

                if top_risk_types and top_risk_types > 0:
                    rows = rows[:top_risk_types]
               

                print("-" * 90)
                print("RISK TYPES:")
                for rt, hits, score, supp, evs in rows:
                    print(f"- {rt}: score={score:.2f} hits={hits} support_articles={supp}")
                    if show_risk_evidence and evs:
                        ev0 = evs[0]
                        if ev0.get("sentence"):
                            print(f"  * evidence: {(ev0.get('sentence') or '')[:220]}")
                        if ev0.get("link"):
                            print(f"  * link: {ev0['link']}")

        # --- neighbors ---
        neigh = self.get_neighbors(pk, top_n=None, min_support_articles=min_support_articles)
        if not neigh:
            print("-" * 90)
            print("NEIGHBORS: none")
            return

        by_t: Dict[str, List[NeighborView]] = {"person": [], "organization": [], "location": [], "unknown": []}
        for n in neigh:
            by_t.setdefault(n.type, []).append(n)

        print("-" * 90)
        print(f"NEIGHBORS (min_support_articles={min_support_articles}):")

        for t in ("person", "organization", "location", "unknown"):
            arr = by_t.get(t, [])
            if not arr:
                continue
            arr = sorted(arr, key=lambda x: x.score, reverse=True)[:top_n_each_type]
            print(f"\n[{t.upper()}] top={len(arr)}")
            for n in arr:
                nli_part = ""
                if n.nli_label and (n.nli_score or 0.0) >= min_nli:
                    nli_part = f" | nli={n.nli_label} ({(n.nli_score or 0.0):.2f})"
                print(f"- {n.display} | support={n.support_articles} | score={n.score:.2f}{nli_part}")
                if show_evidence and n.evidence:
                    ev0 = n.evidence[0]
                    if ev0.get("sentence"):
                        print(f"  * evidence: {(ev0.get('sentence') or '')[:220]}")
                    if ev0.get("link"):
                        print(f"  * link: {ev0['link']}")
