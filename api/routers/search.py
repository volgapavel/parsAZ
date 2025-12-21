"""Search API router - person search in index."""
import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Load person index
INDEX_PATH = Path(__file__).parent.parent.parent / "model" / "person_index.json"
_person_index: Optional[Dict[str, Any]] = None


def get_person_index() -> Dict[str, Any]:
    global _person_index
    if _person_index is None:
        if INDEX_PATH.exists():
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                _person_index = json.load(f)
        else:
            _person_index = {"persons": {}}
    return _person_index


def normalize_key(s: str) -> str:
    """Normalize string for matching."""
    import unicodedata
    import re
    s = s or ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    s = s.replace("i̇", "i")
    return s


def similarity(a: str, b: str) -> float:
    """Calculate string similarity."""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()


class PersonMatch(BaseModel):
    person_key: str
    display: str
    match_score: float


class NeighborInfo(BaseModel):
    neighbor_key: str
    display: str
    type: str
    support_articles: int
    support_mentions: int
    score: float
    nli_label: Optional[str] = None
    nli_score: Optional[float] = None
    evidence: Optional[List[Dict[str, Any]]] = None


class RiskInfo(BaseModel):
    risk_level: str
    overall_risk_score: float
    by_type: Optional[Dict[str, Any]] = None


class PersonCard(BaseModel):
    person_key: str
    display: str
    match_score: float
    risk: Optional[RiskInfo] = None
    neighbors_count: int
    neighbors: List[NeighborInfo]
    semantic_relations: Optional[List[Dict[str, Any]]] = None


class SearchResponse(BaseModel):
    query: str
    matches: List[PersonMatch]
    total: int


class PersonCardResponse(BaseModel):
    status: str
    person: Optional[PersonCard] = None
    error: Optional[str] = None


