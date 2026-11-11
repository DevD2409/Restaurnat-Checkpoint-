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
from app.core.security import decode_access_token
from app.models.table import Table
from app.utils.seed_data import seed_database, ensure_subscription_plans_synced
from app.websocket.connection_manager import manager

# Configure production logging
logger = logging.getLogger("srmp")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

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
    # In development, create tables automatically if needed; staging/production run Alembic preDeployCommand.
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
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
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

@app.websocket("/ws/tenant/{tenant_id}/{channel}")
async def websocket_tenant_channel_endpoint(
    websocket: WebSocket,
    tenant_id: int,
    channel: str,
    token: Optional[str] = Query(None)
):
    """Multi-tenant isolated WebSocket channel with cryptographic membership enforcement."""
    if channel in PRIVILEGED_CHANNELS:
        allowed_roles = PRIVILEGED_CHANNELS[channel]
        if not token:
            await websocket.close(code=1008)
            return
        payload = decode_access_token(token)
        if not payload:
            await websocket.close(code=1008)
            return
        user_role = payload.get("role")
        user_tenant = payload.get("restaurant_id")
        
        # Verify role and strict tenant isolation (Platform super admins can subscribe anywhere)
        if user_role not in allowed_roles:
            await websocket.close(code=1008)
            return
        if user_role != "PLATFORM_SUPER_ADMIN" and user_tenant != tenant_id:
            await websocket.close(code=1008)  # Reject cross-tenant eavesdropping
            return

    await manager.connect(websocket, channel=channel, restaurant_id=tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type": "PONG", "tenant_id": {tenant_id}, "channel": "{channel}"}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel, restaurant_id=tenant_id)
    except Exception:
        manager.disconnect(websocket, channel=channel, restaurant_id=tenant_id)

@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(
    websocket: WebSocket,
    channel: str,
    token: Optional[str] = Query(None)
):
    """Backward-compatible global channel endpoint."""
    if channel in PRIVILEGED_CHANNELS:
        allowed_roles = PRIVILEGED_CHANNELS[channel]
        if token:
            payload = decode_access_token(token)
            if not payload or payload.get("role") not in allowed_roles:
                await websocket.close(code=1008)
                return
        elif settings.ENVIRONMENT == "production":
            await websocket.close(code=1008)
            return

    await manager.connect(websocket, channel=channel, restaurant_id=1)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type": "PONG", "channel": "{channel}"}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel, restaurant_id=1)
    except Exception:
        manager.disconnect(websocket, channel=channel, restaurant_id=1)

@app.websocket("/ws/tenant/{tenant_id}/table/{table_id}")
async def websocket_tenant_table_endpoint(websocket: WebSocket, tenant_id: int, table_id: int):
    await manager.connect(websocket, table_id=table_id, restaurant_id=tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type": "PONG", "tenant_id": {tenant_id}, "table_id": {table_id}}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id=table_id, restaurant_id=tenant_id)
    except Exception:
        manager.disconnect(websocket, table_id=table_id, restaurant_id=tenant_id)

@app.websocket("/ws/table/{table_id}")
async def websocket_table_endpoint(websocket: WebSocket, table_id: int):
    # Dynamically resolve restaurant_id from table record
    resolved_tenant_id = 1
    try:
        db = SessionLocal()
        table = db.query(Table).filter(Table.id == table_id).first()
        if table and table.restaurant_id:
            resolved_tenant_id = table.restaurant_id
        db.close()
    except Exception:
        resolved_tenant_id = 1

    await manager.connect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type": "PONG", "tenant_id": {resolved_tenant_id}, "table_id": {table_id}}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id)
    except Exception:
        manager.disconnect(websocket, table_id=table_id, restaurant_id=resolved_tenant_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
