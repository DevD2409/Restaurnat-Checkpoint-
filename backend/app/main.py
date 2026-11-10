from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.core.security import decode_access_token
from app.models.table import Table
from app.utils.seed_data import seed_database
from app.websocket.connection_manager import manager

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
import os
from fastapi.staticfiles import StaticFiles
from app.routers.feedback import router as feedback_router
from app.routers.subscriptions import router as subscriptions_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist and seed default data
    Base.metadata.create_all(bind=engine)
    try:
        seed_database()
    except Exception as e:
        print(f"Seed note: {e}")
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
        "architecture": "Multi-Tenant Hospitality SaaS"
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
