import pytest

from app.modules.follows.exceptions import AlreadyFollowingError, NotFollowingError, SelfFollowError
from app.modules.follows.models import Follow
from app.modules.follows.service import FollowService


def test_follow_user_success(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    follow = service.follow_user(follower_id=1, followee_id=2)
    assert follow.follower_id == 1
    assert follow.followee_id == 2
    assert follow.tenant_id == "tenant-1"

def test_follow_self_raises_error(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    with pytest.raises(SelfFollowError):
        service.follow_user(follower_id=1, followee_id=1)

def test_follow_duplicate_raises_error(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=1, followee_id=2)
    with pytest.raises(AlreadyFollowingError):
        service.follow_user(follower_id=1, followee_id=2)

def test_unfollow_success(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=1, followee_id=2)
    service.unfollow_user(follower_id=1, followee_id=2)

    # Verify it was deleted
    follow = db_session.query(Follow).filter_by(follower_id=1, followee_id=2).first()
    assert follow is None

def test_unfollow_not_following_raises_error(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    with pytest.raises(NotFollowingError):
        service.unfollow_user(follower_id=1, followee_id=2)

def test_get_followers_returns_correct_list(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=2, followee_id=1)
    service.follow_user(follower_id=3, followee_id=1)

    followers = service.get_followers(user_id=1)
    assert len(followers) == 2
    assert followers[0].follower_id in [2, 3]

def test_get_pending_follow_backs_excludes_users_who_follow_back(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=1, followee_id=2)
    service.follow_user(follower_id=1, followee_id=3)
    service.follow_user(follower_id=3, followee_id=1)

    pending = service.get_pending_follow_backs(user_id=1)

    assert len(pending) == 1
    assert pending[0].followee_id == 2

def test_get_follow_counts_correct(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=1, followee_id=2)
    service.follow_user(follower_id=1, followee_id=3)
    service.follow_user(follower_id=4, followee_id=1)

    counts = service.get_follow_counts(user_id=1)
    assert counts["followers_count"] == 1
    assert counts["following_count"] == 2

def test_is_following_returns_true_and_false(db_session):
    service = FollowService(db_session, tenant_id="tenant-1")
    service.follow_user(follower_id=1, followee_id=2)

    assert service.is_following(follower_id=1, followee_id=2) is True
    assert service.is_following(follower_id=1, followee_id=3) is False
