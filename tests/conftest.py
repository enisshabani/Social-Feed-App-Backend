import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.dependencies import get_current_user
from app.main import app

try:
    from app.core.tasks.ai_tasks import analyze_sentiment_task, suggest_hashtags_task

    def _mock_delay(**kwargs):
        raise RuntimeError("Broker unreachable")

    suggest_hashtags_task.delay = _mock_delay
    analyze_sentiment_task.delay = _mock_delay
except Exception:
    pass

# In-memory SQLite DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Fake user to mock get_current_user
class FakeUser:
    id = 1
    tenant_id = "default"
    role = "user"
    is_active = True

fake_user = FakeUser()

def override_get_current_user():
    return fake_user


@pytest.fixture(autouse=True)
def seed_user(db_session):
    """Seed a test user matching the fake_user so FK relationships work."""
    from app.models.user import User

    user = db_session.query(User).filter(User.id == 1).first()
    if not user:
        db_session.add(
            User(
                id=1,
                username="testuser",
                email="testuser@example.com",
                hashed_password="hashed_password",
                is_active=True,
                role="user",
                tenant_id="default",
            )
        )
        db_session.commit()

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

@pytest.fixture(scope="function", autouse=True)
def db_session():
    from app.core.cache import cache_service
    cache_service.invalidate_prefix("")
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="module")
def test_client():
    with TestClient(app) as client:
        yield client

@pytest.fixture(scope="function")
def current_fake_user():
    return fake_user
