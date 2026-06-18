"""CLI for the chunking module.

    uv run python -m chunking index   --dataset k8s --algorithm recursive
    uv run python -m chunking search  --dataset k8s --algorithm recursive -q "what is a pod?"
    uv run python -m chunking compare --dataset k8s --source concepts/workloads/pods/_index.md

Requires a running Postgres (``docker compose up -d``, with V2 migrated) and
``OPENAI_API_KEY`` / ``DATABASE_URL`` in ``.env``. ``compare`` only needs the
OpenAI key (semantic chunking embeds), not Postgres.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from chunking.pipeline import compare, index, search
from chunking.registry import REGISTRY, ChunkParams


def _add_chunk_params(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--chunk-size", type=int, default=400, help="tokens per chunk")
    parser.add_argument("--chunk-overlap", type=int, default=50, help="token overlap")
    parser.add_argument(
        "--breakpoint-percentile",
        type=float,
        default=90.0,
        help="semantic: distance percentile above which to cut",
    )


def _params(args: argparse.Namespace) -> ChunkParams:
    return ChunkParams(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        breakpoint_percentile=args.breakpoint_percentile,
    )


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="chunking", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    algorithms = sorted(REGISTRY)

    p_index = sub.add_parser("index", help="chunk + embed + store a dataset")
    p_index.add_argument("--dataset", required=True, choices=["k8s", "postgres"])
    p_index.add_argument("--algorithm", required=True, choices=algorithms)
    _add_chunk_params(p_index)
    p_index.add_argument("--limit", type=int, default=None, help="cap number of docs")
    p_index.add_argument(
        "--append",
        action="store_true",
        help="keep existing chunks instead of replacing them",
    )

    p_search = sub.add_parser("search", help="vector search over an indexed dataset")
    p_search.add_argument("--dataset", required=True, choices=["k8s", "postgres"])
    p_search.add_argument("--algorithm", required=True, choices=algorithms)
    p_search.add_argument("-q", "--query", required=True)
    p_search.add_argument("-k", "--top-k", type=int, default=5)

    p_compare = sub.add_parser("compare", help="show how each algorithm partitions one doc")
    p_compare.add_argument("--dataset", required=True, choices=["k8s", "postgres"])
    p_compare.add_argument("--source", required=True, help="path relative to the dataset root")
    p_compare.add_argument(
        "--algorithms",
        nargs="+",
        choices=algorithms,
        default=algorithms,
        help="algorithms to compare (default: all)",
    )
    _add_chunk_params(p_compare)

    args = parser.parse_args()

    if args.command == "index":
        index(
            dataset=args.dataset,
            algorithm=args.algorithm,
            params=_params(args),
            limit=args.limit,
            replace=not args.append,
        )
    elif args.command == "search":
        search(
            dataset=args.dataset,
            algorithm=args.algorithm,
            query=args.query,
            k=args.top_k,
        )
    elif args.command == "compare":
        compare(
            dataset=args.dataset,
            source_path=args.source,
            algorithms=args.algorithms,
            params=_params(args),
        )


if __name__ == "__main__":
    main()
