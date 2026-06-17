"""Fetch a subset of the kubernetes/website docs as clean Markdown.

Sparse-clones `content/en/docs/{concepts,tutorials}` from kubernetes/website,
strips Hugo frontmatter / shortcodes / nav noise, and writes content-only
Markdown into ``data/k8s_docs/``, mirroring the source tree.

Run: ``uv run python scripts/fetch_k8s_docs.py``

The clone lives under ``data/_src/website`` (gitignored) and is reused on
subsequent runs. Output is idempotent (the destination is rebuilt each run).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/kubernetes/website.git"
# Subdirectories of content/en/docs to extract (the chosen subset).
SUBDIRS = ["content/en/docs/concepts", "content/en/docs/tutorials"]

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "_src" / "website"
OUT_DIR = ROOT / "data" / "k8s_docs"

# Minimum cleaned body length (chars) for a file to be kept; drops section
# landing stubs that are basically just frontmatter.
MIN_BODY_CHARS = 80

# --- regexes -----------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
TITLE_RE = re.compile(r"^title:\s*(.+?)\s*$", re.MULTILINE)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# {{< glossary_tooltip ... text="X" ... >}} -> X  (attr order varies)
GLOSSARY_TEXT_RE = re.compile(r'\{\{<\s*glossary_tooltip\b[^>]*?\btext="([^"]*)"[^>]*?>\}\}')
# Paired markers we want to drop while keeping their inner content.
PAIRED_MARKER_RE = re.compile(
    r"\{\{[<%]\s*/?\s*"
    r"(?:note|caution|warning|tip|important|tabs|tab|highlight|blockquote"
    r"|glossary_tooltip|glossary_definition)\b[^}]*?[%>]\}\}"
)
# {{% heading "whatsnext" %}} -> a real Markdown heading.
HEADING_RE = re.compile(r'\{\{%\s*heading\s+"?([a-zA-Z]+)"?\s*%\}\}')
HEADING_LABELS = {
    "whatsnext": "What's next",
    "prerequisites": "Before you begin",
    "objectives": "Objectives",
    "cleanup": "Cleaning up",
    "synopsis": "Synopsis",
    "examples": "Examples",
    "editrequired": "",
}
# Anything still wrapped in a shortcode (self-closing or leftover) -> drop.
ANY_SHORTCODE_RE = re.compile(r"\{\{[<%].*?[%>]\}\}", re.DOTALL)
MULTI_BLANK_RE = re.compile(r"\n{3,}")


def _heading_repl(match: re.Match[str]) -> str:
    key = match.group(1).lower()
    label = HEADING_LABELS.get(key, key.replace("_", " ").capitalize())
    return f"## {label}" if label else ""


def clean_markdown(text: str) -> tuple[str | None, str]:
    """Return ``(title, cleaned_body)`` for a Hugo Markdown file."""
    title: str | None = None
    fm = FRONTMATTER_RE.match(text)
    if fm:
        title_match = TITLE_RE.search(fm.group(1))
        if title_match:
            title = title_match.group(1).strip().strip("\"'")
        text = text[fm.end() :]

    text = HTML_COMMENT_RE.sub("", text)
    text = GLOSSARY_TEXT_RE.sub(lambda m: m.group(1), text)
    text = HEADING_RE.sub(_heading_repl, text)
    text = PAIRED_MARKER_RE.sub("", text)
    text = ANY_SHORTCODE_RE.sub("", text)
    text = MULTI_BLANK_RE.sub("\n\n", text)
    return title, text.strip()


def ensure_clone() -> None:
    """Sparse + shallow clone the chosen subset, reusing an existing clone."""
    if (SRC_DIR / ".git").exists():
        print(f"[k8s] reusing clone at {SRC_DIR.relative_to(ROOT)}")
        return
    SRC_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"[k8s] cloning {REPO_URL} (sparse, depth 1)...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO_URL, str(SRC_DIR)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(SRC_DIR), "sparse-checkout", "set", *SUBDIRS],
        check=True,
    )


def build() -> None:
    ensure_clone()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    kept = skipped = 0
    for sub in SUBDIRS:
        base = SRC_DIR / sub
        for md in sorted(base.rglob("*.md")):
            title, body = clean_markdown(md.read_text(encoding="utf-8"))
            if len(body) < MIN_BODY_CHARS:
                skipped += 1
                continue
            out_rel = md.relative_to(SRC_DIR / "content" / "en" / "docs")
            out_path = OUT_DIR / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            header = f"# {title}\n\n" if title else ""
            out_path.write_text(header + body + "\n", encoding="utf-8")
            kept += 1

    print(f"[k8s] wrote {kept} files to {OUT_DIR.relative_to(ROOT)} ({skipped} stubs skipped)")


if __name__ == "__main__":
    build()
