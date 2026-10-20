# mobium-rag — plan

A question-answering system over Mobium's own documentation, and the
evaluation framework that decides whether it can be trusted. Started
2026-09-28.

## What it is for

A Mobium feature: ask the project a question — "why is a tap under an iOS
alert refused?", "how do I reset one app's permissions on Android?" — and get
an answer grounded in the defect log, the setup guide and the decision
records, with the passages it came from.

## The constraint it has to live with

Mobium is one static binary with no runtime dependencies, and that is
load-bearing. A RAG system needs Python, embedding models and a local model
server, so it cannot ship inside `mobium`. It ships the way third-party
drivers do (`docs/decisions/0003`): as a separate program a user chooses to
install, which `mobium` never needs. The evaluation framework is developer
tooling and never reaches a user.

Open question, for later: whether retrieval alone — a prebuilt index shipped
as data, searched without a model — could live in Go, leaving only generation
optional.

## The rule the evaluation is built on

From Mobium's defect record: a measurement that comes back "zero" or "no
difference" is not a result until it has been shown it can come back
non-zero. An LLM judge is a measurement. So:

1. **Deterministic metrics first.** Recall@k, MRR and nDCG against gold chunk
   ids. No model, nothing to hallucinate, and they run in CI.
2. **A judge only where only a judge can answer** — faithfulness, answer
   relevancy, contextual precision and recall (DeepEval).
3. **Every metric gets a positive and a negative control.** Wrong context
   must score low; a fabricated answer must fail faithfulness; a question the
   corpus cannot answer must be refused, not answered. A metric that does not
   flag its negative control is reported as broken, not as passing.
4. **The judge is measured too.** Agreement with hand labels on a subset,
   the effect of swapping the judge model, and run-to-run variance.
5. **Differences come with intervals.** With ~80 questions, a two-point gain
   can be noise; comparisons are bootstrapped and reported with their
   confidence interval.

## Stack

- Python managed by `uv`, dependencies pinned.
- Chroma as the vector store.
- sentence-transformers: a bi-encoder for retrieval, a cross-encoder for
  reranking.
- An open-weight model through Ollama, for generation and as the judge — no
  per-call cost, nothing leaves the machine. 48GB RAM here: 8–14B models fit.
- DeepEval for the judged metrics.
- Tracing local and open source (Arize Phoenix or Langfuse), not a hosted
  service.

## Phases

Status 2026-10-11: phases 2–4 built. The corpus is Mobium's public docs at
the commit in `corpus.pin`, 938 passages in 724 sections (`make corpus`).
The golden set is 61 questions — 45 single facts, 8 needing two sections,
8 the corpus cannot answer — **every one `draft`**: written by a model from
the corpus, which is the thing the plan warns a golden set must not be
until a person has reviewed it. Retrieval (`make retrieval`): the controls
hold (a perfect retriever 1.000, a random one under 0.1); bge-small alone
reaches recall@5 0.858 and MRR 0.740, reranked by the cross-encoder 0.887
and 0.792 — better on every metric, inside every interval. Five questions
missed outright; at least one looks like a gold label too narrow rather
than a miss. The nearest passage cannot tell an unanswerable question from
an answerable one: the ranges overlap. 
Phase 5 (2026-10-11): llama3.1:8b answered all 61; it refused 1 of the 8
questions the docs cannot answer — about four of the other seven are made
up, one is a refusal in words the strict check misses, and two may be the
golden set's fault (the docs cover Sauce Labs and Tizen by idea, not by
name) — and none of the 53 it should answer. Reviewed 2026-10-12: q058 (Tizen) is
answerable after all — Mobium has no Tizen driver, but anyone can write one
(README, "Drivers for other platforms"), which is what the model said, so it
is now a fact question with that gold section and its answer is right. q061
(Sauce Labs, or any device cloud or farm): not yet, but planned as soon as
resources allow. The corpus says the opposite — ROADMAP lists "Device-cloud
allocation" as not planned, beside an idea for AWS Device Farm — and the
model's "No … a separate concern" followed it. That is the docs' defect, not
the model's: fix ROADMAP, re-pin the corpus, and q061 becomes answerable
with ROADMAP as gold. Done the same day: mobiumdev/mobium#194 (663b4c8)
moved device clouds out of "Not planned", the corpus is pinned there, and
q061 is a fact question with gold `docs/ROADMAP.md#under-consideration`.

