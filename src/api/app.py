from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import iterate_in_threadpool

from db import LlmCall, LlmCallAnalytics, LlmCallRepository
from llm_calls import call_llm, list_models, stream_llm

from .schemas import (
    CallRequest,
    CallResponse,
    CostStatsSchema,
    DailySpendSchema,
    GenerateRequest,
    LatencyPercentilesSchema,
    LlmCallSchema,
    ModelOptionSchema,
    StatsResponse,
    TtftPercentilesSchema,
)

app = FastAPI(title="LLM Study API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_repo = LlmCallRepository()
_analytics = LlmCallAnalytics()


@app.get("/models")
def get_models() -> list[ModelOptionSchema]:
    return [ModelOptionSchema(provider=m.provider, model=m.model) for m in list_models()]


@app.post("/calls", status_code=201)
def create_call(body: CallRequest) -> CallResponse:
    try:
        result = call_llm(
            body.model,
            body.message,
            body.max_tokens,
            body.provider,
            system_prompt=body.system_prompt,
            temperature=body.temperature,
            top_p=body.top_p,
            top_k=body.top_k,
            repository=_repo,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return CallResponse(
        reply=result.reply,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
        ignored_params=result.ignored_params,
    )


@app.get("/calls")
def list_calls(
    model: Annotated[str | None, Query(description="Filter by model name")] = None,
    limit: Annotated[int, Query(gt=0, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[LlmCallSchema]:
    records = _repo.list_all(limit=limit, offset=offset, model=model)
    return [_to_schema(r) for r in records]


@app.get("/calls/{call_id}")
def get_call(call_id: int) -> LlmCallSchema:
    record = _repo.get(call_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Call {call_id} not found")
    return _to_schema(record)


@app.get("/stats")
def get_stats(
    model: Annotated[str | None, Query(description="Filter by model name")] = None,
    days: Annotated[int, Query(gt=0, description="Window for daily spend")] = 30,
) -> StatsResponse:
    cost = _analytics.cost_per_call(model=model)
    latency = _analytics.latency_percentiles(model=model)
    ttft = _analytics.ttft_percentiles(model=model)
    daily = _analytics.daily_spend(days=days)
    return StatsResponse(
        cost=CostStatsSchema(
            count=cost.count,
            total=cost.total,
            avg=cost.avg,
            min=cost.min,
            max=cost.max,
            model=cost.model,
        ),
        latency=LatencyPercentilesSchema(
            p50=latency.p50, p90=latency.p90, p99=latency.p99, model=latency.model
        )
        if latency
        else None,
        ttft=TtftPercentilesSchema(p50=ttft.p50, p90=ttft.p90, p99=ttft.p99, model=ttft.model)
        if ttft
        else None,
        daily_spend=[DailySpendSchema(date=d.date, total=d.total, count=d.count) for d in daily],
    )


@app.websocket("/ws/generate")
async def generate_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        data = await websocket.receive_json()
        body = GenerateRequest.model_validate(data)
    except (ValueError, WebSocketDisconnect) as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close(code=1008)
        return

    gen = stream_llm(
        body.model,
        body.user_prompt,
        body.params.max_tokens,
        body.provider,
        system_prompt=body.system_prompt,
        temperature=body.params.temperature,
        top_p=body.params.top_p,
        top_k=body.params.top_k,
        repository=_repo,
    )
    try:
        async for chunk in iterate_in_threadpool(gen):
            if chunk.type == "delta" and chunk.delta is not None:
                await websocket.send_json({"type": "token", "content": chunk.delta})
            elif chunk.type == "done":
                await websocket.send_json(
                    {
                        "type": "done",
                        "call_id": chunk.call_id,
                        "usage": {
                            "input_tokens": chunk.input_tokens or 0,
                            "output_tokens": chunk.output_tokens or 0,
                        },
                        "cost_usd": chunk.cost_usd or 0.0,
                        "ttft_ms": chunk.ttft_ms or 0.0,
                        "latency_ms": chunk.latency_ms or 0.0,
                        "ignored_params": chunk.ignored_params,
                    }
                )
    except Exception as exc:  # noqa: BLE001
        await websocket.send_json({"type": "error", "message": str(exc)})
    finally:
        gen.close()
        await websocket.close()


def _to_schema(call: LlmCall) -> LlmCallSchema:
    if call.id is None or call.created_at is None:
        msg = "LlmCall from DB is missing id or created_at"
        raise ValueError(msg)
    return LlmCallSchema(
        id=call.id,
        created_at=call.created_at,
        provider=call.provider,
        model=call.model,
        input_tokens=call.input_tokens,
        output_tokens=call.output_tokens,
        cost=call.cost,
        latency=call.latency,
        prompt=call.prompt,
        answer=call.answer,
        max_tokens=call.max_tokens,
        temperature=call.temperature,
        top_p=call.top_p,
        top_k=call.top_k,
        ttft_ms=call.ttft_ms,
        response_status=call.response_status,
        error_message=call.error_message,
        system_prompt=call.system_prompt,
        ignored_params=call.ignored_params,
        request_id=call.request_id,
        stage=call.stage,
    )
