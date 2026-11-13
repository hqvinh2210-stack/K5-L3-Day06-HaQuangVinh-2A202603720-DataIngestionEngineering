"""Run the complete Day 06 ingestion and retrieval benchmark."""
from __future__ import annotations

import json
import os
import statistics
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_ocr_json
from .models import Chunk
from .store import PgVectorStore


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "results"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _chunk_stats(chunks: list[Chunk]) -> dict[str, Any]:
    lengths = [len(chunk.text) for chunk in chunks]
    return {
        "chunk_count": len(chunks),
        "total_characters_with_overlap": sum(lengths),
        "approx_tokens": round(sum(lengths) / 4),
        "min_characters": min(lengths),
        "median_characters": statistics.median(lengths),
        "mean_characters": statistics.mean(lengths),
        "max_characters": max(lengths),
    }


def _run_questions(
    questions: list[dict[str, Any]],
    strategies: list[str],
    embedder: MyEmbedder,
    store: PgVectorStore,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for question in questions:
        query_vector = embedder.embed_query(question["question"])
        for strategy in strategies:
            filters = question.get("filter") if strategy == "C" else None
            hits = store.search(
                strategy=strategy,
                query_vector=query_vector,
                top_k=3,
                filters=filters,
            )
            trace = evaluate_query(question, hits)
            trace["strategy"] = strategy
            trace["applied_filter"] = filters
            traces.append(trace)
    return traces


def main() -> None:
    load_dotenv(STARTER_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing; copy .env.example to .env")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    corpus_path = STARTER_ROOT / "data" / "nghi_dinh_13_2023_ND-CP_ocr.json"
    benchmark_path = REPO_ROOT / "benchmark" / "questions.json"
    pages = load_ocr_json(corpus_path, "nd13_2023", "13nd.signed.pdf")
    if len(pages) < 30:
        raise ValueError(f"Corpus has only {len(pages)} pages; at least 30 required")

    questions = json.loads(benchmark_path.read_text(encoding="utf-8"))
    if len(questions) < 20:
        raise ValueError("Benchmark must contain at least 20 questions")
    if sum(q["split"] == "dev" for q in questions) < 15:
        raise ValueError("Benchmark requires at least 15 dev questions")
    if sum(q["split"] == "test" for q in questions) < 5:
        raise ValueError("Benchmark requires at least 5 test questions")

    chunks_a = [chunk for page in pages for chunk in fixed_size(page, 500, 50)]
    chunks_b = [chunk for page in pages for chunk in by_paragraph(page, 900)]

    embedder = MyEmbedder(device="cpu", batch_size=16)
    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()

    ingest_times: dict[str, float] = {}
    start = time.perf_counter()
    vectors_a = embedder.embed_documents([chunk.text for chunk in chunks_a])
    store.upsert("A", chunks_a, vectors_a)
    ingest_times["A"] = time.perf_counter() - start

    start = time.perf_counter()
    vectors_b = embedder.embed_documents([chunk.text for chunk in chunks_b])
    store.upsert("B", chunks_b, vectors_b)
    ingest_times["B"] = time.perf_counter() - start

    start = time.perf_counter()
    store.upsert("C", chunks_b, vectors_b)
    ingest_times["C"] = time.perf_counter() - start

    counts = {strategy: store.count(strategy) for strategy in ("A", "B", "C")}
    expected = {"A": len(chunks_a), "B": len(chunks_b), "C": len(chunks_b)}
    if counts != expected:
        raise RuntimeError(f"Stored chunk counts mismatch: {counts} != {expected}")

    dev_questions = [q for q in questions if q["split"] == "dev"]
    test_questions = [q for q in questions if q["split"] == "test"]
    dev_traces = _run_questions(dev_questions, ["A", "B", "C"], embedder, store)
    dev_metrics = summarize(dev_traces)
    selected_strategy = max(
        ("A", "B", "C"),
        key=lambda strategy: (
            dev_metrics[strategy]["dev"]["evidence_hit_at_3"],
            dev_metrics[strategy]["dev"]["hit_at_1"],
            -counts[strategy],
            -("A", "B", "C").index(strategy),
        ),
    )

    test_traces = _run_questions(test_questions, ["A", "B", "C"], embedder, store)
    traces = dev_traces + test_traces
    metrics = summarize(traces)

    config = {
        "corpus": str(corpus_path),
        "content_pages": len(pages),
        "embedding_model": embedder.model_name,
        "embedding_dimensions": embedder.dimensions,
        "device": "cpu",
        "vector_store": "PostgreSQL 16 + pgvector 0.8.7",
        "distance": "cosine",
        "strategies": {
            "A": {"chunking": "fixed characters", "size": 500, "overlap": 50, "filter": False},
            "B": {"chunking": "paragraph-aware", "max_size": 900, "filter": False},
            "C": {"chunking": "same vectors as B", "max_size": 900, "filter": "section when provided"},
        },
        "selection_rule": "Highest dev Evidence Hit@3, then dev Hit@1, then fewer chunks, then fixed A-B-C order",
        "selected_on_dev": selected_strategy,
        "api_cost_usd": 0,
    }
    stats = {
        "source_characters": sum(len(page.text) for page in pages),
        "A": {**_chunk_stats(chunks_a), "ingest_seconds": ingest_times["A"]},
        "B": {**_chunk_stats(chunks_b), "ingest_seconds": ingest_times["B"]},
        "C": {**_chunk_stats(chunks_b), "ingest_seconds": ingest_times["C"], "embeddings_reused_from_B": True},
        "stored_counts_after_replace": counts,
    }

    _write_json(RESULTS_DIR / "run_config.json", config)
    _write_json(RESULTS_DIR / "ingestion_stats.json", stats)
    _write_json(RESULTS_DIR / "metrics.json", metrics)
    _write_json(RESULTS_DIR / "traces.json", traces)
    for strategy in ("A", "B", "C"):
        _write_json(
            RESULTS_DIR / f"traces_{strategy}.json",
            [trace for trace in traces if trace["strategy"] == strategy],
        )

    print(json.dumps({"selected_strategy": selected_strategy, "metrics": metrics, "stats": stats}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
