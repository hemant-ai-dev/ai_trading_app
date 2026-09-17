from knowledge.search import search_knowledge


def test_knowledge_search_finds_daily_data_limits():
    hits = search_knowledge("Yahoo daily NSE delay Stooq fallback", limit=3)
    assert hits
    blob = " ".join(h["excerpt"] for h in hits).lower()
    assert "yahoo" in blob or "stooq" in blob
