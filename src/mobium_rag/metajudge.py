"""Phase 6: the judge, measured.

An LLM judge is a measurement, so it gets what any other measurement here
gets (PLAN.md): controls it must fail and pass before its numbers count,
a second judge to compare with, and the same answers scored twice to see
how much a score moves when nothing changed. Agreement with a person's
labels comes from the golden-set review, once there are labels.

Reads the answers phase 5 stored (data/answers.jsonl) and the passages each
was given, by id, so nothing is generated again.
"""

from __future__ import annotations

import json
import os
import random
from itertools import combinations
from statistics import mean
from typing import Any, Callable

from . import corpus
from .evaluate import K, golden, reviewed
from .answer import MODEL
from .generate import ANSWERS, _judge

# The 7-8B pair passed relevance and failed faithfulness's random-passages
# control (2026-10-11, data/judge-report-run2.md); the next pair is larger,
# and two families, so a swap is one. MOBIUM_RAG_JUDGES="a,b" picks others.
JUDGES = os.environ.get("MOBIUM_RAG_JUDGES", "qwen2.5:14b,mistral-small:24b").split(",")
REPORT = corpus.ROOT / "data" / "judge-report.md"
SCORES = corpus.ROOT / "data" / "judge-scores.json"
LABELS = corpus.ROOT / "review" / "labels.json"
# A second set, labeled with no reading of Claude's shown: the judges are
# compared with it on its own too, which measures the first set's coupling.
BLIND = corpus.ROOT / "review" / "labels-blind.json"
THRESHOLD = 0.5
REPEAT = 20


def kappa(a: list[bool], b: list[bool]) -> float:
    """Cohen's kappa for two raters' pass/fail on the same items: 1 when they
    agree on everything, 0 when they agree only as often as chance would."""
    n = len(a)
    if n == 0:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    pa, pb = sum(a) / n, sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def controls(faithful: Callable, relevant: Callable, items: list[dict], others: list[str]) -> list[dict[str, Any]]:
    """Three wrong answers per sampled item, each of which must score under
    the threshold, and the item's own answer, which should not."""
    rng = random.Random(0)
    out = []
    for it in items[:5]:
        q, a, ctx = it["question"], it["answer"], it["context"]
        out += [
            {"metric": "faithfulness", "case": "made-up answer", "must": "fail",
             "score": faithful(q, "Mobium does this by restarting the phone's Bluetooth stack and waiting for the "
                                  "airplane-mode toggle to settle, as Google recommends.", ctx)},
            {"metric": "faithfulness", "case": "its answer over random passages", "must": "fail",
             "score": faithful(q, a, rng.sample(others, K))},
            {"metric": "relevancy", "case": "the answer to another question", "must": "fail",
             "score": relevant(q, "Shut the daemon down first, then simulators, then emulators, then adb.")},
        ]
    for c in out:
        c["ok"] = c["score"] is not None and c["score"] < THRESHOLD
    return out


def safe(score: Callable[..., float]) -> Callable[..., float | None]:
    """A score, or None when the judge's reply could not be read — a reply
    that ran past its cap, or JSON it never closed. One such reply sank a
    run of hundreds; it is now a counted failure of the judge's."""
    def call(*args: Any) -> float | None:
        try:
            return score(*args)
        except Exception:
            return None

    return call


def scored(xs: list[float | None]) -> list[float]:
    return [x for x in xs if x is not None]


def items() -> list[dict]:
    by_id = {p.id: p for p in corpus.load()}
    qs = {q["id"]: q for q in golden()}
    out = []
    for line in ANSWERS.read_text().splitlines():
        a = json.loads(line)
        q = qs[a["id"]]
        if q["gold"] and a["answer"]:
            out.append({"id": a["id"], "question": q["question"], "answer": a["answer"],
                        "context": [by_id[p].text for p in a["passages"] if p in by_id]})
    return out


# A judge that samples gives a different verdict on the same answer: Haiku
# through `claude -p`, which has no temperature setting, flipped 8 of 20
# (run 4). MOBIUM_RAG_VOTES asks each score that many times and keeps the
# median — on pass and fail, the majority — under its own name, "<judge> ×N",
# so the single-vote run stays beside it in the report.
VOTES = int(os.environ.get("MOBIUM_RAG_VOTES", "1"))


