"""
KaPak - Hashtags Tests
Unit tests for hashtag_utils + API tests for trending, hashtag-filtered posts.
"""

from app.core.hashtag_utils import extract_hashtags, get_or_create_hashtag, link_hashtags_to_post
from app.models.hashtag import ContentHashtag, Hashtag


# ==========================================
# UNIT: hashtag_utils functions
# ==========================================

def test_extract_hashtags_returns_unique_lowercase():
    tags = extract_hashtags("Hello #World and #world again #Test")
    assert tags == ["world", "test"]


def test_extract_hashtags_handles_none():
    assert extract_hashtags(None) == []


def test_extract_hashtags_handles_empty_string():
    assert extract_hashtags("") == []


def test_extract_hashtags_no_tags():
    assert extract_hashtags("Plain text without tags") == []


def test_extract_hashtags_unicode():
    tags = extract_hashtags("#shqip #çokollatë #test123")
    assert tags == ["shqip", "çokollatë", "test123"]


def test_get_or_create_hashtag_creates_new(db_session):
    hashtag = get_or_create_hashtag("newtag", db_session, "default")
    assert hashtag.name == "newtag"
    assert hashtag.mention_count == 1
    assert hashtag.tenant_id == "default"


def test_get_or_create_hashtag_increments_existing(db_session):
    h1 = get_or_create_hashtag("reuse", db_session, "default")
    assert h1.mention_count == 1
    h2 = get_or_create_hashtag("reuse", db_session, "default")
    assert h2.id == h1.id
    assert h2.mention_count == 2


def test_get_or_create_hashtag_tenant_isolation(db_session):
    h1 = get_or_create_hashtag("shared", db_session, "tenant-A")
    assert h1.tenant_id == "tenant-A"
    assert h1.mention_count == 1
    h2 = get_or_create_hashtag("shared", db_session, "tenant-B")
    assert h2.id == h1.id
    assert h2.mention_count == 2


def test_link_hashtags_to_post_creates_join_rows(db_session):
    h = get_or_create_hashtag("linked", db_session, "default")
    link_hashtags_to_post(999, ["linked"], db_session, "default")
    rows = db_session.query(ContentHashtag).filter(
        ContentHashtag.hashtag_id == h.id,
        ContentHashtag.post_id == 999,
    ).all()
    assert len(rows) == 1


# ==========================================
# API: Post creation + hashtag linking
# ==========================================

def test_post_creation_auto_links_hashtags(test_client, db_session):
    payload = {"content": "This has #hello and #world", "visibility": "public"}
    res = test_client.post("/api/v1/posts/", json=payload)
    assert res.status_code == 201
    post_id = res.json()["id"]

    rows = db_session.query(ContentHashtag).filter(
        ContentHashtag.post_id == post_id,
    ).all()
    tag_names = sorted(
        h.name for r in rows
        for h in [db_session.query(Hashtag).filter(Hashtag.id == r.hashtag_id).first()]
    )
    assert "hello" in tag_names
    assert "world" in tag_names


def test_post_without_hashtags_creates_no_links(test_client, db_session):
    payload = {"content": "Plain text no tags", "visibility": "public"}
    res = test_client.post("/api/v1/posts/", json=payload)
    assert res.status_code == 201
    post_id = res.json()["id"]

    count = db_session.query(ContentHashtag).filter(
        ContentHashtag.post_id == post_id,
    ).count()
    assert count == 0


# ==========================================
# API: GET /hashtags/trending
# ==========================================

def test_trending_hashtags_returns_top_by_count(test_client):
    for _ in range(3):
        test_client.post("/api/v1/posts/", json={
            "content": "Hashtag #trendinga", "visibility": "public",
        })
    for _ in range(2):
        test_client.post("/api/v1/posts/", json={
            "content": "Hashtag #trendingb", "visibility": "public",
        })
    test_client.post("/api/v1/posts/", json={
        "content": "Only one #trendingc", "visibility": "public",
    })

    res = test_client.get("/api/v1/hashtags/trending?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 3
    names = [h["name"] for h in data]
    assert names[0] == "trendinga"
    assert names[1] == "trendingb"
    assert names[2] == "trendingc"


def test_trending_hashtags_respects_limit(test_client):
    for i in range(5):
        test_client.post("/api/v1/posts/", json={
            "content": f"Tag #{i}", "visibility": "public",
        })
    res = test_client.get("/api/v1/hashtags/trending?limit=3")
    assert res.status_code == 200
    assert len(res.json()) == 3


def test_trending_hashtags_respects_days(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "Fresh #daytest", "visibility": "public",
    })
    res = test_client.get("/api/v1/hashtags/trending?days=1")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["name"] == "daytest"


# ==========================================
# API: GET /hashtags/{name}/posts
# ==========================================

def test_hashtag_posts_paginated(test_client):
    for i in range(3):
        test_client.post("/api/v1/posts/", json={
            "content": f"Post {i} with #paginationtag",
            "visibility": "public",
        })

    r1 = test_client.get("/api/v1/hashtags/paginationtag/posts?skip=0&limit=2")
    assert r1.status_code == 200
    assert len(r1.json()) == 2

    r2 = test_client.get("/api/v1/hashtags/paginationtag/posts?skip=2&limit=2")
    assert r2.status_code == 200
    assert len(r2.json()) == 1


def test_hashtag_posts_not_found(test_client):
    res = test_client.get("/api/v1/hashtags/nonexistent9999/posts")
    assert res.status_code == 404


def test_hashtag_posts_returns_correct_posts(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "Post with #specialtag", "visibility": "public",
    })
    test_client.post("/api/v1/posts/", json={
        "content": "Another #specialtag post", "visibility": "public",
    })
    test_client.post("/api/v1/posts/", json={
        "content": "No matching tag here", "visibility": "public",
    })

    res = test_client.get("/api/v1/hashtags/specialtag/posts")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 2
    for item in data:
        assert "specialtag" in item["content"].lower()


def test_hashtag_posts_invalid_limit(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "Tag #limittest", "visibility": "public",
    })
    res = test_client.get("/api/v1/hashtags/limittest/posts?limit=200")
    assert res.status_code == 422


# ==========================================
# API: GET /hashtags/trending-statuses
# ==========================================

def test_trending_statuses_returns_posts(test_client):
    r1 = test_client.post("/api/v1/posts/", json={
        "content": "Trending post content", "visibility": "public",
    })
    post_id = r1.json()["id"]
    test_client.post(f"/api/v1/posts/{post_id}/like")

    res = test_client.get("/api/v1/hashtags/trending-statuses?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["interaction_count"] >= 1


def test_trending_statuses_empty(test_client):
    res = test_client.get("/api/v1/hashtags/trending-statuses?limit=10")
    assert res.status_code == 200
    assert res.json() == []


def test_trending_statuses_respects_limit(test_client):
    for i in range(3):
        test_client.post("/api/v1/posts/", json={
            "content": f"Status post {i}", "visibility": "public",
        })
    res = test_client.get("/api/v1/hashtags/trending-statuses?limit=2")
    assert res.status_code == 200
    assert len(res.json()) == 2


def test_trending_statuses_ranks_by_interaction(test_client):
    r1 = test_client.post("/api/v1/posts/", json={
        "content": "Less popular post", "visibility": "public",
    })
    r2 = test_client.post("/api/v1/posts/", json={
        "content": "More popular post", "visibility": "public",
    })
    popular_id = r2.json()["id"]

    test_client.post(f"/api/v1/posts/{popular_id}/like")

    res = test_client.get("/api/v1/hashtags/trending-statuses?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 2
    assert data[0]["interaction_count"] > data[1]["interaction_count"]
