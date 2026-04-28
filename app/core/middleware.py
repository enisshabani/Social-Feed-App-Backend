"""
KaPak - Middleware
Logging middleware and other request/response processing.
"""

import time
import logging
from fastapi import Request

logger = logging.getLogger("kapak")


async def logging_middleware(request: Request, call_next):
    """
    Middleware that logs every request with method, path, status, and duration.
    Required by project specification for request logging.
    """
    start_time = time.time()

    # Log incoming request
    logger.info(f"→ {request.method} {request.url.path}")

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = round((time.time() - start_time) * 1000, 2)

    # Log response
    logger.info(
        f"← {request.method} {request.url.path} "
        f"| Status: {response.status_code} "
        f"| Duration: {duration}ms"
    )

    # Add custom headers
    response.headers["X-Process-Time"] = str(duration)
    response.headers["X-App-Name"] = "KaPak"

    return response
