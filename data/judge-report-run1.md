# The judge, measured

53 answered questions the docs cover, from phase 5's answers; each scored once by each judge, and the first 20 a second time. Faithfulness weighs the answer against at most 15 facts drawn from its passages. The golden set is still `draft`, and the person's labels the plan asks the judge to be compared with do not exist until the review is done.

## Controls

| Judge | Passed | Failed |
|---|---|---|
| llama3.1:8b | 10 of 15 | faithfulness, made-up answer: 1.00; faithfulness, its answer over random passages: 1.00; faithfulness, its answer over random passages: 0.50; faithfulness, made-up answer: 1.00; faithfulness, its answer over random passages: 1.00 |
| qwen2.5:7b | 10 of 15 | faithfulness, its answer over random passages: 0.75; faithfulness, its answer over random passages: 1.00; faithfulness, made-up answer: 0.67; faithfulness, its answer over random passages: 0.50; faithfulness, its answer over random passages: 1.00 |

## Scores, and how much they move

| Judge | Metric | Mean | Same answer scored again: mean change | Pass/fail flips | Replies unreadable |
|---|---|---|---|---|---|
| llama3.1:8b | faithfulness (failed a control: not trusted) | 0.187 | 0.000 | 0 of 18 | 9 |
| llama3.1:8b | relevancy | 0.531 | 0.000 | 0 of 20 | 0 |
| qwen2.5:7b | faithfulness (failed a control: not trusted) | 0.481 | 0.000 | 0 of 20 | 0 |
| qwen2.5:7b | relevancy | 0.670 | 0.000 | 0 of 20 | 0 |

## The two judges against each other

| Metric | Agree on pass/fail | Cohen's kappa | Mean difference (qwen − llama) |
|---|---|---|---|
| faithfulness | 23 of 46 | 0.10 | +0.274 |
| relevancy | 38 of 53 | 0.26 | +0.139 |

llama3.1:8b also wrote the answers, so it judges its own words; qwen2.5:7b did not.