@router.get("/persons/search", response_model=SearchResponse)
async def search_persons(
    q: str = Query(..., min_length=1, description="Search query (person name)"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
):
    """
    Search for persons in the index by name.
    Supports exact match, substring match, and fuzzy matching.
    """
    index = get_person_index()
    persons = index.get("persons", {})
    
    q_norm = normalize_key(q)
    if not q_norm:
        return SearchResponse(query=q, matches=[], total=0)
    
    matches: List[PersonMatch] = []
    
    # Exact match first
    for pk, pdata in persons.items():
        disp = pdata.get("display", "")
        d_norm = normalize_key(disp)
        if d_norm == q_norm:
            matches.append(PersonMatch(person_key=pk, display=disp, match_score=1.0))
    
    if matches:
        return SearchResponse(query=q, matches=matches[:limit], total=len(matches))
    
    # Substring match
    for pk, pdata in persons.items():
        disp = pdata.get("display", "")
        d_norm = normalize_key(disp)
        if q_norm in d_norm:
            matches.append(PersonMatch(person_key=pk, display=disp, match_score=0.95))
    
    if matches:
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return SearchResponse(query=q, matches=matches[:limit], total=len(matches))
    
    # Fuzzy match
    for pk, pdata in persons.items():
        disp = pdata.get("display", "")
        d_norm = normalize_key(disp)
        if not d_norm:
            continue
        sim = similarity(q_norm, d_norm)
        if sim >= 0.6:
            matches.append(PersonMatch(person_key=pk, display=disp, match_score=round(sim, 3)))
    
    matches.sort(key=lambda x: x.match_score, reverse=True)
    return SearchResponse(query=q, matches=matches[:limit], total=len(matches))


@router.get("/persons/{person_key}", response_model=PersonCardResponse)
async def get_person_card(
    person_key: str,
    top_neighbors: int = Query(20, ge=1, le=100, description="Max neighbors per type"),
    min_support: int = Query(1, ge=1, description="Min support articles for neighbors"),
):
    """
    Get detailed person card with neighbors, risks, and relations.
    """
    index = get_person_index()
    persons = index.get("persons", {})
    
    if person_key not in persons:
        return PersonCardResponse(status="not_found", error=f"Person '{person_key}' not found")
    
    pdata = persons[person_key]
    
    # Parse neighbors
    neigh_raw = pdata.get("neighbors", {})
    neighbors: List[NeighborInfo] = []
    
    for nk, nd in neigh_raw.items():
        sa = int(nd.get("support_articles", 0))
        if sa < min_support:
            continue
        
        nli = nd.get("nli_relation") if isinstance(nd.get("nli_relation"), dict) else None
        
        neighbors.append(NeighborInfo(
            neighbor_key=nk,
            display=nd.get("display", nk),
            type=(nd.get("type", "unknown")).lower(),
            support_articles=sa,
            support_mentions=int(nd.get("support_mentions", 0)),
            score=float(nd.get("score", 0)),
            nli_label=nli.get("label") if nli else None,
            nli_score=float(nli.get("score")) if nli and nli.get("score") else None,
            evidence=nd.get("evidence", [])[:3],
        ))
    
    neighbors.sort(key=lambda x: x.score, reverse=True)
    neighbors = neighbors[:top_neighbors]
    
    # Parse risks
    risks_raw = pdata.get("risks", {})
    risk_info = None
    if risks_raw:
        risk_info = RiskInfo(
            risk_level=risks_raw.get("risk_level", "LOW"),
            overall_risk_score=float(risks_raw.get("overall_risk_score", 0)),
            by_type=risks_raw.get("by_type"),
        )
    
    # Semantic relations
    sem_rels = []
    for n in neighbors:
        rel = "related_to"
        if n.nli_label and (n.nli_score or 0) >= 0.82:
            if n.nli_label == "met with" and n.type == "person":
                rel = "met_with"
            elif n.nli_label == "works for" and n.type == "organization":
                rel = "works_for"
            elif n.nli_label == "was appointed to" and n.type == "organization":
                rel = "appointed_to"
        
        sem_rels.append({
            "relation": rel,
            "target": n.display,
            "type": n.type,
            "score": n.score,
            "nli_score": n.nli_score,
        })
    
    return PersonCardResponse(
        status="ok",
        person=PersonCard(
            person_key=person_key,
            display=pdata.get("display", person_key),
            match_score=1.0,
            risk=risk_info,
            neighbors_count=len(neigh_raw),
            neighbors=neighbors,
            semantic_relations=sem_rels[:30],
        ),
    )


@router.get("/persons/by-name/{name}")
async def get_person_by_name(
    name: str,
    top_neighbors: int = Query(20, ge=1, le=100),
    min_support: int = Query(1, ge=1),
):
    """
    Search person by name and return card for best match.
    Convenience endpoint that combines search + get card.
    """
    search_result = await search_persons(q=name, limit=5)
    
    if not search_result.matches:
        return PersonCardResponse(status="not_found", error=f"No person found for '{name}'")
    
    best = search_result.matches[0]
    card = await get_person_card(best.person_key, top_neighbors, min_support)
    
    if card.person:
        card.person.match_score = best.match_score
    
    return card


@router.get("/index/stats")
async def get_index_stats():
    """Get global statistics about the person index."""
    index = get_person_index()
    persons = index.get("persons", {})
    
    total_persons = len(persons)
    total_neighbors = 0
    by_type = {"person": 0, "organization": 0, "location": 0, "unknown": 0}
    risk_levels = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    
    for pdata in persons.values():
        neigh = pdata.get("neighbors", {})
        total_neighbors += len(neigh)
        
        for nd in neigh.values():
            t = (nd.get("type", "unknown")).lower()
            by_type[t] = by_type.get(t, 0) + 1
        
        risks = pdata.get("risks", {})
        level = risks.get("risk_level", "LOW")
        risk_levels[level] = risk_levels.get(level, 0) + 1
    
    return {
        "total_persons": total_persons,
        "total_neighbors": total_neighbors,
        "neighbors_by_type": by_type,
        "risk_levels": risk_levels,
    }


@router.get("/top-persons")
async def get_top_persons(
    limit: int = Query(20, ge=1, le=100),
    sort_by: str = Query("neighbors_total", enum=["neighbors_total", "risk_score"]),
):
    """Get top persons by number of connections or risk score."""
    index = get_person_index()
    persons = index.get("persons", {})
    
    rows = []
    for pk, pdata in persons.items():
        neigh = pdata.get("neighbors", {})
        risks = pdata.get("risks", {})
        
        rows.append({
            "person_key": pk,
            "display": pdata.get("display", pk),
            "neighbors_total": len(neigh),
            "risk_level": risks.get("risk_level", "LOW"),
            "risk_score": float(risks.get("overall_risk_score", 0)),
        })
    
    if sort_by == "risk_score":
        rows.sort(key=lambda x: x["risk_score"], reverse=True)
    else:
        rows.sort(key=lambda x: x["neighbors_total"], reverse=True)
    
    return {"persons": rows[:limit], "total": len(rows)}

