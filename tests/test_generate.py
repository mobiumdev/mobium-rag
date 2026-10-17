from mobium_rag.answer import Answer
from mobium_rag.generate import citation_scores, refusal_scores

ANS = {"id": "q1", "gold": ["CHALLENGES#63", "CHALLENGES#106"]}
UNA = {"id": "q2", "gold": []}


def _a(text, cites=()):
    return Answer("q", text, list(cites))


def test_refusals_are_counted_per_kind():
    rows = [(UNA, _a(None)), (UNA, _a("Yes, it supports it.")), (ANS, _a(None)), (ANS, _a("x", ["CHALLENGES#63"]))]
    assert refusal_scores(rows) == {"refused_unanswerable": 1, "unanswerable": 2, "refused_answerable": 1, "answerable": 2}


def test_citations_score_against_gold_sections():
    c = citation_scores(ANS, _a("x", ["CHALLENGES#63~2", "docs/a.md#x"]))
    assert c == {"precision": 0.5, "recall": 0.5}
    assert citation_scores(ANS, _a("x", [])) == {"precision": 0.0, "recall": 0.0}


def test_a_refusal_or_an_unanswerable_question_has_no_citation_score():
    assert citation_scores(ANS, _a(None)) is None
    assert citation_scores(UNA, _a("x", ["docs/a.md#x"])) is None
