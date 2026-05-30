import pytest
from fastapi import HTTPException

from app.core.dependencies import get_current_user
from app.main import app
from app.modules.notifications.models import Notification, NotificationType


# Pre-populate some notifications for integration tests
@pytest.fixture
def populated_db(db_session, current_fake_user):
    n1 = Notification(
        type=NotificationType.FOLLOW,
        actor_id=2,
        recipient_id=current_fake_user.id,
        tenant_id=current_fake_user.tenant_id,
        is_read=False
    )
    n2 = Notification(
        type=NotificationType.LIKE,
        actor_id=3,
        recipient_id=current_fake_user.id,
        tenant_id=current_fake_user.tenant_id,
        is_read=False
    )
    db_session.add_all([n1, n2])
    db_session.commit()
    db_session.refresh(n1)
    db_session.refresh(n2)
    return n1, n2

def test_get_notifications_returns_200(test_client, populated_db):
    response = test_client.get("/api/v1/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["unread_count"] == 2
    assert len(data["items"]) == 2

def test_mark_notification_read_returns_200(test_client, populated_db):
    n1, n2 = populated_db
    response = test_client.put(f"/api/v1/notifications/{n1.id}/read")
    assert response.status_code == 200
    assert response.json()["success"] is True

def test_mark_all_read_returns_200(test_client, populated_db):
    response = test_client.put("/api/v1/notifications/read-all")
    assert response.status_code == 200

    # Verify via get
    get_response = test_client.get("/api/v1/notifications")
    assert get_response.json()["unread_count"] == 0

def test_delete_notification_returns_204(test_client, populated_db):
    n1, n2 = populated_db
    response = test_client.delete(f"/api/v1/notifications/{n1.id}")
    assert response.status_code == 204

    get_response = test_client.get("/api/v1/notifications")
    assert get_response.json()["total"] == 1

def test_clear_notifications_returns_200(test_client, populated_db):
    response = test_client.delete("/api/v1/notifications/clear-all")
    assert response.status_code == 200
    assert response.json()["success"] is True

    get_response = test_client.get("/api/v1/notifications")
    data = get_response.json()
    assert data["total"] == 0
    assert data["unread_count"] == 0

def test_get_unread_count_returns_200(test_client, populated_db):
    response = test_client.get("/api/v1/notifications/unread-count")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 2

def test_unauthorized_returns_401(test_client):
    def _raise_unauthorized():
        raise HTTPException(status_code=401, detail="Not authenticated")

    saved = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = _raise_unauthorized

    try:
        response = test_client.get("/api/v1/notifications")
        assert response.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
        else:
            app.dependency_overrides.pop(get_current_user, None)
