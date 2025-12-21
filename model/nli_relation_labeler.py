# file: nli_relation_labeler.py
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

import torch
from transformers import pipeline

from text_utils import normalize_key

logger = logging.getLogger(__name__)


class NLIRelationLabeler:
    """
    Zero-shot NLI labeler with strong gating to reduce FP.
    """

    def __init__(self, model_name: str, device: str = "cpu", labels: Tuple[str, ...] = ()) -> None:
        dev = 0 if (device.startswith("cuda") and torch.cuda.is_available()) else -1
        self.labels = list(labels)
        self.pipe = pipeline("zero-shot-classification", model=model_name, device=dev)

        self.meet_triggers = (
            "görüş", "görüşüb", "görüşdü", "görüşəcək", "görüşlər",
            "qəbul edib", "qəbul etdi", "qəbul etmiş",
            "danışıqlar", "müzakirə",
            "встрет", "переговор", "обсуд", "принял", "провел встреч",
            "met", "meeting", "talks", "discussed", "received",
        )

        self.appoint_triggers = (
            "təyin", "təyin edildi", "vəzifəsinə təyin", "təyin olun",
            "назнач", "утвержден", "избран",
            "appointed", "named", "elected",
        )

        self.role_triggers = (
            "директор", "гендир", "глава", "председател", "министр", "президент",
            "ceo", "director", "chairman", "minister", "president", "head",
            "nazir", "prezident", "rəhbər", "direktor", "sədr",
        )

    @staticmethod
    def _has_any(sentence: str, triggers: Tuple[str, ...]) -> bool:
        s = normalize_key(sentence)
        return any(t in s for t in triggers)

    @staticmethod
    def _near(sentence: str, a: str, b: str, window: int = 45) -> bool:
        s = normalize_key(sentence)
        a = normalize_key(a)
        b = normalize_key(b)
        if not a or not b:
            return False

        apos = [m.start() for m in re.finditer(re.escape(a), s)]
        bpos = [m.start() for m in re.finditer(re.escape(b), s)]

        for i in apos:
            for j in bpos:
                if abs(i - j) <= window:
                    return True
        return False

    def _head_has_role_nearby(self, sentence: str, head: str, window: int = 60) -> bool:
        s = normalize_key(sentence)
        h = normalize_key(head)
        if not h or h not in s:
            return False

        i = s.find(h)
        left = max(0, i - window)
        right = min(len(s), i + len(h) + window)
        ctx = s[left:right]
        return any(rt in ctx for rt in self.role_triggers)

    def label(
        self,
        sentence: str,
        head: str,
        tail: str,
        head_type: str,
        tail_type: str,
    ) -> Optional[Dict[str, Any]]:
        if not sentence or not head or not tail or not self.labels:
            return None

        ht = (head_type or "").lower()
        tt = (tail_type or "").lower()

        if ht != "person":
            return None
        if tt not in ("person", "organization"):
            return None

        has_meet = self._has_any(sentence, self.meet_triggers)
        has_appoint = self._has_any(sentence, self.appoint_triggers)

        candidate_labels: List[str] = []
        for lbl in self.labels:
            if lbl == "met with":
                if tt == "person" and has_meet:
                    candidate_labels.append(lbl)

            elif lbl == "was appointed to":
                if tt == "organization" and has_appoint:
                    if (
                        self._near(sentence, head, "təyin", 120)
                        or self._near(sentence, head, "назнач", 120)
                        or self._near(sentence, head, "appointed", 120)
                    ):
                        candidate_labels.append(lbl)

            elif lbl == "works for":
                if tt == "organization" and (not has_meet):
                    if self._head_has_role_nearby(sentence, head):
                        candidate_labels.append(lbl)

        if not candidate_labels:
            return None

        try:
            res = self.pipe(
                sentence,
                candidate_labels=candidate_labels,
                hypothesis_template=f"{head} {{}} {tail}.",
                multi_label=True,
            )
            best_label = res["labels"][0]
            best_score = float(res["scores"][0])
            return {"label": best_label, "score": best_score}
        except Exception as e:
            logger.warning("NLI label failed: %s", e)
            return None
