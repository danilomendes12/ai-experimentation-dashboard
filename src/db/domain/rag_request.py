from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RagRequest:
    request_id: str
    query: str
    config: dict[str, object] = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_latency_ms: float = 0.0
    ttft_ms: float | None = None
    faithfulness: float | None = None
    status: str = "pending"
    created_at: datetime | None = None
