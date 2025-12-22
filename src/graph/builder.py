# file: person_graph_builder.py
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

from text_utils import split_sentences, contains_entity, normalize_text, normalize_key

_GEN_SUFFIX = re.compile(r"(nın|nin|nun|nün|ın|in|un|ün)$", re.IGNORECASE)
_LOC_SUFFIX = re.compile(r"(da|də|dan|dən)$", re.IGNORECASE)
_AZ_LAST_VOWEL = re.compile(r"(ı|i|u|ü)$", re.IGNORECASE)


def _token_count(s: str) -> int:
    s = normalize_text(s)
    if not s:
        return 0
    return len([x for x in s.split(" ") if x])


def _last_token(s: str) -> str:
    s = normalize_text(s)
    parts = [x for x in s.split(" ") if x]
    return parts[-1] if parts else ""


def _candidate_bases(display: str, etype: str) -> List[str]:
    """
    Generates candidate bases for aliasing.
    Includes special handling for AZ genitive like 'Paşinyanın' -> 'Paşinyan'.
    """
    n = normalize_text(display)
    if not n:
        return []

    out: List[str] = []

    if etype in ("person", "organization"):
        out.append(_GEN_SUFFIX.sub("", n).strip())

        ln = n.lower()
        for suf in ("nın", "nin", "nun", "nün"):
            if ln.endswith(suf) and len(n) > 2:
                out.append(n[:-2].strip())
                break

        out.append(_AZ_LAST_VOWEL.sub("", n).strip())

    if etype == "location":
        out.append(_LOC_SUFFIX.sub("", n).strip())

    uniq: List[str] = []
    for x in out:
        x = x.strip()
        if x and x != n and x not in uniq:
            uniq.append(x)

    return uniq


