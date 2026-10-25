from mobium_rag.checks import covered, grounded, identifiers, normalize, present, rarity

PASSAGE = ("`mobium shutdown` gives `adb emu kill` ten seconds; a frozen emulator was gone in 10.9 s. "
           "Wear's ✓ and ✕ are marked by their ids (`wear_alertdialog_positive_button`, `negative_button`).")


def test_identifiers_are_quoted_spans_numbers_and_code_names():
    ids = identifiers("Press 'Don't Allow', then run `mobium boot` with --for hidden; "
                      "UIA2.elementFor retries mSealed reads in TalkBack for 6 seconds.")
    assert ids == ["mobium boot", "Don't Allow", "6 seconds", "--for", "UIA2.elementFor", "mSealed", "TalkBack"]


def test_an_apostrophe_is_not_a_quote():
    assert identifiers("It isn't the app's fault.") == []


def test_numbers_match_whole_and_whatever_their_unit_or_spelling():
    hay = "it waited ten seconds, then 10.9 s, and 200ms between reads"
    hay = normalize(hay)
    assert present("10 seconds", hay) and present("10.9 seconds", hay) and present("200 ms", hay)
    assert not present("5", normalize("after 500 ms")) and not present("10", normalize("10.9 s"))


def test_an_identifier_its_passages_lack_is_missing():
    g = grounded("`mobium shutdown` waits 10 seconds, then `adb kill-server`.", [PASSAGE])
    assert g["found"] == ["mobium shutdown", "10 seconds"]
    assert g["missing"] == ["adb kill-server"]


def test_an_id_spelled_out_further_than_its_passage_is_missing():
    # The passage names `negative_button`; the full id is an inference, not a quote.
    g = grounded("Press `wear_alertdialog_negative_button` to dismiss.", [PASSAGE])
    assert g["missing"] == ["wear_alertdialog_negative_button"]


def test_the_questions_own_words_are_echoed_not_missing():
    g = grounded("Mobium supports HarmonyOS devices.", [PASSAGE], "Does Mobium support HarmonyOS devices?")
    assert g["echoed"] == ["HarmonyOS"] and g["missing"] == []


def test_a_token_common_in_the_corpus_is_evidence_of_nothing():
    common = rarity(["on iOS it", "iOS again", "and iOS", "rare_token here"], share=0.5)
    g = grounded("On iOS, `rare_token` and `other_token`.", ["rare_token"], common=common)
    assert g == {"common": ["iOS"], "found": ["rare_token"], "echoed": [], "missing": ["other_token"]}


def test_a_fact_is_covered_when_every_anchor_has_an_alternative():
    anchors = [["6 seconds", "six seconds"], ["300ms", "300 ms"]]
    assert covered("It retries for six seconds, 300 ms apart.", anchors) is True
    assert covered("It retries for six seconds.", anchors) is False
    assert covered("anything", []) is None
