from dataclasses import dataclass


@dataclass
class DailySpend:
    date: str
    total: float
    count: int
