# file: text_utils.py
from __future__ import annotations

import re
import unicodedata
from typing import List

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")

_U_LET = r"A-Za-zÀ-ÖØ-öø-ÿĀ-žƏəİıŞşĞğÇçÖöÜü"


def normalize_text(s: str) -> str:
    s = s or ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_key(s: str) -> str:
    """
    Aggressive normalization for keys only.
    Handles i̇ (latin i + dot) which often appears after lowercasing.
    """
    s = normalize_text(s).lower()
    s = s.replace("i̇", "i")
    s = s.replace("’", "'").replace("`", "'")
    s = s.replace("“", '"').replace("”", '"').replace("«", '"').replace("»", '"')
    return s


def split_sentences(text: str, max_len: int = 400) -> List[str]:
    text = normalize_text(text)
    if not text:
        return []
    parts = _SENT_SPLIT.split(text)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        out.append(p[:max_len])
    return out


def contains_entity(sentence: str, entity: str) -> bool:
    s = normalize_key(sentence)
    e = normalize_key(entity).strip()
    if not e or len(e) < 3:
        return False

    if e in s:
        return True

    pat = rf"(?<![{_U_LET}0-9_]){re.escape(e)}(?![{_U_LET}0-9_])"
    return re.search(pat, s, flags=re.IGNORECASE) is not None
