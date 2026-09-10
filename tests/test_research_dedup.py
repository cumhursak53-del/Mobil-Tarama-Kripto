from engine.research_dedup import is_recent, mark_done, migrate_legacy_lists, prune_expired


def test_migrate_legacy_list_to_timestamps():
    meta = {"processed_videos": ["abc", "def"]}
    migrate_legacy_lists(meta)
    assert isinstance(meta["processed_videos"], dict)
    assert "abc" in meta["processed_videos"]


def test_mark_and_recent():
    meta = {}
    migrate_legacy_lists(meta)
    mark_done(meta, "processed_web_queries", "key1")
    assert is_recent(meta, "processed_web_queries", "key1")
    assert not is_recent(meta, "processed_web_queries", "key2")


def test_prune_expired_clears_old():
    meta = {"processed_news_batches": {"old": "2020-01-01 00:00:00"}}
    removed = prune_expired(meta, "processed_news_batches", ttl_sec=60)
    assert removed == 1
    assert meta["processed_news_batches"] == {}
