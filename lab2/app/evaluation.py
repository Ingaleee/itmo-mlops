"""Metrics shared by the offline gate and the external release check."""


def summarize(cases: list[dict], rankings: list[list[str]]) -> dict:
    if not cases or len(cases) != len(rankings):
        raise ValueError("evaluation requires a non-empty aligned set of cases")
    reciprocals, hits, recalls, details = [], [], [], []
    for case, ranking in zip(cases, rankings, strict=True):
        relevant = set(case["relevant"])
        if not relevant or len(ranking) != len(set(ranking)):
            raise ValueError("evaluation requires relevance labels and unique results")
        top3 = ranking[:3]
        ranks = [top3.index(identifier) + 1 for identifier in relevant if identifier in top3]
        reciprocals.append(1 / min(ranks) if ranks else 0.0)
        hits.append(int(bool(ranks)))
        recalls.append(len(set(top3) & relevant) / len(relevant))
        details.append({"query": case["query"], "top3": top3, "relevant": sorted(relevant)})
    return {
        "mrr": round(sum(reciprocals) / len(cases), 6),
        # Preserve the supplied assignment's gate semantics: a hit per query.
        "recall_at_3": round(sum(hits) / len(cases), 6),
        "hit_rate_at_3": round(sum(hits) / len(cases), 6),
        "macro_recall_at_3": round(sum(recalls) / len(cases), 6),
        "metric_definitions": {
            "mrr": "mean reciprocal rank truncated at 3, as in the assignment",
            "recall_at_3": "query hit rate at 3, as in the assignment",
            "macro_recall_at_3": "mean fraction of each query's relevant documents retrieved at 3",
        },
        "cases": details,
    }
