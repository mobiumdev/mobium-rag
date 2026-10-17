"""Build the hand-labeling page from the stored answers.

Twenty answered, answerable questions, chosen with a fixed seed, each with
the answer and the passages it was given. A person marks whether every
claim is in the passages (faithful) and whether it answers the question
(relevant) — the two things the judge scores — and the page keeps the
marks in its own database, exported to review/labels.json for
`metajudge` to compare each judge with. Run from the repository root:

    uv run python review/build_labels.py            # the first page, with readings
    uv run python review/build_labels.py --blind    # a second 20, unlabeled ones, no readings
"""

import json
import random
import re
from pathlib import Path

from mobium_rag import corpus
from mobium_rag.evaluate import golden
from mobium_rag.generate import ANSWERS

N = 20
OUT = corpus.ROOT / "review" / "answer-labels.html"
TEMPLATE = corpus.ROOT / "review" / "answer-labels.template.html"
# Claude's claim-by-claim reading of each answer, shown collapsed beside it.
# The marks stay the person's; the report says the readings were shown.
READINGS = corpus.ROOT / "review" / "readings.json"
LABELS = corpus.ROOT / "review" / "labels.json"
BLIND_OUT = corpus.ROOT / "review" / "answer-labels-blind.html"
BLIND_INTRO = ("Twenty more of the generator's answers, not the twenty already labeled, and with no reading of "
               "Claude's anywhere on the page. For each, read the answer against the passages it was given and mark "
               "whether every claim in it is in those passages, and whether it answers the question. Your marks here "
               "are independent of a Claude judge; that is what this page is for.")


def items(seed: int = 0, exclude: set[str] = frozenset()) -> list[dict]:
    by_id = {p.id: p for p in corpus.load()}
    qs = {q["id"]: q for q in golden()}
    pool = []
    for line in ANSWERS.read_text().splitlines():
        a = json.loads(line)
        q = qs[a["id"]]
        if q["gold"] and a["answer"] and a["id"] not in exclude:  # what metajudge scores: answered, answerable
            pool.append({"id": a["id"], "question": q["question"], "answer": a["answer"],
                         "passages": [{"label": f"P{i + 1}", "id": p, "heading": by_id[p].heading,
                                       "text": by_id[p].text} for i, p in enumerate(a["passages"]) if p in by_id]})
    return sorted(random.Random(seed).sample(pool, min(N, len(pool))), key=lambda x: x["id"])


def main(argv: list[str]) -> None:
    """With --blind: a second page, of answers not yet labeled, chosen with
    another seed, and with no reading of Claude's on it — so its marks are
    independent of a Claude judge, and the coupling of the first set can be
    measured rather than guessed at."""
    blind = "--blind" in argv
    if blind:
        labeled = set(json.loads(LABELS.read_text())) if LABELS.exists() else set()
        its = items(seed=1, exclude=labeled)
        for it in its:
            it["reading"] = None
        out = BLIND_OUT
    else:
        readings = json.loads(READINGS.read_text()) if READINGS.exists() else {}
        its = items()
        for it in its:
            it["reading"] = readings.get(it["id"])
        out = OUT
    data = {"pin": corpus.PIN.read_text().strip()[:7], "blind": blind, "items": its}
    page = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if blind:
        page = page.replace("<title>Answer Labels</title>", "<title>Blind Answer Labels</title>", 1)
        page = page.replace("<h1>Answer Labels</h1>", "<h1>Blind Answer Labels</h1>", 1)
        page = re.sub(r'(<p class="sub" id="sub">).*?(</p>)', r"\1" + BLIND_INTRO + r"\2", page, count=1, flags=re.S)
    out.write_text(page)
    print(f"{len(data['items'])} items -> {out.relative_to(corpus.ROOT)}")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
