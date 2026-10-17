"""Phases 3 and 4: retrieval, one stage and two, against the golden set.

Every metric is shown it can come back high and low before a number is
reported (PLAN.md, "The rule the evaluation is built on"): a perfect
retriever must score 1 and a random one near 0. A difference between two
retrievers is paired by question and bootstrapped, with its interval.
"""

from __future__ import annotations

import json
import random
from statistics import mean

from . import corpus
from .metrics import mrr, ndcg_at, recall_at
from .retrieve import EMBED, RERANK, Index

K = 5
FIRST_STAGE = 20
GOLDEN = corpus.ROOT / "data" / "golden.jsonl"
REPORT = corpus.ROOT / "data" / "retrieval-report.md"


def golden() -> list[dict]:
    return [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]


def reviewed(qs: list[dict]) -> str:
    """How much of the golden set a person has reviewed, for a report."""
    n = sum(q.get("status") == "reviewed" for q in qs)
    if n == len(qs):
        return "all reviewed by a person"
    return f"{n} reviewed by a person, {len(qs) - n} `draft` — written by a model and not yet trusted"


def score(ranked: list[str], gold: list[str]) -> dict[str, float]:
    return {"recall@5": recall_at(ranked, gold, K), "mrr": mrr(ranked, gold), "ndcg@5": ndcg_at(ranked, gold, K)}


def boot_diff(a: list[float], b: list[float], n: int = 4000, seed: int = 0) -> tuple[float, float, float]:
    """Mean of b − a over questions, and its 95% interval."""
    d = [y - x for x, y in zip(a, b)]
    rng = random.Random(seed)
    s = sorted(mean(rng.choice(d) for _ in d) for _ in range(n))
    return mean(d), s[int(0.025 * n)], s[int(0.975 * n) - 1]


