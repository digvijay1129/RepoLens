"""Offline retrieval and citation quality metrics for RepoLens evaluation runs.

Input rows are exports from actual search/chat runs plus human-reviewed expected
relevant chunks and supported citations. This module never calls an LLM.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


class EvaluationDataError(ValueError):
    """Raised when an evaluation row is incomplete or malformed."""


def _string_set(row: Mapping[str, Any], key: str) -> set[str]:
    value = row.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise EvaluationDataError(f"{key} must be a list of non-empty strings.")
    return set(value)


def _string_list(row: Mapping[str, Any], key: str) -> list[str]:
    value = row.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise EvaluationDataError(f"{key} must be a list of non-empty strings.")
    return value


def _dcg(relevant: set[str], ranked: list[str], k: int) -> float:
    return sum(
        (1.0 / math.log2(rank + 1))
        for rank, item in enumerate(ranked[:k], start=1)
        if item in relevant
    )


def evaluate_rows(rows: Iterable[Mapping[str, Any]], *, k: int = 5) -> dict[str, Any]:
    """Return recall@k, MRR, nDCG@k and grounded-citation metrics.

    Required row fields:
      query, relevant_chunk_ids, retrieved_chunk_ids, known_source_ids,
      cited_source_ids, supported_source_ids.
    The supported-source field must be human-reviewed; it is not inferred from
    the model's own citation claim.
    """
    if not 1 <= k <= 20:
        raise EvaluationDataError("k must be between 1 and 20.")

    evaluations: list[dict[str, Any]] = []
    recall_values: list[float] = []
    reciprocal_ranks: list[float] = []
    ndcg_values: list[float] = []
    total_citations = 0
    valid_citations = 0
    supported_citations = 0
    answerable_rows = 0
    citation_covered_rows = 0
    unknown_citations = 0

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, Mapping):
            raise EvaluationDataError(f"Row {index} must be a JSON object.")
        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            raise EvaluationDataError(f"Row {index}: query must be a non-empty string.")

        relevant = _string_set(row, "relevant_chunk_ids")
        retrieved = _string_list(row, "retrieved_chunk_ids")
        known_source_ids = _string_set(row, "known_source_ids")
        cited_source_ids = _string_list(row, "cited_source_ids")
        supported_source_ids = _string_set(row, "supported_source_ids")

        # Treat an identifier as retrieved at its first occurrence only.
        ranked = list(dict.fromkeys(retrieved))
        top_k = ranked[:k]
        hits = len(set(top_k) & relevant)
        answerable = bool(relevant)
        recall = hits / len(relevant) if answerable else None
        first_relevant_rank = next(
            (rank for rank, chunk_id in enumerate(ranked, start=1) if chunk_id in relevant),
            None,
        )
        mrr = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
        ideal_dcg = _dcg(relevant, list(relevant), k)
        ndcg = _dcg(relevant, ranked, k) / ideal_dcg if ideal_dcg else 0.0

        if answerable:
            answerable_rows += 1
            assert recall is not None
            recall_values.append(recall)
            reciprocal_ranks.append(mrr)
            ndcg_values.append(ndcg)

        total_citations += len(cited_source_ids)
        valid_count = sum(source_id in known_source_ids for source_id in cited_source_ids)
        supported_count = sum(
            source_id in known_source_ids and source_id in supported_source_ids
            for source_id in cited_source_ids
        )
        valid_citations += valid_count
        supported_citations += supported_count
        unknown_citations += len(cited_source_ids) - valid_count
        covered = supported_count > 0
        if answerable and covered:
            citation_covered_rows += 1

        evaluations.append({
            "query": query,
            "answerable": answerable,
            f"recall@{k}": round(recall, 6) if recall is not None else None,
            "mrr": round(mrr, 6) if answerable else None,
            f"ndcg@{k}": round(ndcg, 6) if answerable else None,
            "cited_source_count": len(cited_source_ids),
            "valid_citation_count": valid_count,
            "supported_citation_count": supported_count,
            "unknown_citation_count": len(cited_source_ids) - valid_count,
        })

    if not evaluations:
        raise EvaluationDataError("Evaluation input contains no rows.")

    average = lambda values: round(sum(values) / len(values), 6) if values else 0.0
    return {
        "queries_evaluated": len(evaluations),
        "answerable_queries": answerable_rows,
        "unanswerable_queries": len(evaluations) - answerable_rows,
        "cutoff_k": k,
        f"mean_recall@{k}": average(recall_values),
        "mean_reciprocal_rank": average(reciprocal_ranks),
        f"mean_ndcg@{k}": average(ndcg_values),
        "citation_count": total_citations,
        "citation_validity": round(valid_citations / total_citations, 6) if total_citations else 0.0,
        "citation_support_precision": round(supported_citations / total_citations, 6) if total_citations else 0.0,
        "citation_coverage": round(citation_covered_rows / answerable_rows, 6) if answerable_rows else 0.0,
        "unknown_citation_count": unknown_citations,
        "per_query": evaluations,
    }
