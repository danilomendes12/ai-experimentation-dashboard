from dataclasses import dataclass, field
from datetime import datetime

from .stage import Stage


@dataclass
class LlmCall:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency: float
    prompt: str
    answer: str
    id: int | None = None
    created_at: datetime | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    ttft_ms: float | None = None
    response_status: str | None = None
    error_message: str | None = None
    system_prompt: str | None = None
    ignored_params: list[str] = field(default_factory=list)
    request_id: str | None = None
    stage: Stage | None = None
