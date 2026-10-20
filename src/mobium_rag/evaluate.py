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

from . import corpus, graph
from .metrics import mrr, ndcg_at, recall_at
from .retrieve import EMBED, RERANK, RERANK_BGE, Index

K = 5
FIRST_STAGE = 20
# Reciprocal rank fusion's constant, the usual one.
RRF_K = 60
# The bi-encoder's top passages whose cited neighbors join the candidates.
SEEDS = 5
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


def run(compare: bool = True) -> str:
    """The report. `compare` adds the graph, the ceilings and the other
    rerankers, each a reranking of every question and one a 2.2 GB model:
    `make retrieval` runs them, the gate leaves them out, since on CI's CPU
    they took the run past its 20 minutes."""
    pin = corpus.PIN.read_text().strip()
    passages = corpus.load()
    qs = [q for q in golden() if q["gold"]]
    ids = [p.id for p in passages]
    index = Index(passages, pin)

    edges = graph.build(passages)
    sections = sorted({corpus.section_of(i) for i in ids})
    random_edges = graph.shuffled(edges, sections)
    parts: dict[str, list[str]] = {}
    for i in ids:
        parts.setdefault(corpus.section_of(i), []).append(i)

    def expanded(question: str, hits: list[tuple[str, float]], g: dict[str, set[str]]) -> list[str]:
        cands = [pid for pid, _ in hits]
        for s in sorted(graph.neighbors(g, cands[:SEEDS])):
            cands += [i for i in parts[s] if i not in cands]
        return [pid for pid, _ in index.rerank(question, cands, K)]

    systems: dict[str, dict[str, list[str]]] = {
        "oracle (control)": {}, "random (control)": {}, "bi-encoder": {}, "two-stage": {}}
    if compare:
        systems |= {
            "two-stage + graph": {}, "two-stage + shuffled graph (control)": {}, "two-stage, 40 candidates (control)": {},
            "best reranking of 20 (ceiling)": {}, "best reranking of 40 (ceiling)": {},
            "two-stage, fused with first stage": {}, "two-stage, heading only (before)": {},
            "bge reranker, 20": {}, "bge reranker, 40": {}, "bge reranker, 40, fused": {}}

    def top(scores: dict[str, float]) -> list[str]:
        return [pid for pid, _ in sorted(scores.items(), key=lambda x: -x[1])[:K]]

    def fused(first: list[str], scores: dict[str, float]) -> list[str]:
        """Reciprocal rank fusion: each list's rank counts, neither list's score."""
        by_rr = sorted(first, key=lambda c: -scores[c])
        rrf = {c: 1 / (RRF_K + first.index(c) + 1) + 1 / (RRF_K + by_rr.index(c) + 1) for c in first}
        return top(rrf)

    def ceiling(cands: list[str], gold: list[str]) -> list[str]:
        """The best any reranker could do with these candidates: gold first."""
        g = [c for c in cands if corpus.section_of(c) in gold]
        return g + [c for c in cands if c not in g]
    rng = random.Random(0)
    best_sim: dict[str, float] = {}
    for q in qs + [q for q in golden() if not q["gold"]]:
        wide = index.search(q["question"], 2 * FIRST_STAGE)
        hits = wide[:FIRST_STAGE]
        best_sim[q["id"]] = hits[0][1]
        if not q["gold"]:
            continue
        systems["oracle (control)"][q["id"]] = q["gold"] + rng.sample(ids, K)
        systems["random (control)"][q["id"]] = rng.sample(ids, FIRST_STAGE)
        systems["bi-encoder"][q["id"]] = [pid for pid, _ in hits[:K]]
        systems["two-stage"][q["id"]] = [pid for pid, _ in index.rerank(q["question"], [pid for pid, _ in hits], K)]
        if not compare:
            continue
        systems["two-stage + graph"][q["id"]] = expanded(q["question"], hits, edges)
        systems["two-stage + shuffled graph (control)"][q["id"]] = expanded(q["question"], hits, random_edges)
        systems["two-stage, 40 candidates (control)"][q["id"]] = [pid for pid, _ in index.rerank(q["question"], [pid for pid, _ in wide], K)]
        first, first40 = [pid for pid, _ in hits], [pid for pid, _ in wide]
        mini = index.scores(q["question"], first)
        systems["best reranking of 20 (ceiling)"][q["id"]] = ceiling(first, q["gold"])
        systems["best reranking of 40 (ceiling)"][q["id"]] = ceiling(first40, q["gold"])
        systems["two-stage, fused with first stage"][q["id"]] = fused(first, mini)
        systems["two-stage, heading only (before)"][q["id"]] = top(index.scores(q["question"], first, with_path=False))
        bge = index.scores(q["question"], first40, RERANK_BGE, with_path=False)
        systems["bge reranker, 20"][q["id"]] = top({c: bge[c] for c in first})
        systems["bge reranker, 40"][q["id"]] = top(bge)
        systems["bge reranker, 40, fused"][q["id"]] = fused(first40, bge)

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

    if compare:
        compared(L, per, qs, edges, sections)
    else:
        L.append("\nThe graph, the ceilings and the other rerankers are left out of this run; "
                 "`make retrieval` measures them.")
    return finish(L, per, qs, systems, best_sim)


