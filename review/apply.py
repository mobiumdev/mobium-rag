"""Apply the golden review's decisions to data/golden.jsonl and the key facts.

review/decisions.json is the review page's database, one decision per
question, exported with ArtifactData. A decision's `also` adds gold
sections; anything the reviewer dropped or added in a note ("DROP …",
"ADD …", "kind fact") is carried in the tables below, so every change is
read here rather than parsed out of prose. Run from the repository root:

    uv run python review/apply.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISIONS = ROOT / "review" / "decisions.json"
GOLDEN = ROOT / "data" / "golden.jsonl"
FACTS = ROOT / "data" / "key-facts-draft.json"
PROPOSED = ROOT / "data" / "golden-proposed.jsonl"

# From the notes, word for word in effect.
DROP = {
    "q004": ["CHALLENGES#55"],   # the opposite case; Findings that were not defects answers it
    "q007": ["CHALLENGES#63"],   # superseded by 305 (#195)
    "q008": ["CHALLENGES#106"],  # superseded by 305 (#195)
    "q046": ["CHALLENGES#63"],   # its fact is in 305's table
}
ADD = {
    "q006": ["CHALLENGES#108"],  # retries are three attempts now
    "q007": ["CHALLENGES#305"],
    "q008": ["CHALLENGES#305"],
    "q019": ["CHALLENGES#306"],  # the quoted fix
}
# Defects in Mobium a question's review found — the inner loop: a wrong
# answer turned into a fix there, each confirmed by the entry's "Found by".
FOUND = {
    "q007": [305],             # which button accept presses on an iOS prompt
    "q027": [313],             # an Apple TV alert, with q053
    "q053": [313],
    "q056": [315, 316, 317],   # Wear OS, measured to answer it
    "q049": [318],             # the claim behind its answer, tested
}
# Unanswerable until a ruling or a doc made them answerable.
KIND = {q: "fact" for q in ("q055", "q056", "q057", "q058", "q059", "q060", "q061")}


def main() -> None:
    decisions = json.loads(DECISIONS.read_text())
    rows = [json.loads(line) for line in GOLDEN.read_text().splitlines() if line.strip()]
    facts = json.loads(FACTS.read_text())
    # Proposed questions join the set once decided: approved or edited ones
    # move in, with their drafted facts unless the review gave its own; a
    # rejected one is dropped; an undecided one stays proposed.
    proposed = [json.loads(line) for line in PROPOSED.read_text().splitlines() if line.strip()] \
        if PROPOSED.exists() else []
    have = {r["id"] for r in rows}
    waiting = []
    for p in proposed:
        d = decisions.get(p["id"], {}).get("decision")
        if d in ("approve", "edit") and p["id"] not in have:
            facts.setdefault(p["id"], {"concern": ""}).setdefault("facts", p.get("facts") or [])
            rows.append({k: p[k] for k in ("id", "question", "kind", "gold")})
        elif d is None:
            waiting.append(p)
    missing = [r["id"] for r in rows if r["id"] not in decisions]
    if missing:
        raise SystemExit(f"no decision for {', '.join(missing)}: review them first")
    # A rejected question leaves the set, as a rejected proposal never joins it.
    rejected = [r["id"] for r in rows if decisions[r["id"]].get("decision") == "reject"]
    rows = [r for r in rows if r["id"] not in rejected]
    for r in rows:
        d = decisions[r["id"]]
        if d.get("decision") not in ("approve", "edit"):
            raise SystemExit(f"{r['id']}: decision {d.get('decision')!r} is not approve, edit or reject")
        if d.get("question"):
            r["question"] = d["question"]
        r["kind"] = KIND.get(r["id"], r["kind"])
        gold = [g for g in r["gold"] if g not in DROP.get(r["id"], [])]
        for g in ADD.get(r["id"], []) + list(d.get("also") or []):
            if g not in gold:
                gold.append(g)
        r["gold"] = gold
        if (r["kind"] == "unanswerable") != (not gold):
            raise SystemExit(f"{r['id']}: kind {r['kind']} with gold {gold}")
        r["status"] = "reviewed"
        if r["id"] in FOUND:
            r["found"] = FOUND[r["id"]]
        if d.get("facts"):
            facts.setdefault(r["id"], {"concern": ""})["facts"] = d["facts"]
    GOLDEN.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    if PROPOSED.exists():
        PROPOSED.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in waiting))
    FACTS.write_text(json.dumps(facts, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(rows)} questions reviewed; {len(rejected)} rejected and removed; "
          f"{len(waiting)} proposed, waiting for a decision")


if __name__ == "__main__":
    main()
