from dataclasses import dataclass


@dataclass
class LatencyPercentiles:
    p50: float
    p90: float
    p99: float
    model: str | None = None
