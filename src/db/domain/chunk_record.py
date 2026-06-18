from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """One embedded chunk ready to persist in ``doc_chunks``.

    Tagged with ``algorithm`` + ``dataset`` so chunking strategies coexist in a
    single table and can be queried / compared independently.
    """

    algorithm: str
    dataset: str
    source_path: str
    chunk_index: int
    content: str
    n_tokens: int
    embedding: list[float]
