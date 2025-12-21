# file: config.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class PipelineConfig:
    device: str = "cuda" 
    max_articles: int = 200

    ner_model: str = "Davlan/xlm-roberta-large-ner-hrl"
    min_entity_len: int = 3
    ner_max_chunk_chars: int = 2500

    max_entities_per_sentence: int = 10
    max_evidence_per_neighbor: int = 3
    min_neighbor_support_articles: int = 2
    max_neighbor_df_share: float = 0.25

    stop_neighbors_lower: Tuple[str, ...] = (
        "azərtac", "reuters", "bbc", "cnn",
        "facebook", "instagram", "telegram", "youtube", "tiktok",
    )

    stop_persons_lower: Tuple[str, ...] = (
        "prezident", "president", "президент",
        "prezidentin", "президента", "президентом",
        "cənab", "xanım",
    )

    person_fuzzy_sim_threshold: float = 0.93

    enable_shortname_merge: bool = True
    person_canonical_min_tokens: int = 2
    shortname_merge_min_cooccur: int = 3
    shortname_merge_min_ratio: float = 0.75
    shortname_merge_second_best_gap: float = 1.5 

    use_nli: bool = True
    nli_model: str = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
    nli_threshold: float = 0.82
    relation_labels: Tuple[str, ...] = (
        "met with",
        "works for",
        "was appointed to",
    )

    use_risk: bool = True
    risk_min_score_to_store: float = 0.35
    risk_max_evidence_per_type: int = 3
