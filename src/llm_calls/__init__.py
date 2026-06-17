from collections.abc import Generator, Iterator

from accounting import estimate_partial_cost
from db import LlmCall, LlmCallRepository, Stage

from .anthropic_client import AnthropicProvider
from .base import CallLLMFn, LLMResponse, StreamChunk
from .gemini_client import GeminiProvider
from .models import ModelEntry, list_models
from .ollama_client import OllamaProvider
from .openai_client import OpenAIProvider

_REGISTRY: dict[str, CallLLMFn] = {
    "anthropic": AnthropicProvider(),
    "openai": OpenAIProvider(),
    "gemini": GeminiProvider(),
    "ollama": OllamaProvider(),
}

_DEFAULT_REPO: LlmCallRepository | None = None


def _get_repo() -> LlmCallRepository:
    global _DEFAULT_REPO  # noqa: PLW0603
    if _DEFAULT_REPO is None:
        _DEFAULT_REPO = LlmCallRepository()
    return _DEFAULT_REPO


def call_llm(
    model: str,
    input_message: str,
    max_output_tokens: int,
    provider: str,
    *,
    system_prompt: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    request_id: str | None = None,
    stage: Stage | None = None,
    repository: LlmCallRepository | None = None,
) -> LLMResponse:
    if provider not in _REGISTRY:
        msg = f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}"
        raise ValueError(msg)

    repo = repository if repository is not None else _get_repo()

    try:
        result = _REGISTRY[provider](
            model,
            input_message,
            max_output_tokens,
            system_prompt=system_prompt,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
        )
    except Exception as e:
        repo.save(
            LlmCall(
                provider=provider,
                model=model,
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                latency=0.0,
                prompt=input_message,
                answer="",
                max_tokens=max_output_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                response_status="error",
                error_message=str(e),
                system_prompt=system_prompt,
                request_id=request_id,
                stage=stage,
            )
        )
        raise

    repo.save(
        LlmCall(
            provider=provider,
            model=model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost=result.cost_usd,
            latency=result.latency_ms,
            prompt=input_message,
            answer=result.reply,
            max_tokens=max_output_tokens,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            response_status="success",
            system_prompt=system_prompt,
            ignored_params=result.ignored_params,
            request_id=request_id,
            stage=stage,
        )
    )
    return result


def stream_llm(
    model: str,
    input_message: str,
    max_output_tokens: int,
    provider: str,
    *,
    system_prompt: str | None = None,
    temperature: float | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    request_id: str | None = None,
    stage: Stage | None = None,
    repository: LlmCallRepository | None = None,
) -> Generator[StreamChunk, None, None]:
    if provider not in _REGISTRY:
        msg = f"Unknown provider '{provider}'. Available: {list(_REGISTRY)}"
        raise ValueError(msg)

    repo = repository if repository is not None else _get_repo()
    inner = _REGISTRY[provider].__stream__(
        model,
        input_message,
        max_output_tokens,
        system_prompt=system_prompt,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
    )
    return _persist_stream(
        inner,
        repo,
        provider,
        model,
        input_message,
        max_output_tokens,
        system_prompt,
        temperature,
        top_p,
        top_k,
        request_id,
        stage,
    )


def _persist_stream(
    gen: Iterator[StreamChunk],
    repo: LlmCallRepository,
    provider: str,
    model: str,
    prompt: str,
    max_tokens: int,
    system_prompt: str | None,
    temperature: float | None,
    top_p: float | None,
    top_k: int | None,
    request_id: str | None,
    stage: Stage | None,
) -> Generator[StreamChunk, None, None]:
    deltas: list[str] = []
    persisted = False
    exc: BaseException | None = None
    try:
        for chunk in gen:
            if chunk.type == "delta" and chunk.delta:
                deltas.append(chunk.delta)
            elif chunk.type == "done":
                saved = repo.save(
                    LlmCall(
                        provider=provider,
                        model=model,
                        input_tokens=chunk.input_tokens or 0,
                        output_tokens=chunk.output_tokens or 0,
                        cost=chunk.cost_usd or 0.0,
                        latency=chunk.latency_ms or 0.0,
                        prompt=prompt,
                        answer="".join(deltas),
                        max_tokens=max_tokens,
                        temperature=temperature,
                        top_p=top_p,
                        top_k=top_k,
                        ttft_ms=chunk.ttft_ms,
                        response_status="success",
                        system_prompt=system_prompt,
                        ignored_params=chunk.ignored_params,
                        request_id=request_id,
                        stage=stage,
                    )
                )
                persisted = True
                chunk = StreamChunk(  # noqa: PLW2901
                    type="done",
                    input_tokens=chunk.input_tokens,
                    output_tokens=chunk.output_tokens,
                    cost_usd=chunk.cost_usd,
                    latency_ms=chunk.latency_ms,
                    ttft_ms=chunk.ttft_ms,
                    call_id=saved.id,
                    ignored_params=chunk.ignored_params,
                )
            yield chunk
    except BaseException as e:
        exc = e
        raise
    finally:
        if not persisted:
            is_cancelled = exc is None or isinstance(exc, GeneratorExit)
            partial = "".join(deltas)
            in_tok, out_tok, cost_usd = estimate_partial_cost(
                provider, model, prompt, system_prompt, partial
            )
            repo.save(
                LlmCall(
                    provider=provider,
                    model=model,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost=cost_usd,
                    latency=0.0,
                    prompt=prompt,
                    answer=partial,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    response_status="cancelled" if is_cancelled else "error",
                    error_message=None if is_cancelled else str(exc),
                    system_prompt=system_prompt,
                    request_id=request_id,
                    stage=stage,
                )
            )


__all__ = [
    "CallLLMFn",
    "LLMResponse",
    "ModelEntry",
    "StreamChunk",
    "call_llm",
    "list_models",
    "stream_llm",
]
