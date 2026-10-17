"""The corpus: Mobium's public docs at a pinned commit, cut into passages
with stable ids.

Read from the pinned commit with `git show`, never from the working tree, so
the index is built from exactly what the pin names (THREAT-MODEL.md, LLM04),
and only from the public repository — never a private one: one index per
audience (LLM08).

A passage is a section under a heading — a CHALLENGES entry is
`CHALLENGES#105`, since entries are what the docs and the code cite by
number. A section longer than MAX_CHARS is cut into parts,
`docs/SETUP.md#parallel-runs~2`: an embedding model reads about 2,000
characters and ignores the rest. A gold label names a section, and any of
its parts retrieved counts (section_of).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PIN = ROOT / "corpus.pin"
OUT = ROOT / "data" / "corpus.jsonl"
# The public repository's checkout; CI checks it out elsewhere.
SOURCE = Path(os.environ.get("MOBIUM_PUBLIC", Path.home() / "mobium-public"))
MAX_CHARS = 1800

# What is left out, and why: a license notice answers no question about
# Mobium, and a check's own scripts are code, not docs.
EXCLUDE = re.compile(r"^(clients/|THIRD_PARTY_NOTICES\.md$|LICENSE|NOTICE|.*testdata/)")


@dataclass(frozen=True)
class Passage:
    id: str
    path: str
    heading: str
    text: str


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(SOURCE), *args], capture_output=True, text=True, check=True).stdout


def slug(heading: str) -> str:
    s = re.sub(r"[`*_~]", "", heading.strip().lower())
    s = re.sub(r"[^a-z0-9 -]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")


def _parts(text: str) -> list[str]:
    """Cut at paragraphs; a paragraph still too long — a bullet list or a
    table with no blank line in it — at its lines."""
    if len(text) <= MAX_CHARS:
        return [text]
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if len(para) <= MAX_CHARS:
            units.append(para + "\n\n")
        else:
            units += [line + "\n" for line in para.splitlines()]
    out, cur = [], ""
    for u in units:
        if cur and len(cur) + len(u) > MAX_CHARS:
            out.append(cur.strip())
            cur = ""
        cur += u
    if cur.strip():
        out.append(cur.strip())
    return out


def section_of(passage_id: str) -> str:
    """The section a passage belongs to — what a gold label names: a part
    (`~2`) counts as its section."""
    return passage_id.split("~", 1)[0]


def split(path: str, markdown: str) -> list[Passage]:
    """A file's passages: one per heading's section, CHALLENGES entries
    whole, long sections in parts."""
    is_challenges = path == "docs/CHALLENGES.md"
    sections: list[tuple[str, list[str]]] = [("", [])]
    in_code = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^#{1,3} ", line):
            sections.append((line.lstrip("#").strip(), []))
        else:
            sections[-1][1].append(line)
    stem = "CHALLENGES" if is_challenges else path
    out: list[Passage] = []
    seen: dict[str, int] = {}
    for heading, lines in sections:
        body = "\n".join(lines).strip()
        if not body:
            continue
        m = re.match(r"^(\d+)\. ", heading) if is_challenges else None
        key = m.group(1) if m else (slug(heading) or "top")
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}-{seen[key]}"
        pieces = _parts(body)
        for i, piece in enumerate(pieces):
            pid = f"{stem}#{key}" + (f"~{i + 1}" if len(pieces) > 1 else "")
            text = (f"{heading}\n\n{piece}" if heading else piece)
            out.append(Passage(pid, path, heading, text))
    return out


def build(commit: str | None = None) -> list[Passage]:
    commit = commit or PIN.read_text().strip()
    files = [f for f in _git("ls-tree", "-r", "--name-only", commit).splitlines()
             if f.endswith(".md") and not EXCLUDE.match(f)]
    passages: list[Passage] = []
    for f in sorted(files):
        passages += split(f, _git("show", f"{commit}:{f}"))
    ids = [p.id for p in passages]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"passage ids are not unique: {sorted(dupes)[:5]}")
    return passages


def write(passages: list[Passage]) -> None:
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("".join(json.dumps(asdict(p)) + "\n" for p in passages))


def load() -> list[Passage]:
    return [Passage(**json.loads(line)) for line in OUT.read_text().splitlines()]


if __name__ == "__main__":
    ps = build()
    write(ps)
    print(f"{len(ps)} passages from {len({p.path for p in ps})} files at {PIN.read_text().strip()[:7]}")
