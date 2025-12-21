"""Process API router - text analysis with NER and risk classification."""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Lazy load ML models
_ner_module = None
_risk_classifier = None


def get_ner_module():
    """Lazy load NER module."""
    global _ner_module
    if _ner_module is None:
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "model"))
            from ner_module import NERModule
            _ner_module = NERModule(
                model_name="Davlan/xlm-roberta-large-ner-hrl",
                device="cpu",
                max_chunk_chars=2500,
            )
        except Exception as e:
            print(f"Failed to load NER module: {e}")
            _ner_module = None
    return _ner_module


def get_risk_classifier():
    """Lazy load risk classifier."""
    global _risk_classifier
    if _risk_classifier is None:
        try:
            sys.path.insert(0, str(Path(__file__).parent.parent.parent / "model"))
            from risk_classifier import RiskClassifier
            _risk_classifier = RiskClassifier()
        except Exception as e:
            print(f"Failed to load risk classifier: {e}")
            _risk_classifier = None
    return _risk_classifier


class TextInput(BaseModel):
    text: str
    analyze_risk: bool = True


class Entity(BaseModel):
    name: str
    type: str
    confidence: float


class RiskResult(BaseModel):
    risk_level: str
    overall_risk_score: float
    detected_risks: List[Dict[str, Any]]


class ProcessResponse(BaseModel):
    status: str
    entities: List[Entity]
    risk: Optional[RiskResult] = None
    error: Optional[str] = None


@router.post("/process/text", response_model=ProcessResponse)
async def process_text(input_data: TextInput):
    """
    Process text to extract entities and classify risks.
    
    Uses:
    - NER: Davlan/xlm-roberta-large-ner-hrl for entity extraction
    - Risk: Rule-based classifier for Azerbaijani risk keywords
    """
    if not input_data.text or len(input_data.text.strip()) < 10:
        return ProcessResponse(
            status="error",
            entities=[],
            error="Text is too short (min 10 characters)"
        )
    
    entities: List[Entity] = []
    risk_result: Optional[RiskResult] = None
    
    # NER extraction
    ner = get_ner_module()
    if ner:
        try:
            ner_results = ner.extract(input_data.text)
            seen = set()
            for r in ner_results:
                key = (r["name"].lower(), r["type"])
                if key not in seen:
                    seen.add(key)
                    entities.append(Entity(
                        name=r["name"],
                        type=r["type"],
                        confidence=round(r["confidence"], 3),
                    ))
        except Exception as e:
            print(f"NER error: {e}")
    
    # Risk classification
    if input_data.analyze_risk:
        risk_clf = get_risk_classifier()
        if risk_clf:
            try:
                # Split into sentences and classify each
                import re
                sentences = re.split(r'[.!?]+', input_data.text)
                all_risks: List[Dict[str, Any]] = []
                max_score = 0.0
                
                for sent in sentences:
                    if len(sent.strip()) < 10:
                        continue
                    result = risk_clf.classify_sentence(sent)
                    if result["detected_risks"]:
                        for r in result["detected_risks"]:
                            r["sentence"] = sent[:200]
                        all_risks.extend(result["detected_risks"])
                        max_score = max(max_score, result["overall_risk_score"])
                
                # Deduplicate risks by type
                by_type: Dict[str, Dict[str, Any]] = {}
                for r in all_risks:
                    rt = r["type"]
                    if rt not in by_type or r["confidence"] > by_type[rt]["confidence"]:
                        by_type[rt] = r
                
                risk_level = "LOW"
                if max_score >= 0.75:
                    risk_level = "CRITICAL"
                elif max_score >= 0.50:
                    risk_level = "HIGH"
                elif max_score >= 0.25:
                    risk_level = "MEDIUM"
                
                risk_result = RiskResult(
                    risk_level=risk_level,
                    overall_risk_score=round(max_score, 3),
                    detected_risks=list(by_type.values()),
                )
            except Exception as e:
                print(f"Risk classification error: {e}")
    
    return ProcessResponse(
        status="ok",
        entities=entities,
        risk=risk_result,
    )


@router.get("/process/health")
async def process_health():
    """Check if ML models are available."""
    ner_ok = get_ner_module() is not None
    risk_ok = get_risk_classifier() is not None
    
    return {
        "ner_available": ner_ok,
        "risk_classifier_available": risk_ok,
        "status": "ok" if (ner_ok and risk_ok) else "partial",
    }

