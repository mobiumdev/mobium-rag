"""Add questions to the golden review page, ready for a person to decide.

For each question in a JSONL file (data/golden-proposed.jsonl by default):
its gold sections with an excerpt, what the two-stage retriever returns
for it at the corpus pin with the gold ones marked, the drafted key facts,
and a check of each from a checks file — Claude's reading of the question
against the docs and code, shown on the page as such. Decisions are left
empty: the page's database is where a person makes them, and
review/apply.py applies them.

Questions already on the page are replaced by id; the decided 61 are kept
as they were shown. Run from the repository root:

    uv run python review/build_review.py [questions.jsonl] [checks.json]
"""

import json
import re
import sys
from pathlib import Path

from mobium_rag import corpus
from mobium_rag.evaluate import FIRST_STAGE, K
from mobium_rag.retrieve import Index

ROOT = corpus.ROOT
PAGE = ROOT / "review" / "golden-review.html"
EXCERPT = 420


def section(by_section: dict[str, corpus.Passage], sid: str) -> dict:
    p = by_section[sid]
    body = p.text.split("\n", 1)[1] if "\n" in p.text else p.text
    body = re.sub(r"\s+", " ", body).strip()
    return {"id": sid, "heading": p.heading, "path": p.path,
            "excerpt": body[:EXCERPT] + ("…" if len(body) > EXCERPT else "")}


def entry(q: dict, index: Index, by_section: dict, check: str | None) -> dict:
    hits = index.search(q["question"], FIRST_STAGE)
    top = index.rerank(q["question"], [pid for pid, _ in hits], K)
    retrieved, seen = [], set()
    for pid, _ in top:
        sid = corpus.section_of(pid)
        if sid in seen:
            continue
        seen.add(sid)
        retrieved.append(dict(section(by_section, sid), gold=sid in q["gold"]))
    out = {"id": q["id"], "kind": q["kind"], "question": q["question"],
           "gold": [section(by_section, g) for g in q["gold"]], "retrieved": retrieved,
           "missed": bool(q["gold"]) and not any(r["gold"] for r in retrieved),
           "facts": q.get("facts") or [], "concern": q.get("concern", "")}
    if check:
        out["check"] = check
    return out


def main(argv: list[str]) -> None:
    src = Path(argv[0]) if argv else ROOT / "data" / "golden-proposed.jsonl"
    checks = json.loads(Path(argv[1]).read_text()) if len(argv) > 1 else {}
    passages = corpus.load()
    by_section: dict[str, corpus.Passage] = {}
    for p in passages:
        by_section.setdefault(corpus.section_of(p.id), p)
    pin = corpus.PIN.read_text().strip()
    index = Index(passages, pin)
    qs = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    missing = [g for q in qs for g in q["gold"] if g not in by_section]
    if missing:
        raise SystemExit(f"gold sections not in the corpus at {pin[:7]}: {missing}")

    page = PAGE.read_text()
    m = re.search(r"const DATA = (.*?);\nconst KIND", page, re.S)
    data = json.loads(m.group(1))
    new = {q["id"]: entry(q, index, by_section, checks.get(q["id"])) for q in qs}
    data["questions"] = [q for q in data["questions"] if q["id"] not in new] + list(new.values())
    data.setdefault("pins", {})
    for qid in new:
        data["pins"][qid] = pin[:7]
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    page = page[:m.start(1)] + blob + page[m.end(1):]
    page = re.sub(r"\d+ draft questions", f"{len(data['questions'])} questions", page, count=1)
    page = re.sub(r"\d+ questions · corpus", f"{len(data['questions'])} questions · corpus", page, count=1)
    PAGE.write_text(page)
    print(f"{len(new)} questions added or replaced; the page now holds {len(data['questions'])}")


if __name__ == "__main__":
    main(sys.argv[1:])
