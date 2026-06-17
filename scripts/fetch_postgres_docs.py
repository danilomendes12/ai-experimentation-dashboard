"""Fetch the PostgreSQL documentation as clean Markdown.

The official Postgres docs are DocBook SGML under ``doc/src/sgml``. This script
sparse-clones that directory, neutralizes the custom/include entities that
break a per-file XML parse, converts each chapter/reference file to GitHub
Markdown via ``pandoc``, strips unresolved cross-reference artifacts, and writes
the result into ``data/postgres_docs/``.

Requires pandoc on PATH (``brew install pandoc``).

Run: ``uv run python scripts/fetch_postgres_docs.py``
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO_URL = "https://github.com/postgres/postgres.git"
SUBDIR = "doc/src/sgml"

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "_src" / "postgres"
SGML_DIR = SRC_DIR / SUBDIR
OUT_DIR = ROOT / "data" / "postgres_docs"

MIN_BODY_CHARS = 120

# Master / include-only files that hold no prose of their own.
SKIP_FILES = {"postgres.sgml", "filelist.sgml", "version.sgml", "standalone-profile.sgml"}

# XML built-ins pandoc resolves on its own; keep them intact.
BUILTIN_ENTITIES = {"lt", "gt", "amp", "quot", "apos"}
# Map the named character entities Postgres uses to literal Unicode.
CHAR_ENTITIES = {
    "mdash": "—",
    "ndash": "–",
    "nbsp": " ",
    "sect": "§",
    "bull": "•",
    "copy": "©",
    "rarr": "→",
    "larr": "←",
    "zwsp": "\u200b",
    "ocirc": "ô",
    "aacute": "á",
    "oacute": "ó",
    "eacute": "é",
    "uuml": "ü",
    "auml": "ä",
    "ouml": "ö",
    "ccedil": "ç",
    "AElig": "Æ",
    "times": "×",
    "deg": "°",
    "hellip": "…",
    "trade": "™",
    "reg": "®",
}

ENTITY_RE = re.compile(r"&([a-zA-Z][a-zA-Z0-9._-]*);")
# Unresolved DocBook xref -> pandoc emits [???](#anchor); drop the noise.
XREF_RE = re.compile(r"\[\?\?\?\]\(#[^)]*\)")
MULTI_BLANK_RE = re.compile(r"\n{3,}")


def _entity_repl(match: re.Match[str]) -> str:
    name = match.group(1)
    if name in BUILTIN_ENTITIES:
        return match.group(0)
    return CHAR_ENTITIES.get(name, "")  # drop version vars / file includes


def preprocess(sgml: str) -> str:
    """Neutralize entities so pandoc can parse a single file as XML."""
    sgml = re.sub(r"<!DOCTYPE.*?>", "", sgml, flags=re.DOTALL)
    return ENTITY_RE.sub(_entity_repl, sgml)


def convert(sgml_path: Path) -> str | None:
    """Convert one SGML file to cleaned Markdown, or ``None`` on failure."""
    source = preprocess(sgml_path.read_text(encoding="utf-8"))
    try:
        result = subprocess.run(
            ["pandoc", "-f", "docbook", "-t", "gfm", "--wrap=none"],
            input=source,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return None
    md = XREF_RE.sub("", result.stdout)
    md = MULTI_BLANK_RE.sub("\n\n", md)
    return md.strip()


def ensure_clone() -> None:
    if (SRC_DIR / ".git").exists():
        print(f"[pg] reusing clone at {SRC_DIR.relative_to(ROOT)}")
        return
    SRC_DIR.parent.mkdir(parents=True, exist_ok=True)
    print(f"[pg] cloning {REPO_URL} (sparse, depth 1)...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", REPO_URL, str(SRC_DIR)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(SRC_DIR), "sparse-checkout", "set", SUBDIR],
        check=True,
    )


def build() -> None:
    if shutil.which("pandoc") is None:
        raise SystemExit("pandoc not found on PATH — run: brew install pandoc")
    ensure_clone()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    kept = skipped = failed = 0
    for sgml in sorted(SGML_DIR.rglob("*.sgml")):
        if sgml.name in SKIP_FILES:
            continue
        md = convert(sgml)
        if md is None:
            failed += 1
            continue
        if len(md) < MIN_BODY_CHARS:
            skipped += 1
            continue
        out_path = (OUT_DIR / sgml.relative_to(SGML_DIR)).with_suffix(".md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md + "\n", encoding="utf-8")
        kept += 1

    print(
        f"[pg] wrote {kept} files to {OUT_DIR.relative_to(ROOT)} "
        f"({skipped} thin skipped, {failed} pandoc failures)"
    )


if __name__ == "__main__":
    build()
