"""
KaPak - AI Tests
API tests for AI endpoint behavior (task creation + status polling).
"""

from app.models.ai_task import AiTask


# ==========================================
# API: POST /ai/suggest-hashtags
# ==========================================

def test_suggest_hashtags_returns_202(test_client):
    payload = {"post_text": "This is a test post about programming and technology"}
    res = test_client.post("/api/v1/ai/suggest-hashtags", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert data["task_type"] == "suggest_hashtags"
    assert "id" in data
    assert "status" in data


def test_suggest_hashtags_creates_db_record(test_client, db_session):
    payload = {"post_text": "Learning FastAPI and SQLAlchemy"}
    res = test_client.post("/api/v1/ai/suggest-hashtags", json=payload)
    task_id = res.json()["id"]

    task = db_session.query(AiTask).filter(AiTask.id == task_id).first()
    assert task is not None
    assert task.task_type == "suggest_hashtags"
    assert task.input_data == {"post_text": "Learning FastAPI and SQLAlchemy"}
    assert task.user_id == 1
    assert task.tenant_id == "default"


def test_suggest_hashtags_empty_text_rejected(test_client):
    res = test_client.post("/api/v1/ai/suggest-hashtags", json={"post_text": ""})
    assert res.status_code == 422


def test_suggest_hashtags_text_too_long(test_client):
    payload = {"post_text": "x" * 5001}
    res = test_client.post("/api/v1/ai/suggest-hashtags", json=payload)
    assert res.status_code == 422


def test_suggest_hashtags_missing_field(test_client):
    res = test_client.post("/api/v1/ai/suggest-hashtags", json={})
    assert res.status_code == 422


# ==========================================
# API: POST /ai/analyze-sentiment
# ==========================================

def test_analyze_sentiment_returns_202(test_client):
    payload = {"post_text": "I am feeling great today!"}
    res = test_client.post("/api/v1/ai/analyze-sentiment", json=payload)
    assert res.status_code == 202
    data = res.json()
    assert data["task_type"] == "analyze_sentiment"


def test_analyze_sentiment_creates_db_record(test_client, db_session):
    payload = {"post_text": "This is terrible and awful"}
    res = test_client.post("/api/v1/ai/analyze-sentiment", json=payload)
    task_id = res.json()["id"]

    task = db_session.query(AiTask).filter(AiTask.id == task_id).first()
    assert task is not None
    assert task.task_type == "analyze_sentiment"


def test_analyze_sentiment_empty_rejected(test_client):
    res = test_client.post("/api/v1/ai/analyze-sentiment", json={"post_text": ""})
    assert res.status_code == 422


def test_analyze_sentiment_text_too_long(test_client):
    payload = {"post_text": "x" * 5001}
    res = test_client.post("/api/v1/ai/analyze-sentiment", json=payload)
    assert res.status_code == 422


def test_analyze_sentiment_missing_field(test_client):
    res = test_client.post("/api/v1/ai/analyze-sentiment", json={})
    assert res.status_code == 422


# ==========================================
# API: GET /tasks/{task_id}/status
# ==========================================

def test_poll_task_returns_status(test_client):
    payload = {"post_text": "Post text for polling test"}
    ai_res = test_client.post("/api/v1/ai/suggest-hashtags", json=payload)
    task_id = ai_res.json()["id"]

    res = test_client.get(f"/api/v1/tasks/{task_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["task_id"] == task_id
    assert data["task_type"] == "suggest_hashtags"
    assert data["status"] == "failed"


def test_poll_task_after_enqueue_failure(test_client):
    payload = {"post_text": "Celery broker is down in tests"}
    ai_res = test_client.post("/api/v1/ai/suggest-hashtags", json=payload)
    task_id = ai_res.json()["id"]

    res = test_client.get(f"/api/v1/tasks/{task_id}/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "Broker unreachable" in data["error_message"]


def test_poll_task_not_found(test_client):
    res = test_client.get("/api/v1/tasks/99999/status")
    assert res.status_code == 404
