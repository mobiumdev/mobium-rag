import math

from mobium_rag.metrics import mrr, ndcg_at, recall_at, sections

GOLD = ["CHALLENGES#63", "CHALLENGES#106"]


def test_parts_count_as_their_section_once():
    assert sections(["CHALLENGES#63~1", "CHALLENGES#63~2", "docs/a.md#x"]) == ["CHALLENGES#63", "docs/a.md#x"]


def test_perfect_retrieval_scores_one():
    got = ["CHALLENGES#63", "CHALLENGES#106~2", "docs/a.md#x"]
    assert recall_at(got, GOLD, 5) == 1 and mrr(got, GOLD) == 1 and ndcg_at(got, GOLD, 5) == 1


def test_nothing_relevant_scores_zero():
    got = ["docs/a.md#x", "docs/b.md#y"]
    assert recall_at(got, GOLD, 5) == 0 and mrr(got, GOLD) == 0 and ndcg_at(got, GOLD, 5) == 0


def test_a_gold_section_past_k_is_not_counted():
    got = [f"docs/a.md#{i}" for i in range(5)] + ["CHALLENGES#63"]
    assert recall_at(got, GOLD, 5) == 0 and recall_at(got, GOLD, 6) == 0.5
    assert mrr(got, GOLD) == 1 / 6


def test_lower_ranks_score_less():
    first = ["CHALLENGES#63", "x#1", "x#2"]
    third = ["x#1", "x#2", "CHALLENGES#63"]
    assert ndcg_at(first, ["CHALLENGES#63"], 5) == 1
    assert math.isclose(ndcg_at(third, ["CHALLENGES#63"], 5), 1 / math.log2(4))
