"""Orchestration: index a corpus with one strategy, and search it back.

``index`` runs the full pipeline (load → chunk → batch-embed → store) and prints
a summary of how the indexing went. ``search`` embeds a query and prints the
nearest chunks. Both are thin enough to read top to bottom.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from chunking.base import Chunk
from chunking.embeddings import EMBED_MODEL, Embedder
from chunking.load_dataset import load_dataset, load_document
from chunking.registry import ChunkParams, build_strategy
from chunking.tokens import count_tokens
from db import ChunkRecord, ChunkVectorStore


@dataclass(frozen=True, slots=True)
class _Placed:
    source_path: str
    chunk_index: int
    content: str
    n_tokens: int


def _percentile(sorted_values: list[int], pct: float) -> int:
    if not sorted_values:
        return 0
    idx = min(len(sorted_values) - 1, int(pct / 100 * len(sorted_values)))
    return sorted_values[idx]


def index(
    *,
    dataset: str,
    algorithm: str,
    params: ChunkParams,
    limit: int | None = None,
    replace: bool = True,
) -> None:
    strategy = build_strategy(algorithm, params)
    store = ChunkVectorStore()
    embedder = Embedder()

    print(f"→ Carregando dataset '{dataset}'...")
    docs = load_dataset(dataset, limit)

    # 1) Chunking
    t0 = time.perf_counter()
    placed: list[_Placed] = [
        _Placed(doc.source_path, c.chunk_index, c.content, c.n_tokens)
        for doc in docs
        for c in strategy.split(doc.text)
    ]
    chunk_ms = (time.perf_counter() - t0) * 1000

    if not placed:
        print("Nenhum chunk gerado — corpus vazio?")
        return

    # 2) Batch embedding
    print(f"→ Embeddando {len(placed)} chunks em batches de {embedder.batch_size}...")
    t1 = time.perf_counter()
    result = embedder.embed([p.content for p in placed])
    embed_ms = (time.perf_counter() - t1) * 1000

    # 3) Persist
    records = [
        ChunkRecord(
            algorithm=strategy.name,
            dataset=dataset,
            source_path=p.source_path,
            chunk_index=p.chunk_index,
            content=p.content,
            n_tokens=p.n_tokens,
            embedding=vector,
        )
        for p, vector in zip(placed, result.vectors, strict=True)
    ]
    deleted = store.delete(strategy.name, dataset) if replace else 0
    t2 = time.perf_counter()
    store.add(records)
    insert_ms = (time.perf_counter() - t2) * 1000

    _print_summary(
        strategy_desc=strategy.describe(),
        dataset=dataset,
        n_docs=len(docs),
        token_sizes=sorted(p.n_tokens for p in placed),
        result_tokens=result.total_tokens,
        result_cost=result.cost_usd,
        chunk_ms=chunk_ms,
        embed_ms=embed_ms,
        insert_ms=insert_ms,
        deleted=deleted,
        total_in_store=store.count(strategy.name, dataset),
    )


def search(*, dataset: str, algorithm: str, query: str, k: int = 5) -> None:
    embedder = Embedder()
    store = ChunkVectorStore()

    result = embedder.embed([query])
    hits = store.search(result.vectors[0], algorithm, dataset, k)

    print(f"\nBusca: {query!r}")
    print(f"  dataset={dataset}  algoritmo={algorithm}  modelo={EMBED_MODEL}")
    print(f"  custo da query: ${result.cost_usd:.6f} ({result.total_tokens} tokens)\n")
    if not hits:
        print("  (nenhum resultado — esse algoritmo/dataset já foi indexado?)")
        return
    for rank, hit in enumerate(hits, start=1):
        snippet = " ".join(hit.content.split())[:200]
        print(
            f"  {rank}. [dist {hit.distance:.4f}] {hit.source_path}#{hit.chunk_index} "
            f"({hit.n_tokens} tok)"
        )
        print(f"     {snippet}…\n")


def _print_summary(
    *,
    strategy_desc: dict[str, object],
    dataset: str,
    n_docs: int,
    token_sizes: list[int],
    result_tokens: int,
    result_cost: float,
    chunk_ms: float,
    embed_ms: float,
    insert_ms: float,
    deleted: int,
    total_in_store: int,
) -> None:
    n = len(token_sizes)
    avg = sum(token_sizes) / n
    cfg = "  ".join(f"{k}={v}" for k, v in strategy_desc.items())
    print("\n" + "=" * 64)
    print("RESUMO DA INDEXAÇÃO")
    print("=" * 64)
    print(f"Config        {cfg}")
    print(f"Dataset       {dataset}  ({n_docs} documentos)")
    print(f"Chunks        {n} gerados  (~{n / n_docs:.1f} por documento)")
    print(
        f"Tokens/chunk  min={token_sizes[0]}  p50={_percentile(token_sizes, 50)}  "
        f"avg={avg:.0f}  p90={_percentile(token_sizes, 90)}  max={token_sizes[-1]}"
    )
    print(f"Embeddings    {result_tokens} tokens  →  ${result_cost:.4f}")
    print(
        f"Tempos        chunking={chunk_ms:.0f}ms  embedding={embed_ms:.0f}ms  "
        f"insert={insert_ms:.0f}ms"
    )
    if deleted:
        print(f"Substituição  {deleted} chunks antigos removidos")
    print(f"Total armazenado para ({strategy_desc['algorithm']}, {dataset}): {total_in_store}")
    print("=" * 64)


def compare(
    *,
    dataset: str,
    source_path: str,
    algorithms: list[str],
    params: ChunkParams,
    preview_chars: int = 90,
) -> None:
    """Chunk one document with several algorithms and show how each partitioned it."""
    doc = load_document(dataset, source_path)
    print(f"\nComparando chunking de {dataset}:{source_path}  ({count_tokens(doc.text)} tokens)")

    partitions: dict[str, list[Chunk]] = {}
    for algorithm in algorithms:
        strategy = build_strategy(algorithm, params)
        chunks = strategy.split(doc.text)
        partitions[algorithm] = chunks
        _print_partition(algorithm, strategy.describe(), chunks, preview_chars)

    _print_compare_table(partitions)


def _print_partition(
    algorithm: str, desc: dict[str, object], chunks: list[Chunk], preview_chars: int
) -> None:
    cfg = "  ".join(f"{k}={v}" for k, v in desc.items() if k != "algorithm")
    print(f"\n── {algorithm}  ({cfg}) ──")
    print(f"   {len(chunks)} chunks")
    for chunk in chunks:
        preview = " ".join(chunk.content.split())[:preview_chars]
        print(f"   [{chunk.chunk_index:>2}] {chunk.n_tokens:>4} tok │ {preview}…")


def _print_compare_table(partitions: dict[str, list[Chunk]]) -> None:
    print("\n" + "=" * 64)
    print("RESUMO DA COMPARAÇÃO")
    print("=" * 64)
    print(f"{'algoritmo':<12} {'chunks':>7} {'min':>5} {'avg':>5} {'p90':>5} {'max':>5}")
    for algorithm, chunks in partitions.items():
        sizes = sorted(c.n_tokens for c in chunks)
        if not sizes:
            print(f"{algorithm:<12} {0:>7}")
            continue
        avg = sum(sizes) / len(sizes)
        print(
            f"{algorithm:<12} {len(sizes):>7} {sizes[0]:>5} {avg:>5.0f} "
            f"{_percentile(sizes, 90):>5} {sizes[-1]:>5}"
        )
    print("=" * 64)
