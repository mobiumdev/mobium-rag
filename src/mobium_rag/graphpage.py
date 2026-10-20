"""The citation graph as a page: `make graph` writes site/index.html.

Every node is a section of Mobium's docs at the pinned commit with at least
one citation in or out (graph.py), linked to its source on GitHub at that
commit. If a retrieval report is present, the page also says what the graph
did for retrieval, read from it rather than written in by hand.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import corpus, graph
from .corpus import section_of, slug

TEMPLATE = corpus.ROOT / "site" / "graph.template.html"
OUT = corpus.ROOT / "site" / "index.html"
REPORT = corpus.ROOT / "data" / "retrieval-report.md"
REPO = "https://github.com/mobiumdev/mobium/blob"


def family(path: str) -> str:
    if path == "docs/CHALLENGES.md":
        return "defects"
    if path == "docs/ROADMAP.md":
        return "roadmap"
    if path.startswith("docs/checks/"):
        return "checks"
    if path.startswith("docs/decisions/"):
        return "decisions"
    if path.startswith(("docs/guides/", "docs/quickstart/", "skills/")):
        return "guides"
    if path.startswith("docs/"):
        return "reference"
    return "project"


def data() -> dict:
    pin = corpus.PIN.read_text().strip()
    passages = corpus.load()
    edges = graph.build(passages)
    heads: dict[str, tuple[str, str]] = {}
    for p in passages:
        heads.setdefault(section_of(p.id), (p.path, p.heading))
    nodes = []
    for sid in sorted(edges):
        path, heading = heads[sid]
        top = sid == next(s for s, (pp, _) in heads.items() if pp == path)
        anchor = "" if top or not heading else "#" + slug(heading)
        nodes.append({"id": sid, "path": path, "title": heading or path, "family": family(path),
                      "url": f"{REPO}/{pin}/{path}{anchor}"})
    links = sorted({tuple(sorted((a, b))) for a, ns in edges.items() for b in ns})
    out = {"pin": pin, "sections": len(heads), "nodes": nodes,
           "links": [{"source": a, "target": b} for a, b in links], "retrieval": None}
    if REPORT.exists():
        text = REPORT.read_text()
        rows = {}
        for name in ("two-stage", "two-stage + graph"):
            m = re.search(rf"^\| {re.escape(name)} \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|$", text, re.M)
            if m:
                rows[name] = [float(x) for x in m.groups()]
        m = re.search(r"^\| two-stage \+ graph \| recall@5 \| ([+-][\d.]+) \| ([+-][\d.]+) to ([+-][\d.]+) \|$", text, re.M)
        if len(rows) == 2 and m:
            out["retrieval"] = {"rows": rows, "recall_diff": [float(x) for x in m.groups()]}
    return out


def render(full: bool) -> str:
    """The page; `full` adds the document skeleton GitHub Pages needs and
    the artifact viewer supplies itself."""
    body = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data(), separators=(",", ":")))
    if not full:
        return body
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f"</head>\n<body>\n{body}\n</body>\n</html>\n")


if __name__ == "__main__":
    # `python -m mobium_rag.graphpage [path]`: the Pages file, or the bare
    # page at path for a preview.
    target = Path(sys.argv[1]) if sys.argv[1:] else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(full=not sys.argv[1:]))
    print(f"wrote {target}")