The re-pin, measured (2026-10-12): q061 is missed outright (0.873 with the
new golden set at the old pin), and the edit itself cost two more — one
bullet shifted every chunk after it in ROADMAP's long "Under consideration"
section, a mixed chunk reached the top 20, and the reranker pushed q028's and
q058's gold, both borderline, out of the top 5. Two-stage recall@5 0.836,
MRR 0.760, under the old floors; re-baselined to 0.81 and 0.73, since a new
pin is a deliberate corpus change — one question under the run, because one
run in ten came back 0.818 (q003 missed; its gold is the reranker's clear
first, so the first stage is the suspect; not reproduced in nine more runs,
two from a fresh index). An open lead. Phase 5 over the stored answers: refused
1 of 6 unanswerable, 0 of 55 answerable; citations precision 0.606, recall
0.764 (the answers predate the pin). Chunking that splits long sections at
their bullets would stop one entry moving its neighbors; not done. With q058 moved: refused 1 of 7
unanswerable, 0 of 54 answerable; citations precision 0.617, recall 0.778;
two-stage recall@5 0.889, MRR 0.781 (gate passes). Citation precision 0.610,
recall 0.774; no citation of a passage it was not given.

**Reviewed 2026-10-13: all 61 questions.** Decided on the review page
(its database exported to `review/decisions.json`; q022–q060 first set
while Lana was away and marked so in each note), applied by
`review/apply.py`: 7 questions reworded, gold sections added to 31
and dropped from four whose answer #195 replaced, the key
facts rewritten from the code, and seven unanswerable questions made fact
questions by a ruling or a doc (q058 and q061 on 2026-10-12) — HarmonyOS, KaiOS and BlackBerry by the
Tizen ruling (no plans; anyone can write a driver), Wear OS by measuring it
(mobiumdev/mobium#208, README "Platforms"), Sauce Labs and device clouds by
#194. One is left unanswerable: q054, an enterprise license, because a paid
offering is planned and not written down. Corpus pinned at `4ca9a44`, 967
passages; every gold section is in it. Two-stage recall@5 0.814, MRR 0.753:
the gate passes, by 0.004. The reviewed set exposes a weakness the draft
hid: all five "can Mobium run on X" questions miss their gold section
(README "Drivers for other platforms", ROADMAP "Under consideration"),
ranked below sections that name a device or a guide. Answers and the judge
have not been rerun on the reviewed set.

Phase 6, first run (2026-10-11): the controls caught the judge. With
DeepEval's default faithfulness, which counts only claims the passages
contradict, both llama3.1:8b and qwen2.5:7b scored a made-up answer 1.00
faithful and failed 5 of 10 faithfulness controls, so no faithfulness score
is reported; relevance passed every control (llama 0.531, qwen 0.670). The
two judges agree little (kappa 0.10 faithfulness, 0.26 relevance). Scoring
the same answers again moved nothing, which at temperature 0 says the
judges are deterministic, not that they are right. Rerun with
`penalize_ambiguous_claims`, which counts an unsupported claim too.

Phase 6, second run (2026-10-11, `data/judge-report-run2.md`; the first is
`data/judge-report-run1.md`): counting unsupported claims fixed the made-up
answer — llama3.1:8b now fails it 5 times in 5, qwen2.5:7b 4 in 5 (0.67
once) — but not the other control. An answer scored against five random
passages, which say nothing it says, still scored 0.50 or 1.00: twice in 5
for llama, four times in 5 for qwen. So faithfulness is still not trusted
from either judge, and llama also left 9 of its faithfulness replies
unreadable (mean 0.143 over the rest). Relevance is unchanged: every
control passed, llama 0.531, qwen 0.670, kappa 0.26. Two 7–8B judges
cannot tell supported from unsupported here; the next step is a stronger
judge behind the same controls, which is a decision, not a fix.


1. **Scaffold.** Repository, `uv`, pinned dependencies, `make eval`.
2. **Corpus and golden set.** Chunk Mobium's docs with stable ids (a
   CHALLENGES entry is a natural unit). Write ~80 questions with their gold
   chunks: single-fact lookups, multi-hop, and questions the corpus cannot
   answer. Hand-written and reviewed — a golden set is a test suite, and a
   generated one encodes the generator's assumptions, as a hand-written
   fixture encoded Mobium's author's.
