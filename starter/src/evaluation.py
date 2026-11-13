"""Evaluate retrieval evidence and preserve per-query traces."""
import re
import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return re.sub(r"\s+", " ", text).strip()


def _is_hit(question: dict[str, Any], hit: dict[str, Any]) -> bool:
    alternatives = question.get("gold_alternatives") or [
        {
            "source_id": question["gold_source_id"],
            "page": question["gold_page"],
            "evidence": question["evidence_quote"],
        }
    ]
    for gold in alternatives:
        if (
            hit.get("document_id") == gold["source_id"]
            and hit.get("page") == gold["page"]
            and _normalize(gold["evidence"]) in _normalize(hit.get("text", ""))
        ):
            return True
    return False


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    annotated_hits = []
    for rank, hit in enumerate(hits, start=1):
        annotated_hits.append({**hit, "rank": rank, "is_gold_hit": _is_hit(question, hit)})
    return {
        "question_id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "filter": question.get("filter"),
        "hit_at_1": bool(annotated_hits and annotated_hits[0]["is_gold_hit"]),
        "evidence_hit_at_3": any(hit["is_gold_hit"] for hit in annotated_hits[:3]),
        "hits": annotated_hits,
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for strategy in sorted({trace["strategy"] for trace in traces}):
        summary[strategy] = {}
        for split in ("dev", "test"):
            selected = [
                trace for trace in traces
                if trace["strategy"] == strategy and trace["split"] == split
            ]
            total = len(selected)
            hit1 = sum(trace["hit_at_1"] for trace in selected)
            hit3 = sum(trace["evidence_hit_at_3"] for trace in selected)
            summary[strategy][split] = {
                "hit_at_1": hit1,
                "evidence_hit_at_3": hit3,
                "total": total,
                "hit_at_1_rate": hit1 / total if total else 0.0,
                "evidence_hit_at_3_rate": hit3 / total if total else 0.0,
            }
    return summary
