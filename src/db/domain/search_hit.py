from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A single nearest-neighbour result from the chunk vector store."""

    source_path: str
    chunk_index: int
    content: str
    n_tokens: int
    distance: float
