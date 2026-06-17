from dataclasses import dataclass


@dataclass
class CostStats:
    count: int
    total: float
    avg: float
    min: float
    max: float
    model: str | None = None
