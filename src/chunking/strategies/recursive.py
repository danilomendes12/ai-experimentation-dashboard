"""Recursive character chunking, backed by ``langchain-text-splitters``.

Delegates to LangChain's ``RecursiveCharacterTextSplitter``: it tries to split on
the most semantic boundary available (Markdown headings, then blank lines,
newlines, sentences, words, characters) and only falls back to a finer separator
when a piece is still larger than ``chunk_size``.

The splitter is built ``from_tiktoken_encoder`` so ``chunk_size`` / ``chunk_overlap``
are measured in ``cl100k_base`` tokens — the same units as the embedding model.
"""

from __future__ import annotations

from langchain_text_splitters import RecursiveCharacterTextSplitter

from chunking.base import Chunk, ChunkingStrategy
from chunking.tokens import ENCODING_NAME, count_tokens

# Coarsest (most semantic) → finest. "" means split per-character as a last resort.
DEFAULT_SEPARATORS: list[str] = [
    "\n## ",
    "\n### ",
    "\n#### ",
    "\n\n",
    "\n",
    ". ",
    " ",
    "",
]


class RecursiveChunker(ChunkingStrategy):
    name = "recursive"

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            msg = "chunk_overlap must be smaller than chunk_size"
            raise ValueError(msg)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name=ENCODING_NAME,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=DEFAULT_SEPARATORS,
        )

    def describe(self) -> dict[str, object]:
        return {
            "algorithm": self.name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "backend": "langchain RecursiveCharacterTextSplitter",
            "length_unit": "tokens (cl100k_base)",
        }

    def split(self, text: str) -> list[Chunk]:
        pieces = [p for p in self._splitter.split_text(text) if p.strip()]
        return [
            Chunk(content=p, chunk_index=i, n_tokens=count_tokens(p)) for i, p in enumerate(pieces)
        ]
