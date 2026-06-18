"""Chunking-algorithm comparison module.

Index a Markdown corpus (``k8s`` or ``postgres``) into pgvector with a chosen
chunking strategy, then run vector search against it. Strategies are tagged in
the ``doc_chunks`` table so several can coexist and be compared.

CLI: ``uv run python -m chunking --help``
"""

from chunking.base import Chunk, ChunkingStrategy
from chunking.embeddings import Embedder, EmbedResult
from chunking.load_dataset import Document, load_dataset
from chunking.pipeline import index, search
from chunking.registry import REGISTRY, build_strategy

__all__ = [
    "REGISTRY",
    "Chunk",
    "ChunkingStrategy",
    "Document",
    "EmbedResult",
    "Embedder",
    "build_strategy",
    "index",
    "load_dataset",
    "search",
]
