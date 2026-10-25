# Golden set v2: the specification

Started 2026-10-24. The golden set began as a model's draft of 61
questions, grew by additions to 82, and leans on what it was drafted from:
three quarters of its gold is CHALLENGES entries, one question is
unanswerable, and nothing in it covers what Mobium gained after
`7b590a4`. Version 2 is written from nothing, against Mobium's public
`main` at **`f232d54`**, to this specification. The 82 stay in
`data/golden.jsonl` and keep the gate until v2 is reviewed and adopted.

A golden set is a test suite. Each question is a test case: it has one
right answer, the answer is in the corpus, and a reader can say whether an
answer has it.

## What the set is for

1. **Retrieval:** does the right section come back (recall@5, MRR).
2. **Generation:** does the answer say the key facts, and only what its
   passages say (Phase 6b, steps 2 and 3).
3. **Refusal:** does the system say "the docs don't say" when they don't.

## Shape: 100 questions

| Kind | Count | What it is |
|---|---|---|
| `fact` | 70 | One section answers it fully |
| `multi` | 20 | Needs two sections or more, for one ask (not two questions joined) |
| `unanswerable` | 10 | The corpus does not answer it; the right answer is a refusal |

Every answerable question also has a **category** — what the asker wants —
and a **persona** — who asks:

| Category | Target | Asks |
|---|---|---|
| `how-to` | 35 | How do I do X with Mobium |
| `behavior` | 25 | What does Mobium do when X; what does this result or error mean |
| `troubleshooting` | 15 | X went wrong; why, and what to do |
| `support` | 8 | Does Mobium do X / run on Y, and to what extent |
| `rationale` | 7 | Why is Mobium built this way |

Personas: `new-user`, `test-author`, `ci-engineer`, `agent-builder`
(MCP, skills, an LLM driving Mobium), `driver-author`, `contributor`.

### Coverage rules

- **Beyond the defect log.** At most 30 of the 90 answerable questions
  have only CHALLENGES gold. The rest are answered from the guides, README,
  SETUP, API, quickstarts, decision records and the other docs.
- **Today's Mobium.** At least 20 questions are about what Mobium gained
  after `7b590a4` (marked `new_since_pin`): screen readers and assistants
  (ACCESSIBILITY), the proxy (PROXY, guides/network), recording as code,
  Windows hosts (WINDOWS), two-thumb sliders, TV select, simulator audio,
  CHALLENGES 348–361.
- **Every area, 20 each**, by id: g001–g020 setup, devices and platforms;
  g021–g040 locators and interaction; g041–g060 the test runner, traces,
  recording and CI; g061–g080 dialogs, permissions, the system,
  accessibility and network; g081–g100 agents, MCP, clients and extension.
  Each area has 14 `fact`, 4 `multi` and 2 `unanswerable`.

## Rules for each question

1. **One right answer, from the corpus at the pin.** The answer is in the
   gold sections. Nothing outside the corpus is needed.
2. **Checked against the code.** The drafter reads the code behind the
   answer and records where (`verified_in`). If the docs and the code
   disagree, the question is kept with a `concern` naming the defect —
   the docs are fixed, not the question bent to fit them.
3. **Unambiguous.** Self-contained, no "it" or "this" pointing outside the
   question. Names the platform whenever the answer differs by platform.
   One ask. No yes/no question unless the answer must also say why or how
   far.
4. **Asked the way a person would.** Plain words from someone with the
   problem, not the section's heading reworded; that leaks the answer to
   retrieval.
5. **Gold is the minimal sufficient set.** Every section a right answer
   needs, and no section that only mentions the subject. Parts (`~2`)
   count as their section.
6. **Key facts are atomic.** One to three per question, each one claim a
   reader can check. Each fact has **anchors**: tokens a right answer must
   contain, each with its alternatives (`[["6 seconds", "six seconds"]]`).
   Every alternative appears in a gold section. Common words (`iOS`, `map`)
   are not anchors; a fact with nothing distinctive to anchor has an empty
   list and is left to the judge.
7. **Unanswerable means checked absent.** The drafter searched the corpus
   and the code and records why it is not answered and the nearest
   sections (`nearest`) — the hard negatives a retriever will bring back.
   Mix: features Mobium does not have, facts the docs never state (a price,
   a date), and questions that sound covered but are not.
8. **Public.** No private data, no comparison with other test tools; only
   Vibium is named among them (the trace format). Platform names are fine.

## The record

One JSON object per line, in `data/golden-v2-proposed.jsonl`:

```json
{"id": "g001", "question": "...", "kind": "fact", "category": "how-to",
 "persona": "new-user", "gold": ["docs/SETUP.md#android"],
 "facts": [{"fact": "...", "anchors": [["sdkmanager"], ["platform-tools"]]}],
 "new_since_pin": false, "verified_in": ["internal/android/sdk.go:41"],
 "nearest": [], "concern": "", "check": "Claude's reading: ..."}
```

`check` is the drafter's reading, shown on the review page as Claude's —
the person decides; `review/apply.py` applies what they decided.

## Checked by code before review

`review/check_golden_v2.py`: the counts and quotas above, ids unique,
every gold and nearest section in the corpus at the pin, every anchor
alternative found in its question's gold sections, no anchor common in the
corpus, no unanswerable question with gold or facts, no question repeated.
