"""Loading the Markdown corpora built by ``scripts/fetch_*_docs.py``.

Two datasets live under ``data/`` (gitignored): ``k8s`` and ``postgres``. Pick
one to index — they are kept separate end to end via the ``dataset`` column.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]

DATASETS: dict[str, Path] = {
    "k8s": _ROOT / "data" / "k8s_docs",
    "postgres": _ROOT / "data" / "postgres_docs",
}


@dataclass(frozen=True, slots=True)
class Document:
    source_path: str  # path relative to the dataset root, e.g. "concepts/overview.md"
    text: str


def _dataset_root(name: str) -> Path:
    try:
        base = DATASETS[name]
    except KeyError:
        available = ", ".join(sorted(DATASETS))
        msg = f"unknown dataset {name!r}; available: {available}"
        raise SystemExit(msg) from None
    if not base.exists():
        msg = (
            f"dataset dir {base} not found — build it first with "
            f"scripts/fetch_{'postgres' if name == 'postgres' else 'k8s'}_docs.py"
        )
        raise SystemExit(msg)
    return base


def load_dataset(name: str, limit: int | None = None) -> list[Document]:
    """Read every ``*.md`` file of a dataset (optionally capped at ``limit``)."""
    base = _dataset_root(name)
    files = sorted(base.rglob("*.md"))
    if limit is not None:
        files = files[:limit]
    return [
        Document(source_path=str(f.relative_to(base)), text=f.read_text(encoding="utf-8"))
        for f in files
    ]


def load_document(name: str, source_path: str) -> Document:
    """Read a single document of a dataset by its relative ``source_path``."""
    path = _dataset_root(name) / source_path
    if not path.is_file():
        msg = f"document {source_path!r} not found in dataset {name!r} ({path})"
        raise SystemExit(msg)
    return Document(source_path=source_path, text=path.read_text(encoding="utf-8"))
