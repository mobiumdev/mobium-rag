"""Phase 6b, step 2: checks with no judge (PLAN.md).

Two lookups over the stored answers, repeatable by construction:

- **Identifiers.** Every backticked token, quoted string, number, code name
  and flag in an answer must appear in the passages it was given. One that
  does not is a claim with nothing under it — the kind of thing a judge
  scored 0.5 to 1.0 faithful to random passages (phase 6, run 2).
- **Key-fact anchors.** Each key fact's anchors are tokens a right answer
  must contain, each a list of alternatives; a fact is covered when every
  anchor has one alternative in the answer. A fact with no anchor is not
  checkable here and is left to the judge. Anchors are drafted from the
  facts (`draft`) and count only once a person has reviewed them.

Repeatable is not right: both are measured against the person's labels,
like any judge.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any, Callable

from . import corpus
from .evaluate import golden
from .generate import ANSWERS
from .metajudge import kappa, labels

REPORT = corpus.ROOT / "data" / "checks-report.md"
ANCHORS = corpus.ROOT / "data" / "key-fact-anchors.json"
FACTS = corpus.ROOT / "data" / "key-facts-draft.json"
PLANTED = "It does this through `app_bluetooth_reset`."
# A token in this share of passages or more is found whatever the passages:
# held to every identifier, the answers over random passages were flagged 46
# times of 57; at 2%, 22 of 23, the one left a random draw that had the
# token (2026-10-24, the report's controls).
COMMON = 0.02

_BACKTICK = re.compile(r"`([^`\n]+)`")                           # `app_fill`
_DOUBLE = re.compile(r"\"([^\"\n]{2,60})\"")                      # "iPhone 17 Pro"
_SINGLE = re.compile(r"(?<![\w])'((?:[^'\n]|'(?=\w))+?)'(?![\w])")  # 'Don't Allow', apostrophe kept
_NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?:\s?(?:ms|s|seconds?|minutes?|%))?(?![\w.]*\w)")
_CODE = re.compile(
    r"--[a-z][\w-]*"                                             # --for
    r"|\b[A-Za-z]\w*(?:[._:]\w+)+\b"                             # UIA2.elementFor, value_scale, secret:NAME
    r"|\b[a-z]+[A-Z]\w*\b"                                       # mSealed
    r"|\b[A-Z][a-z]+[A-Z]\w*\b")                                 # TalkBack, UiAutomator2


_WORDS = {w: str(n) for n, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
_UNIT = re.compile(r"\s?(?:ms|s|seconds?|minutes?|%)$")


def straight(text: str) -> str:
    return text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')


def normalize(text: str) -> str:
    """Case, curly quotes, markdown emphasis, runs of white space and a
    number written as a word ("ten seconds") don't make a token a different
    token."""
    text = re.sub(r"\s+", " ", re.sub(r"[`*]", "", straight(text))).strip().lower()
    return re.sub(r"\b(" + "|".join(_WORDS) + r")\b", lambda m: _WORDS[m.group(1)], text)


def quoted(text: str) -> list[str]:
    """Spans in backticks or quotes. A single-quoted span is only taken
    when the quote is not an apostrophe inside it ('Don't Allow')."""
    t = straight(text)
    out = _BACKTICK.findall(t) + _DOUBLE.findall(t) + _SINGLE.findall(t)
    return [s.strip() for s in out if s.strip()]


def identifiers(text: str) -> list[str]:
    """The tokens of an answer a passage can be held to, in order, once each."""
    found = quoted(text)
    plain = re.sub(r"`[^`\n]+`", " ", text)                      # a number inside a command is the command's
    found += [m.group(0).strip() for m in _NUMBER.finditer(plain)]
    found += _CODE.findall(plain)
    seen, out = set(), []
    for tok in found:
        key = normalize(tok)
        if key and key not in seen:
            seen.add(key)
            out.append(tok)
    return out


def present(token: str, haystack: str) -> bool:
    """A token in normalized text: a number or a word as a whole token, so
    "5" is not found in "500"; anything with punctuation as a substring. A
    number's unit is not held to: 10.9 seconds is 10.9 s is 10.9s."""
    t = normalize(token)
    if re.fullmatch(r"\d+(?:\.\d+)?(?:" + _UNIT.pattern + ")?", t):
        n = _UNIT.sub("", t)
        return re.search(rf"(?<![\d.]){re.escape(n)}(?!\d|\.\d)", haystack) is not None
    if re.fullmatch(r"[\w.]+", t):
        return re.search(rf"(?<![\w.]){re.escape(t)}(?![\w]|\.\d)", haystack) is not None
    return t in haystack


def grounded(answer: str, passages: list[str], question: str = "",
             common: Callable[[str], bool] = lambda t: False) -> dict[str, list[str]]:
    """An answer's identifiers sorted four ways: common across the corpus
    (`iOS`, `map`, `1`: in a passage whatever the passage, so evidence of
    nothing), in its passages, only in the question (repeated, not
    introduced: "Does Mobium support HarmonyOS?" gives the answer HarmonyOS
    whether or not it is true), and in none of these."""
    hay, asked = normalize("\n".join(passages)), normalize(question)
    out: dict[str, list[str]] = {"common": [], "found": [], "echoed": [], "missing": []}
    for t in identifiers(answer):
        kind = ("common" if common(t) else "found" if present(t, hay)
                else "echoed" if present(t, asked) else "missing")
        out[kind].append(t)
    return out


def rarity(passages: list[str], share: float = COMMON) -> Callable[[str], bool]:
    """Whether a token is in at least `share` of the corpus's passages."""
    hays = [normalize(t) for t in passages]
    seen: dict[str, bool] = {}

    def common(token: str) -> bool:
        if token not in seen:
            seen[token] = sum(present(token, h) for h in hays) >= share * len(hays)
        return seen[token]

    return common


def draft_anchors(fact: str, common: Callable[[str], bool] = lambda t: False) -> list[list[str]]:
    """A first guess at a fact's anchors: its identifiers rare in the corpus,
    each its only alternative. A person prunes them to what a right answer
    must say, adds alternatives and word anchors, or empties the list."""
    return [[t] for t in identifiers(fact) if not common(t)]


def covered(answer: str, anchors: list[list[str]]) -> bool | None:
    """Every anchor has an alternative in the answer; None when there is
    nothing to check."""
    if not anchors:
        return None
    hay = normalize(answer)
    return all(any(present(alt, hay) for alt in alts) for alts in anchors)


def write_draft_anchors() -> None:
    """Anchors for every fact not yet given any, marked draft; a reviewed
    entry is never rewritten."""
    facts = json.loads(FACTS.read_text())
    common = rarity([p.text for p in corpus.load()])
    kept = json.loads(ANCHORS.read_text()) if ANCHORS.exists() else {}
    for q, entry in facts.items():
        old = kept.get(q, [])
        if old and any(f.get("status") == "reviewed" for f in old):
            continue
        kept[q] = [{"fact": f, "anchors": draft_anchors(f, common), "status": "draft"} for f in entry["facts"]]
    ANCHORS.write_text(json.dumps(kept, indent=1, ensure_ascii=False) + "\n")


def rows() -> list[dict[str, Any]]:
    by_id = {p.id: p for p in corpus.load()}
    qs = {q["id"]: q for q in golden()}
    anchors = json.loads(ANCHORS.read_text()) if ANCHORS.exists() else {}
    others = [p.text for p in by_id.values()]
    rng = random.Random(0)
    common = rarity(others)
    out = []
    for line in ANSWERS.read_text().splitlines():
        a = json.loads(line)
        q = qs[a["id"]]
        if not (q["gold"] and a["answer"]):
            continue
        given = [by_id[p].text for p in a["passages"] if p in by_id]
        g = grounded(a["answer"], given, q["question"], common)
        facts = [(f["status"], covered(a["answer"], f["anchors"])) for f in anchors.get(a["id"], [])]
        # The controls: the same answer over random passages, and with an
        # identifier no passage has, must both be flagged.
        shuffled = grounded(a["answer"], rng.sample(others, len(given)), q["question"], common)
        planted = grounded(a["answer"] + " " + PLANTED, given, q["question"], common)
        # Only an answer holding a token of its own, not the question's, can be
        # flagged over random passages: one the question has is echoed there.
        own = any(not present(t, normalize(q["question"])) for t in g["found"])
        out.append({"id": a["id"], "answer": a["answer"], **g, "facts": facts,
                    "control_random": bool(shuffled["missing"]) if own else None,
                    "control_planted": bool(planted["missing"])})
    return out


def report() -> str:
    rs = rows()
    marks = labels()
    now = {r["id"]: r["answer"] for r in rs}
    marks = {q: m for q, m in marks.items() if q in now and m.get("answer", now[q]) == now[q]}
    flagged = [r for r in rs if r["missing"]]
    with_ids = [r for r in rs if r["found"] or r["echoed"] or r["missing"]]
    echoed = [r for r in rs if r["echoed"] and not r["missing"]]
    L = ["# Checks with no judge\n",
         f"{len(rs)} answered questions the docs cover, from phase 5's answers. Every identifier in an answer — "
         "backticked, quoted, a number, a code name, a flag — looked for in the passages it was given "
         "(`checks.py`). Repeatable by construction; measured against the person's labels below, like any judge.\n",
         "## Controls\n",
         f"- An identifier no passage has, added to each answer, flagged: **{sum(r['control_planted'] for r in rs)} "
         f"of {len(rs)}**.",
         f"- Each answer with a rare identifier its passages contain and its question does not, checked against as "
         f"many random passages instead, flagged: **{sum(r['control_random'] is True for r in rs)} of "
         f"{sum(r['control_random'] is not None for r in rs)}**.\n",
         "## Identifiers\n",
         f"- Answers with an identifier rare enough to hold to a passage (in under {COMMON:.0%} of the corpus): "
         f"{len(with_ids)} of {len(rs)}; the rest have nothing this check can use. Common ones ignored: "
         f"{sum(len(r['common']) for r in rs)}, in {sum(1 for r in rs if r['common'])} answers.",
         f"- Answers with an identifier no passage contains: **{len(flagged)}**.",
         f"- Answers whose only unfound identifiers are the question's own, repeated: {len(echoed)}"
         + (f" ({', '.join(r['id'] for r in echoed)})" if echoed else "")
         + ". Not flagged: the answer did not introduce them, so this check cannot say whether what it says of "
         "them is true.\n"]
    if flagged:
        L += ["| Question | Not in its passages | Found |", "|---|---|---|"]
        L += [f"| {r['id']} | {', '.join(f'`{t}`' for t in r['missing'])} | {len(r['found'])} |" for r in flagged]

    L.append("\n## Against the person's faithfulness labels\n")
    pairs = [(not r["missing"], marks[r["id"]]["faithful"], r["id"]) for r in rs
             if isinstance(marks.get(r["id"], {}).get("faithful"), bool)]
    if not pairs:
        L.append("No labels of these answers.")
    else:
        c, p = [x for x, _, _ in pairs], [y for _, y, _ in pairs]
        caught = [i for x, y, i in pairs if not x and not y]
        wrong = [i for x, y, i in pairs if not x and y]
        L += [f"\"No missing identifier\" read as faithful, over {len(pairs)} labeled answers: agrees {sum(a == b for a, b in zip(c, p))} "
              f"of {len(pairs)}, kappa {kappa(c, p):.2f}.",
              f"- Of the {sum(not y for y in p)} the person marked unfaithful, flagged here: {len(caught)}"
              + (f" ({', '.join(caught)})" if caught else "") + ".",
              f"- Flagged here, marked faithful by the person: {len(wrong)}" + (f" ({', '.join(wrong)})" if wrong else "") + ".",
              "\nA flag is evidence against an answer; no flag is not evidence for it — most claims carry no identifier."]

    L.append("\n## Key-fact coverage\n")
    facts = [f for r in rs for f in r["facts"]]
    if not facts:
        L.append("No anchors yet: `python -m mobium_rag.checks anchors` drafts them into data/key-fact-anchors.json.")
    else:
        for status in ("reviewed", "draft"):
            fs = [ok for s, ok in facts if s == status]
            if not fs:
                continue
            checkable = [ok for ok in fs if ok is not None]
            note = "" if status == "reviewed" else " — drafted from the facts and not reviewed, so these do not count yet"
            L.append(f"- {status.capitalize()} anchors{note}: {len(checkable)} of {len(fs)} facts checkable, "
                     f"{sum(checkable)} of those covered.")
    REPORT.write_text("\n".join(L) + "\n")
    return REPORT.read_text()


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["anchors"]:
        write_draft_anchors()
    print(report())
