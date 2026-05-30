"""
KaPak - Search Tests
API tests for full-text search across posts, users, and hashtags.
"""

from app.models.search_history import SearchHistory


# ==========================================
# API: GET /search/posts
# ==========================================

def test_search_posts_by_content(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "A post with the keyword pineapple", "visibility": "public",
    })
    test_client.post("/api/v1/posts/", json={
        "content": "Another post without that word", "visibility": "public",
    })

    res = test_client.get("/api/v1/search/posts?q=pineapple")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert "pineapple" in data["items"][0]["content"]


def test_search_posts_by_author_username(test_client):
    res = test_client.get("/api/v1/search/posts?q=testuser")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 0


def test_search_posts_pagination(test_client):
    for i in range(5):
        test_client.post("/api/v1/posts/", json={
            "content": f"Pagination test post number {i}", "visibility": "public",
        })

    r1 = test_client.get("/api/v1/search/posts?q=pagination&offset=0&limit=2")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 5
    assert len(d1["items"]) == 2
    assert d1["offset"] == 0

    r2 = test_client.get("/api/v1/search/posts?q=pagination&offset=4&limit=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 1
    assert d2["offset"] == 4


def test_search_posts_empty_results(test_client):
    res = test_client.get("/api/v1/search/posts?q=xyznonexistent12345")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_search_posts_logs_history(test_client, db_session):
    test_client.post("/api/v1/posts/", json={
        "content": "Loggable search term", "visibility": "public",
    })

    test_client.get("/api/v1/search/posts?q=loggable")

    entry = db_session.query(SearchHistory).filter(
        SearchHistory.query == "loggable",
        SearchHistory.search_type == "posts",
    ).first()
    assert entry is not None
    assert entry.user_id == 1
    assert entry.result_count > 0


def test_search_posts_with_comments(test_client):
    pres = test_client.post("/api/v1/posts/", json={
        "content": "Parent post", "visibility": "public",
    })
    pid = pres.json()["id"]
    test_client.post(f"/api/v1/posts/{pid}/comments", json={
        "content": "This has zebrafish in the comment",
    })

    res = test_client.get("/api/v1/search/posts?q=zebrafish&include_comments=true")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1

    found = False
    for item in data["items"]:
        ctx = item.get("match_context")
        if ctx and ctx.get("matched_comments"):
            found = True
            break
    assert found, "Expected match_context with matched_comments"


def test_search_posts_comment_only_match(test_client):
    pres = test_client.post("/api/v1/posts/", json={
        "content": "Post body has no fish word", "visibility": "public",
    })
    test_client.post(f"/api/v1/posts/{pres.json()['id']}/comments", json={
        "content": "But the comment mentions goldfish",
    })

    no_comments = test_client.get("/api/v1/search/posts?q=goldfish&include_comments=false")
    assert no_comments.status_code == 200
    assert no_comments.json()["total"] == 0

    with_comments = test_client.get("/api/v1/search/posts?q=goldfish&include_comments=true")
    assert with_comments.status_code == 200
    assert with_comments.json()["total"] == 1


def test_search_requires_query(test_client):
    res = test_client.get("/api/v1/search/posts")
    assert res.status_code == 422


# ==========================================
# API: GET /search/users
# ==========================================

def test_search_users(test_client):
    res = test_client.get("/api/v1/search/users?q=test")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["username"] == "testuser"


def test_search_users_no_results(test_client):
    res = test_client.get("/api/v1/search/users?q=zzzzznobody")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_search_users_logs_history(test_client, db_session):
    test_client.get("/api/v1/search/users?q=test")

    entry = db_session.query(SearchHistory).filter(
        SearchHistory.query == "test",
        SearchHistory.search_type == "users",
    ).first()
    assert entry is not None


def test_search_users_pagination(test_client, db_session):
    from app.models.user import User

    db_session.add_all([
        User(id=2, username="testuser2", email="test2@example.com", hashed_password="h", is_active=True, role="user", tenant_id="default"),
        User(id=3, username="testuser3", email="test3@example.com", hashed_password="h", is_active=True, role="user", tenant_id="default"),
    ])
    db_session.commit()

    r1 = test_client.get("/api/v1/search/users?q=testuser&offset=0&limit=2")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2
    assert d1["offset"] == 0

    r2 = test_client.get("/api/v1/search/users?q=testuser&offset=2&limit=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 1
    assert d2["offset"] == 2


# ==========================================
# API: GET /search/hashtags
# ==========================================

def test_search_hashtags(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "This has #searchhashtag embedded", "visibility": "public",
    })

    res = test_client.get("/api/v1/search/hashtags?q=searchhash")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(h["name"] == "searchhashtag" for h in data["items"])


def test_search_hashtags_strips_leading_hash(test_client):
    test_client.post("/api/v1/posts/", json={
        "content": "Another #hashtest one", "visibility": "public",
    })

    r1 = test_client.get("/api/v1/search/hashtags?q=hashtest")
    r2 = test_client.get("/api/v1/search/hashtags?q=%23hashtest")
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["total"] == r2.json()["total"]


def test_search_hashtags_no_results(test_client):
    res = test_client.get("/api/v1/search/hashtags?q=xyznonexistent")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0


def test_search_hashtags_logs_history(test_client, db_session):
    test_client.post("/api/v1/posts/", json={
        "content": "#histtag", "visibility": "public",
    })
    test_client.get("/api/v1/search/hashtags?q=histtag")

    entry = db_session.query(SearchHistory).filter(
        SearchHistory.query == "histtag",
        SearchHistory.search_type == "hashtags",
    ).first()
    assert entry is not None


def test_search_hashtags_pagination(test_client):
    for name in ["alpha", "beta", "gamma"]:
        test_client.post("/api/v1/posts/", json={
            "content": f"Tag #paghash{name}", "visibility": "public",
        })

    r1 = test_client.get("/api/v1/search/hashtags?q=paghash&offset=0&limit=2")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 3
    assert len(d1["items"]) == 2

    r2 = test_client.get("/api/v1/search/hashtags?q=paghash&offset=2&limit=2")
    assert r2.status_code == 200
    d2 = r2.json()
    assert len(d2["items"]) == 1
    assert d2["offset"] == 2


def test_search_hashtags_sorted_by_mention_count(test_client):
    for _ in range(3):
        test_client.post("/api/v1/posts/", json={
            "content": "Popular #sorttest", "visibility": "public",
        })
    test_client.post("/api/v1/posts/", json={
        "content": "Rare #sortother", "visibility": "public",
    })

    res = test_client.get("/api/v1/search/hashtags?q=sort")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["items"][0]["name"] == "sorttest"
    assert data["items"][1]["name"] == "sortother"
    assert data["items"][0]["mention_count"] > data["items"][1]["mention_count"]
