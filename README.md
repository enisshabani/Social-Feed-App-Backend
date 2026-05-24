# KaPak Backend

FastAPI backend for KaPak with Redis-backed Celery tasks and Google AI Studio support.

## AI And Celery Setup

These steps do not require Docker Compose.

### One-Time Setup

1. Get a Google AI key from https://aistudio.google.com/apikey.

2. Add the key to `.env`:

```env
GOOGLE_API_KEY=paste-your-key-here
GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
```

3. Install and start Redis.

Using Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

On Windows without Docker, install Redis from:

```text
https://github.com/microsoftarchive/redis/releases
```

Download `Redis-x64-3.0.504.msi`, install it, and let it auto-start.

On macOS with Homebrew:

```bash
brew install redis
brew services start redis
```

4. Install Python dependencies.

Windows PowerShell:

```powershell
cd Social-Feed-App-Backend
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux:

```bash
cd Social-Feed-App-Backend
source ../venv/bin/activate
pip install -r requirements.txt
```

## Run Locally

Open four terminals in this order.

### Terminal 1 - Redis

If Redis was started with Docker:

```bash
docker start redis
```

If Redis was installed natively and configured as a service, it should already be running.

### Terminal 2 - Backend

Windows PowerShell:

```powershell
cd Social-Feed-App-Backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

macOS/Linux:

```bash
cd Social-Feed-App-Backend
source ../venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Terminal 3 - Celery Worker

Windows PowerShell:

```powershell
cd Social-Feed-App-Backend
.venv\Scripts\Activate.ps1
celery -A app.core.celery_app worker --loglevel=info --pool=solo
```

macOS/Linux:

```bash
cd Social-Feed-App-Backend
source ../venv/bin/activate
celery -A app.core.celery_app worker --loglevel=info
```

Use `--pool=solo` on Windows to avoid Celery worker crashes.

### Terminal 4 - Frontend

```bash
cd Social-Feed-App-Frontend
npm run dev
```

Open http://localhost:5173.

## Testing AI

- Hashtags: type a post in the composer, click the wand button, and wait a few seconds for suggestions.
- Sentiment: click the smiley face on any post to analyze its mood.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `No module named celery` | Run `pip install -r requirements.txt`. |
| Always returns `["kapak", "social", "trending"]` | Redis is not running. Start Redis and restart the backend and worker. |
| `429 Too Many Requests` | The free quota is exhausted for the day. Wait or use another valid key. |
| Celery crashes on Windows | Start the worker with `--pool=solo`. |
| Redis connection refused | Start Redis with `docker start redis` or your native Redis service. |
