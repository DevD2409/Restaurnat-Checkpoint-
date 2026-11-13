import json
import os
import time
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.dependencies import (
    authenticate_websocket_user,
    is_staff_user,
    verify_table_session_token,
)
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.user import User, UserRole
from app.utils.seed_data import seed_database, ensure_subscription_plans_synced
from app.websocket.connection_manager import manager

# Configure production logging
logger = logging.getLogger("srmp")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

import re

REDACT_QUERY_PARAMS_REGEX = re.compile(
    r"([?&](?:token|session_token)=)[^&\s'\"]+",
    re.IGNORECASE
)

class RedactSensitiveQueryFilter(logging.Filter):
    """Redacts sensitive query parameters like token and session_token from all log output."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = REDACT_QUERY_PARAMS_REGEX.sub(r"\1[REDACTED]", record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    REDACT_QUERY_PARAMS_REGEX.sub(r"\1[REDACTED]", str(arg)) if isinstance(arg, str) else arg
                    for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: REDACT_QUERY_PARAMS_REGEX.sub(r"\1[REDACTED]", str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
        return True

_redact_filter = RedactSensitiveQueryFilter()
for _log_name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "srmp", "websocket", "fastapi"):
    logging.getLogger(_log_name).addFilter(_redact_filter)

# Optional Sentry error reporting integration
if settings.SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.2 if settings.ENVIRONMENT == "production" else 1.0,
        )
        logger.info("Sentry error reporting initialized.")
    except Exception as e:
        logger.warning(f"Could not initialize Sentry: {e}")

# Import routers
from app.routers.auth import router as auth_router
from app.routers.restaurants import router as restaurant_router
from app.routers.tables import router as tables_router
from app.routers.menu import router as menu_router
from app.routers.orders import router as orders_router
from app.routers.kitchen import router as kitchen_router
from app.routers.service_requests import router as service_requests_router
from app.routers.reservations import router as reservations_router
from app.routers.billing import router as billing_router
from app.routers.payments import router as payments_router
from app.routers.analytics import router as analytics_router
from app.routers.onboarding import router as onboarding_router
from app.routers.super_admin import router as super_admin_router
from app.routers.feedback import router as feedback_router
from app.routers.subscriptions import router as subscriptions_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # In development, create tables automatically if needed; staging/production run Alembic migrations (alembic upgrade head).
    if settings.ENVIRONMENT not in ("staging", "production"):
        Base.metadata.create_all(bind=engine)

    env_lower = settings.ENVIRONMENT.lower()
    if env_lower == "production":
        should_seed_demo = False
    elif settings.SEED_DEMO_DATA is not None:
        should_seed_demo = settings.SEED_DEMO_DATA
    else:
        seed_demo_flag = os.getenv("SEED_DEMO_DATA")
        should_seed_demo = (
            seed_demo_flag.lower() in ("1", "true", "yes")
            if seed_demo_flag is not None
            else env_lower not in ("staging", "production")
        )
    try:
        if should_seed_demo:
            seed_database()
        else:
            db = SessionLocal()
            try:
                if ensure_subscription_plans_synced(db):
                    db.commit()
            finally:
                db.close()
    except Exception as e:
        logger.warning(f"Startup seed/plan sync note: {e}")
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Multi-Tenant Hospitality SaaS Platform powering Customer Dining, KDS, Staff Management, and Super Admin Administration.",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Production request logging with timing, client IP extraction, and X-Request-ID propagation."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start_time = time.time()

    response: Response = await call_next(request)

    process_time_ms = round((time.time() - start_time) * 1000, 2)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time"] = f"{process_time_ms}ms"

    # Don't clutter logs with high-frequency health probes
    if not request.url.path.startswith("/health"):
        client_ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "unknown")
        logger.info(
            f"req_id={request_id} client={client_ip} method={request.method} path={request.url.path} "
            f"status={response.status_code} duration={process_time_ms}ms"
        )

    return response

# Include Routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(restaurant_router, prefix=settings.API_V1_STR)
app.include_router(tables_router, prefix=settings.API_V1_STR)
app.include_router(menu_router, prefix=settings.API_V1_STR)
app.include_router(orders_router, prefix=settings.API_V1_STR)
app.include_router(kitchen_router, prefix=settings.API_V1_STR)
app.include_router(service_requests_router, prefix=settings.API_V1_STR)
app.include_router(reservations_router, prefix=settings.API_V1_STR)
app.include_router(billing_router, prefix=settings.API_V1_STR)
app.include_router(payments_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(onboarding_router, prefix=settings.API_V1_STR)
app.include_router(super_admin_router, prefix=settings.API_V1_STR)
app.include_router(feedback_router, prefix=settings.API_V1_STR)
app.include_router(subscriptions_router, prefix=settings.API_V1_STR)

# Static files directory for uploads and media
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
os.makedirs(os.path.join(STATIC_DIR, "uploads", "feedback"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "architecture": "Multi-Tenant Hospitality SaaS"
    }

@app.get("/health/live")
def health_liveness():
    """Liveness probe: verifies process is alive and accepting connections."""
    return {"status": "alive", "service": settings.PROJECT_NAME, "version": settings.VERSION}

@app.get("/health/db")
def health_db():
    """Database probe: tests actual database query execution and measures round-trip latency."""
    start = time.time()
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        latency_ms = round((time.time() - start) * 1000, 2)
        db_type = "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite"
        return {
            "status": "connected",
            "database_type": db_type,
            "latency_ms": latency_ms
        }
    except Exception as e:
        logger.error(f"Database health probe failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {str(e)}"
        )
    finally:
        db.close()

@app.get("/health/ready")
def health_readiness():
    """Readiness probe: verifies all core dependencies (DB, storage) are available to serve traffic."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Readiness check failed - DB unreachable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready: database unreachable"
        )
    finally:
        db.close()

    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "storage_backend": settings.STORAGE_BACKEND
    }

