"""
KaPak - Middleware
Logging middleware and other request/response processing.
"""

import time
import logging
import re
from fastapi import Request
from app.core.tenant import set_tenant, reset_tenant

logger = logging.getLogger("kapak")


def normalize_tenant_id(value: str | None) -> str:
    if not value:
        return "default"

    tenant_id = re.sub(r"[^a-zA-Z0-9_-]", "", value.strip().lower())
    if not tenant_id or tenant_id in {"www", "localhost", "127001", "0000"}:
        return "default"

    return tenant_id


def tenant_from_host(host: str | None) -> str:
    if not host:
        return "default"

    hostname = host.split(":", 1)[0].lower()
    if hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return "default"

    parts = hostname.split(".")

    if len(parts) > 1:
        return normalize_tenant_id(parts[0])

    return "default"


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

async def tenant_middleware(request: Request, call_next):
    """
    Middleware that parses the tenant_id and injects it into ContextVar.
    """
    header_tenant = request.headers.get("x-tenant-id")
    tenant_id = normalize_tenant_id(header_tenant)
    if not header_tenant:
        tenant_id = tenant_from_host(request.headers.get("host"))
        
    token = set_tenant(tenant_id)
    
    try:
        response = await call_next(request)
        # Optional: Add tenant to headers for debugging
        response.headers["X-Tenant-ID"] = tenant_id
        return response
    finally:
        reset_tenant(token)