def run() -> str:
    pin = corpus.PIN.read_text().strip()
    passages = corpus.load()
    qs = [q for q in golden() if q["gold"]]
    ids = [p.id for p in passages]
    index = Index(passages, pin)

    systems: dict[str, dict[str, list[str]]] = {"oracle (control)": {}, "random (control)": {}, "bi-encoder": {}, "two-stage": {}}
    rng = random.Random(0)
    best_sim: dict[str, float] = {}
    for q in qs + [q for q in golden() if not q["gold"]]:
        hits = index.search(q["question"], FIRST_STAGE)
        best_sim[q["id"]] = hits[0][1]
        if not q["gold"]:
            continue
        systems["oracle (control)"][q["id"]] = q["gold"] + rng.sample(ids, K)
        systems["random (control)"][q["id"]] = rng.sample(ids, FIRST_STAGE)
        systems["bi-encoder"][q["id"]] = [pid for pid, _ in hits[:K]]
        systems["two-stage"][q["id"]] = [pid for pid, _ in index.rerank(q["question"], [pid for pid, _ in hits], K)]

    per = {name: {q["id"]: score(r[q["id"]], q["gold"]) for q in qs} for name, r in systems.items()}
    L = ["# Retrieval\n",
         f"Corpus: Mobium's public docs at `{pin[:7]}`, {len(passages)} passages. Embedding `{EMBED[0]}` "
         f"@{EMBED[1][:7]}; reranker `{RERANK[0]}` @{RERANK[1][:7]}. Two-stage: {FIRST_STAGE} candidates "
         f"from the bi-encoder, reranked to {K}.\n",
         f"**Golden set: {len(golden())} questions, {reviewed(golden())}.** "
         f"{len(qs)} have gold sections; {len(golden()) - len(qs)} unanswerable, for generation.\n",
         "| Retriever | recall@5 | MRR | nDCG@5 |", "|---|---|---|---|"]
    for name in systems:
        m = per[name]
        L.append(f"| {name} | " + " | ".join(f"{mean(v[key] for v in m.values()):.3f}" for key in ("recall@5", "mrr", "ndcg@5")) + " |")
    ok = all(mean(v[k] for v in per["oracle (control)"].values()) == 1 for k in ("recall@5", "mrr", "ndcg@5")) and \
        all(mean(v[k] for v in per["random (control)"].values()) < 0.1 for k in ("recall@5", "mrr", "ndcg@5"))
    L.append(f"\nControls: {'the perfect retriever scores 1 and the random one under 0.1 on every metric — the metrics can move both ways.' if ok else '**a control did not score as it must: the metrics are not trusted.**'}\n")

    L.append("## Two-stage against one\n")
    L.append("| Metric | Difference | 95% interval |")
    L.append("|---|---|---|")
    for key in ("recall@5", "mrr", "ndcg@5"):
        a = [per["bi-encoder"][q["id"]][key] for q in qs]
        b = [per["two-stage"][q["id"]][key] for q in qs]
        d, lo, hi = boot_diff(a, b)
        L.append(f"| {key} | {d:+.3f} | {lo:+.3f} to {hi:+.3f} |")

    L.append("\n## By kind\n")
    L.append("| Kind | Questions | bi-encoder recall@5 | two-stage recall@5 |")
    L.append("|---|---|---|---|")
    for kind in ("fact", "multi"):
        sub = [q for q in qs if q["kind"] == kind]
        L.append(f"| {kind} | {len(sub)} | {mean(per['bi-encoder'][q['id']]['recall@5'] for q in sub):.3f} | "
                 f"{mean(per['two-stage'][q['id']]['recall@5'] for q in sub):.3f} |")

    ans = [best_sim[q["id"]] for q in qs]
    una = [best_sim[q["id"]] for q in golden() if not q["gold"]]
    L.append("\n## How close the nearest passage is\n")
    L.append(f"Answerable questions: median best similarity {sorted(ans)[len(ans) // 2]:.3f} (min {min(ans):.3f}); "
             f"unanswerable: median {sorted(una)[len(una) // 2]:.3f} (max {max(una):.3f}). "
             "Whether a threshold can tell them apart is for the generation phase, which must refuse the second kind.\n")

    L.append("## Questions the two-stage retriever missed entirely\n")
    for q in qs:
        if per["two-stage"][q["id"]]["recall@5"] == 0:
            L.append(f"- {q['id']} ({q['kind']}): {q['question']} — gold {', '.join(q['gold'])}; got "
                     f"{', '.join(systems['two-stage'][q['id']][:3])}")
    REPORT.write_text("\n".join(L) + "\n")
    return REPORT.read_text()


# The regression gate's floors, just under the run at the current pin
# (2026-10-12, corpus 663b4c8: recall@5 0.836, MRR 0.760): retrieval is
# deterministic — pinned models, a pinned corpus — so a fall below either is a
# change, not noise. A new pin is a deliberate change to the corpus and moves
# the floors with it: at 5b27730 they were 0.85 and 0.75 (run 0.887, 0.792),
# and the one-bullet ROADMAP edit of mobiumdev/mobium#194 shifted the chunks
# after it enough to push two borderline gold sections out of the top 5.
# One question is 0.018 of recall@5, and one run in ten at this pin came back
# 0.818 (q003 missed; not reproduced in nine more, two from a fresh index), so
# the floors sit one question under the run rather than just under it.
FLOORS = {"recall@5": 0.81, "mrr": 0.73}


def gate() -> int:
    """`make ci`: the report, then a failure if a control scored as it must
    not or the two-stage retriever fell below a floor."""
    text = run()
    print(text)
    failed = []
    if "the metrics can move both ways" not in text:
        failed.append("a control did not score as it must")
    row = next(line for line in text.splitlines() if line.startswith("| two-stage |"))
    recall, mrr_ = (float(x) for x in row.strip("|").split("|")[1:3])
    for name, got in (("recall@5", recall), ("mrr", mrr_)):
        if got < FLOORS[name]:
            failed.append(f"{name} {got:.3f} is under its floor {FLOORS[name]}")
    for f in failed:
        print(f"GATE: {f}")
    print("GATE: passed" if not failed else "GATE: failed")
    return 1 if failed else 0


if __name__ == "__main__":
    import sys

    sys.exit(gate() if sys.argv[1:] == ["gate"] else (print(run()) or 0))
