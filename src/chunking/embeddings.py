"""Batch embedding via the OpenAI API.

Anthropic has no embeddings endpoint, so the vector side of this study uses
OpenAI ``text-embedding-3-small`` (1536 dims). Texts are sent in batches to
amortize HTTP overhead; cost is derived from the reported token usage.
"""

from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
# USD per 1M tokens — https://openai.com/api/pricing/
PRICE_PER_MTOK = 0.02


@dataclass(frozen=True, slots=True)
class EmbedResult:
    vectors: list[list[float]]
    total_tokens: int
    cost_usd: float


class Embedder:
    """Thin batching wrapper over the OpenAI embeddings endpoint."""

    def __init__(self, model: str = EMBED_MODEL, batch_size: int = 128) -> None:
        self.client = OpenAI()
        self.model = model
        self.batch_size = batch_size

    def embed(self, texts: list[str]) -> EmbedResult:
        vectors: list[list[float]] = []
        total_tokens = 0
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            vectors.extend(item.embedding for item in response.data)
            total_tokens += response.usage.total_tokens
        cost = total_tokens / 1_000_000 * PRICE_PER_MTOK
        return EmbedResult(vectors=vectors, total_tokens=total_tokens, cost_usd=cost)

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text]).vectors[0]