3. **Baseline retrieval.** Bi-encoder, k=5. Deterministic metrics.
4. **Two-stage retrieval.** Bi-encoder k=10, cross-encoder rerank to 5.
   Reported as a difference from the baseline, with its interval.
5. **Generation.** Faithfulness, answer relevancy, and refusal on the
   unanswerable questions.
6. **Meta-evaluation.** The controls and the judge checks above.
7. **CI.** A small subset as a regression gate.
8. **The feature.** A companion program, installed separately, answering
   from the evaluated configuration.

**Next, the judge chosen by measurement (decided 2026-10-13).** Two larger
local judges, qwen2.5:14b and mistral-small:24b (`metajudge.JUDGES`, two
families so a swap is one), run behind the same controls on answers
regenerated for the reviewed set (`data/answers.jsonl`, llama3.1:8b:
refused 1 of 1 unanswerable and 0 of 60 answerable; citations precision
0.656, recall 0.654). Then a Claude model as a third judge, **without an API
key**: `claudecli.py` reaches it through Claude Code's own `claude -p`,
signed in, so it counts against the plan's usage and bills nothing per
token; the metrics, controls and report are the same. Run, once the local
run is done:

    MOBIUM_RAG_JUDGES=claude-cli:claude-haiku-5-5 make judge

A full DeepEval faithfulness score through it took about 11 s (a made-up
answer 0.0), so a run is roughly half an hour. The report compares each
judge with the person's labels (`review/labels.json`, exported from the
labeling page's database; `python -m mobium_rag.metajudge report` redraws
it without scoring again). The labeling page shows Claude's reading of each
answer beside it, so a Claude judge's agreement with labels made after
reading it is not independent; the report says the readings were shown.

Phase 6, third run (2026-10-13, `data/judge-report-run3.md`), on the
answers regenerated for the reviewed set: **qwen2.5:14b passed all 15
controls** — the made-up answer, the answer over random passages and
another question's answer, each 0.00, five times — the first judge to pass
the random-passages control both 7–8B judges failed. mistral-small:24b
passed every faithfulness control and failed one relevance control, scoring
another question's answer 1.00 once, so its relevance is not trusted. Scored
twice, nothing moved at temperature 0 (0 of 20 flips each). Faithfulness:
qwen 0.406, mistral 0.324, agreeing on 46 of 60 (kappa 0.54, moderate);
relevance: qwen 0.645. The faithfulness means are low because the claim
counting is strict and llama3.1:8b's answers say more than their passages
— which is what the labels have to confirm. Next: the person's labels, then
Claude Haiku through `claude -p` beside these two, and a judge chosen on
controls and agreement with the person.

Phase 6, fourth run (2026-10-13, `data/judge-report-run4.md`): Claude Haiku
5.5 as a judge through `claude -p`, joining run 3's two in one report.
**It passed all 15 controls, and it is not repeatable**: scoring the same 20
answers again changed faithfulness by 0.26 on average and flipped 8 of 20
pass/fail verdicts (relevance: 0.08, 1 of 20), where both local judges, at
temperature 0, moved not at all. `claude -p` has no temperature setting, so
every call samples. Faithfulness 0.540, relevance 0.896; agreement with the
local judges on faithfulness is low (kappa 0.29 with qwen, 0.33 with
mistral). So through Claude Code one Haiku score is a noisy reading: if it
is to judge, it scores each answer several times and takes the majority, or
goes through the API at temperature 0. The person's labels decide between
qwen2.5:14b (every control, no flips) and Haiku.

**78 reviewed (2026-10-14).** The nine questions proposed on 2026-10-12
(q062–q070) and eight drafted from what changed since (q071–q078) went on
the review page with retrieval and a check of each against its gold
section (`review/build_review.py`); Lana decided all seventeen — fifteen as
drafted, q068 with a fact added (the search now pulls at most once), q078
by the Tizen ruling for a car head unit. `apply.py` brought them in: 67
single-fact, 10 two-section, 1 unanswerable. At pin 4ca9a44 the gate
passes on 78 as on 61: two-stage recall@5 0.816, MRR 0.752. Four more
(q079–q082, CHALLENGES 318–321) wait in `golden-proposed-next-pin.jsonl`
for the corpus to move past d263c6d. The stored answers and the judge runs
cover the first 61; the seventeen get answers on the next generation run.