def compared(L: list[str], per: dict, qs: list[dict], edges: dict, sections: list[str]) -> None:
    L.append(f"\n## The docs' citations as a graph\n")
    L.append(f"{sum(len(v) for v in edges.values()) // 2} edges among {len(sections)} sections, read from "
             f"\"CHALLENGES N\", \"defect N\" and Markdown links (graph.py); the bi-encoder's top {SEEDS} "
             "add their cited neighbors to the reranker's candidates. Two controls: the same number of neighbors "
             f"chosen at random, and {2 * FIRST_STAGE} bi-encoder candidates with no graph.\n")
    L.append("| Against two-stage | Metric | Difference | 95% interval |")
    L.append("|---|---|---|---|")
    for name in ("two-stage + graph", "two-stage + shuffled graph (control)", "two-stage, 40 candidates (control)"):
        for key in ("recall@5", "mrr", "ndcg@5"):
            d, lo, hi = boot_diff([per["two-stage"][q["id"]][key] for q in qs], [per[name][q["id"]][key] for q in qs])
            L.append(f"| {name} | {key} | {d:+.3f} | {lo:+.3f} to {hi:+.3f} |")
    moved = [(q["id"], per["two-stage"][q["id"]]["recall@5"], per["two-stage + graph"][q["id"]]["recall@5"])
             for q in qs if per["two-stage"][q["id"]]["recall@5"] != per["two-stage + graph"][q["id"]]["recall@5"]]
    L.append("\nQuestions whose recall@5 the graph changed: " +
             (", ".join(f"{i} {a:.2f}→{b:.2f}" for i, a, b in moved) or "none") + ".")

    L.append("\n## Rerankers\n")
    L.append(f"The ceilings put every gold candidate first: no reranker of those candidates can do better. "
             f"Fused is reciprocal rank fusion (k={RRF_K}) of the first stage's ranking and the reranker's. "
             f"bge is `{RERANK_BGE[0]}` @{RERANK_BGE[1][:7]}, given the heading only, as it was measured. "
             "Two-stage reads each passage with its file named; heading only is how it read them before.\n")
    L.append("| Against two-stage | Metric | Difference | 95% interval |")
    L.append("|---|---|---|---|")
    for name in ("two-stage, heading only (before)", "two-stage, fused with first stage", "bge reranker, 20",
                 "bge reranker, 40", "bge reranker, 40, fused"):
        for key in ("recall@5", "mrr", "ndcg@5"):
            d, lo, hi = boot_diff([per["two-stage"][q["id"]][key] for q in qs], [per[name][q["id"]][key] for q in qs])
            L.append(f"| {name} | {key} | {d:+.3f} | {lo:+.3f} to {hi:+.3f} |")


def finish(L: list[str], per: dict, qs: list[dict], systems: dict, best_sim: dict) -> str:
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


# The regression gate's floors, one question under the run at the current
# pin (2026-10-19, corpus 7b590a4, the reranker given the file name:
# recall@5 0.818, MRR 0.768; heading only it was 0.786 and 0.745, under the
# old floors of 0.81 and 0.73). Before that (2026-10-12, corpus 663b4c8:
# recall@5 0.836, MRR 0.760). Retrieval is
# deterministic — pinned models, a pinned corpus — so a fall below either is a
# change, not noise. A new pin is a deliberate change to the corpus and moves
# the floors with it: at 5b27730 they were 0.85 and 0.75 (run 0.887, 0.792),
# and the one-bullet ROADMAP edit of mobiumdev/mobium#194 shifted the chunks
# after it enough to push two borderline gold sections out of the top 5.
# One question is 0.018 of recall@5, and one run in ten at this pin came back
# 0.818 (q003 missed; not reproduced in nine more, two from a fresh index), so
# the floors sit one question under the run rather than just under it.
FLOORS = {"recall@5": 0.80, "mrr": 0.75}


def gate() -> int:
    """`make ci`: the report, then a failure if a control scored as it must
    not or the two-stage retriever fell below a floor."""
    text = run(compare=False)
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
