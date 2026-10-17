import json

from mobium_rag import metajudge


def test_report_compares_each_judge_with_the_labels(tmp_path, monkeypatch):
    # Judge a passes everything; judge b agrees with the person. The person
    # failed q2's faithfulness, so a passes one answer the person failed.
    scores = {"faithfulness": [[0.9, 0.8, 0.2], [0.9, 0.8, 0.2]], "relevancy": [[0.9, 0.9, 0.9], [0.9, 0.9, 0.9]]}
    saved = {"judges": ["a", "b"], "ids": ["q1", "q2", "q3"],
             "scores": {"a": {"faithfulness": [[0.9, 0.9, 0.9], [0.9, 0.9, 0.9]], "relevancy": scores["relevancy"]},
                        "b": {"faithfulness": [[0.9, 0.2, None], [0.9, 0.2, None]], "relevancy": scores["relevancy"]}},
             "controls": {"a": [], "b": []}}
    (tmp_path / "s.json").write_text(json.dumps(saved))
    (tmp_path / "l.json").write_text(json.dumps({"q1": {"faithful": True, "relevant": True},
                                                 "q2": {"faithful": False, "relevant": True}}))
    monkeypatch.setattr(metajudge, "SCORES", tmp_path / "s.json")
    monkeypatch.setattr(metajudge, "LABELS", tmp_path / "l.json")
    monkeypatch.setattr(metajudge, "BLIND", tmp_path / "missing-blind.json")
    monkeypatch.setattr(metajudge, "REPORT", tmp_path / "r.md")
    out = metajudge.report()
    assert "a person labeled 2 of these answers" in out
    assert "| every label | a | faithfulness | 1 of 2 | 0.00 | 1 of 1 |" in out
    assert "| every label | b | faithfulness | 2 of 2 | 1.00 | 0 of 1 |" in out
    assert "labeled blind" not in out  # no blind set yet


def test_a_blind_set_is_compared_on_its_own(tmp_path, monkeypatch):
    saved = {"judges": ["a"], "ids": ["q1", "q2", "q3"], "controls": {"a": []},
             "scores": {"a": {"faithfulness": [[0.9, 0.9, 0.1], [0.9, 0.9, 0.1]], "relevancy": [[0.9] * 3, [0.9] * 3]}}}
    (tmp_path / "s.json").write_text(json.dumps(saved))
    (tmp_path / "l.json").write_text(json.dumps({"q1": {"faithful": True, "relevant": True}}))
    (tmp_path / "b.json").write_text(json.dumps({"q2": {"faithful": False, "relevant": True},
                                                 "q3": {"faithful": False, "relevant": True}}))
    for name, f in (("SCORES", "s.json"), ("LABELS", "l.json"), ("BLIND", "b.json"), ("REPORT", "r.md")):
        monkeypatch.setattr(metajudge, name, tmp_path / f)
    out = metajudge.report()
    assert "| every label | a | faithfulness | 2 of 3 |" in out
    assert "| labeled with Claude's reading shown | a | faithfulness | 1 of 1 |" in out
    assert "| labeled blind | a | faithfulness | 1 of 2 |" in out


def test_report_without_labels_says_how_to_add_them(tmp_path, monkeypatch):
    saved = {"judges": ["a", "b"], "ids": ["q1"], "controls": {"a": [], "b": []},
             "scores": {m: {"faithfulness": [[0.9], [0.9]], "relevancy": [[0.9], [0.9]]} for m in ("a", "b")}}
    (tmp_path / "s.json").write_text(json.dumps(saved))
    monkeypatch.setattr(metajudge, "SCORES", tmp_path / "s.json")
    monkeypatch.setattr(metajudge, "LABELS", tmp_path / "missing.json")
    monkeypatch.setattr(metajudge, "BLIND", tmp_path / "missing-blind.json")
    monkeypatch.setattr(metajudge, "REPORT", tmp_path / "r.md")
    assert "No labels yet" in metajudge.report()


def test_a_judge_run_later_joins_the_record(tmp_path, monkeypatch):
    monkeypatch.setattr(metajudge, "SCORES", tmp_path / "s.json")
    monkeypatch.setattr(metajudge, "LABELS", tmp_path / "missing.json")
    monkeypatch.setattr(metajudge, "BLIND", tmp_path / "missing-blind.json")
    monkeypatch.setattr(metajudge, "REPORT", tmp_path / "r.md")
    one = {"faithfulness": [[0.9], [0.9]], "relevancy": [[0.9], [0.9]]}
    metajudge.save(["a", "b"], ["q1"], {"a": one, "b": one}, {"a": [], "b": []})
    metajudge.save(["claude-cli:h"], ["q1"], {"claude-cli:h": one}, {"claude-cli:h": []})
    saved = json.loads((tmp_path / "s.json").read_text())
    assert saved["judges"] == ["a", "b", "claude-cli:h"]
    out = metajudge.report()
    assert "| a, claude-cli:h | faithfulness |" in out and "| b, claude-cli:h | relevancy |" in out
    # Answers that changed start the record over.
    metajudge.save(["c"], ["q2"], {"c": one}, {"c": []})
    assert json.loads((tmp_path / "s.json").read_text())["judges"] == ["c"]
    assert "One judge" in metajudge.report()


def test_a_voted_score_is_the_median_of_its_votes():
    replies = iter([0.0, 1.0, 1.0, 1.0, None, 0.0, None, None, None])
    score = metajudge.voted(lambda *a: next(replies), 3)
    assert score("q") == 1.0          # 0, 1, 1: the majority passes
    assert score("q") == 0.5          # 1, unreadable, 0: the two read, halved
    assert score("q") is None         # nothing read
    assert metajudge.voted(len, 1) is len  # one vote is the judge as it was
