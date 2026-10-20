# The judge, measured

81 answered questions the docs cover, from phase 5's answers; each scored once by each judge, and the first 20 a second time. Faithfulness weighs the answer against at most 15 facts drawn from its passages. The golden set is all reviewed by a person; a person labeled 20 of these answers — some with Claude's claim-by-claim reading of each shown beside it (review/readings.json), some blind, with none — and each set is compared on its own below.

## Controls

| Judge | Passed | Failed |
|---|---|---|
| qwen2.5:14b | 15 of 15 | none |
| mistral-small:24b | 14 of 15 | relevancy, the answer to another question: 1.00 |
| claude-cli:claude-haiku-5-5 | 15 of 15 | none |
| claude-cli:claude-haiku-5-5 ×3 | 15 of 15 | none |

## Scores, and how much they move

| Judge | Metric | Mean | Same answer scored again: mean change | Pass/fail flips | Replies unreadable |
|---|---|---|---|---|---|
| qwen2.5:14b | faithfulness | 0.391 | 0.000 | 0 of 20 | 0 |
| qwen2.5:14b | relevancy | 0.676 | 0.000 | 0 of 20 | 0 |
| mistral-small:24b | faithfulness | 0.404 | 0.000 | 0 of 20 | 0 |
| mistral-small:24b | relevancy (failed a control: not trusted) | 0.887 | 0.000 | 0 of 20 | 0 |
| claude-cli:claude-haiku-5-5 | faithfulness | 0.522 | 0.217 | 6 of 20 | 0 |
| claude-cli:claude-haiku-5-5 | relevancy | 0.930 | 0.033 | 0 of 20 | 0 |
| claude-cli:claude-haiku-5-5 ×3 | faithfulness | 0.493 | 0.210 | 3 of 20 | 0 |
| claude-cli:claude-haiku-5-5 ×3 | relevancy | 0.924 | 0.046 | 0 of 20 | 0 |

## The judges against each other

| Judges | Metric | Agree on pass/fail | Cohen's kappa | Mean difference (second − first) |
|---|---|---|---|---|
| qwen2.5:14b, mistral-small:24b | faithfulness | 55 of 81 | 0.36 | +0.014 |
| qwen2.5:14b, mistral-small:24b | relevancy | 65 of 81 | 0.22 | +0.211 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 | faithfulness | 59 of 81 | 0.46 | +0.131 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 | relevancy | 63 of 81 | 0.08 | +0.255 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 ×3 | faithfulness | 58 of 81 | 0.44 | +0.102 |
| qwen2.5:14b, claude-cli:claude-haiku-5-5 ×3 | relevancy | 63 of 81 | 0.08 | +0.248 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 | faithfulness | 51 of 81 | 0.25 | +0.117 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 | relevancy | 79 of 81 | 0.49 | +0.043 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 ×3 | faithfulness | 46 of 81 | 0.13 | +0.088 |
| mistral-small:24b, claude-cli:claude-haiku-5-5 ×3 | relevancy | 79 of 81 | 0.49 | +0.037 |
| claude-cli:claude-haiku-5-5, claude-cli:claude-haiku-5-5 ×3 | faithfulness | 68 of 81 | 0.66 | -0.029 |
| claude-cli:claude-haiku-5-5, claude-cli:claude-haiku-5-5 ×3 | relevancy | 81 of 81 | 1.00 | -0.007 |

llama3.1:8b wrote the answers; no judge here did.

## Each judge against a person

| Labels | Judge | Metric | Agrees with the person | Cohen's kappa | Judge passes what the person failed |
|---|---|---|---|---|---|
| every label | qwen2.5:14b | faithfulness | 13 of 20 | 0.33 | 1 of 6 |
| every label | qwen2.5:14b | relevancy | 13 of 20 | 0.13 | 4 of 6 |
| every label | mistral-small:24b | faithfulness | 14 of 20 | 0.35 | 2 of 6 |
| every label | mistral-small:24b | relevancy | 15 of 20 | 0.22 | 5 of 6 |
| every label | claude-cli:claude-haiku-5-5 | faithfulness | 15 of 20 | 0.43 | 2 of 6 |
| every label | claude-cli:claude-haiku-5-5 | relevancy | 14 of 20 | 0.00 | 6 of 6 |
| every label | claude-cli:claude-haiku-5-5 ×3 | faithfulness | 15 of 20 | 0.48 | 1 of 6 |
| every label | claude-cli:claude-haiku-5-5 ×3 | relevancy | 14 of 20 | 0.00 | 6 of 6 |
