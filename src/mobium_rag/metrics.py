"""Retrieval metrics against gold sections: deterministic, no model.

Retrieved passages are reduced to the sections they belong to, in order,
before anything is counted: two parts of one section are one find, and a
gold label names a section (corpus.section_of).
"""

from __future__ import annotations

import math

from .corpus import section_of


def sections(retrieved: list[str]) -> list[str]:
    out: list[str] = []
    for pid in retrieved:
        s = section_of(pid)
        if s not in out:
            out.append(s)
    return out


def recall_at(retrieved: list[str], gold: list[str], k: int) -> float:
    """The share of the gold sections among the first k sections retrieved."""
    top = set(sections(retrieved)[:k])
    return sum(g in top for g in gold) / len(gold)


def mrr(retrieved: list[str], gold: list[str]) -> float:
    """One over the rank of the first gold section; 0 if none was retrieved."""
    for i, s in enumerate(sections(retrieved), 1):
        if s in gold:
            return 1 / i
    return 0.0


def ndcg_at(retrieved: list[str], gold: list[str], k: int) -> float:
    """Binary-relevance nDCG over the first k sections: 1 when every gold
    section leads the list, less the further down they sit."""
    top = sections(retrieved)[:k]
    dcg = sum(1 / math.log2(i + 2) for i, s in enumerate(top) if s in gold)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(gold), k)))
    return dcg / ideal
