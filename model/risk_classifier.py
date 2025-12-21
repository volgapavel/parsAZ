# file: risk_classifier.py
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple


class RiskLevel(Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class DetectedRisk:
    type: str
    confidence: float
    keyword_matches: int
    matched: List[str]


class RiskClassifier:
    """
    Простой rule-based риск-классификатор (по предложениям).
    Возвращает:
      detected_risks: list[{type, confidence, keyword_matches, matched}]
      overall_risk_score: float
      risk_level: str
    """

    def __init__(self) -> None:
        self.risk_keywords: Dict[str, List[str]] = {
            "corruption": ["rüşvət", "korrupsiya", "qanunsuz", "rüşvətxor"],
            "organized_crime": ["mafiya", "cinayət", "band", "qrup"],
            "fraud": ["saxtakarlıq", "aldatma", "fırıldaq", "saxta"],
            "money_laundering": ["pul yıkama", "çirkli pul", "şübhəli əməliyyat"],
            "sanctions": ["sanksiya", "qadağan", "məhdudlaşdır"],
            "legal_proceedings": ["məhkəmə", "ittiham", "istintaq", "həbs", "prokuror"],
        }

        self.risk_phrases: Dict[str, List[str]] = {
            "corruption": ["rüşvət alıb", "rüşvət verib", "korrupsiya törədib"],
            "sanctions": ["sanksiya qoyulub", "sanksiya tətbiq", "sanksiya siyahısı"],
            "legal_proceedings": ["cinayət işi", "istintaq aparılır", "həbs olunub"],
            "money_laundering": ["pul yuyulması", "çirkli pul"],
        }

        self.phrase_confidence = 0.85
        self.keyword_step = 0.20
        self.keyword_cap = 0.95

    def classify_sentence(self, sentence: str) -> Dict[str, Any]:
        s = (sentence or "").lower()
        detected: List[DetectedRisk] = []

        for rtype, phrases in self.risk_phrases.items():
            matched = [p for p in phrases if p in s]
            if matched:
                detected.append(
                    DetectedRisk(
                        type=rtype,
                        confidence=self.phrase_confidence,
                        keyword_matches=len(matched),
                        matched=matched,
                    )
                )

        for rtype, kws in self.risk_keywords.items():
            matched = [kw for kw in kws if kw in s]
            if matched:
                conf = min(len(matched) * self.keyword_step, self.keyword_cap)
                detected.append(
                    DetectedRisk(
                        type=rtype,
                        confidence=float(conf),
                        keyword_matches=len(matched),
                        matched=matched,
                    )
                )

        by_type: Dict[str, Tuple[float, int, List[str]]] = {}
        for d in detected:
            prev = by_type.get(d.type)
            if prev is None:
                by_type[d.type] = (d.confidence, d.keyword_matches, list(d.matched))
            else:
                best_conf = max(prev[0], d.confidence)
                by_type[d.type] = (best_conf, prev[1] + d.keyword_matches, list({*prev[2], *d.matched}))

        out_risks: List[Dict[str, Any]] = []
        for rt, (conf, km, matched) in by_type.items():
            out_risks.append(
                {
                    "type": rt,
                    "confidence": float(conf),
                    "keyword_matches": int(km),
                    "matched": matched,
                }
            )

        overall = (sum(r["confidence"] for r in out_risks) / len(out_risks)) if out_risks else 0.0

        return {
            "detected_risks": out_risks,
            "overall_risk_score": float(overall),
            "risk_level": self._risk_level(overall),
        }

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 0.75:
            return RiskLevel.CRITICAL.value
        if score >= 0.50:
            return RiskLevel.HIGH.value
        if score >= 0.25:
            return RiskLevel.MEDIUM.value
        return RiskLevel.LOW.value
