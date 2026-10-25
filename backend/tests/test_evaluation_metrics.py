"""Tests for offline retrieval and citation evaluation metrics."""

import pytest

from app.evaluation.metrics import EvaluationDataError, evaluate_rows


def test_evaluation_calculates_retrieval_and_citation_quality() -> None:
    report = evaluate_rows(
        [
            {
                "query": "authentication flow",
                "relevant_chunk_ids": ["auth-a", "auth-b"],
                "retrieved_chunk_ids": ["auth-a", "db-a", "auth-b"],
                "known_source_ids": ["S1", "S2"],
                "cited_source_ids": ["S1", "S99"],
                "supported_source_ids": ["S1"],
            },
            {
                "query": "database connection",
                "relevant_chunk_ids": ["db-a"],
                "retrieved_chunk_ids": ["db-a", "auth-a"],
                "known_source_ids": ["S1"],
                "cited_source_ids": ["S1"],
                "supported_source_ids": ["S1"],
            },
        ],
        k=3,
    )

    assert report["queries_evaluated"] == 2
    assert report["mean_recall@3"] == 1.0
    assert report["mean_reciprocal_rank"] == 1.0
    assert report["mean_ndcg@3"] == pytest.approx(0.95986)
    assert report["citation_count"] == 3
    assert report["citation_validity"] == pytest.approx(2 / 3)
    assert report["citation_support_precision"] == pytest.approx(2 / 3)
    assert report["citation_coverage"] == 1.0
    assert report["unknown_citation_count"] == 1


def test_evaluation_handles_unanswerable_queries_and_invalid_k() -> None:
    report = evaluate_rows(
        [{
            "query": "unknown symbol",
            "relevant_chunk_ids": [],
            "retrieved_chunk_ids": [],
            "known_source_ids": [],
            "cited_source_ids": [],
            "supported_source_ids": [],
        }]
    )
    assert report["answerable_queries"] == 0
    assert report["unanswerable_queries"] == 1
    assert report["mean_recall@5"] == 0.0
    assert report["citation_coverage"] == 0.0

    with pytest.raises(EvaluationDataError, match="between 1 and 20"):
        evaluate_rows([], k=0)


def test_evaluation_rejects_malformed_fields_and_empty_input() -> None:
    with pytest.raises(EvaluationDataError, match="contains no rows"):
        evaluate_rows([])
    with pytest.raises(EvaluationDataError, match="relevant_chunk_ids"):
        evaluate_rows([{
            "query": "bad shape",
            "relevant_chunk_ids": "not-a-list",
        }])

from app.evaluation.evaluate import load_jsonl


def test_load_jsonl_reads_example_rows_and_rejects_invalid_json(tmp_path) -> None:
    dataset = tmp_path / "run.jsonl"
    dataset.write_text(
        '{"query":"q","relevant_chunk_ids":[],"retrieved_chunk_ids":[],"known_source_ids":[],"cited_source_ids":[],"supported_source_ids":[]}\n',
        encoding="utf-8",
    )
    assert len(load_jsonl(dataset)) == 1

    dataset.write_text("{not-json}\n", encoding="utf-8")
    with pytest.raises(EvaluationDataError, match="invalid JSON"):
        load_jsonl(dataset)