def build_alias_map(
    surface_forms: Dict[str, Tuple[str, str]],
    surface_counts: Counter,
    cfg
) -> Dict[str, str]:
    keys = set(surface_forms.keys())
    alias = {k: k for k in keys}

    def cnt(k: str) -> int:
        return int(surface_counts.get(k, 0))

    def better(a: str, b: str) -> str:
        ca, cb = cnt(a), cnt(b)
        if cb > ca:
            return b
        if ca > cb:
            return a
        return b if len(b) > len(a) else a

    for k, (disp, et) in surface_forms.items():
        for base in _candidate_bases(disp, et):
            bk = normalize_key(base)
            if bk in keys:
                alias[k] = bk
                break

    person_keys = [k for k, (_, et) in surface_forms.items() if (et or "").lower() == "person"]

    def sim(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio()

    buckets: Dict[str, List[str]] = {}
    for k in person_keys:
        buckets.setdefault(k[:4], []).append(k)

    for _, ks in buckets.items():
        ks = sorted(ks, key=lambda x: (cnt(x), len(x)), reverse=True)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, b = ks[i], ks[j]
                if a == b:
                    continue

                if a.startswith(b) or b.startswith(a):
                    canon = better(a, b)
                    alias[a] = canon
                    alias[b] = canon
                    continue

                if sim(a, b) >= float(cfg.person_fuzzy_sim_threshold):
                    canon = better(a, b)
                    alias[a] = canon
                    alias[b] = canon

    return alias


def _choose_person_display(existing: str, candidate: str) -> str:
    if not existing:
        return candidate
    if _token_count(candidate) > _token_count(existing):
        return candidate
    if _token_count(candidate) < _token_count(existing):
        return existing
    return candidate if len(candidate) > len(existing) else existing


def compute_shortname_alias(
    articles: List[Dict[str, Any]],
    entities_by_article: List[List[Dict[str, Any]]],
    alias: Dict[str, str],
    cfg
) -> Dict[str, str]:

    stop_persons = set(getattr(cfg, "stop_persons_lower", ()) or ())
    short_total = Counter()
    pair_cnt = Counter()

    for art, ents in zip(articles, entities_by_article):
        text = art.get("content") or art.get("text") or ""
        sents = split_sentences(text)
        if not sents:
            continue

        persons_u: Dict[str, str] = {}
        for e in ents:
            if (e.get("type") or "").lower() != "person":
                continue

            name = (e.get("name") or "").strip()
            if len(normalize_text(name)) < cfg.min_entity_len:
                continue

            nk = normalize_key(name)
            if nk in stop_persons:
                continue

            k = alias.get(nk, nk)
            persons_u[k] = _choose_person_display(persons_u.get(k, ""), name)

        if not persons_u:
            continue

        for sent in sents:
            present = [(pk, pd) for pk, pd in persons_u.items() if contains_entity(sent, pd)]
            if len(present) < 2:
                continue

            fulls, shorts = [], []
            for pk, pd in present:
                tcnt = _token_count(pd)
                if tcnt >= int(cfg.person_canonical_min_tokens):
                    fulls.append((pk, pd))
                elif tcnt == 1:
                    shorts.append((pk, pd))

            if not shorts or not fulls:
                continue

            for sk, sd in shorts:
                s_norm = normalize_key(sd)
                if s_norm in stop_persons:
                    continue

                short_total[sk] += 1

                for fk, fd in fulls:
                    if fk == sk:
                        continue

                    fd_norm = normalize_text(fd)
                    if fd_norm.lower().startswith((sd + " ").lower()) or normalize_key(_last_token(fd)) == s_norm:
                        pair_cnt[(sk, fk)] += 1

    out: Dict[str, str] = {}
    for sk, total in short_total.items():
        cands = [(fk, pair_cnt[(sk, fk)]) for (ssk, fk) in pair_cnt.keys() if ssk == sk]
        if not cands:
            continue

        cands.sort(key=lambda x: x[1], reverse=True)
        best_fk, best_cnt = cands[0]
        second_cnt = cands[1][1] if len(cands) > 1 else 0

        if best_cnt < int(cfg.shortname_merge_min_cooccur):
            continue
        if total <= 0:
            continue
        if (best_cnt / float(total)) < float(cfg.shortname_merge_min_ratio):
            continue
        if second_cnt > 0 and best_cnt < second_cnt * float(cfg.shortname_merge_second_best_gap):
            continue

        out[sk] = best_fk

    return out


def _compress_alias(alias: Dict[str, str]) -> Dict[str, str]:

    def resolve(k: str) -> str:
        seen = set()
        while True:
            nk = alias.get(k, k)
            if nk == k:
                return k
            if nk in seen:
                return nk
            seen.add(nk)
            k = nk

    for k in list(alias.keys()):
        alias[k] = resolve(k)

    return alias


def build_person_index(
    articles: List[Dict[str, Any]],
    entities_by_article: List[List[Dict[str, Any]]],
    cfg
) -> Dict[str, Any]:
    surface_forms: Dict[str, Tuple[str, str]] = {}
    surface_counts: Counter = Counter()

    for ents in entities_by_article:
        for e in ents:
            et = (e.get("type") or "").lower()
            if et not in ("person", "organization", "location"):
                continue

            name = (e.get("name") or "").strip()
            if len(normalize_text(name)) < cfg.min_entity_len:
                continue

            k = normalize_key(name)
            surface_counts[k] += 1
            surface_forms.setdefault(k, (name, et))

    alias = build_alias_map(surface_forms, surface_counts, cfg)

    if getattr(cfg, "enable_shortname_merge", False):
        short_map = compute_shortname_alias(articles, entities_by_article, alias, cfg)
        for sk, fk in short_map.items():
            if sk in alias and fk in alias:
                alias[sk] = fk

    alias = _compress_alias(alias)

    stop_persons = set(getattr(cfg, "stop_persons_lower", ()) or ())

    pairs: List[Tuple[str, str, str, str, str, Dict[str, Any]]] = []

    for art, ents in zip(articles, entities_by_article):
        text = art.get("content") or art.get("text") or ""
        sents = split_sentences(text)
        if not sents:
            continue

        persons_u: Dict[str, str] = {}
        others_u: Dict[str, Tuple[str, str]] = {}

        for e in ents:
            et = (e.get("type") or "").lower()
            name = (e.get("name") or "").strip()

            if et not in ("person", "organization", "location"):
                continue
            if len(normalize_text(name)) < cfg.min_entity_len:
                continue

            k0 = normalize_key(name)
            if et == "person" and k0 in stop_persons:
                continue

            k = alias.get(k0, k0)

            if et == "person":
                persons_u[k] = _choose_person_display(persons_u.get(k, ""), name)

            others_u[k] = (name, et)

        if not persons_u:
            continue

        for sent in sents:
            present_persons = [pk for pk, pdisp in persons_u.items() if contains_entity(sent, pdisp)]
            if not present_persons:
                continue

            present_others: List[Tuple[str, str, str]] = []
            for ok, (odisp, otype) in others_u.items():
                if contains_entity(sent, odisp):
                    present_others.append((ok, odisp, otype))

            if not present_others:
                continue

            present_others = present_others[: cfg.max_entities_per_sentence]

            for pk in present_persons:
                for ok, odisp, otype in present_others:
                    if ok == pk:
                        continue

                    ev = {
                        "sentence": sent,
                        "article_id": art.get("article_id") or art.get("id"),
                        "title": art.get("title"),
                        "link": art.get("link"),
                    }
                    pairs.append((pk, persons_u[pk], ok, odisp, otype, ev))

    neighbor_df = Counter()
    seen_neighbor_article = set()
    N = max(len(articles), 1)

    for _, _, ok, _, _, ev in pairs:
        aid = ev.get("article_id")
        if aid is None:
            continue
        key = (ok, aid)
        if key not in seen_neighbor_article:
            neighbor_df[ok] += 1
            seen_neighbor_article.add(key)

    def idf(ok: str) -> float:
        df = neighbor_df.get(ok, 0)
        return math.log((N + 1) / (df + 1)) + 1.0

    def too_common(ok: str) -> bool:
        return neighbor_df.get(ok, 0) > cfg.max_neighbor_df_share * N

    idx = defaultdict(
        lambda: {
            "display": None,
            "neighbors": defaultdict(
                lambda: {
                    "display": None,
                    "type": None,
                    "support_articles": set(),
                    "support_mentions": 0,
                    "evidence": [],
                }
            ),
        }
    )

    for pk, pdisp, ok, odisp, otype, ev in pairs:
        p = idx[pk]
        if p["display"] is None:
            p["display"] = pdisp

        n = p["neighbors"][ok]
        n["display"] = odisp
        n["type"] = otype

        if ev.get("article_id") is not None:
            n["support_articles"].add(ev["article_id"])

        n["support_mentions"] += 1

        if len(n["evidence"]) < cfg.max_evidence_per_neighbor:
            n["evidence"].append(ev)

    persons_out: Dict[str, Any] = {}
    stop_neighbors = set(cfg.stop_neighbors_lower)

    for pk, pdata in idx.items():
        neigh_out: Dict[str, Any] = {}

        for ok, n in pdata["neighbors"].items():
            support_articles = len(n["support_articles"])
            if support_articles < cfg.min_neighbor_support_articles:
                continue

            disp_norm = normalize_key(n["display"] or "")
            if disp_norm in stop_neighbors:
                continue

            if too_common(ok):
                continue

            score = math.log1p(support_articles) * idf(ok)

            neigh_out[ok] = {
                "display": n["display"],
                "type": n["type"],
                "support_articles": support_articles,
                "support_mentions": int(n["support_mentions"]),
                "score": float(score),
                "evidence": n["evidence"],
            }

        if neigh_out:
            persons_out[pk] = {"display": pdata["display"], "neighbors": neigh_out}

    return {"persons": persons_out}
