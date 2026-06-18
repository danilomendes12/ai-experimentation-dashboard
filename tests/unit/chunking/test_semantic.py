"""Unit tests for the semantic chunker.

A fake ``embed_fn`` makes the breakpoint deterministic (no network): "apple"
sentences embed near one axis, "boat" sentences near the orthogonal one, so the
only large neighbour distance is at the topic switch.
"""

import pytest

from chunking.strategies.semantic import SemanticChunker


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0] if "apple" in t.lower() else [0.0, 1.0] for t in texts]


APPLES_THEN_BOATS = (
    "Apples are red. Apples are sweet. Apples grow on trees. "
    "Boats float on water. Boats have sails. Boats are big."
)


def test_cut_happens_at_the_topic_switch() -> None:
    chunker = SemanticChunker(breakpoint_percentile=80, buffer_size=0, embed_fn=_fake_embed)
    chunks = chunker.split(APPLES_THEN_BOATS)
    assert len(chunks) == 2
    assert "apple" in chunks[0].content.lower()
    assert "boat" in chunks[1].content.lower()
    assert "boat" not in chunks[0].content.lower()
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_single_sentence_is_one_chunk() -> None:
    chunks = SemanticChunker(embed_fn=_fake_embed).split("Just one sentence with no boundary")
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_empty_text_yields_no_chunks() -> None:
    assert SemanticChunker(embed_fn=_fake_embed).split("   \n\n  ") == []


def test_invalid_percentile_rejected() -> None:
    with pytest.raises(ValueError, match="breakpoint_percentile"):
        SemanticChunker(breakpoint_percentile=100)


def test_describe_reports_cut_criterion() -> None:
    desc = SemanticChunker(breakpoint_percentile=95, embed_fn=_fake_embed).describe()
    assert desc["algorithm"] == "semantic"
    assert desc["breakpoint_percentile"] == 95
    assert "distance" in str(desc["cut_criterion"])
