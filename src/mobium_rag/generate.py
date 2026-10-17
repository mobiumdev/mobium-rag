"""Phase 5: answers over the golden set, measured.

Deterministic only, as the plan orders it: whether each question was
answered or refused as it should be, and whether its citations name the
gold sections. The answers are stored, and the judged metrics —
faithfulness and relevance — are scored from them in phase 6
(metajudge.py), by two judges, each behind its controls; a judging failure
never costs a generation run.
"""

from __future__ import annotations

import json
from statistics import mean
from typing import Any

from . import claudecli, corpus
from .answer import MODEL, Answer, answer, ollama_chat
from .corpus import section_of
from .evaluate import FIRST_STAGE, K, golden, reviewed

REPORT = corpus.ROOT / "data" / "generation-report.md"
TRUTHS = 15
ANSWERS = corpus.ROOT / "data" / "answers.jsonl"


def refusal_scores(rows: list[tuple[dict, Answer]]) -> dict[str, Any]:
    """Unanswerable questions refused, and answerable ones not."""
    una = [a for q, a in rows if not q["gold"]]
    ans = [a for q, a in rows if q["gold"]]
    return {
        "refused_unanswerable": sum(a.refused for a in una), "unanswerable": len(una),
        "refused_answerable": sum(a.refused for a in ans), "answerable": len(ans),
    }


def citation_scores(q: dict, a: Answer) -> dict[str, float] | None:
    """For an answered, answerable question: the share of cited sections
    that are gold (precision) and of gold sections cited (recall)."""
    if a.refused or not q["gold"]:
        return None
    cited = {section_of(c) for c in a.citations}
    precision = len(cited & set(q["gold"])) / len(cited) if cited else 0.0
    recall = len(cited & set(q["gold"])) / len(q["gold"])
    return {"precision": precision, "recall": recall}


def _judge(model: str):
    from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
    from deepeval.models import OllamaModel
    from deepeval.test_case import LLMTestCase

    # Ollama's default window cuts five passages short, and DeepEval first
    # lists every fact in them: uncapped, one call ran past five minutes. A
    # window that holds them, a cap on what one reply may run to, and at most
    # TRUTHS facts drawn from the passages per score (measured 2026-10-11:
    # about 20 s a faithfulness score, 5 s a relevance score).
    # A Claude model through Claude Code's command line, signed in, with no
    # API key: the same metrics, reached another way (claudecli.py).
    judge: Any
    if model.startswith(claudecli.PREFIX):
        judge = claudecli.ClaudeCLI(model[len(claudecli.PREFIX):])
    else:
        judge = OllamaModel(model=model, temperature=0, generation_kwargs={"num_ctx": 16384, "num_predict": 2048})

    def faithful(question: str, output: str, context: list[str]) -> float:
        # A claim the passages do not support must count against the answer,
        # not only one they contradict: by default DeepEval scored "Mobium
        # restarts the phone's Bluetooth stack" 1.00 faithful to passages that
        # never mention Bluetooth, for both judges (phase 6, 2026-10-11).
        m = FaithfulnessMetric(model=judge, async_mode=False, include_reason=False, truths_extraction_limit=TRUTHS,
                               penalize_ambiguous_claims=True)
        m.measure(LLMTestCase(input=question, actual_output=output, retrieval_context=context))
        return float(m.score)

    def relevant(question: str, output: str) -> float:
        m = AnswerRelevancyMetric(model=judge, async_mode=False, include_reason=False)
        m.measure(LLMTestCase(input=question, actual_output=output))
        return float(m.score)

    return faithful, relevant


def run(limit: int | None = None) -> str:
    from .retrieve import Index

    passages = corpus.load()
    pin = corpus.PIN.read_text().strip()
    index = Index(passages, pin)
    chat = ollama_chat()
    qs = golden()[:limit] if limit else golden()
    rows: list[tuple[dict, Answer]] = []
    contexts: dict[str, list[str]] = {}
    for q in qs:
        hits = index.search(q["question"], FIRST_STAGE)
        top = index.rerank(q["question"], [pid for pid, _ in hits], K)
        given = [(pid, index.by_id[pid].text) for pid, _ in top]
        contexts[q["id"]] = [t for _, t in given]
        rows.append((q, answer(q["question"], given, chat)))
    with ANSWERS.open("w") as f:
        for q, a in rows:
            f.write(json.dumps({"id": q["id"], "answer": a.answer, "citations": a.citations,
                                "invalid": a.invalid_citations, "passages": a.passages}) + "\n")

    return report(rows)


def stored() -> list[tuple[dict, Answer]]:
    """The answers a run kept, paired with their questions."""
    qs = {q["id"]: q for q in golden()}
    rows = []
    for line in ANSWERS.read_text().splitlines():
        a = json.loads(line)
        rows.append((qs[a["id"]], Answer(qs[a["id"]]["question"], a["answer"], a["citations"],
                                         a.get("invalid", []), a["passages"])))
    return rows


def report(rows: list[tuple[dict, Answer]]) -> str:
    ref = refusal_scores(rows)
    cites = [c for q, a in rows if (c := citation_scores(q, a))]
    invalid = sum(len(a.invalid_citations) for _, a in rows)
    L = ["# Generation\n",
         f"Answers from `{MODEL}` through Ollama, temperature 0, over the reranked top {K} of {FIRST_STAGE}. "
         f"{len(rows)} questions, {reviewed([q for q, _ in rows])}.\n",
         "## Answered or refused\n",
         f"- Not in the docs, refused: **{ref['refused_unanswerable']} of {ref['unanswerable']}** (each one not refused is an answer made up).",
         f"- In the docs, refused anyway: {ref['refused_answerable']} of {ref['answerable']}.\n",
         "## Citations, over answered questions the docs cover\n",
         (f"- Precision {mean(c['precision'] for c in cites):.3f}, recall {mean(c['recall'] for c in cites):.3f}, over {len(cites)} answers."
          if cites else "- No answers to score."),
         f"- Citations to a passage the model was not given: {invalid} (dropped).\n",
         "## Judged\n",
         "Faithfulness and relevance are scored from these stored answers in phase 6 (`make judge`), "
         "by two judges, each only after its controls."]
    REPORT.write_text("\n".join(L) + "\n")
    return REPORT.read_text()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["report"]:
        print(report(stored()))
    else:
        print(run(int(sys.argv[1]) if len(sys.argv) > 1 else None))
