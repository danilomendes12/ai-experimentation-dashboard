from dataclasses import dataclass


@dataclass
class TtftPercentiles:
    p50: float
    p90: float
    p99: float
    model: str | None = None