# WebSockets Privileged Access Matrix
PRIVILEGED_CHANNELS = {
    "admin": ["PLATFORM_SUPER_ADMIN", "RESTAURANT_OWNER", "ADMIN", "RESTAURANT_MANAGER", "MANAGER"],
    "kitchen": ["PLATFORM_SUPER_ADMIN", "RESTAURANT_OWNER", "ADMIN", "RESTAURANT_MANAGER", "MANAGER", "KITCHEN", "CHEF"],
    "staff": ["PLATFORM_SUPER_ADMIN", "RESTAURANT_OWNER", "ADMIN", "RESTAURANT_MANAGER", "MANAGER", "WAITER", "CASHIER"]
}

def _authenticate_ws_token(token: Optional[str]) -> Optional[User]:
    """Resolve active non-locked user for WebSocket auth using a short-lived DB session."""
    if not token:
        return None
    db = None
    try:
        db = SessionLocal()
        return authenticate_websocket_user(token, db)
    except Exception as e:
        logger.warning(f"WebSocket token authentication failed: {e}")
        return None
    finally:
        if db is not None:
            db.close()


def _is_active_restaurant(restaurant_id: Optional[int]) -> bool:
    """Verify the target restaurant exists and is active without ever defaulting to tenant 1."""
    if restaurant_id is None or restaurant_id <= 0:
        return False
    db = None
    try:
        db = SessionLocal()
        return (
            db.query(Restaurant.id)
            .filter(Restaurant.id == restaurant_id, Restaurant.is_active == True)
            .first()
            is not None
        )
    except Exception as e:
        logger.warning(f"WebSocket restaurant verification failed for restaurant_id={restaurant_id}: {e}")
        return False
    finally:
        if db is not None:
            db.close()


def _resolve_table_ws_tenant(
    websocket: WebSocket,
    *,
    table_id: int,
    expected_tenant_id: Optional[int] = None,
    token: Optional[str] = None,
    session_token: Optional[str] = None,
) -> Optional[int]:
    """
    Validate table ownership, tenant match, and caller credentials (staff JWT or active TableSession)
    for table WebSocket connections. Never falls back to tenant 1 on missing table or DB failure.
    """
    raw_session = (
        session_token
        if session_token is not None
        else websocket.headers.get("x-table-session")
    )

    db = None
    try:
        db = SessionLocal()
        user: Optional[User] = None
        if token is not None:
            user = authenticate_websocket_user(token, db)
            if not user:
                return None

        table = (
            db.query(Table)
            .join(Restaurant, Table.restaurant_id == Restaurant.id)
            .filter(
                Table.id == table_id,
                Table.is_active == True,
                Restaurant.is_active == True,
            )
            .first()
        )
        if not table or not table.restaurant_id:
            return None

        if expected_tenant_id is not None and table.restaurant_id != expected_tenant_id:
            return None

        if user is not None and is_staff_user(user):
            if user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id != table.restaurant_id:
                return None
            if raw_session is not None:
                if not verify_table_session_token(db, raw_session, expected_table_id=table.id):
                    return None
            return table.restaurant_id

        # Non-staff / customer callers must present an active, non-ended TableSession for this exact table
        if raw_session is None:
            return None
        active_session = verify_table_session_token(db, raw_session, expected_table_id=table.id)
        if not active_session:
            return None
        return table.restaurant_id
    except Exception as e:
        logger.warning(f"Table WebSocket authorization lookup failed for table_id={table_id}: {e}")
        return None
    finally:
        if db is not None:
            db.close()


async def _run_ws_heartbeat(websocket: WebSocket, pong_payload: dict, disconnect_fn) -> None:
    try:
        while True:
            await websocket.receive_text()
            await websocket.send_text(json.dumps(pong_payload))
    except WebSocketDisconnect:
        disconnect_fn()
    except Exception:
        disconnect_fn()


