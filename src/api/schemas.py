from datetime import datetime

from pydantic import BaseModel, Field

# ── Request ────────────────────────────────────────────────────────────────────


class CallRequest(BaseModel):
    provider: str
    model: str
    message: str
    max_tokens: int = Field(default=1024, gt=0)
    system_prompt: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None


class GenParams(BaseModel):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    max_tokens: int = Field(default=1024, gt=0)


class GenerateRequest(BaseModel):
    provider: str
    model: str
    system_prompt: str | None = None
    user_prompt: str
    params: GenParams = Field(default_factory=GenParams)


# ── Response: resultado imediato da chamada ────────────────────────────────────


class CallResponse(BaseModel):
    reply: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    ignored_params: list[str] = []


# ── Response: registro persistido ─────────────────────────────────────────────


class LlmCallSchema(BaseModel):
    id: int
    created_at: datetime
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    latency: float
    prompt: str
    answer: str
    max_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    ttft_ms: float | None = None
    response_status: str | None = None
    error_message: str | None = None
    system_prompt: str | None = None
    ignored_params: list[str] = []
    request_id: str | None = None
    stage: str | None = None


# ── Response: analytics ────────────────────────────────────────────────────────


class CostStatsSchema(BaseModel):
    count: int
    total: float
    avg: float
    min: float
    max: float
    model: str | None = None


class LatencyPercentilesSchema(BaseModel):
    p50: float
    p90: float
    p99: float
    model: str | None = None


class TtftPercentilesSchema(BaseModel):
    p50: float
    p90: float
    p99: float
    model: str | None = None


class DailySpendSchema(BaseModel):
    date: str
    total: float
    count: int


class StatsResponse(BaseModel):
    cost: CostStatsSchema
    latency: LatencyPercentilesSchema | None
    ttft: TtftPercentilesSchema | None
    daily_spend: list[DailySpendSchema]


class ModelOptionSchema(BaseModel):
    provider: str
    model: str
