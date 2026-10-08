import pytest
from app.evaluation import summarize


def test_relevance_fraction_is_distinct_from_query_hit_rate():
    report = summarize([{"query": "query", "relevant": ["a", "b"]}], [["x", "a", "z"]])
    assert report["mrr"] == .5
    assert report["hit_rate_at_3"] == report["recall_at_3"] == 1
    assert report["macro_recall_at_3"] == .5


def test_rank_beyond_three_does_not_pass_the_assignment_gate():
    report = summarize([{"query": "query", "relevant": ["a"]}], [["x", "y", "z", "a"]])
    assert report["mrr"] == report["hit_rate_at_3"] == 0


@pytest.mark.parametrize("cases,rankings", [([], []), ([{"query": "q", "relevant": []}], [["a"]]),
                                           ([{"query": "q", "relevant": ["a"]}], [["a", "a"]])])
def test_invalid_evaluation_cannot_succeed(cases, rankings):
    with pytest.raises(ValueError):
        summarize(cases, rankings)
