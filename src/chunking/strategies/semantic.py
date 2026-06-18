"""Semantic chunking.

Cut where meaning shifts: split the document into sentences, embed each one
(with a small neighbour buffer to denoise), measure the cosine distance between
*adjacent* sentence embeddings, and start a new chunk wherever that distance
spikes above the ``breakpoint_percentile`` of all distances. So the cut
criterion is the jump in embedding distance between neighbouring sentences.

This is the only strategy that calls the embedding API while splitting (every
other one is pure text), so it is the slowest / costliest to chunk with.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

from chunking.base import Chunk, ChunkingStrategy
from chunking.embeddings import Embedder
from chunking.tokens import count_tokens

# Maps a list of texts to their embedding vectors. Injectable for testing;
# defaults to the OpenAI embedder, built lazily so constructing a SemanticChunker
# (e.g. via the registry) never needs an API key until it actually splits.
EmbedFn = Callable[[list[str]], list[list[float]]]

_PERCENTILE_MAX = 100.0

# Sentence boundary: after .!? (incl. closing quote/paren), or a blank line.
_SENTENCE_RE = re.compile(r"(?<=[.!?])[\"')\]]?\s+|\n{2,}")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def _with_buffer(sentences: list[str], buffer_size: int) -> list[str]:
    """Combine each sentence with its ``buffer_size`` neighbours on each side."""
    if buffer_size <= 0:
        return sentences
    combined: list[str] = []
    for i in range(len(sentences)):
        lo = max(0, i - buffer_size)
        hi = min(len(sentences), i + buffer_size + 1)
        combined.append(" ".join(sentences[lo:hi]))
    return combined


def _neighbor_distances(vectors: list[list[float]]) -> list[float]:
    """Cosine distance (1 - cosine similarity) between consecutive vectors."""
    matrix = np.asarray(vectors, dtype=np.float64)
    normed = matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    sims = np.sum(normed[:-1] * normed[1:], axis=1)
    return [float(d) for d in (1.0 - sims)]


class SemanticChunker(ChunkingStrategy):
    name = "semantic"

    def __init__(
        self,
        breakpoint_percentile: float = 90.0,
        buffer_size: int = 1,
        embed_fn: EmbedFn | None = None,
    ) -> None:
        if not 0 < breakpoint_percentile < _PERCENTILE_MAX:
            msg = "breakpoint_percentile must be in (0, 100)"
            raise ValueError(msg)
        self.breakpoint_percentile = breakpoint_percentile
        self.buffer_size = buffer_size
        self._embed_fn = embed_fn
        self._embedder: Embedder | None = None

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._embed_fn is not None:
            return self._embed_fn(texts)
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder.embed(texts).vectors

    def describe(self) -> dict[str, object]:
        return {
            "algorithm": self.name,
            "breakpoint_percentile": self.breakpoint_percentile,
            "buffer_size": self.buffer_size,
            "cut_criterion": "cosine-distance spike between adjacent sentences",
        }

    def split(self, text: str) -> list[Chunk]:
        sentences = _split_sentences(text)
        if len(sentences) <= 1:
            content = text.strip()
            return [Chunk(content, 0, count_tokens(content))] if content else []

        vectors = self._embed(_with_buffer(sentences, self.buffer_size))
        distances = _neighbor_distances(vectors)
        threshold = float(np.percentile(distances, self.breakpoint_percentile))
        cut_after = {i for i, dist in enumerate(distances) if dist > threshold}

        chunks: list[Chunk] = []
        window: list[str] = []
        for i, sentence in enumerate(sentences):
            window.append(sentence)
            if i in cut_after:
                chunks.append(self._emit(window, len(chunks)))
                window = []
        if window:
            chunks.append(self._emit(window, len(chunks)))
        return [c for c in chunks if c.content]

    @staticmethod
    def _emit(sentences: list[str], index: int) -> Chunk:
        content = " ".join(sentences).strip()
        return Chunk(content=content, chunk_index=index, n_tokens=count_tokens(content))
