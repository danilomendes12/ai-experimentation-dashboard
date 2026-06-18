"""Core abstractions shared by every chunking strategy.

A :class:`ChunkingStrategy` turns the raw Markdown of a single document into an
ordered list of :class:`Chunk` objects. Strategies own the splitting logic *and*
the token count of each piece (they already tokenize to measure length), so the
indexing pipeline never has to re-tokenize.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Chunk:
    """A single unit of text to embed and store, scoped to one source document."""

    content: str
    chunk_index: int  # position within its source document, starting at 0
    n_tokens: int


class ChunkingStrategy(abc.ABC):
    """Splits a document's text into chunks. One concrete class per algorithm."""

    #: Stable identifier persisted in ``doc_chunks.algorithm`` and used on the CLI.
    name: str

    @abc.abstractmethod
    def split(self, text: str) -> list[Chunk]:
        """Split ``text`` into ordered chunks (``chunk_index`` 0..n within it)."""

    @abc.abstractmethod
    def describe(self) -> dict[str, object]:
        """Return the strategy's configuration, for the indexing summary."""
