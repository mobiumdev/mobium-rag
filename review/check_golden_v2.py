"""Check a drafted golden set v2 against its specification (review/GOLDEN-V2.md)
before a person reviews it: the counts and quotas, every gold and nearest
section in the corpus at the pin, every anchor alternative found in its
question's gold sections and rare in the corpus, unanswerable questions
with no gold or facts, and no question repeated.

Prints each problem and exits 1 if there is any. Run from the repository
root:

    uv run python review/check_golden_v2.py [questions.jsonl] [--commit f232d54]
"""

import json
import re
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path

from mobium_rag import corpus
from mobium_rag.checks import normalize, present, rarity

ROOT = corpus.ROOT
PIN = "f232d54"
KINDS = {"fact": 70, "multi": 20, "unanswerable": 10}
CATEGORIES = {"how-to": 35, "behavior": 25, "troubleshooting": 15, "support": 8, "rationale": 7}
PERSONAS = {"new-user", "test-author", "ci-engineer", "agent-builder", "driver-author", "contributor"}
AREAS = 5                     # g001–g020, g021–g040, ...: 14 fact, 4 multi, 2 unanswerable each
CHALLENGES_ONLY_MAX = 30
NEW_SINCE_PIN_MIN = 20


def words(q: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", q.lower())) - {"the", "a", "an", "to", "of", "in", "on", "and", "is", "it",
                                                        "i", "my", "do", "does", "how", "what", "why", "with", "for"}


def problems(qs: list[dict], sections: dict[str, str], common) -> list[str]:
    out = []
    ids = [q["id"] for q in qs]
    if len(qs) != 100:
        out.append(f"{len(qs)} questions, not 100")
    if sorted(ids) != [f"g{n:03d}" for n in range(1, 101)]:
        out.append(f"ids are not g001–g100 once each: {sorted(i for i, c in Counter(ids).items() if c > 1)} repeated")
    for kind, n in KINDS.items():
        got = sum(q["kind"] == kind for q in qs)
        if got != n:
            out.append(f"{got} {kind}, not {n}")
    answerable = [q for q in qs if q["kind"] != "unanswerable"]
    for cat, n in CATEGORIES.items():
        got = sum(q.get("category") == cat for q in answerable)
        if got != n:
            out.append(f"{got} {cat}, target {n}")
    for a in range(AREAS):
        area = [q for q in qs if q["id"] in {f"g{n:03d}" for n in range(a * 20 + 1, a * 20 + 21)}]
        got = Counter(q["kind"] for q in area)
        if got != Counter({"fact": 14, "multi": 4, "unanswerable": 2}):
            out.append(f"area g{a * 20 + 1:03d}–g{a * 20 + 20:03d}: {dict(got)}")
    only = [q["id"] for q in answerable if q["gold"] and all(g.startswith("CHALLENGES#") for g in q["gold"])]
    if len(only) > CHALLENGES_ONLY_MAX:
        out.append(f"{len(only)} questions with only CHALLENGES gold, at most {CHALLENGES_ONLY_MAX}")
    new = sum(bool(q.get("new_since_pin")) for q in qs)
    if new < NEW_SINCE_PIN_MIN:
        out.append(f"{new} new_since_pin, at least {NEW_SINCE_PIN_MIN}")

    for q in qs:
        i = q["id"]
        if q.get("persona") not in PERSONAS:
            out.append(f"{i}: persona {q.get('persona')!r}")
        for s in q["gold"] + q.get("nearest", []):
            if s not in sections:
                out.append(f"{i}: section not in the corpus at {PIN}: {s}")
        if q["kind"] == "unanswerable":
            if q["gold"] or q["facts"]:
                out.append(f"{i}: unanswerable with gold or facts")
            if not q.get("nearest"):
                out.append(f"{i}: unanswerable with no nearest sections")
            continue
        if q["kind"] == "multi" and len(q["gold"]) < 2:
            out.append(f"{i}: multi with {len(q['gold'])} gold section")
        if not q["gold"]:
            out.append(f"{i}: answerable with no gold")
        if not 1 <= len(q["facts"]) <= 3:
            out.append(f"{i}: {len(q['facts'])} key facts, not 1 to 3")
        if not q.get("verified_in"):
            out.append(f"{i}: nothing in verified_in")
        hay = normalize("\n".join(sections.get(s, "") for s in q["gold"]))
        for f in q["facts"]:
            for alts in f["anchors"]:
                for alt in alts:
                    if not present(alt, hay):
                        out.append(f"{i}: anchor not in its gold: {alt!r}")
                    elif common(alt):
                        out.append(f"{i}: anchor common in the corpus: {alt!r}")

    texts = {q["id"]: words(q["question"]) for q in qs}
    for a, b in combinations(ids, 2):
        wa, wb = texts[a], texts[b]
        if wa and wb and len(wa & wb) / len(wa | wb) > 0.6:
            out.append(f"{a} and {b} ask nearly the same: {sorted(wa & wb)}")
    return out


def main(argv: list[str]) -> int:
    global PIN
    if "--commit" in argv:
        k = argv.index("--commit")
        PIN = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    src = Path(argv[0]) if argv else ROOT / "data" / "golden-v2-proposed.jsonl"
    qs = [json.loads(line) for line in src.read_text().splitlines() if line.strip()]
    passages = corpus.build(PIN)
    sections: dict[str, str] = {}
    for p in passages:
        sid = corpus.section_of(p.id)
        sections[sid] = sections.get(sid, "") + "\n" + p.text
    found = problems(qs, sections, rarity([p.text for p in passages]))
    print("\n".join(found) or f"{len(qs)} questions: no problems")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
