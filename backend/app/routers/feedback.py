from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.models.user import User, UserRole
from app.models.feedback import Feedback
from app.models.restaurant import Restaurant

router = APIRouter(prefix="/feedback", tags=["Customer Feedback & Reviews"])

class FeedbackCreate(BaseModel):
    restaurant_id: Optional[int] = None
    restaurant_slug: Optional[str] = None
    order_id: Optional[int] = None
    table_id: Optional[int] = None
    customer_name: Optional[str] = "Dining Guest"
    customer_phone: Optional[str] = None
    rating: Optional[int] = Field(None, ge=1, le=5)
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    food_rating: Optional[int] = Field(5, ge=1, le=5)
    service_rating: Optional[int] = Field(5, ge=1, le=5)
    ambience_rating: Optional[int] = Field(5, ge=1, le=5)
    ambiance_rating: Optional[int] = Field(5, ge=1, le=5)
    cleanliness_rating: Optional[int] = Field(5, ge=1, le=5)
    comments: Optional[str] = None
    comment: Optional[str] = None

class FeedbackResponse(BaseModel):
    id: int
    restaurant_id: int
    order_id: Optional[int] = None
    table_id: Optional[int] = None
    customer_name: str
    overall_rating: int
    rating: int
    food_rating: Optional[int] = None
    service_rating: Optional[int] = None
    ambience_rating: Optional[int] = None
    cleanliness_rating: Optional[int] = None
    comment: Optional[str] = None
    comments: Optional[str] = None
    is_published: bool = True
    created_at: str

@router.post("/", status_code=status.HTTP_201_CREATED)
def submit_feedback(data: FeedbackCreate, db: Session = Depends(get_db)):
    """Customer submits feedback & star rating for their table/order."""
    target_restaurant_id = data.restaurant_id
    if not target_restaurant_id and data.restaurant_slug:
        r = db.query(Restaurant).filter(Restaurant.slug == data.restaurant_slug).first()
        if r:
            target_restaurant_id = r.id
    if not target_restaurant_id:
        target_restaurant_id = 1

    final_rating = data.overall_rating or data.rating or 5
    final_ambience = data.ambience_rating or data.ambiance_rating or 5
    final_comment = data.comment or data.comments or ""

    feedback = Feedback(
        restaurant_id=target_restaurant_id,
        order_id=data.order_id,
        table_id=data.table_id,
        customer_name=data.customer_name or "Dining Guest",
        overall_rating=final_rating,
        food_rating=data.food_rating or 5,
        service_rating=data.service_rating or 5,
        ambience_rating=final_ambience,
        cleanliness_rating=data.cleanliness_rating or 5,
        comment=final_comment,
        is_published=True
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return {
        "message": "Thank you for your valuable feedback!",
        "id": feedback.id,
        "restaurant_id": feedback.restaurant_id,
        "overall_rating": feedback.overall_rating,
        "rating": feedback.overall_rating,
        "customer_name": feedback.customer_name,
        "comment": feedback.comment
    }

@router.get("/restaurant/{restaurant_id}", response_model=List[FeedbackResponse])
def get_restaurant_public_feedbacks(restaurant_id: int, db: Session = Depends(get_db)):
    """Public customer reviews for a given restaurant."""
    feedbacks = db.query(Feedback).filter(
        Feedback.restaurant_id == restaurant_id,
        Feedback.is_published == True
    ).order_by(Feedback.created_at.desc()).limit(50).all()

    return [
        FeedbackResponse(
            id=f.id,
            restaurant_id=f.restaurant_id,
            order_id=f.order_id,
            table_id=f.table_id,
            customer_name=f.customer_name,
            overall_rating=f.overall_rating,
            rating=f.overall_rating,
            food_rating=f.food_rating,
            service_rating=f.service_rating,
            ambience_rating=f.ambience_rating,
            cleanliness_rating=f.cleanliness_rating,
            comment=f.comment,
            comments=f.comment,
            is_published=f.is_published,
            created_at=f.created_at.isoformat() if f.created_at else ""
        )
        for f in feedbacks
    ]

@router.get("/", response_model=List[FeedbackResponse])
def list_feedback(
    restaurant_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """Staff/Owner reviews customer feedback strictly scoped to their restaurant."""
    query = db.query(Feedback)
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN:
        query = query.filter(Feedback.restaurant_id == current_user.restaurant_id)
    elif restaurant_id is not None:
        query = query.filter(Feedback.restaurant_id == restaurant_id)

    feedbacks = query.order_by(Feedback.created_at.desc()).limit(100).all()
    return [
        FeedbackResponse(
            id=f.id,
            restaurant_id=f.restaurant_id,
            order_id=f.order_id,
            table_id=f.table_id,
            customer_name=f.customer_name,
            overall_rating=f.overall_rating,
            rating=f.overall_rating,
            food_rating=f.food_rating,
            service_rating=f.service_rating,
            ambience_rating=f.ambience_rating,
            cleanliness_rating=f.cleanliness_rating,
            comment=f.comment,
            comments=f.comment,
            is_published=f.is_published,
            created_at=f.created_at.isoformat() if f.created_at else ""
        )
        for f in feedbacks
    ]
