"""
KaPak - Integration Test: Hashtag Lifecycle
End-to-end flow: create post with hashtags -> search finds it -> hashtag feed returns it.
"""


def test_full_hashtag_lifecycle(test_client, db_session):
    payload = {"content": "Integration test with #lifecycle tag", "visibility": "public"}
    post_res = test_client.post("/api/v1/posts/", json=payload)
    assert post_res.status_code == 201
    post_id = post_res.json()["id"]

    search_res = test_client.get("/api/v1/search/posts?q=lifecycle")
    assert search_res.status_code == 200
    assert search_res.json()["total"] >= 1
    found = any(item["id"] == post_id for item in search_res.json()["items"])
    assert found, "Search should return the post with #lifecycle"

    hashtag_res = test_client.get("/api/v1/hashtags/lifecycle/posts")
    assert hashtag_res.status_code == 200
    data = hashtag_res.json()
    assert len(data) >= 1
    assert any(item["id"] == post_id for item in data)

    search_hash = test_client.get("/api/v1/search/hashtags?q=lifecycle")
    assert search_hash.status_code == 200
    assert search_hash.json()["total"] >= 1


def test_multiple_posts_same_hashtag(test_client):
    ids = []
    for i in range(3):
        res = test_client.post("/api/v1/posts/", json={
            "content": f"Batch post {i} with #batchtag", "visibility": "public",
        })
        ids.append(res.json()["id"])

    feed_res = test_client.get("/api/v1/hashtags/batchtag/posts?limit=10")
    assert feed_res.status_code == 200
    assert len(feed_res.json()) == 3
    returned_ids = {item["id"] for item in feed_res.json()}
    assert returned_ids == set(ids)
