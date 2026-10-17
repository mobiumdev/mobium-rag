"""Build the reviewer's guide page from REVIEWING.md, so the two never differ.

A small converter for the Markdown the guide uses — headings, paragraphs,
lists, tables, code, bold, links and a Mermaid diagram — into a page in the
review pages' own look. Run from the repository root:

    uv run python review/build_guide.py
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "REVIEWING.md"
OUT = ROOT / "review" / "reviewing.html"


def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>|`", "", s).lower()).strip("-")


def convert(md: str) -> tuple[str, list[tuple[int, str, str]], str]:
    lines = md.splitlines()
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    title = ""
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            lang = line[3:].strip()
            body = []
            i += 1
            while not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            if lang == "mermaid":
                out.append('<div class="diagram"><pre class="mermaid">' + html.escape("\n".join(body)) + "</pre></div>")
            else:
                out.append('<pre class="code"><code>' + html.escape("\n".join(body)) + "</code></pre>")
        elif m := re.match(r"(#{1,4}) (.*)", line):
            flush()
            n, text = len(m.group(1)), m.group(2)
            if n == 1:
                title = text
            else:
                toc.append((n, slug(text), inline(text)))
                out.append(f'<h{n} id="{slug(text)}">{inline(text)}</h{n}>')
        elif line.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            i -= 1
            head, body_rows = rows[0], [r for r in rows[2:]]
            t = ['<div class="table"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"]
            t += ["<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body_rows]
            out.append("".join(t) + "</tbody></table></div>")
        elif re.match(r"\s*(- |\d+\. )", line):
            flush()
            ordered = bool(re.match(r"\s*\d+\. ", line))
            items: list[str] = []
            while i < len(lines) and lines[i].strip() and (re.match(r"\s*(- |\d+\. )", lines[i]) or lines[i].startswith("  ")):
                if re.match(r"\s*(- |\d+\. )", lines[i]) and not lines[i].startswith("    "):
                    items.append(re.sub(r"^\s*(- |\d+\. )", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            i -= 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(it)}</li>" for it in items) + f"</{tag}>")
        elif not line.strip():
            flush()
        else:
            para.append(line.strip())
        i += 1
    flush()
    return title, toc, "\n".join(out)


PAGE = """<title>Reviewer's Guide</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Literata:opsz,wght@7..72,400;7..72,600&family=Public+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Layout: the review pages' marking-sheet look, as a guide: a contents rail beside one readable column. */
:root{
  --paper:#f7f8fa; --sheet:#ffffff; --ink:#1c2230; --muted:#5d6678; --rule:#dfe3ea; --wash:#eef1f6;
  --accent:#2453a8; --accent-wash:#e6edfa; --mark:#fff1a8;
  --f-read:"Literata", Georgia, "Times New Roman", serif;
  --f-ui:"Public Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --f-mono:"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#12151c; --sheet:#181c25; --ink:#e4e8f1; --muted:#9aa3b5; --rule:#2b3140; --wash:#1f2430;
  --accent:#8fb0f0; --accent-wash:#1d2840; --mark:#4a4214; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#12151c; --sheet:#181c25; --ink:#e4e8f1; --muted:#9aa3b5; --rule:#2b3140; --wash:#1f2430;
  --accent:#8fb0f0; --accent-wash:#1d2840; --mark:#4a4214; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.6 var(--f-read);padding-inline:16px;padding-block:24px 72px}
.wrap{max-width:1080px;margin:0 auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:40px}
@media (max-width:820px){.wrap{grid-template-columns:1fr;gap:16px}}
nav{position:sticky;top:calc(env(safe-area-inset-top,0px) + 16px);align-self:start;font:13px/1.45 var(--f-ui)}
@media (max-width:820px){nav{position:static}}
nav .eyebrow{font:600 11px/1 var(--f-ui);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 10px}
nav ol{list-style:none;margin:0;padding:0;display:grid;gap:6px}
nav a{color:var(--ink);text-decoration:none}
nav a:hover{color:var(--accent)}
nav li.l3{padding-left:12px;color:var(--muted)}
nav li.l3 a{color:var(--muted)}
main{min-width:0;max-width:72ch}
h1{font:600 34px/1.15 var(--f-read);margin:0 0 6px;text-wrap:balance}
.sub{font:14px/1.5 var(--f-ui);color:var(--muted);margin:0 0 28px}
h2{font:600 24px/1.25 var(--f-read);margin:44px 0 12px;padding-top:12px;border-top:1px solid var(--rule);text-wrap:balance}
h3{font:600 13px/1.3 var(--f-ui);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:28px 0 8px}
p,li{text-wrap:pretty}
ul,ol{padding-left:22px}
li{margin:4px 0}
a{color:var(--accent)}
code{font:13.5px/1.4 var(--f-mono);background:var(--wash);border-radius:3px;padding:1px 5px}
strong{font-weight:600}
.table{overflow-x:auto;margin:14px 0}
table{border-collapse:collapse;font:14px/1.45 var(--f-ui);min-width:100%}
th{font:600 11px/1.3 var(--f-ui);letter-spacing:.06em;text-transform:uppercase;color:var(--muted);text-align:left;border-bottom:2px solid var(--rule);padding:8px 10px}
td{border-bottom:1px solid var(--rule);padding:8px 10px;vertical-align:top}
.diagram{overflow-x:auto;background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:14px;margin:16px 0}
pre.mermaid{margin:0;background:transparent}
pre.code{overflow-x:auto;background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:12px 14px}
a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
</style>
<div class="wrap">
<nav aria-label="Contents"><p class="eyebrow">Contents</p><ol>__TOC__</ol></nav>
<main>
<h1>__TITLE__</h1>
<p class="sub">mobium-rag · for the person in the loop · built from REVIEWING.md</p>
__BODY__
</main>
</div>
"""


def main() -> None:
    title, toc, body = convert(SRC.read_text())
    nav = "".join(f'<li class="l{n}"><a href="#{s}">{t}</a></li>' for n, s, t in toc if n <= 3)
    OUT.write_text(PAGE.replace("__TOC__", nav).replace("__TITLE__", inline(title)).replace("__BODY__", body))
    print(f"{OUT.relative_to(ROOT)}: {len(toc)} sections")


if __name__ == "__main__":
    main()
