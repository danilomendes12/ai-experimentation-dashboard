# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A personal learning/study repository for AI engineering. Code here consists of self-contained experiments and exercises against LLM provider SDKs (Anthropic, OpenAI, Gemini, Ollama) — not a production application. Expect throwaway scripts and small modules over a cohesive architecture.

## Environment & commands

This project uses **uv** as the package manager and Python **3.12**.

- Install/sync dependencies: `uv sync`
- Run a script: `uv run python <path>` (e.g. `uv run python main.py`)
- Lint: `uv run ruff check` (add `--fix` to autofix)
- Format: `uv run ruff format`
- Type check: `uv run mypy <path>`
- Run all pre-commit hooks manually: `uv run pre-commit run --all-files`
- Install the git hook: `uv run pre-commit install`
- Run tests: `uv run pytest`

## Key modules

### `src/llm_calls/`
Abstract LLM call layer with a unified interface across four providers:
- `base.py` — `CallLLMFn` ABC, `LLMResponse` and `StreamChunk` dataclasses.
- `anthropic_client.py`, `openai_client.py`, `gemini_client.py`, `ollama_client.py` — concrete implementations.
- `__init__.py` — exports `call_llm(model, message, max_tokens, provider)` and `stream_llm(...)`. Both functions automatically persist every call to the SQLite repository (see below).

Ollama notes: uses the OpenAI-compatible REST API (`http://localhost:11434/v1`); no API key required; `cost_usd` is always `0.0`; `top_k` is ignored (appended to `ignored_params`). Override the URL via `OLLAMA_BASE_URL`.

### `src/db/`
Persistence and analytics layer backed by **Postgres + pgvector** at runtime (`docker compose up -d`; connection string in `DATABASE_URL`), with a SQLite fallback used by the test suite. Organized in pragmatic DDD layers, one class per file:

- `domain/` — entities and value objects: `LlmCall` (carries optional `request_id`/`stage`), `RagRequest`, the `Stage` literal (`embed`|`rerank`|`generate`), and analytics outputs `CostStats`, `LatencyPercentiles`, `TtftPercentiles`, `DailySpend`.
- `infrastructure/` — the dialect adapters. `base.py` (`DbBackend` ABC), `sqlite.py` (`SqliteBackend`), `postgres.py` (`PostgresBackend`), `factory.py` (`make_backend`). `make_backend(target)` returns `SqliteBackend` for a `Path` (tests) or `PostgresBackend` for a DSN `str`/`None` (reads `DATABASE_URL`), hiding every SQL-dialect difference (placeholders, auto-increment, timestamp/JSON handling).
- `repositories/` — `LlmCallRepository` (`save`, `get`, `list_all`), `RagRequestRepository` (`save`, `get`, `update`), and `LlmCallAnalytics` (`cost_per_call`, `latency_percentiles`, `ttft_percentiles`, `daily_spend`). Percentiles are computed in Python, so results match across both backends.
- `__init__.py` — facade that re-exports the public API, so `from db import LlmCall, LlmCallRepository, ...` keeps working.

**Schema ownership:** on Postgres the schema is owned by **Flyway** — versioned `.sql` under `migrations/`, applied by the `flyway` service in `docker-compose.yml` (`PostgresBackend.schema_sql()` returns `[]`, so the app never issues DDL). The SQLite test backend keeps an equivalent in-code DDL in `infrastructure/sqlite.py`; **keep the two in sync** when changing the schema (add a new `migrations/Vn__*.sql` and mirror it in `sqlite.py`).

Tables: `llm_calls` (one row per LLM call, with `request_id`/`stage`) and `rag_request` (`request_id` PK, `query`, `config_json`, `total_cost_usd`, `total_latency_ms`, `ttft_ms` nullable, `faithfulness` nullable, `status`).

### `src/api/`
API HTTP construída com FastAPI, exposta via uvicorn:
- `schemas.py` — modelos Pydantic de request/response (`CallRequest`, `CallResponse`, `LlmCallSchema`, `StatsResponse` e auxiliares).
- `app.py` — instância FastAPI com as rotas abaixo. Usa `_repo` e `_analytics` como singletons de módulo.

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/calls` | Executa uma chamada LLM e persiste o resultado |
| `GET` | `/calls` | Lista chamadas (`?model=`, `?limit=`, `?offset=`) |
| `GET` | `/calls/{id}` | Retorna um registro específico |
| `GET` | `/stats` | Agregações de custo, latência, TTFT e gasto diário (`?model=`, `?days=`) |
| `WS` | `/ws/stream` | Streaming de resposta LLM via WebSocket; aceita o mesmo payload `CallRequest` como JSON e devolve chunks `StreamChunk` até um `{"type":"done"}` final |

Rodar localmente: `uv run uvicorn api.app:app --reload`
Documentação interativa: `http://localhost:8000/docs`

### `dashboard/`
Next.js 16 front-end (pnpm, TypeScript, Tailwind CSS, shadcn/ui). Connects exclusively to the FastAPI backend — API keys never leave the Python process.

- `app/dashboard/` — analytics page: stat cards (cost, latency p50/p90/p99, TTFT), cost-by-model bar chart, paginated calls table with a detail sheet per row.
- `app/playground/` — side-by-side model comparison (up to 3 models): config rail with system/user prompts and optional `temperature`, `top_p`, `top_k`, `max_tokens` params; each column streams tokens over `WS /ws/generate` and displays latency/cost/TTFT on completion.
- `lib/config.ts` — reads `NEXT_PUBLIC_API_BASE` (default `http://localhost:8000`) and derives `WS_BASE`.
- `lib/types.ts` — shared TypeScript types (`GenParams`, `ModelOption`, WebSocket frame shapes, REST response shapes).

Run: `cd dashboard && pnpm dev` → `http://localhost:3000`

Backend must be running first: `uv run uvicorn api.app:app --reload`

### `tests/`
Pytest suite (`uv run pytest`):
- `tests/db/test_analytics.py` — unit tests for every analytics query using an in-memory SQLite fixture.
- `tests/test_providers.py` — integration tests calling real provider APIs (Anthropic, OpenAI, Gemini) for both `call_llm` and `stream_llm`, and verifying persistence. Gemini is marked `xfail` to tolerate quota failures.
- `tests/test_ollama.py` — integration tests for the Ollama provider. All tests are auto-skipped when Ollama is not reachable on port 11434 (`skipif` checks socket connectivity at collection time).

## Conventions

- New experiments go under `src/`, grouped into a subdirectory per topic (see `src/hello_world/`). `main.py` at the repo root is a standalone scratch entry point.
- pre-commit runs `ruff check --fix`, `ruff format`, and `mypy` (all in strict mode) on every commit — code must pass all three.
- GitHub Actions CI runs ruff + mypy on every push and PR — see `.github/workflows/ci.yml`.
- API keys are loaded from a gitignored `.env` (use `python-dotenv`). Copy `.env.example` and fill in `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GEMINI_API_KEY` / `LANGSMITH_API_KEY`. Never hardcode keys.
- For REST routes, annotate return types instead of using `response_model=` (ruff FAST001 flags it as redundant).
- **Anthropic (Claude) is the primary LLM provider**; OpenAI and Gemini are kept for comparison. Default new experiments to the `anthropic` SDK unless the exercise is explicitly cross-provider.
- When adding a new provider, implement `CallLLMFn` in `src/llm_calls/` and register it in `_REGISTRY` in `__init__.py`.
