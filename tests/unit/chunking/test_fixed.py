"""Unit tests for the fixed-size chunker — pure logic, no network or DB."""

import pytest

from chunking.strategies.fixed import FixedChunker
from chunking.tokens import count_tokens, encode


def test_short_text_is_a_single_chunk() -> None:
    chunks = FixedChunker(chunk_size=100, chunk_overlap=10).split("just a few tokens here")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_windows_respect_chunk_size() -> None:
    text = " ".join(f"word{i}" for i in range(500))
    chunks = FixedChunker(chunk_size=50, chunk_overlap=10).split(text)
    assert len(chunks) > 1
    assert all(c.n_tokens <= 50 for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_windows_advance_by_size_minus_overlap() -> None:
    text = " ".join(f"word{i}" for i in range(300))
    size, overlap = 40, 15
    chunks = FixedChunker(chunk_size=size, chunk_overlap=overlap).split(text)
    # Number of windows ≈ ceil((n_tokens - overlap) / (size - overlap)).
    n_tokens = len(encode(text))
    step = size - overlap
    expected = -(-(n_tokens - overlap) // step)
    assert len(chunks) == expected


def test_empty_text_yields_no_chunks() -> None:
    assert FixedChunker().split("   ") == []


def test_n_tokens_matches_content() -> None:
    text = " ".join(str(i) for i in range(200))
    chunks = FixedChunker(chunk_size=30, chunk_overlap=5).split(text)
    assert all(c.n_tokens == count_tokens(c.content) for c in chunks)


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError, match="chunk_overlap"):
        FixedChunker(chunk_size=20, chunk_overlap=20)