def voted(score: Callable[..., float | None], n: int) -> Callable[..., float | None]:
    """A score asked n times, its median kept; replies that could not be
    read are left out, and none read at all is None."""
    if n <= 1:
        return score

    def call(*args: Any) -> float | None:
        got = sorted(x for x in (score(*args) for _ in range(n)) if x is not None)
        if not got:
            return None
        mid = len(got) // 2
        return got[mid] if len(got) % 2 else (got[mid - 1] + got[mid]) / 2

    return call


def run() -> str:
    its = items()
    others = [p.text for p in corpus.load()]
    scores: dict[str, dict[str, list[list[float]]]] = {}
    ctl: dict[str, list[dict]] = {}
    names = []
    for judge in JUDGES:
        faithful, relevant = _judge(judge)
        faithful, relevant = voted(safe(faithful), VOTES), voted(safe(relevant), VOTES)
        model = judge if VOTES <= 1 else f"{judge} ×{VOTES}"
        names.append(model)
        ctl[model] = controls(faithful, relevant, its, others)
        scores[model] = {"faithfulness": [], "relevancy": []}
        # Every answer once, then the first REPEAT again: the spread a score
        # shows when nothing changed. Two full passes for two judges was
        # most of two hours.
        for n in (len(its), REPEAT):
            scores[model]["faithfulness"].append([faithful(i["question"], i["answer"], i["context"]) for i in its[:n]])
            scores[model]["relevancy"].append([relevant(i["question"], i["answer"]) for i in its[:n]])

    save(names, [i["id"] for i in its], scores, ctl)
    return report()


def save(judges: list[str], ids: list[str], scores: dict, ctl: dict) -> None:
    """Keeps these judges' scores beside those of judges run before on the
    same answers, so a judge run later — a Claude model, after the local
    ones — joins one report rather than replacing it. Answers that changed
    start the record over."""
    kept: dict[str, Any] = {"judges": [], "ids": ids, "scores": {}, "controls": {}}
    if SCORES.exists():
        old = json.loads(SCORES.read_text())
        if old.get("ids") == ids:
            kept = old
    for m in judges:
        if m not in kept["judges"]:
            kept["judges"].append(m)
        kept["scores"][m], kept["controls"][m] = scores[m], ctl[m]
    SCORES.write_text(json.dumps(kept, indent=1))


def labels() -> dict[str, dict]:
    """A person's marks from the labeling pages, exported: question id to
    faithful and relevant, each true, false or missing; marks from the blind
    page carry blind=True."""
    out = json.loads(LABELS.read_text()) if LABELS.exists() else {}
    if BLIND.exists():
        for q, m in json.loads(BLIND.read_text()).items():
            out[q] = dict(m, blind=True)
    return out


