"""A Claude model as a judge, reached through Claude Code's own command line.

`claude -p` answers one prompt and exits, signed in as whoever is signed in
to Claude Code, so a judge run needs no API key and bills nothing per token:
it counts against that plan's usage. The judge is the same DeepEval metric
as the local ones — only how the model is reached differs — so its controls,
its repeat and its agreement with the person are measured the same way.

Each call has no tools, no saved session, no MCP servers, and a judge's
system prompt in place of Claude Code's own, and runs from an empty folder,
so no project's CLAUDE.md is read. `MOBIUM_RAG_JUDGES=claude-cli:<model>`
picks it, e.g. `claude-cli:claude-haiku-5-5`.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
from typing import Any, Callable

from deepeval.models import DeepEvalBaseLLM

PREFIX = "claude-cli:"
SYSTEM = ("You are an evaluation judge. Follow the instructions in the message exactly, and answer with "
          "the JSON they ask for and nothing else: no prose, no code fences.")
TIMEOUT = 300  # seconds a call may take (THREAT-MODEL.md, LLM10)


def command(model: str) -> list[str]:
    return ["claude", "-p", "--model", model, "--tools", "", "--system-prompt", SYSTEM,
            "--no-session-persistence", "--strict-mcp-config", "--output-format", "json"]


def run_cli(model: str, prompt: str) -> str:
    """One prompt to the model, its answer's text back."""
    with tempfile.TemporaryDirectory() as empty:
        p = subprocess.run(command(model), input=prompt, capture_output=True, text=True, timeout=TIMEOUT, cwd=empty)
    try:
        out = json.loads(p.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"claude -p exited {p.returncode} without its JSON answer: "
                           f"{(p.stderr or p.stdout).strip()[:300]}") from None
    if p.returncode != 0 or out.get("is_error"):
        raise RuntimeError(f"claude -p failed ({p.returncode}): {str(out.get('result', ''))[:300]}")
    return str(out.get("result", ""))


def json_in(text: str) -> Any:
    """The JSON object in a reply, without fences or words around it."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"no JSON object in the judge's reply: {text[:200]!r}")
    return json.loads(text[start:end + 1])


class ClaudeCLI(DeepEvalBaseLLM):
    def __init__(self, model: str, runner: Callable[[str, str], str] = run_cli):
        self.name = model
        self.runner = runner
        super().__init__(model)

    def load_model(self):
        return self

    def get_model_name(self) -> str:
        return PREFIX + self.name

    def generate(self, prompt: str, schema: Any = None) -> Any:
        if schema is not None:
            prompt += ("\n\nAnswer with one JSON object that matches this JSON schema:\n"
                       + json.dumps(schema.model_json_schema()))
        text = self.runner(self.name, prompt)
        return schema.model_validate(json_in(text)) if schema is not None else text

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        return await asyncio.to_thread(self.generate, prompt, schema)
