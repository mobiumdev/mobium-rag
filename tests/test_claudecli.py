import json
import os
import subprocess

import pytest
from pydantic import BaseModel

from mobium_rag import claudecli


class Verdicts(BaseModel):
    verdicts: list[str]


def test_the_judge_is_asked_with_no_tools_no_session_and_its_own_prompt():
    cmd = claudecli.command("claude-haiku-5-5")
    assert cmd[:4] == ["claude", "-p", "--model", "claude-haiku-5-5"]
    assert cmd[cmd.index("--tools") + 1] == ""
    assert cmd[cmd.index("--system-prompt") + 1] == claudecli.SYSTEM
    for flag in ("--no-session-persistence", "--strict-mcp-config"):
        assert flag in cmd
    assert "--bare" not in cmd  # it skips the keychain, where the sign-in is


def test_a_reply_is_read_into_the_schema_the_metric_asks_for():
    seen = {}

    def runner(model, prompt):
        seen["model"], seen["prompt"] = model, prompt
        return 'Here it is:\n```json\n{"verdicts": ["yes", "no"]}\n```'

    j = claudecli.ClaudeCLI("claude-haiku-5-5", runner=runner)
    out = j.generate("Judge these.", schema=Verdicts)
    assert out.verdicts == ["yes", "no"]
    assert seen["model"] == "claude-haiku-5-5" and '"verdicts"' in seen["prompt"]
    assert j.get_model_name() == "claude-cli:claude-haiku-5-5"
    assert j.generate("Say hi.") == 'Here it is:\n```json\n{"verdicts": ["yes", "no"]}\n```'


def test_a_reply_with_no_json_is_an_error_not_a_score():
    with pytest.raises(ValueError):
        claudecli.ClaudeCLI("m", runner=lambda m, p: "I cannot judge that.").generate("x", schema=Verdicts)


def test_a_failed_call_is_an_error(monkeypatch):
    def fake(*a, **k):
        return subprocess.CompletedProcess(a, 1, stdout=json.dumps({"is_error": True, "result": "not signed in"}), stderr="")

    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="not signed in"):
        claudecli.run_cli("m", "x")


# One real call, signed in: opt in, since it counts against the plan.
@pytest.mark.skipif(os.environ.get("MOBIUM_RAG_CLAUDE_TESTS") != "1", reason="MOBIUM_RAG_CLAUDE_TESTS=1 to call claude -p")
def test_a_real_call_answers_in_the_schema():
    out = claudecli.ClaudeCLI("claude-haiku-5-5").generate(
        'Return {"verdicts": ["yes"]} if 2 + 2 = 4, else {"verdicts": ["no"]}.', schema=Verdicts)
    assert out.verdicts == ["yes"]
