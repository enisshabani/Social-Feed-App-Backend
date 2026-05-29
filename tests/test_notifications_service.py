import pytest

from app.models.notification_preference import NotificationPreference
from app.modules.notifications.exceptions import NotificationForbiddenError, NotificationNotFoundError
from app.modules.notifications.models import Notification, NotificationType
from app.modules.notifications.schemas import NotificationPreferenceSchema
from app.modules.notifications.service import NotificationService


def test_get_notifications_filters_by_tenant_type_and_read_status(db_session):
    db_session.add_all(
        [
            Notification(
                type=NotificationType.FOLLOW,
                actor_id=2,
                recipient_id=1,
                tenant_id="tenant-1",
                is_read=False,
            ),
            Notification(
                type=NotificationType.LIKE,
                actor_id=3,
                recipient_id=1,
                tenant_id="tenant-1",
                is_read=False,
            ),
            Notification(
                type=NotificationType.FOLLOW,
                actor_id=4,
                recipient_id=1,
                tenant_id="tenant-1",
                is_read=True,
            ),
            Notification(
                type=NotificationType.FOLLOW,
                actor_id=5,
                recipient_id=1,
                tenant_id="tenant-2",
                is_read=False,
            ),
        ]
    )
    db_session.commit()

    service = NotificationService(db_session, tenant_id="tenant-1")
    items, unread_count, total = service.get_notifications(
        recipient_id=1,
        type_filter=NotificationType.FOLLOW,
        is_read_filter=False,
    )

    assert total == 1
    assert unread_count == 2
    assert len(items) == 1
    assert items[0].actor_id == 2


def test_mark_as_read_requires_matching_recipient_and_tenant(db_session):
    notification = Notification(
        type=NotificationType.FOLLOW,
        actor_id=2,
        recipient_id=1,
        tenant_id="tenant-1",
        is_read=False,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    service = NotificationService(db_session, tenant_id="tenant-1")
    service.mark_as_read(notification_id=notification.id, recipient_id=1)

    db_session.refresh(notification)
    assert notification.is_read is True

    with pytest.raises(NotificationForbiddenError):
        service.mark_as_read(notification_id=notification.id, recipient_id=99)

    other_tenant_service = NotificationService(db_session, tenant_id="tenant-2")
    with pytest.raises(NotificationNotFoundError):
        other_tenant_service.mark_as_read(notification_id=notification.id, recipient_id=1)


def test_clear_notifications_deletes_only_current_users_tenant_records(db_session):
    db_session.add_all(
        [
            Notification(type=NotificationType.FOLLOW, actor_id=2, recipient_id=1, tenant_id="tenant-1"),
            Notification(type=NotificationType.LIKE, actor_id=3, recipient_id=1, tenant_id="tenant-1"),
            Notification(type=NotificationType.MENTION, actor_id=4, recipient_id=2, tenant_id="tenant-1"),
            Notification(type=NotificationType.FOLLOW, actor_id=5, recipient_id=1, tenant_id="tenant-2"),
        ]
    )
    db_session.commit()

    service = NotificationService(db_session, tenant_id="tenant-1")
    deleted = service.clear_notifications(recipient_id=1)

    remaining = db_session.query(Notification).all()
    assert deleted == 2
    assert {(item.recipient_id, item.tenant_id) for item in remaining} == {(2, "tenant-1"), (1, "tenant-2")}


def test_notification_preferences_are_created_and_updated(db_session):
    service = NotificationService(db_session, tenant_id="tenant-1")

    default_preferences = service.get_preferences(user_id=1)

    assert default_preferences.user_id == 1
    assert default_preferences.tenant_id == "tenant-1"
    assert default_preferences.highlight_unread is True
    assert db_session.query(NotificationPreference).count() == 1

    updated = service.update_preferences(
        user_id=1,
        preferences=NotificationPreferenceSchema(
            filter_not_following=True,
            filter_not_followed_by=True,
            filter_new_accounts=True,
            highlight_unread=False,
            display_all_categories=False,
        ),
    )

    assert updated.filter_not_following is True
    assert updated.filter_not_followed_by is True
    assert updated.filter_new_accounts is True
    assert updated.highlight_unread is False
    assert updated.display_all_categories is False
    assert db_session.query(NotificationPreference).count() == 1
