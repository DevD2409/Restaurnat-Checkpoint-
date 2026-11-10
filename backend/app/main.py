from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.core.security import decode_access_token
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
    description="Unified API backend powering Customer App, Kitchen Display System (KDS), Staff Portal, and Restaurant Administration Dashboard.",
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

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

# WebSockets
PRIVILEGED_CHANNELS = {
    "admin": ["ADMIN", "MANAGER"],
    "kitchen": ["ADMIN", "MANAGER", "KITCHEN", "CHEF"],
    "staff": ["ADMIN", "MANAGER", "WAITER", "CASHIER"]
}

@app.websocket("/ws/{channel}")
async def websocket_channel_endpoint(
    websocket: WebSocket,
    channel: str,
    token: Optional[str] = Query(None)
):
    if channel in PRIVILEGED_CHANNELS:
        allowed_roles = PRIVILEGED_CHANNELS[channel]
        if token:
            payload = decode_access_token(token)
            if not payload or payload.get("role") not in allowed_roles:
                await websocket.close(code=1008)  # Policy violation
                return
        elif settings.ENVIRONMENT == "production":
            await websocket.close(code=1008)  # Policy violation
            return

    await manager.connect(websocket, channel=channel)
    try:
        while True:
            data = await websocket.receive_text()
            # Can handle incoming client messages or pings
            await websocket.send_text(f'{{"type": "PONG", "channel": "{channel}"}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel=channel)
    except Exception:
        manager.disconnect(websocket, channel=channel)

@app.websocket("/ws/table/{table_id}")
async def websocket_table_endpoint(websocket: WebSocket, table_id: int):
    await manager.connect(websocket, table_id=table_id)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f'{{"type": "PONG", "table_id": {table_id}}}')
    except WebSocketDisconnect:
        manager.disconnect(websocket, table_id=table_id)
    except Exception:
        manager.disconnect(websocket, table_id=table_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

