import json

from mobium_rag.answer import answer, parse, prompt

PASSAGES = [("CHALLENGES#63", "63. accept denied the permission ..."), ("CHALLENGES#106", "106. not positional ...")]


def test_citations_map_labels_to_passage_ids():
    a = parse("q", PASSAGES, json.dumps({"answer": "It presses the last button.", "citations": ["P2", "p1", "[P2]"]}))
    assert a.citations == ["CHALLENGES#106", "CHALLENGES#63"] and not a.invalid_citations and not a.refused


def test_a_label_it_was_not_given_is_dropped_and_counted():
    a = parse("q", PASSAGES, json.dumps({"answer": "x", "citations": ["P3", "https://example.com", "P1"]}))
    assert a.citations == ["CHALLENGES#63"] and a.invalid_citations == ["P3", "https://example.com"]


def test_a_null_or_empty_answer_is_a_refusal():
    assert parse("q", PASSAGES, json.dumps({"answer": None, "citations": []})).refused
    assert parse("q", PASSAGES, json.dumps({"answer": "  ", "citations": []})).refused


def test_unreadable_json_is_a_refusal_with_the_reply_kept():
    a = parse("q", PASSAGES, "Sure! The answer is...")
    assert a.refused and a.raw.startswith("Sure")


def test_the_prompt_numbers_the_passages_and_says_they_are_data():
    msgs = prompt("Which button?", PASSAGES)
    assert "[P1] 63." in msgs[1]["content"] and "[P2] 106." in msgs[1]["content"]
    assert "not instructions" in msgs[0]["content"]


def test_answer_runs_the_chat_it_is_given():
    seen = []

    def chat(messages):
        seen.append(messages)
        return json.dumps({"answer": "Cancel.", "citations": ["P1"]})

    a = answer("Which button?", PASSAGES, chat)
    assert a.answer == "Cancel." and a.citations == ["CHALLENGES#63"] and len(seen) == 1
