from engine.lab_state import empty_lab_state
from engine.research_queue import (
    bump_metric,
    dequeue_research_topics,
    enqueue_research,
    normalize_source,
    record_backtest_outcome,
)


def test_normalize_source():
    assert normalize_source("web:abc") == "web"
    assert normalize_source("combinator") == "combinator"
    assert normalize_source("") == "other"


def test_research_queue_priority():
    state = empty_lab_state()
    enqueue_research(state, "low priority topic here", priority=3)
    enqueue_research(state, "high priority topic here", priority=9)
    topics = dequeue_research_topics(state, limit=1)
    assert len(topics) == 1
    assert "high priority" in topics[0]


def test_source_metrics_backtest_fail_enqueues():
    state = empty_lab_state()
    recipe = {"id": "abc", "name": "TestRec", "source": "combinator"}
    record_backtest_outcome(state, recipe, {"passed": False, "profit_factor": 0.9, "n": 10})
    assert state["source_metrics"]["combinator"]["backtests"] == 1
    assert len(state["research_queue"]) >= 1


def test_bump_metric():
    state = empty_lab_state()
    bump_metric(state, "youtube:x", "recipes_added", 2)
    assert state["source_metrics"]["youtube"]["recipes_added"] == 2
