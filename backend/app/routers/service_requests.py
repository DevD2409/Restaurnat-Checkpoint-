from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import (
    STAFF_ROLES,
    require_roles,
    resolve_explicit_tenant_id,
)
from app.models.service_request import ServiceRequest, ServiceRequestType, ServiceRequestStatus
from app.models.table import Table, TableStatus
from app.models.user import User, UserRole
from app.schemas.service_request import (
    ServiceRequestCreate, ServiceRequestStatusUpdate, ServiceRequestResponse
)
from app.websocket.connection_manager import manager

router = APIRouter(prefix="/service-requests", tags=["Call Waiter & Service Requests"])

@router.post("/", response_model=ServiceRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_service_request(
    req_data: ServiceRequestCreate,
    db: Session = Depends(get_db)
):
    table = db.query(Table).filter(Table.id == req_data.table_id, Table.is_active == True).first()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")

    target_restaurant_id = table.restaurant_id

    new_req = ServiceRequest(
        restaurant_id=target_restaurant_id,
        table_id=req_data.table_id,
        request_type=req_data.request_type,
        status=ServiceRequestStatus.PENDING,
        customer_notes=req_data.customer_notes
    )
    db.add(new_req)

    if req_data.request_type == ServiceRequestType.BILL:
        table.status = TableStatus.BILL_REQUESTED

    db.commit()
    db.refresh(new_req)

    await manager.broadcast_event(
        "SERVICE_REQUEST_CREATED",
        {
            "id": new_req.id,
            "table_id": new_req.table_id,
            "table_number": table.table_number,
            "restaurant_id": target_restaurant_id,
            "request_type": new_req.request_type.value,
            "customer_notes": new_req.customer_notes,
            "created_at": new_req.created_at.isoformat()
        },
        restaurant_id=target_restaurant_id
    )

    return ServiceRequestResponse(
        id=new_req.id,
        restaurant_id=new_req.restaurant_id,
        table_id=new_req.table_id,
        table_number=table.table_number,
        request_type=new_req.request_type,
        status=new_req.status,
        customer_notes=new_req.customer_notes,
        created_at=new_req.created_at
    )

@router.get("/", response_model=List[ServiceRequestResponse])
def get_service_requests(
    status_filter: Optional[ServiceRequestStatus] = Query(None, alias="status"),
    table_id: Optional[int] = None,
    restaurant_id: Optional[int] = Query(None),
    current_user: User = Depends(require_roles(STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    query = db.query(ServiceRequest).options(
        joinedload(ServiceRequest.table),
        joinedload(ServiceRequest.assigned_staff)
    )

    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)
    query = query.filter(ServiceRequest.restaurant_id == target_id)

    if status_filter:
        query = query.filter(ServiceRequest.status == status_filter)
    if table_id:
        query = query.filter(ServiceRequest.table_id == table_id)

    requests = query.order_by(ServiceRequest.created_at.desc()).all()
    results = []
    for r in requests:
        results.append(
            ServiceRequestResponse(
                id=r.id,
                restaurant_id=r.restaurant_id,
                table_id=r.table_id,
                table_number=r.table.table_number if r.table else None,
                request_type=r.request_type,
                status=r.status,
                customer_notes=r.customer_notes,
                staff_notes=r.staff_notes,
                assigned_staff_id=r.assigned_staff_id,
                assigned_staff_name=r.assigned_staff.full_name if r.assigned_staff else None,
                created_at=r.created_at,
                acknowledged_at=r.acknowledged_at,
                resolved_at=r.resolved_at
            )
        )
    return results

@router.patch("/{request_id}/status", response_model=ServiceRequestResponse)
async def update_service_request_status(
    request_id: int,
    status_update: ServiceRequestStatusUpdate,
    current_user: User = Depends(require_roles(STAFF_ROLES)),
    db: Session = Depends(get_db)
):
    req = db.query(ServiceRequest).options(
        joinedload(ServiceRequest.table),
        joinedload(ServiceRequest.assigned_staff)
    ).filter(ServiceRequest.id == request_id).first()

    if not req:
        raise HTTPException(status_code=404, detail="Service request not found")

    resolve_explicit_tenant_id(current_user, req.restaurant_id)

    req.status = status_update.status
    if status_update.staff_notes is not None:
        req.staff_notes = status_update.staff_notes
    if status_update.assigned_staff_id is not None:
        assignee = db.query(User).filter(User.id == status_update.assigned_staff_id).first()
        if not assignee or not assignee.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned staff user not found or inactive",
            )
        if assignee.role in (UserRole.PLATFORM_SUPER_ADMIN, UserRole.CUSTOMER):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned user must hold a restaurant staff role",
            )
        if assignee.restaurant_id != req.restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant assignment denied: assigned_staff_id belongs to another restaurant",
            )
        req.assigned_staff_id = assignee.id

    now = datetime.now(timezone.utc)
    if status_update.status == ServiceRequestStatus.ACKNOWLEDGED and not req.acknowledged_at:
        req.acknowledged_at = now
    elif status_update.status == ServiceRequestStatus.RESOLVED and not req.resolved_at:
        req.resolved_at = now

    db.commit()
    db.refresh(req)

    await manager.broadcast_event(
        "SERVICE_REQUEST_UPDATED",
        {
            "id": req.id,
            "table_id": req.table_id,
            "table_number": req.table.table_number if req.table else None,
            "restaurant_id": req.restaurant_id,
            "request_type": req.request_type.value,
            "status": req.status.value,
            "staff_notes": req.staff_notes,
            "assigned_staff_name": req.assigned_staff.full_name if req.assigned_staff else None
        },
        restaurant_id=req.restaurant_id
    )

    return ServiceRequestResponse(
        id=req.id,
        restaurant_id=req.restaurant_id,
        table_id=req.table_id,
        table_number=req.table.table_number if req.table else None,
        request_type=req.request_type,
        status=req.status,
        customer_notes=req.customer_notes,
        staff_notes=req.staff_notes,
        assigned_staff_id=req.assigned_staff_id,
        assigned_staff_name=req.assigned_staff.full_name if req.assigned_staff else None,
        created_at=req.created_at,
        acknowledged_at=req.acknowledged_at,
        resolved_at=req.resolved_at
    )
