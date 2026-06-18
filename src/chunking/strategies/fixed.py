"""Fixed-size chunking.

The simplest baseline: ignore document structure entirely and cut the token
stream into equal ``chunk_size`` windows that slide forward by
``chunk_size - chunk_overlap`` tokens. Fast and deterministic, but blind to
sentence/paragraph boundaries — useful as a comparison floor.
"""

from __future__ import annotations

from chunking.base import Chunk, ChunkingStrategy
from chunking.tokens import count_tokens, decode, encode


class FixedChunker(ChunkingStrategy):
    name = "fixed"

    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        if chunk_overlap >= chunk_size:
            msg = "chunk_overlap must be smaller than chunk_size"
            raise ValueError(msg)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def describe(self) -> dict[str, object]:
        return {
            "algorithm": self.name,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "length_unit": "tokens (cl100k_base)",
        }

    def split(self, text: str) -> list[Chunk]:
        tokens = encode(text)
        step = self.chunk_size - self.chunk_overlap
        chunks: list[Chunk] = []
        index = 0
        for start in range(0, len(tokens), step):
            content = decode(tokens[start : start + self.chunk_size]).strip()
            if content:
                chunks.append(
                    Chunk(content=content, chunk_index=index, n_tokens=count_tokens(content))
                )
                index += 1
            if start + self.chunk_size >= len(tokens):
                break  # this window already reached the end; avoid a dup tail
        return chunks
