from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from books_recommender.artifacts import load_run, resolve_run
from books_recommender.config import find_repo_root, load_config
from books_recommender.data.prepare import prepare_dataset, validate_raw_files
from books_recommender.evaluation.evaluator import evaluate_run
from books_recommender.recommend import recommend
from books_recommender.spark import create_spark
from books_recommender.training import train_models


def _csv(value: str | None) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _integers(value: str | None) -> list[int]:
    return [int(part) for part in _csv(value)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="books-recommender")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Build model-ready Parquet tables")
    prepare.add_argument("--config", default="configs/demo.yaml")

    train = subparsers.add_parser("train", help="Train one or more models")
    train.add_argument("--config", default="configs/demo.yaml")
    train.add_argument("--models", default="all", help="Comma-separated names or 'all'")
    train.add_argument("--run-id")

    evaluate = subparsers.add_parser("evaluate", help="Evaluate a trained run")
    evaluate.add_argument("--run-id", required=True)
    evaluate.add_argument("--artifacts", default="artifacts")

    recommend_parser = subparsers.add_parser("recommend", help="Generate top-N recommendations")
    recommend_parser.add_argument("--run-id", required=True)
    recommend_parser.add_argument("--artifacts", default="artifacts")
    recommend_parser.add_argument("--user-id", type=int)
    recommend_parser.add_argument(
        "--seed-book-ids", help="Comma-separated upstream book_id_csv IDs"
    )
    recommend_parser.add_argument("--genres", help="Comma-separated genres for a cold user")
    recommend_parser.add_argument("--top-k", type=int, default=20)

    run_all = subparsers.add_parser("run-all", help="Prepare, train, and evaluate")
    run_all.add_argument("--config", default="configs/demo.yaml")
    run_all.add_argument("--models", default="all")
    run_all.add_argument("--run-id")
    export = subparsers.add_parser("export-serving", help="Export a small trained run for Readora")
    export.add_argument("--run-id", required=True)
    export.add_argument("--artifacts", default="artifacts")
    serve = subparsers.add_parser("serve", help="Serve the upstream Readora recommender contract")
    serve.add_argument("--run-id", default="latest")
    serve.add_argument("--artifacts", default="artifacts")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8001)
    return parser


def _artifact_root(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (find_repo_root() / path).resolve()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    spark = None
    try:
        if args.command == "serve":
            from books_recommender.serving.api import serve

            run_dir = resolve_run(_artifact_root(args.artifacts), args.run_id)
            if not (run_dir / "serving" / "manifest.json").is_file():
                raise FileNotFoundError(
                    "This run has no serving bundle. Train with configs/demo.yaml "
                    "or run export-serving --run-id <run_id> first."
                )
            serve(run_dir, args.host, args.port)
            return 0
        if args.command in {"prepare", "train", "run-all"}:
            config = load_config(args.config)
        else:
            run_dir = resolve_run(_artifact_root(args.artifacts), args.run_id)
            config = load_run(run_dir)
        if args.command in {"prepare", "run-all"}:
            validate_raw_files(config)
        spark = create_spark(config)

        if args.command == "prepare":
            print(json.dumps(prepare_dataset(spark, config), indent=2, ensure_ascii=False))
        elif args.command == "train":
            identifier, _ = train_models(spark, config, _csv(args.models), args.run_id)
            print(json.dumps({"run_id": identifier, "status": "trained"}, indent=2))
        elif args.command == "evaluate":
            print(json.dumps(evaluate_run(spark, config, run_dir), indent=2, ensure_ascii=False))
        elif args.command == "recommend":
            if args.top_k <= 0:
                raise ValueError("top-k must be positive")
            rows = recommend(
                spark,
                config,
                run_dir,
                user_id=args.user_id,
                seed_book_ids=_integers(args.seed_book_ids),
                genres=_csv(args.genres),
                top_k=args.top_k,
            )
            print(json.dumps(rows, indent=2, ensure_ascii=False))
        elif args.command == "run-all":
            prepare_dataset(spark, config)
            identifier, run_dir = train_models(spark, config, _csv(args.models), args.run_id)
            report = evaluate_run(spark, config, run_dir)
            print(
                json.dumps({"run_id": identifier, "metrics": report}, indent=2, ensure_ascii=False)
            )
        elif args.command == "export-serving":
            from books_recommender.serving.export import export_serving

            print(export_serving(spark, config, run_dir))
        return 0
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        if spark is not None:
            spark.stop()


if __name__ == "__main__":
    raise SystemExit(main())