**The judges against a person (2026-10-14, `data/judge-report-run4-labels.md`).**
Lana labeled the 20 answers (`review/labels.json`): 13 faithful, 18
relevant, each mark hers, made with Claude's claim-by-claim reading shown.
Faithfulness, agreement with her: Haiku 16 of 20 (kappa 0.56), qwen2.5:14b
13 (0.30), mistral-small:24b 11 (0.10). qwen is too strict — it failed five
answers she judged faithful (q007, q020, q025, q038, q044) — and Haiku is
closest, but flips 8 of 20 verdicts when scored again, and its agreement
is not independent of labels made after Claude's reading. Relevance cannot
be judged from these labels: two negatives in twenty, every kappa near 0.
Next, to choose: Haiku scored three times by majority, against the same
labels; and a second 20, labeled blind, with more answers that miss the
question.

**Haiku by majority of three (2026-10-14, `data/judge-report-run5.md`).**
`MOBIUM_RAG_VOTES=3` asks every score three times and keeps the median,
recorded as "claude-cli:claude-haiku-5-5 ×3"; 1 h 31 min.
It passed all 15 controls. **Voting halves the noise and does not remove
it**: rescoring the same 20 flipped 4 faithfulness verdicts (8 with one
vote), a mean change of 0.11 (0.26); relevance 0 flips. Against Lana's 20
labels it agrees on faithfulness 15 of 20 (kappa 0.43), one fewer than a
single vote, so the extra calls bought repeatability, not agreement. One
vote and three agree with each other on 51 of 60 (kappa 0.67). Still
open: the blind labels, then the choice between qwen2.5:14b (repeatable,
too strict) and Haiku ×3 (closer to her, still 4 flips in 20) — or Haiku
through the API at temperature 0, which needs a key this project does not
use.

## Not decided yet

- The generator and judge models — chosen by measurement in phases 5–6, not
  up front. The judges being measured are above; the generator is still
  llama3.1:8b by default, never compared.
- Whether the golden set is versioned with Mobium's docs, since the answers
  change when the docs do.

**Re-pinned to `7b590a4` and the reranker given the file name
(2026-10-19).** Every gold section exists at the new pin (1,007 passages),
but two-stage recall@5 fell to 0.786 and MRR to 0.745, under the floors of
0.81 and 0.73: 26 new CHALLENGES entries compete with the old ones (q028
now gets 296, 298 and 334 for 297). The reranker loses what it is given —
the best reranking of its 20 candidates reaches 0.879, of 40, 0.957 — so
seven changes were measured against it, each paired and bootstrapped
(`data/retrieval-report.md`, "Rerankers"): the docs' citations as a graph
(+0.000), 40 candidates (+0.013), rank fusion with the first stage
(+0.036), `BAAI/bge-reranker-v2-m3` over 20 and 40 (+0.019, +0.035), that
fused (+0.029), and the passage's file named in front of its text. Only
the last cleared zero: MRR +0.023 (+0.005 to +0.045), nDCG@5 +0.021
(+0.005 to +0.041), recall@5 +0.032 (+0.000 to +0.071). Adopted as the
default (`retrieve.Index.scores`, generation and the review page too);
the run is 0.818 and 0.768, the same twice, and the floors are one
question under it, 0.80 and 0.75. Seven tries on one set of 78 can find
one by luck, so the held-out check is q079–q082, unreviewed, and more
unseen questions. The platform questions (q055–q061) still all miss, under
every reranker: the likelier fix is a section in Mobium's docs that answers
"which platforms", not retrieval. Stored answers predate both the pin and
the change; the next generation run covers all 78.

**82 reviewed (2026-10-19).** q079–q082 (CHALLENGES 318–321) went on the
review page at `7b590a4` with Claude's check of each; Lana decided them in
chat, since the page had not saved them, and they were written to its
database as hers: q079, q080 and q082 approved, q081 edited — CHALLENGES
320 says a range the page stops short fails as `not_confirmed` and names
no code for an ARIA slider, so the fact says "fails, saying so (as
not_confirmed for a range)". The gate on 82: two-stage recall@5 0.815, MRR
0.767, above the floors of 0.80 and 0.75. As a held-out check of the file
name they do not decide it: the heading-only reranker also ranks q079–q081's
gold first, and q082's gold is not in the 20 candidates under either, so
its miss is the first stage's.
