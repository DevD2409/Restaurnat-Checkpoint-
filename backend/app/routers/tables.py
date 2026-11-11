import io
import base64
import uuid
from typing import List, Optional
from datetime import datetime, timezone
import qrcode
from fastapi import APIRouter, Depends, HTTPException, status, Response, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import generate_table_qr_token, verify_table_qr_token, decode_access_token
from app.core.dependencies import require_roles, oauth2_scheme
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession, TableStatus
from app.models.order import Order, OrderStatus
from app.models.billing import Bill, BillStatus
from app.schemas.table import (
    TableCreate, TableUpdate, TableResponse, TableSessionCreate,
    TableSessionResponse, QRValidationRequest, QRValidationResponse
)
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/tables", tags=["Tables & Floor Management"])

STAFF_ROLES = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER,
    UserRole.WAITER,
    UserRole.CASHIER
]

@router.get("/", response_model=List[TableResponse])
def get_tables(
    restaurant_id: Optional[int] = Query(None),
    slug: Optional[str] = Query(None),
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    target_id = restaurant_id
    if slug:
        r = db.query(Restaurant).filter(Restaurant.slug == slug).first()
        if r:
            target_id = r.id
    elif token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            user = db.query(User).filter(User.id == int(payload["sub"])).first()
            if user and user.role != UserRole.PLATFORM_SUPER_ADMIN and user.restaurant_id:
                target_id = user.restaurant_id

    query = db.query(Table).filter(Table.is_active == True)
    if target_id is not None:
        query = query.filter(Table.restaurant_id == target_id)
    else:
        query = query.filter(Table.restaurant_id == 1)

    tables = query.order_by(Table.table_number.asc()).all()
    results = []
    for t in tables:
        active_session = db.query(TableSession).filter(
            TableSession.table_id == t.id,
            TableSession.is_active == True
        ).first()

        active_order = db.query(Order).filter(
            Order.table_id == t.id,
            Order.status.in_([OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.SERVED])
        ).order_by(Order.created_at.desc(), Order.id.desc()).first()

        active_bill = None
        if active_order:
            active_bill = db.query(Bill).filter(
                Bill.order_id == active_order.id,
                Bill.status != BillStatus.PAID
            ).first()

        t_dict = {
            "id": t.id,
            "restaurant_id": t.restaurant_id,
            "table_number": t.table_number,
            "capacity": t.capacity,
            "section": t.section,
            "status": t.status,
            "pos_x": t.pos_x,
            "pos_y": t.pos_y,
            "qr_token": t.qr_token,
            "current_session_id": active_session.id if active_session else None,
            "is_active": t.is_active,
            "active_order_id": active_order.id if active_order else None,
            "active_bill_amount": active_bill.final_amount if active_bill else (active_order.total_amount if active_order else None),
            "session_start_time": active_session.started_at if active_session else None
        }
        results.append(TableResponse(**t_dict))
    return results

@router.post("/", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(
    table_data: TableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    target_id = current_user.restaurant_id
    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN and table_data.restaurant_id:
        target_id = table_data.restaurant_id
    if not target_id:
        target_id = 1

    existing = db.query(Table).filter(
        Table.restaurant_id == target_id,
        Table.table_number == table_data.table_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Table number '{table_data.table_number}' already exists in this restaurant")

    new_table = Table(
        restaurant_id=target_id,
        table_number=table_data.table_number,
        service_type=getattr(table_data, "service_type", "TABLE"),
        capacity=table_data.capacity,
        section=table_data.section,
        status=table_data.status,
        pos_x=table_data.pos_x,
        pos_y=table_data.pos_y,
        is_active=True
    )
    db.add(new_table)
    db.commit()
    db.refresh(new_table)

    # Generate tamper-proof signed QR token scoped to restaurant_id
    token = generate_table_qr_token(new_table.restaurant_id, new_table.id, new_table.table_number)
    new_table.qr_token = token
    db.commit()
    db.refresh(new_table)

    await manager.broadcast_event("TABLE_CREATED", {
        "table_id": new_table.id,
        "table_number": new_table.table_number,
        "restaurant_id": new_table.restaurant_id,
        "status": new_table.status.value
    }, restaurant_id=new_table.restaurant_id)

    return TableResponse(
        id=new_table.id,
        restaurant_id=new_table.restaurant_id,
        table_number=new_table.table_number,
        capacity=new_table.capacity,
        section=new_table.section,
        status=new_table.status,
        pos_x=new_table.pos_x,
        pos_y=new_table.pos_y,
        qr_token=new_table.qr_token,
        is_active=new_table.is_active
    )

@router.put("/{table_id}", response_model=TableResponse)
async def update_table(
    table_id: int,
    table_update: TableUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES))
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot modify table of another restaurant"
        )

    update_dict = table_update.model_dump(exclude_unset=True)
    status_changed = False
    if "status" in update_dict and update_dict["status"] != table.status:
        status_changed = True

    for field, value in update_dict.items():
        setattr(table, field, value)

    db.commit()
    db.refresh(table)

    if status_changed:
        await manager.broadcast_event("TABLE_STATUS_CHANGED", {
            "table_id": table.id,
            "table_number": table.table_number,
            "restaurant_id": table.restaurant_id,
            "status": table.status.value
        }, restaurant_id=table.restaurant_id)

    return TableResponse(
        id=table.id,
        restaurant_id=table.restaurant_id,
        table_number=table.table_number,
        capacity=table.capacity,
        section=table.section,
        status=table.status,
        pos_x=table.pos_x,
        pos_y=table.pos_y,
        qr_token=table.qr_token,
        is_active=table.is_active
    )

@router.post("/validate-qr", response_model=QRValidationResponse)
def validate_qr_token(req: QRValidationRequest, db: Session = Depends(get_db)):
    verification = verify_table_qr_token(req.qr_token)
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid, expired or tampered QR code token"
        )
    
    table = db.query(Table).filter(
        Table.id == verification["table_id"],
        Table.restaurant_id == verification["restaurant_id"],
        Table.is_active == True
    ).first()

    if not table:
        raise HTTPException(status_code=404, detail="Assigned table not found")

    active_session = db.query(TableSession).filter(
        TableSession.table_id == table.id,
        TableSession.is_active == True
    ).first()

    if table.status in [TableStatus.AVAILABLE, TableStatus.CLEANING] and active_session:
        active_session.is_active = False
        active_session.ended_at = datetime.now(timezone.utc)
        active_session = None

    if not active_session:
        session_token = f"sess_{uuid.uuid4().hex}"
        active_session = TableSession(
            table_id=table.id,
            customer_name="Guest",
            guest_count=2,
            session_token=session_token,
            is_active=True
        )
        db.add(active_session)
        table.status = TableStatus.OCCUPIED
        table.current_session_id = active_session.id
        db.commit()
        db.refresh(active_session)

    return QRValidationResponse(
        valid=True,
        table_id=table.id,
        table_number=table.table_number,
        restaurant_id=table.restaurant_id,
        session_token=active_session.session_token,
        message=f"Welcome to Table {table.table_number}!"
    )

@router.post("/{table_id}/session", response_model=TableSessionResponse)
async def create_table_session(
    table_id: int,
    session_data: TableSessionCreate,
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    session_token = f"sess_{uuid.uuid4().hex}"
    session = TableSession(
        table_id=table.id,
        customer_name=session_data.customer_name,
        customer_phone=session_data.customer_phone,
        guest_count=session_data.guest_count,
        session_token=session_token,
        is_active=True
    )
    db.add(session)
    table.status = TableStatus.OCCUPIED
    db.commit()
    db.refresh(session)
    table.current_session_id = session.id
    db.commit()

    await manager.broadcast_event("TABLE_OCCUPIED", {
        "table_id": table.id,
        "table_number": table.table_number,
        "restaurant_id": table.restaurant_id,
        "customer_name": session.customer_name
    }, restaurant_id=table.restaurant_id)

    return TableSessionResponse(
        id=session.id,
        table_id=session.table_id,
        customer_name=session.customer_name,
        customer_phone=session.customer_phone,
        guest_count=session.guest_count,
        session_token=session.session_token,
        is_active=session.is_active,
        started_at=session.started_at,
        table_number=table.table_number
    )

@router.post("/{table_id}/session/end")
async def end_table_session(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(STAFF_ROLES))
):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and table.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot end table session of another restaurant"
        )

    active_sessions = db.query(TableSession).filter(
        TableSession.table_id == table_id,
        TableSession.is_active == True
    ).all()

    for s in active_sessions:
        s.is_active = False
        s.ended_at = datetime.now(timezone.utc)

    table.status = TableStatus.AVAILABLE
    table.current_session_id = None
    db.commit()

    await manager.broadcast_event("TABLE_FREED", {
        "table_id": table.id,
        "table_number": table.table_number,
        "restaurant_id": table.restaurant_id,
        "status": "Available"
    }, restaurant_id=table.restaurant_id)

    return {"message": f"Table {table.table_number} session ended. Table is now available."}

@router.get("/{table_id}/qr-code-image")
def get_table_qr_image(table_id: int, db: Session = Depends(get_db)):
    table = db.query(Table).filter(Table.id == table_id).first()
    if not table or not table.qr_token:
        raise HTTPException(status_code=404, detail="Table or QR token not found")

    qr_data = f"/table/{table.qr_token}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")
