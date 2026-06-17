from pathlib import Path
from statistics import quantiles

from db.domain.cost_stats import CostStats
from db.domain.daily_spend import DailySpend
from db.domain.latency_percentiles import LatencyPercentiles
from db.domain.ttft_percentiles import TtftPercentiles
from db.infrastructure import DbBackend, make_backend


def _compute_percentiles(values: list[float]) -> tuple[float, float, float]:
    n = len(values)
    _min_for_quantiles = 4
    if n < _min_for_quantiles:
        return values[n // 2], values[-1], values[-1]
    # quantiles(data, n=100) returns 99 cut points; index i → p(i+1)
    cuts = quantiles(values, n=100)
    return cuts[49], cuts[89], cuts[98]


class LlmCallAnalytics:
    def __init__(self, target: Path | str | None = None) -> None:
        self._backend: DbBackend = make_backend(target)

    def cost_per_call(self, model: str | None = None) -> CostStats:
        ph = self._backend.placeholder
        sql = (
            "SELECT COUNT(*) AS cnt, SUM(cost) AS total, AVG(cost) AS avg,"
            " MIN(cost) AS min, MAX(cost) AS max"
            " FROM llm_calls WHERE response_status IN ('success', 'cancelled')"
        )
        params: list[str] = []
        if model is not None:
            sql += f" AND model = {ph}"
            params.append(model)
        with self._backend.connect() as conn:
            row = conn.execute(sql, params).fetchone()
        return CostStats(
            count=row["cnt"] or 0,
            total=row["total"] or 0.0,
            avg=row["avg"] or 0.0,
            min=row["min"] or 0.0,
            max=row["max"] or 0.0,
            model=model,
        )

    def latency_percentiles(self, model: str | None = None) -> LatencyPercentiles | None:
        ph = self._backend.placeholder
        sql = "SELECT latency FROM llm_calls WHERE response_status = 'success'"
        params: list[str] = []
        if model is not None:
            sql += f" AND model = {ph}"
            params.append(model)
        sql += " ORDER BY latency"
        with self._backend.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        if not rows:
            return None
        p50, p90, p99 = _compute_percentiles([float(r["latency"]) for r in rows])
        return LatencyPercentiles(p50=p50, p90=p90, p99=p99, model=model)

    def ttft_percentiles(self, model: str | None = None) -> TtftPercentiles | None:
        ph = self._backend.placeholder
        sql = "SELECT ttft_ms FROM llm_calls WHERE ttft_ms IS NOT NULL"
        params: list[str] = []
        if model is not None:
            sql += f" AND model = {ph}"
            params.append(model)
        sql += " ORDER BY ttft_ms"
        with self._backend.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        if not rows:
            return None
        p50, p90, p99 = _compute_percentiles([float(r["ttft_ms"]) for r in rows])
        return TtftPercentiles(p50=p50, p90=p90, p99=p99, model=model)

    def daily_spend(self, days: int = 30) -> list[DailySpend]:
        with self._backend.connect() as conn:
            rows = conn.execute(
                self._backend.daily_spend_sql(),
                (self._backend.daily_spend_param(days),),
            ).fetchall()
        return [
            DailySpend(date=str(r["day"]), total=float(r["total"]), count=int(r["cnt"]))
            for r in rows
        ]
