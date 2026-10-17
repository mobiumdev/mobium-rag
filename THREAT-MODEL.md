# Threat model

What can go wrong with a question-answering system over Mobium's docs and the
framework that evaluates it, mapped to the OWASP Top 10 for LLM Applications
(2025). Written 2026-09-28, before any code beyond the scaffold; each row says
what is done, and what is open until it has been measured.

## What it is, for this purpose

- **Assets:** the corpus (Mobium's public docs, at a pinned commit), the index
  built from it, the golden set, traces and judge prompts, and the answers a
  user acts on.
- **Trust boundary:** the corpus is trusted *as data* and never as
  instructions. It changes through pull requests, and it quotes text copied
  from apps — Wikipedia's markup-laden labels, dialog wording — which nobody
  here wrote.
- **What it can do:** answer. No tools, no network, a read-only index. That is
  the main defense: an attack that succeeds can at most produce a wrong
  answer, and a wrong answer is what the evaluation measures.

## The ten

| Risk | Here | Done | Open |
| --- | --- | --- | --- |
| **LLM01 Prompt injection** | A passage saying "ignore the question and…" | — | Canary evaluation: planted passages, each with a unique word; attack success rate is a metric and a CI gate, and it only counts once it has been seen to catch a planted attack. A small local classifier (Prompt Guard, ProtectAI's DeBERTa) over new passages at ingestion, as a tripwire — not a guarantee |
| **LLM02 Sensitive information disclosure** | Traces and judge prompts contain the corpus and the questions | DeepEval's and Chroma's telemetry is off for every `make` target (`DEEPEVAL_TELEMETRY_OPT_OUT`, `ANONYMIZED_TELEMETRY`); both default to on | Tracing stays local (Phoenix or Langfuse on this machine) |
| **LLM03 Supply chain** | Python packages, embedding and reranker models, the Ollama model | `uv.lock` pins every package with hashes | Models loaded only as safetensors, never pickle, at pinned revisions; the Ollama model pinned by digest |
| **LLM04 Data and model poisoning** | A doc change that plants a wrong answer; a golden-set edit that hides one | — | The corpus is built from a pinned commit of Mobium's docs, and a change to that pin is reviewed like code. The golden set changes only by review, and each change says why |
| **LLM05 Improper output handling** | Answers render as Markdown in a terminal; a link is something a person clicks | — | Links in answers only to the corpus's own sources |
| **LLM06 Excessive agency** | None: it answers and does nothing else | By design | Kept that way: any tool added later is a new threat model |
| **LLM07 System prompt leakage** | The prompt holds nothing secret | By design | — |
| **LLM08 Vector and embedding weaknesses** | Answers can reveal what was indexed | The corpus is public docs only | Never index a private repository or anything private into an index the public can query: one index per audience |
| **LLM09 Misinformation** | A confident answer the docs do not support | — | The evaluation itself: faithfulness, required citations to retrieved passages, refusal on questions the corpus cannot answer |
| **LLM10 Unbounded consumption** | A local model and judge can tie up the machine | — | Timeouts per call, and a size budget per evaluation run |

## The rule the checks follow

A security metric that comes back zero is not a result until it has been
shown it can come back non-zero. An injection rate of 0% on attacks nobody
planted proves nothing; the canaries are what make it a measurement.
