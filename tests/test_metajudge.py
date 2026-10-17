import math

from mobium_rag.metajudge import controls, kappa


def test_kappa():
    assert kappa([True, False, True, False], [True, False, True, False]) == 1
    assert kappa([True, True, False, False], [True, False, True, False]) == 0
    assert math.isnan(kappa([], []))
    assert kappa([True] * 4, [True] * 4) == 1  # agreement on a constant is not chance's


def test_a_lenient_judge_fails_its_controls():
    items = [{"question": "q", "answer": "a", "context": ["c"]}]
    lenient = controls(lambda q, a, c: 1.0, lambda q, a: 1.0, items, ["x"] * 10)
    strict = controls(lambda q, a, c: 0.0, lambda q, a: 0.0, items, ["x"] * 10)
    assert not any(c["ok"] for c in lenient) and all(c["ok"] for c in strict)
    assert {c["metric"] for c in lenient} == {"faithfulness", "relevancy"}


def test_an_unreadable_reply_is_counted_not_fatal():
    from mobium_rag.metajudge import safe, scored

    def broken(*args):
        raise ValueError("Invalid JSON: EOF while parsing")

    assert safe(broken)("q", "a", ["c"]) is None
    assert scored([0.5, None, 1.0]) == [0.5, 1.0]


def test_an_unreadable_control_is_not_a_pass():
    items = [{"question": "q", "answer": "a", "context": ["c"]}]
    out = controls(lambda q, a, c: None, lambda q, a: None, items, ["x"] * 10)
    assert not any(c["ok"] for c in out)
