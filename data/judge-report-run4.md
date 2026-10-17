# The judge, measured

60 answered questions the docs cover, from phase 5's answers; each scored once by each judge, and the first 20 a second time. Faithfulness weighs the answer against at most 15 facts drawn from its passages. The golden set is all reviewed by a person; a person labeled 0 of these answers (review/labels.json), with Claude's claim-by-claim reading of each shown beside it (review/readings.json) — so agreement here is with the person's marks, made after reading Claude's.

## Controls

| Judge | Passed | Failed |
|---|---|---|
| qwen2.5:14b | 15 of 15 | none |
| mistral-small:24b | 14 of 15 | relevancy, the answer to another question: 1.00 |
| claude-cli:claude-haiku-5-5 | 15 of 15 | none |

## Scores, and how much they move

| Judge | Metric | Mean | Same answer scored again: mean change | Pass/fail flips | Replies unreadable |
|---|---|---|---|---|---|
| qwen2.5:14b | faithfulness | 0.406 | 0.000 | 0 of 20 | 0 |
| qwen2.5:14b | relevancy | 0.645 | 0.000 | 0 of 20 | 0 |
| mistral-small:24b | faithfulness | 0.324 | 0.000 | 0 of 20 | 0 |
| mistral-small:24b | relevancy (failed a control: not trusted) | 0.905 | 0.000 | 0 of 20 | 0 |
| claude-cli:claude-haiku-5-5 | faithfulness | 0.540 | 0.264 | 8 of 20 | 0 |
| claude-cli:claude-haiku-5-5 | relevancy | 0.896 | 0.078 | 1 of 20 | 0 |

## The judges against each other

| Judges | Metric | Agree on pass/fail | Cohen's kappa | Mean difference (second − first) |
|---|---|---|---|---|
| qwen2.5:14b, mistral-small:24b | faithfulness | 46 of 60 | 0.54 | -0.082 |
| qwen2.5:14b, mistral-small:24b | relevancy | 50 of 60 | 0.24 | +0.259 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 | faithfulness | 39 of 60 | 0.29 | +0.134 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 | relevancy | 48 of 60 | 0.17 | +0.251 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 | faithfulness | 39 of 60 | 0.33 | +0.216 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 | relevancy | 56 of 60 | 0.30 | -0.009 |

llama3.1:8b wrote the answers; no judge here did.

## Each judge against a person

No labels yet: label the answers on the labeling page, export them to review/labels.json, and run `python -m mobium_rag.metajudge report`.
