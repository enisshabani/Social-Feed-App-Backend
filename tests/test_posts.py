"""
KaPak - Posts & Feeds API Tests
Verifies all posts, comments, likes, reposts, bookmarks, drafts, and AI refinement endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.database import Base, get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.post import Post, Comment, PostLike, Draft

# 1. Setup in-memory test database
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 2. Setup mock user fixture
mock_user = User(
    id=1,
    username="testuser",
    email="testuser@example.com",
    hashed_password="hashed_password",
    is_active=True,
    role="user"
)

# 3. Create database override dependency injections
def override_get_db():
    database = TestingSessionLocal()
    try:
        yield database
    finally:
        database.close()

def override_get_current_user():
    # Return transient mock user
    return User(
        id=1,
        username="testuser",
        email="testuser@example.com",
        is_active=True,
        role="user"
    )

# Apply overrides
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Build database schema before every test and tear it down after."""
    Base.metadata.create_all(bind=engine)
    
    # Pre-populate a fresh User record in DB matching current user ID
    db = TestingSessionLocal()
    u = User(
        id=1,
        username="testuser",
        email="testuser@example.com",
        hashed_password="hashed_password",
        is_active=True,
        role="user"
    )
    db.merge(u)
    db.commit()
    db.close()
    
    yield
    Base.metadata.drop_all(bind=engine)



# ==========================================
# TEST CASES
# ==========================================

def test_create_post():
    """Verify creating a post parses tags/mentions and builds HTML content."""
    payload = {
        "content": "Hello #world, this is @testuser!",
        "visibility": "public"
    }
    response = client.post("/api/v1/posts/", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["content"] == payload["content"]
    assert data["author_id"] == mock_user.id
    assert '<span class="hashtag">#world</span>' in data["content_html"]
    assert '<span class="mention">@testuser</span>' in data["content_html"]


def test_get_single_post():
    """Verify fetching post detail and relationships."""
    # Create post first
    payload = {"content": "Detail post", "visibility": "public"}
    post_res = client.post("/api/v1/posts/", json=payload)
    post_id = post_res.json()["id"]

    response = client.get(f"/api/v1/posts/{post_id}")
    assert response.status_code == 200
    assert response.json()["id"] == post_id
    assert response.json()["content"] == "Detail post"


def test_like_post_toggle():
    """Verify liking and unliking a post updates counters."""
    # Create post
    post_res = client.post("/api/v1/posts/", json={"content": "Liking post", "visibility": "public"})
    post_id = post_res.json()["id"]

    # First click - Like
    response = client.post(f"/api/v1/posts/{post_id}/like")
    assert response.status_code == 200
    assert response.json()["liked"] is True
    assert "liked successfully" in response.json()["message"]

    # Verify counter in get post
    detail_res = client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["like_count"] == 1

    # Second click - Unlike
    response = client.post(f"/api/v1/posts/{post_id}/like")
    assert response.status_code == 200
    assert response.json()["liked"] is False
    assert "unliked successfully" in response.json()["message"]

    # Verify counter goes back to 0
    detail_res = client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["like_count"] == 0


def test_post_comment():
    """Verify adding comments to a post."""
    post_res = client.post("/api/v1/posts/", json={"content": "Post with comment", "visibility": "public"})
    post_id = post_res.json()["id"]

    payload = {"content": "This is a great post!"}
    response = client.post(f"/api/v1/posts/{post_id}/comments", json=payload)
    assert response.status_code == 201
    assert response.json()["content"] == payload["content"]
    assert response.json()["post_id"] == post_id


def test_repost_post():
    """Verify reposting toggles correctly."""
    post_res = client.post("/api/v1/posts/", json={"content": "Original Post", "visibility": "public"})
    post_id = post_res.json()["id"]

    response = client.post(f"/api/v1/posts/{post_id}/repost")
    assert response.status_code == 200
    assert response.json()["reposted"] is True

    # Check repost counters
    detail_res = client.get(f"/api/v1/posts/{post_id}")
    assert detail_res.json()["repost_count"] == 1


def test_draft_publish():
    """Verify saving a draft and publishing it as a post."""
    # 1. Save draft
    payload = {"content": "This is a draft content."}
    draft_res = client.post("/api/v1/posts/drafts/save", json=payload)
    assert draft_res.status_code == 201
    draft_id = draft_res.json()["id"]

    # 2. Get drafts
    drafts_list = client.get("/api/v1/posts/drafts/all")
    assert len(drafts_list.json()) == 1

    # 3. Publish draft
    publish_res = client.post(f"/api/v1/posts/drafts/{draft_id}/publish")
    assert publish_res.status_code == 201
    assert publish_res.json()["content"] == payload["content"]

    # 4. Draft should be deleted
    drafts_list = client.get("/api/v1/posts/drafts/all")
    assert len(drafts_list.json()) == 0


def test_ai_text_refinement():
    """Verify AI text refinement works with mock fallback."""
    payload = {"content": "This is raw input text", "style": "professional"}
    response = client.post("/api/v1/posts/refine-ai", json=payload)
    assert response.status_code == 200
    assert "refined_content" in response.json()
    assert "#Professional" in response.json()["refined_content"]


def test_get_feeds():
    """Verify home, explore, and tag feed endpoints."""
    # Create posts with tag
    client.post("/api/v1/posts/", json={"content": "Tag test #cooltag", "visibility": "public"})

    # Test home feed
    home_feed = client.get("/api/v1/feeds/home")
    assert home_feed.status_code == 200
    assert len(home_feed.json()["items"]) == 1

    # Test explore hashtags
    explore = client.get("/api/v1/feeds/explore")
    assert explore.status_code == 200
    assert len(explore.json()) == 1
    assert explore.json()[0]["tag"] == "cooltag"

    # Test tag search
    tag_feed = client.get("/api/v1/feeds/tag/cooltag")
    assert tag_feed.status_code == 200
    assert len(tag_feed.json()["items"]) == 1