def report() -> str:
    """The report from the stored scores, so labels made after a run are
    compared without scoring again."""
    saved = json.loads(SCORES.read_text())
    judges, ids, scores, ctl = saved["judges"], saved["ids"], saved["scores"], saved["controls"]
    # A label is of the answer it was made on: once that answer is written
    # again, differently, the label says nothing about the one scored here.
    # The answers are not committed, so a clone without them cannot tell.
    now = ({a["id"]: a["answer"] for a in map(json.loads, ANSWERS.read_text().splitlines())}
           if ANSWERS.exists() else None)
    marks = labels()
    stale = sorted(q for q, m in marks.items() if now is not None and "answer" in m and m["answer"] != now.get(q))
    marks = {q: m for q, m in marks.items() if q not in stale}
    labeled = sum(1 for i in ids if i in marks)
    L = ["# The judge, measured\n",
         f"{len(ids)} answered questions the docs cover, from phase 5's answers; each scored once by each judge, "
         f"and the first {REPEAT} a second time. Faithfulness weighs the answer against at most 15 facts drawn "
         "from its passages. "
         f"The golden set is {reviewed(golden())}; a person labeled {labeled} of these answers — some with Claude's "
         "claim-by-claim reading of each shown beside it (review/readings.json), some blind, with none — and "
         "each set is compared on its own below."
         + (f" Left out: {len(stale)} labels of an answer since written again ({', '.join(stale)}); "
            "`python review/build_labels.py --relabel` makes the page to label them again." if stale else "")
         + "\n",
         "## Controls\n", "| Judge | Passed | Failed |", "|---|---|---|"]
    for m in judges:
        bad = [c for c in ctl[m] if not c["ok"]]
        L.append(f"| {m} | {len(ctl[m]) - len(bad)} of {len(ctl[m])} | "
                 + ("; ".join(f"{c['metric']}, {c['case']}: " + ("unreadable" if c["score"] is None else f"{c['score']:.2f}")
                              for c in bad) or "none") + " |")
    trusted = {m: {met for met in ("faithfulness", "relevancy")
                   if all(c["ok"] for c in ctl[m] if c["metric"] == met)} for m in judges}

    L.append("\n## Scores, and how much they move\n")
    L.append("| Judge | Metric | Mean | Same answer scored again: mean change | Pass/fail flips | Replies unreadable |")
    L.append("|---|---|---|---|---|---|")
    for m in judges:
        for met in ("faithfulness", "relevancy"):
            r1, r2 = scores[m][met]
            pairs = [(x, y) for x, y in zip(r1, r2) if x is not None and y is not None]
            flips = sum((x >= THRESHOLD) != (y >= THRESHOLD) for x, y in pairs)
            note = "" if met in trusted[m] else " (failed a control: not trusted)"
            lost = sum(x is None for x in r1 + r2)
            L.append(f"| {m} | {met}{note} | {mean(scored(r1)):.3f} | {mean(abs(x - y) for x, y in pairs):.3f} | "
                     f"{flips} of {len(pairs)} | {lost} |")

    L.append("\n## The judges against each other\n")
    if len(judges) < 2:
        L.append("One judge: nothing to compare it with.")
    else:
        L.append("| Judges | Metric | Agree on pass/fail | Cohen's kappa | Mean difference (second − first) |")
        L.append("|---|---|---|---|---|")
        for a, b in combinations(judges, 2):
            for met in ("faithfulness", "relevancy"):
                both = [(x, y) for x, y in zip(scores[a][met][0], scores[b][met][0])
                        if x is not None and y is not None]
                pa, pb = [x >= THRESHOLD for x, _ in both], [y >= THRESHOLD for _, y in both]
                diff = f"{mean(y - x for x, y in both):+.3f}" if both else "—"
                L.append(f"| {a}, {b} | {met} | {sum(x == y for x, y in zip(pa, pb))} of {len(both)} | "
                         f"{kappa(pa, pb):.2f} | {diff} |")
    mine = [m for m in judges if m == MODEL]
    L.append(f"\n{MODEL} wrote the answers" + (f", so {mine[0]} judges its own words." if mine else
                                               "; no judge here did."))

    L.append("\n## Each judge against a person\n")
    if not labeled:
        L.append("No labels yet: label the answers on the labeling page, export them to review/labels.json, "
                 "and run `python -m mobium_rag.metajudge report`.")
    else:
        key = {"faithfulness": "faithful", "relevancy": "relevant"}
        sets = [("every label", lambda q: True)]
        if any(m.get("blind") for m in marks.values()):
            sets += [("labeled with Claude's reading shown", lambda q: not marks[q].get("blind")),
                     ("labeled blind", lambda q: bool(marks[q].get("blind")))]
        L.append("| Labels | Judge | Metric | Agrees with the person | Cohen's kappa | Judge passes what the person failed |")
        L.append("|---|---|---|---|---|---|")
        for name, keep in sets:
            for m in judges:
                for met in ("faithfulness", "relevancy"):
                    pairs = [(x >= THRESHOLD, marks[i][key[met]]) for i, x in zip(ids, scores[m][met][0])
                             if x is not None and isinstance(marks.get(i, {}).get(key[met]), bool) and keep(i)]
                    j, p = [a for a, _ in pairs], [b for _, b in pairs]
                    L.append(f"| {name} | {m} | {met} | {sum(a == b for a, b in pairs)} of {len(pairs)} | "
                             f"{kappa(j, p):.2f} | {sum(a and not b for a, b in pairs)} of {sum(not b for b in p)} |")
    REPORT.write_text("\n".join(L) + "\n")
    return REPORT.read_text()


if __name__ == "__main__":
    import sys

    print(report() if sys.argv[1:] == ["report"] else run())
