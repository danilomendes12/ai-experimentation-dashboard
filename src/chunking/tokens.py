"""Token counting shared by the splitters and the embedder.

``text-embedding-3-*`` tokenize with ``cl100k_base``, so measuring chunk length
in those same tokens keeps splitting consistent with what the embedding API
actually charges and truncates on.
"""

from __future__ import annotations

import tiktoken

ENCODING_NAME = "cl100k_base"
_ENCODING = tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(text: str) -> int:
    """Number of ``cl100k_base`` tokens in ``text``."""
    return len(_ENCODING.encode(text))


def encode(text: str) -> list[int]:
    """Encode ``text`` to ``cl100k_base`` token ids (used by fixed chunking)."""
    return _ENCODING.encode(text)


def decode(token_ids: list[int]) -> str:
    """Inverse of :func:`encode`."""
    return _ENCODING.decode(token_ids)
