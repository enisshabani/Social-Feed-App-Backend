from app.modules.follows.models import Follow


def test_follow_endpoint_creates_relationship(test_client, db_session, monkeypatch):
    created_notifications = []

    def fake_follow_notification(actor_id: int, recipient_id: int, tenant_id: str):
        created_notifications.append((actor_id, recipient_id, tenant_id))

    monkeypatch.setattr(
        "app.modules.follows.router.process_follow_notification",
        fake_follow_notification,
    )

    response = test_client.post("/api/v1/follows/2")

    assert response.status_code == 201
    data = response.json()
    assert data["follower_id"] == 1
    assert data["followee_id"] == 2
    assert created_notifications == [(1, 2, "default")]

    follow = db_session.query(Follow).filter_by(
        follower_id=1,
        followee_id=2,
        tenant_id="default",
    ).one()
    assert follow.id == data["id"]
    assert follow.tenant_id == "default"


def test_follow_endpoint_rejects_self_follow(test_client, db_session):
    response = test_client.post("/api/v1/follows/1")

    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot follow yourself"


def test_follow_endpoint_rejects_duplicate_follow(test_client, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.follows.router.process_follow_notification", lambda **_: None)

    first_response = test_client.post("/api/v1/follows/2")
    duplicate_response = test_client.post("/api/v1/follows/2")

    assert first_response.status_code == 201
    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Already following this user"


def test_unfollow_endpoint_deletes_relationship(test_client, db_session, monkeypatch):
    monkeypatch.setattr("app.modules.follows.router.process_follow_notification", lambda **_: None)
    test_client.post("/api/v1/follows/2")

    response = test_client.delete("/api/v1/follows/2")

    assert response.status_code == 204
    assert db_session.query(Follow).filter_by(
        follower_id=1,
        followee_id=2,
        tenant_id="default",
    ).first() is None


def test_follow_read_endpoints_return_lists_counts_and_status(test_client, db_session):
    db_session.add_all(
        [
            Follow(follower_id=1, followee_id=2, tenant_id="default"),
            Follow(follower_id=3, followee_id=2, tenant_id="default"),
            Follow(follower_id=1, followee_id=4, tenant_id="default"),
            Follow(follower_id=4, followee_id=1, tenant_id="default"),
            Follow(follower_id=9, followee_id=2, tenant_id="tenant-2"),
        ]
    )
    db_session.commit()

    followers_response = test_client.get("/api/v1/follows/followers/2")
    following_response = test_client.get("/api/v1/follows/following/1")
    counts_response = test_client.get("/api/v1/follows/counts/1")
    check_response = test_client.get("/api/v1/follows/check/2")
    pending_response = test_client.get("/api/v1/follows/pending-follow-backs")

    assert followers_response.status_code == 200
    assert sorted(item["follower_id"] for item in followers_response.json()) == [1, 3]

    assert following_response.status_code == 200
    assert sorted(item["followee_id"] for item in following_response.json()) == [2, 4]

    assert counts_response.status_code == 200
    assert counts_response.json() == {"followers_count": 1, "following_count": 2}

    assert check_response.status_code == 200
    assert check_response.json() == {"is_following": True}

    assert pending_response.status_code == 200
    assert [item["followee_id"] for item in pending_response.json()] == [2]
