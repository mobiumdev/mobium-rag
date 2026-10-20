"""The docs' own cross-references, as a graph over sections.

Mobium's docs cite each other explicitly: "CHALLENGES 305", "defects 55,
61, 63 and 64", and Markdown links to a file or a heading. Each is an edge
between the section that cites and the section cited, read by pattern, with
no model: an edge here is something a person wrote, never something
inferred. Retrieval uses it to pull a seed passage's neighbors into the
reranker's candidates (evaluate.py), so a question whose answer is cited
from the passage it matches can reach it.
"""

from __future__ import annotations

import posixpath
import random
import re
from collections import defaultdict

from .corpus import Passage, section_of, slug

# "CHALLENGES 315–317", "CHALLENGES#105", "defects 55, 61, 63 and 64".
CITE = re.compile(r"\b(?:CHALLENGES[ #]|defects? )((?:\d+(?:\s*[–-]\s*\d+)?(?:,\s*|\s+and\s+)?)+)")
NUM = re.compile(r"(\d+)(?:\s*[–-]\s*(\d+))?")
LINK = re.compile(r"\]\(([^)\s#]+\.md)(?:#([^)\s]+))?\)")
# A range wider than this is a span of the log, not a list of citations.
MAX_RANGE = 12


def _cited(text: str) -> set[str]:
    out: set[str] = set()
    for m in CITE.finditer(text):
        for a, b in NUM.findall(m.group(1)):
            lo, hi = int(a), int(b or a)
            if 0 <= hi - lo <= MAX_RANGE:
                out |= {f"CHALLENGES#{n}" for n in range(lo, hi + 1)}
    return out


def build(passages: list[Passage]) -> dict[str, set[str]]:
    """Undirected edges between sections, both ends in the corpus."""
    sections = {section_of(p.id) for p in passages}
    first: dict[str, str] = {}
    for p in passages:
        first.setdefault(p.path, section_of(p.id))
    stem = {"docs/CHALLENGES.md": "CHALLENGES"}
    edges: dict[str, set[str]] = defaultdict(set)
    for p in passages:
        src = section_of(p.id)
        targets = _cited(p.text)
        for path, anchor in LINK.findall(p.text):
            path = posixpath.normpath(posixpath.join(posixpath.dirname(p.path), path))
            if anchor and path in stem:
                # An entry's id is its number: #82-a-settings-switch… is CHALLENGES#82.
                targets.add(f"{stem[path]}#{re.match(r'\d*', anchor).group() or slug(anchor)}")
            elif anchor:
                targets.add(f"{path}#{slug(anchor)}")
            elif path in first:
                targets.add(first[path])
        for t in targets & sections - {src}:
            edges[src].add(t)
            edges[t].add(src)
    return dict(edges)


def shuffled(edges: dict[str, set[str]], sections: list[str], seed: int = 0) -> dict[str, set[str]]:
    """The control: every section keeps its number of neighbors, chosen at
    random. A gain this graph also gives is more candidates, not the edges."""
    rng = random.Random(seed)
    return {s: set(rng.sample(sections, len(n))) for s, n in edges.items()}


def neighbors(edges: dict[str, set[str]], seeds: list[str]) -> set[str]:
    return set().union(*(edges.get(section_of(s), set()) for s in seeds)) if seeds else set()
