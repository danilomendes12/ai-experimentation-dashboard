"""Unit tests for the recursive chunker — pure logic, no network or DB."""

import pytest

from chunking.strategies.recursive import RecursiveChunker
from chunking.tokens import count_tokens


def test_short_text_is_a_single_chunk() -> None:
    chunker = RecursiveChunker(chunk_size=100, chunk_overlap=10)
    chunks = chunker.split("A short paragraph that fits in one chunk.")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].n_tokens == count_tokens(chunks[0].content)


def test_long_text_respects_chunk_size() -> None:
    text = "\n\n".join(f"Paragraph number {i} with a few extra words here." for i in range(80))
    chunker = RecursiveChunker(chunk_size=60, chunk_overlap=10)
    chunks = chunker.split(text)
    assert len(chunks) > 1
    assert all(c.n_tokens <= 60 for c in chunks)


def test_chunk_indices_are_sequential() -> None:
    text = "\n\n".join(f"Section {i} content goes on for a little while." for i in range(40))
    chunks = RecursiveChunker(chunk_size=50, chunk_overlap=8).split(text)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_overlap_carries_context_between_chunks() -> None:
    # Many tiny pieces force the merger to pack + overlap rather than recurse.
    text = " ".join(f"word{i}" for i in range(300))
    chunks = RecursiveChunker(chunk_size=40, chunk_overlap=15).split(text)
    assert len(chunks) >= 2
    tail = set(chunks[0].content.split()[-10:])
    head = set(chunks[1].content.split()[:10])
    assert tail & head, "consecutive chunks should share overlapping tokens"


def test_empty_text_yields_no_chunks() -> None:
    assert RecursiveChunker().split("   \n\n  ") == []


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        RecursiveChunker(chunk_size=50, chunk_overlap=50)


def test_describe_reports_config() -> None:
    desc = RecursiveChunker(chunk_size=256, chunk_overlap=32).describe()
    assert desc["algorithm"] == "recursive"
    assert desc["chunk_size"] == 256
    assert desc["chunk_overlap"] == 32
