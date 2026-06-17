from pathlib import Path

import pytest

from db import RagRequest, RagRequestRepository


@pytest.fixture
def repo(tmp_path: Path) -> RagRequestRepository:
    return RagRequestRepository(tmp_path / "test.db")


def _rag(**kwargs: object) -> RagRequest:
    defaults: dict[str, object] = {
        "request_id": "req-1",
        "query": "what is rag?",
        "config": {"k": 5, "rerank": True},
        "total_cost_usd": 0.02,
        "total_latency_ms": 350.0,
        "status": "running",
    }
    defaults.update(kwargs)
    return RagRequest(**defaults)  # type: ignore[arg-type]


def test_save_sets_created_at(repo: RagRequestRepository) -> None:
    saved = repo.save(_rag())
    assert saved.created_at is not None


def test_get_roundtrips_config_json(repo: RagRequestRepository) -> None:
    repo.save(_rag())
    got = repo.get("req-1")
    assert got is not None
    assert got.config == {"k": 5, "rerank": True}
    assert got.faithfulness is None
    assert got.ttft_ms is None
    assert got.status == "running"


def test_get_unknown_id_returns_none(repo: RagRequestRepository) -> None:
    assert repo.get("nope") is None


def test_update_sets_status_and_faithfulness(repo: RagRequestRepository) -> None:
    repo.save(_rag())
    repo.update("req-1", status="done", faithfulness=0.91)
    got = repo.get("req-1")
    assert got is not None
    assert got.status == "done"
    assert got.faithfulness == pytest.approx(0.91)


def test_update_with_no_fields_is_noop(repo: RagRequestRepository) -> None:
    repo.save(_rag())
    repo.update("req-1")
    got = repo.get("req-1")
    assert got is not None
    assert got.status == "running"
