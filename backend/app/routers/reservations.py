from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import (
    STAFF_ROLES as CENTRAL_STAFF_ROLES,
    require_roles,
    resolve_explicit_tenant_id,
)
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.reservation import Reservation, ReservationStatus
from app.models.table import Table, TableStatus
from app.schemas.reservation import (
    ReservationCreate, ReservationStatusUpdate, ReservationResponse
)
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/reservations", tags=["Table Reservations"])

@router.post("/", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    res_data: ReservationCreate,
    db: Session = Depends(get_db)
):
    target_id = res_data.restaurant_id or 1
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id, Restaurant.is_active == True).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    if res_data.table_id:
        table = db.query(Table).filter(Table.id == res_data.table_id, Table.is_active == True).first()
        if not table:
            raise HTTPException(status_code=400, detail="Invalid table_id")
        if table.restaurant_id != target_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant table reference is not permitted",
            )
        conflict = db.query(Reservation).filter(
            Reservation.table_id == res_data.table_id,
            Reservation.restaurant_id == target_id,
            Reservation.reservation_date == res_data.reservation_date,
            Reservation.reservation_time == res_data.reservation_time,
            Reservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.PENDING])
        ).first()
        if conflict:
            raise HTTPException(
                status_code=400,
                detail="Selected table is already booked for this date and time slot"
            )

    reservation = Reservation(
        restaurant_id=target_id,
        customer_name=res_data.customer_name,
        customer_email=res_data.customer_email,
        customer_phone=res_data.customer_phone,
        guest_count=res_data.guest_count,
        reservation_date=res_data.reservation_date,
        reservation_time=res_data.reservation_time,
        table_id=res_data.table_id,
        status=ReservationStatus.PENDING,
        special_requests=res_data.special_requests
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    await manager.broadcast_event("RESERVATION_CREATED", {
        "id": reservation.id,
        "restaurant_id": reservation.restaurant_id,
        "customer_name": reservation.customer_name,
        "date": reservation.reservation_date,
        "time": reservation.reservation_time,
        "guest_count": reservation.guest_count
    }, restaurant_id=reservation.restaurant_id)

    return reservation

@router.get("/", response_model=List[ReservationResponse])
def get_reservations(
    date_filter: Optional[str] = Query(None, alias="date"),
    status_filter: Optional[ReservationStatus] = Query(None, alias="status"),
    restaurant_id: Optional[int] = Query(None),
    current_user: User = Depends(require_roles(CENTRAL_STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    query = db.query(Reservation).options(joinedload(Reservation.table))

    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)
    query = query.filter(Reservation.restaurant_id == target_id)

    if date_filter:
        query = query.filter(Reservation.reservation_date == date_filter)
    if status_filter:
        query = query.filter(Reservation.status == status_filter)

    reservations = query.order_by(Reservation.reservation_date.asc(), Reservation.reservation_time.asc()).all()
    results = []
    for r in reservations:
        r_dict = {
            "id": r.id,
            "restaurant_id": r.restaurant_id,
            "customer_name": r.customer_name,
            "customer_email": r.customer_email,
            "customer_phone": r.customer_phone,
            "guest_count": r.guest_count,
            "reservation_date": r.reservation_date,
            "reservation_time": r.reservation_time,
            "table_id": r.table_id,
            "table_number": r.table.table_number if r.table else None,
            "status": r.status,
            "special_requests": r.special_requests,
            "created_at": r.created_at
        }
        results.append(ReservationResponse(**r_dict))
    return results

@router.patch("/{res_id}/status", response_model=ReservationResponse)
async def update_reservation_status(
    res_id: int,
    status_update: ReservationStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CENTRAL_STAFF_ROLES))
):
    reservation = db.query(Reservation).options(joinedload(Reservation.table)).filter(Reservation.id == res_id).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    resolve_explicit_tenant_id(current_user, reservation.restaurant_id)

    reservation.status = status_update.status
    if status_update.table_id is not None:
        table = db.query(Table).filter(Table.id == status_update.table_id, Table.is_active == True).first()
        if not table:
            raise HTTPException(status_code=400, detail="Invalid table_id")
        if table.restaurant_id != reservation.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Cannot assign a table belonging to another restaurant",
            )
        reservation.table_id = status_update.table_id
        if status_update.status == ReservationStatus.CONFIRMED:
            table.status = TableStatus.RESERVED

    if status_update.special_requests is not None:
        reservation.special_requests = status_update.special_requests

    db.commit()
    db.refresh(reservation)

    return ReservationResponse(
        id=reservation.id,
        restaurant_id=reservation.restaurant_id,
        customer_name=reservation.customer_name,
        customer_email=reservation.customer_email,
        customer_phone=reservation.customer_phone,
        guest_count=reservation.guest_count,
        reservation_date=reservation.reservation_date,
        reservation_time=reservation.reservation_time,
        table_id=reservation.table_id,
        table_number=reservation.table.table_number if reservation.table else None,
        status=reservation.status,
        special_requests=reservation.special_requests,
        created_at=reservation.created_at
    )
