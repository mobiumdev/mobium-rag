"""The review page for golden set v2 (review/GOLDEN-V2.md): a new page, not
the 82's, built from the same page with its questions taken out.

For each drafted question: its gold sections with an excerpt, what the
two-stage retriever returns for it from the corpus at f232d54 with the gold
marked, its key facts with their anchors, and Claude's check of it. The
corpus.pin and the 82's index are not touched: the retrieval here is its
own index, keyed by the commit.

A fact shows as one line, its anchors after it in ⟦ ⟧: alternatives
separated by " / ", anchors by " ; ". The reviewer edits the line; the
apply step reads it back the same way (`fact_line`, `parse_fact_line`).

    uv run python review/build_review_v2.py [questions.jsonl] [--commit f232d54]
"""

import json
import re
import sys
from pathlib import Path

from mobium_rag import corpus
from mobium_rag.evaluate import FIRST_STAGE, K
from mobium_rag.retrieve import Index

ROOT = corpus.ROOT
SOURCE_PAGE = ROOT / "review" / "golden-review.html"
PAGE = ROOT / "review" / "golden-review-v2.html"
EXCERPT = 420


def fact_line(f: dict) -> str:
    anchors = " ; ".join(" / ".join(alts) for alts in f["anchors"])
    return f["fact"] + (f" ⟦{anchors}⟧" if anchors else "")


def parse_fact_line(line: str) -> dict:
    m = re.match(r"^(.*?)\s*⟦(.*)⟧\s*$", line)
    if not m:
        return {"fact": line.strip(), "anchors": []}
    anchors = [[a.strip() for a in part.split(" / ") if a.strip()] for part in m.group(2).split(" ; ")]
    return {"fact": m.group(1).strip(), "anchors": [a for a in anchors if a]}


def section(by_section: dict[str, corpus.Passage], sid: str) -> dict:
    p = by_section[sid]
    body = p.text.split("\n", 1)[1] if "\n" in p.text else p.text
    body = re.sub(r"\s+", " ", body).strip()
    return {"id": sid, "heading": p.heading, "path": p.path,
            "excerpt": body[:EXCERPT] + ("…" if len(body) > EXCERPT else "")}


def entry(q: dict, index: Index, by_section: dict) -> dict:
    hits = index.search(q["question"], FIRST_STAGE)
    top = index.rerank(q["question"], [pid for pid, _ in hits], K)
    retrieved, seen = [], set()
    for pid, _ in top:
        sid = corpus.section_of(pid)
        if sid not in seen:
            seen.add(sid)
            retrieved.append(dict(section(by_section, sid), gold=sid in q["gold"]))
    tags = [q.get("category") or "", q.get("persona") or ""] + (["new since 7b590a4"] if q.get("new_since_pin") else [])
    check = q.get("check", "")
    if q["kind"] == "unanswerable" and q.get("nearest"):
        check += " Nearest sections: " + ", ".join(q["nearest"]) + "."
    if q.get("verified_in"):
        check += " Verified in: " + ", ".join(q["verified_in"]) + "."
    return {"id": q["id"], "kind": q["kind"], "question": q["question"], "tags": [t for t in tags if t],
            "gold": [section(by_section, g) for g in q["gold"]], "retrieved": retrieved,
            "missed": bool(q["gold"]) and not any(r["gold"] for r in retrieved),
            "facts": [fact_line(f) for f in q["facts"]], "concern": q.get("concern", ""), "check": check.strip()}


def main(argv: list[str]) -> None:
    commit = "f232d54"
    if "--commit" in argv:
        k = argv.index("--commit")
        commit, argv = argv[k + 1], argv[:k] + argv[k + 2:]
    src = Path(argv[0]) if argv else ROOT / "data" / "golden-v2-proposed.jsonl"
    qs = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    passages = corpus.build(commit)
    by_section: dict[str, corpus.Passage] = {}
    for p in passages:
        by_section.setdefault(corpus.section_of(p.id), p)
    index = Index(passages, commit)

    page = SOURCE_PAGE.read_text()
    m = re.search(r"const DATA = (.*?);\nconst KIND", page, re.S)
    data = {"pin": commit, "questions": [entry(q, index, by_section) for q in qs], "pins": {}}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = page[:m.start(1)] + blob + page[m.end(1):]
    page = page.replace("<h1>Golden Set Review</h1>", "<h1>Golden Set v2 Review</h1>")
    page = page.replace("<title>Golden Set Review</title>", "<title>Golden Set v2 Review</title>", 1)
    page = re.sub(r"\d+ questions · corpus", f"{len(qs)} questions · corpus", page, count=1)
    page = page.replace("key facts drafted 2026-10-12", "drafted 2026-10-24 to review/GOLDEN-V2.md; "
                        "anchors follow each fact in ⟦ ⟧, alternatives split by / and anchors by ;")
    # Category, persona and whether it is new show beside the kind.
    page = page.replace('q.missed ? el("span",{class:"tag miss",text:"Missed by retrieval"}) : null,',
                        '...(q.tags || []).map(t => el("span",{class:"tag",text:t})),\n    '
                        'q.missed ? el("span",{class:"tag miss",text:"Missed by retrieval"}) : null,', 1)
    PAGE.write_text(page)
    print(f"{len(qs)} questions on {PAGE.relative_to(ROOT)}, retrieved at {commit}")


if __name__ == "__main__":
    main(sys.argv[1:])
