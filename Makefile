# Telemetry off for everything run from here: both default to on, and
# traces, prompts and the corpus stay on this machine (THREAT-MODEL.md, LLM02).
export DEEPEVAL_TELEMETRY_OPT_OUT := YES
export ANONYMIZED_TELEMETRY := False

.PHONY: test
test:
	uv run pytest -q

.PHONY: corpus retrieval
corpus:
	uv run python -m mobium_rag.corpus

retrieval: corpus
	uv run python -m mobium_rag.evaluate

.PHONY: generation
generation: corpus
	uv run python -m mobium_rag.generate

.PHONY: ci
ci: test corpus
	uv run python -m mobium_rag.evaluate gate

# A local judge under load answers in tens of seconds; DeepEval's default
# per-call timeout gave up on the first call. Still bounded (THREAT-MODEL.md,
# LLM10): five minutes a call, fifteen a metric.
.PHONY: judge
judge: export DEEPEVAL_PER_ATTEMPT_TIMEOUT_SECONDS_OVERRIDE := 300
judge: export DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE := 900
judge:
	uv run python -m mobium_rag.metajudge

# The docs' citations as a page for GitHub Pages: site/index.html. Run after
# `make retrieval` for the page to say what the graph did for retrieval.
.PHONY: graph
graph: corpus
	uv run python -m mobium_rag.graphpage