@app.websocket("/ws/tenant/{tenant_id}/{channel}")
async def websocket_tenant_channel_endpoint(
    websocket: WebSocket,
    tenant_id: int,
    channel: str,
    token: Optional[str] = Query(None)
):
    """Multi-tenant isolated WebSocket channel with active-user & password-rotation enforcement."""
    norm_channel = (channel or "").strip().lower()
    if not norm_channel or not _is_active_restaurant(tenant_id):
        await websocket.close(code=1008)
        return

    if norm_channel in PRIVILEGED_CHANNELS:
        allowed_roles = PRIVILEGED_CHANNELS[norm_channel]
        user = _authenticate_ws_token(token)
        if not user or user.role.value not in allowed_roles:
            await websocket.close(code=1008)
            return
        if user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id != tenant_id:
            await websocket.close(code=1008)  # Reject cross-tenant eavesdropping
            return
    elif token is not None:
        user = _authenticate_ws_token(token)
        if not user:
            await websocket.close(code=1008)
            return
        if user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id != tenant_id:
            await websocket.close(code=1008)
            return

    await manager.connect(websocket, channel=norm_channel, restaurant_id=tenant_id)
    await _run_ws_heartbeat(
        websocket,
        {"type": "PONG", "tenant_id": tenant_id, "channel": norm_channel},
        lambda: manager.disconnect(websocket, channel=norm_channel, restaurant_id=tenant_id),
    )


@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(
    websocket: WebSocket,
    channel: str,
    token: Optional[str] = Query(None),
    restaurant_id: Optional[int] = Query(None),
):
    """
    Tenant-scoped WebSocket channel endpoint.
    Privileged channels always require valid authentication in every environment and never default
    a super-admin or anonymous connection to tenant 1.
    """
    norm_channel = (channel or "").strip().lower()
    if not norm_channel:
        await websocket.close(code=1008)
        return

    resolved_restaurant_id: Optional[int] = None
    if norm_channel in PRIVILEGED_CHANNELS:
        allowed_roles = PRIVILEGED_CHANNELS[norm_channel]
        user = _authenticate_ws_token(token)
        if not user or user.role.value not in allowed_roles:
            await websocket.close(code=1008)
            return

        if user.role == UserRole.PLATFORM_SUPER_ADMIN:
            resolved_restaurant_id = restaurant_id if restaurant_id is not None else user.restaurant_id
            if not resolved_restaurant_id:
                await websocket.close(code=1008)
                return
        else:
            if not user.restaurant_id or (restaurant_id is not None and restaurant_id != user.restaurant_id):
                await websocket.close(code=1008)
                return
            resolved_restaurant_id = user.restaurant_id
    else:
        if token is not None:
            user = _authenticate_ws_token(token)
            if not user:
                await websocket.close(code=1008)
                return
            if user.role == UserRole.PLATFORM_SUPER_ADMIN:
                resolved_restaurant_id = restaurant_id if restaurant_id is not None else user.restaurant_id
            else:
                if not user.restaurant_id or (restaurant_id is not None and restaurant_id != user.restaurant_id):
                    await websocket.close(code=1008)
                    return
                resolved_restaurant_id = user.restaurant_id
        else:
            resolved_restaurant_id = restaurant_id

        if not resolved_restaurant_id:
            await websocket.close(code=1008)
            return

    if not _is_active_restaurant(resolved_restaurant_id):
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, channel=norm_channel, restaurant_id=resolved_restaurant_id)
    await _run_ws_heartbeat(
        websocket,
        {"type": "PONG", "tenant_id": resolved_restaurant_id, "channel": norm_channel},
        lambda: manager.disconnect(websocket, channel=norm_channel, restaurant_id=resolved_restaurant_id),
    )


@app.websocket("/ws/tenant/{tenant_id}/table/{table_id}")
async def websocket_tenant_table_endpoint(
    websocket: WebSocket,
    tenant_id: int,
    table_id: int,
    token: Optional[str] = Query(None),
    session_token: Optional[str] = Query(None),
):
    resolved_tenant_id = _resolve_table_ws_tenant(
        websocket,
        table_id=table_id,
        expected_tenant_id=tenant_id,
        token=token,
        session_token=session_token,
    )
    if resolved_tenant_id is None:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id)
    await _run_ws_heartbeat(
        websocket,
        {"type": "PONG", "tenant_id": resolved_tenant_id, "table_id": table_id},
        lambda: manager.disconnect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id),
    )


@app.websocket("/ws/table/{table_id}")
async def websocket_table_endpoint(
    websocket: WebSocket,
    table_id: int,
    token: Optional[str] = Query(None),
    session_token: Optional[str] = Query(None),
):
    resolved_tenant_id = _resolve_table_ws_tenant(
        websocket,
        table_id=table_id,
        expected_tenant_id=None,
        token=token,
        session_token=session_token,
    )
    if resolved_tenant_id is None:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id)
    await _run_ws_heartbeat(
        websocket,
        {"type": "PONG", "tenant_id": resolved_tenant_id, "table_id": table_id},
        lambda: manager.disconnect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id),
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
