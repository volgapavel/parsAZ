# file: ner_module.py
from __future__ import annotations

import logging
from typing import Any, Dict, List

import torch
from transformers import pipeline

from text_utils import split_sentences, normalize_text

logger = logging.getLogger(__name__)


class NERModule:
    def __init__(self, model_name: str, device: str = "cpu", max_chunk_chars: int = 2500):
        dev = 0 if (device.startswith("cuda") and torch.cuda.is_available()) else -1
        self.pipe = pipeline(
            "ner",
            model=model_name,
            aggregation_strategy="simple",
            device=dev,
        )
        self.max_chunk_chars = int(max_chunk_chars)

    @staticmethod
    def _map_label(lbl: str) -> str:
        lbl = (lbl or "").upper()
        if "PER" in lbl:
            return "person"
        if "ORG" in lbl:
            return "organization"
        if "LOC" in lbl or "GPE" in lbl:
            return "location"
        return "unknown"

    def _chunk_text(self, text: str) -> List[str]:
        text = normalize_text(text)
        if not text:
            return []
        if len(text) <= self.max_chunk_chars:
            return [text]

        sents = split_sentences(text, max_len=600)
        chunks: List[str] = []
        cur: List[str] = []
        cur_len = 0

        for s in sents:
            if cur_len + len(s) + 1 > self.max_chunk_chars and cur:
                chunks.append(" ".join(cur))
                cur = [s]
                cur_len = len(s)
            else:
                cur.append(s)
                cur_len += len(s) + 1

        if cur:
            chunks.append(" ".join(cur))

        return chunks

    def extract(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        out: List[Dict[str, Any]] = []
        for chunk in self._chunk_text(text):
            try:
                res = self.pipe(chunk)
            except Exception as e:
                logger.exception("NER failed: %s", e)
                continue

            for r in res:
                name = (r.get("word") or "").strip()
                if not name:
                    continue
                out.append(
                    {
                        "name": name,
                        "type": self._map_label(r.get("entity_group") or r.get("entity")),
                        "confidence": float(r.get("score") or 0.0),
                        "start": int(r.get("start") or 0),
                        "end": int(r.get("end") or 0),
                    }
                )

        return out
