"""Name → strategy lookup, so the CLI and pipeline stay strategy-agnostic.

To add an algorithm: implement :class:`~chunking.base.ChunkingStrategy` under
``strategies/`` and add one entry to :data:`REGISTRY`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from chunking.base import ChunkingStrategy
from chunking.strategies.fixed import FixedChunker
from chunking.strategies.recursive import RecursiveChunker
from chunking.strategies.semantic import SemanticChunker


@dataclass(frozen=True, slots=True)
class ChunkParams:
    """All chunking knobs the CLI can expose; each strategy uses what it needs."""

    chunk_size: int = 400
    chunk_overlap: int = 50
    breakpoint_percentile: float = 90.0


StrategyBuilder = Callable[[ChunkParams], ChunkingStrategy]

REGISTRY: dict[str, StrategyBuilder] = {
    "recursive": lambda p: RecursiveChunker(p.chunk_size, p.chunk_overlap),
    "fixed": lambda p: FixedChunker(p.chunk_size, p.chunk_overlap),
    "semantic": lambda p: SemanticChunker(p.breakpoint_percentile),
}


def build_strategy(name: str, params: ChunkParams) -> ChunkingStrategy:
    try:
        builder = REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(REGISTRY))
        msg = f"unknown algorithm {name!r}; available: {available}"
        raise SystemExit(msg) from None
    return builder(params)
