import os
import uuid
import re
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user, resolve_explicit_tenant_id
from app.models.user import User, UserRole
from app.models.feedback import Feedback, FeedbackDishRating, FeedbackPhoto
from app.models.restaurant import Restaurant
from app.models.order import Order, OrderStatus, PaymentStatus
from app.services.storage_service import storage_service
from app.schemas.feedback import (
    FeedbackCreate, FeedbackResponse, DishRatingResponse, PhotoResponse,
    FeedbackModerateRequest, FeedbackReportRequest, FeedbackAnalyticsResponse,
    DishRatingAnalytics, ReviewTrendPoint
)

router = APIRouter(prefix="/feedback", tags=["Customer Feedback & Reviews"])

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "uploads", "feedback")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Helper: Anti-Spam & Content Moderation Heuristics
SUSPICIOUS_SPAM_PATTERNS = [
    r"https?://(?!g\.page|maps\.google|google\.com)[^\s]+",  # External non-Google affiliate/phishing URLs
    r"(buy\s+now|cheap\s+crypto|casino|viagra|free\s+followers|whatsapp\s+\+\d+)",
    r"(.)\1{9,}",  # 10 or more identical repeating characters e.g. "aaaaaaaaaa"
]

def check_anti_spam(comment: Optional[str]) -> Tuple[bool, Optional[str]]:
    """
    Checks text for malicious spam, external scam links, or spam patterns.
    Note: Genuine critical or negative reviews (e.g., 1-star complaints) are NEVER marked as spam.
    """
    if not comment or not comment.strip():
        return False, None

    clean_text = comment.strip()
    for pattern in SUSPICIOUS_SPAM_PATTERNS:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return True, "Flagged by automated anti-spam heuristic: suspicious promotional content or characters detected"

    return False, None

# Helper: Build FeedbackResponse schema
def format_feedback_response(fb: Feedback, google_url: Optional[str] = None) -> FeedbackResponse:
    order_num = fb.order.order_number if fb.order else None
    dish_list = [
        DishRatingResponse(
            id=d.id,
            menu_item_id=d.menu_item_id,
            dish_name=d.dish_name,
            rating=d.rating,
            comment=d.comment
        )
        for d in (fb.dish_ratings or [])
    ]
    photo_list = [
        PhotoResponse(
            id=p.id,
            photo_url=p.photo_url,
            file_size_bytes=p.file_size_bytes,
            mime_type=p.mime_type,
            moderation_status=p.moderation_status
        )
        for d_photo in (fb.photos or [])
        for p in [d_photo]
    ]

    effective_google_url = google_url or (fb.restaurant.google_review_url if fb.restaurant else None)

    return FeedbackResponse(
        id=fb.id,
        restaurant_id=fb.restaurant_id,
        order_id=fb.order_id,
        order_number=order_num,
        table_id=fb.table_id,
        customer_name=fb.customer_name or "Dining Guest",
        customer_phone=fb.customer_phone,
        overall_rating=fb.overall_rating,
        rating=fb.overall_rating,
        food_rating=fb.food_rating,
        service_rating=fb.service_rating,
        ambience_rating=fb.ambience_rating,
        cleanliness_rating=fb.cleanliness_rating,
        comment=fb.comment,
        comments=fb.comment,
        status=fb.status or "APPROVED",
        is_published=bool(fb.is_published),
        is_verified_dining=bool(fb.is_verified_dining),
        flag_reason=fb.flag_reason,
        dish_ratings=dish_list,
        photos=photo_list,
        google_review_url=effective_google_url,
        google_review_notice="Google reviews are completely voluntary and submitted independently by you on Google. SRMP never automatically posts reviews to Google Maps.",
        created_at=fb.created_at.isoformat() if fb.created_at else "",
        updated_at=fb.updated_at.isoformat() if fb.updated_at else None
    )

# 1. Submit Customer Feedback
@router.post("/", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(data: FeedbackCreate, db: Session = Depends(get_db)):
    """
    Submits customer ratings for individual dishes, food quality, service quality,
    cleanliness & ambience, and overall experience.
    Enforces completed & paid order eligibility and duplicate submission prevention.
    """
    # 1. Resolve and validate Order (if provided for verified review)
    target_restaurant_id = data.restaurant_id
    order = None
    is_verified_dining = False

    if data.order_id:
        order = db.query(Order).filter(Order.id == data.order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

        target_restaurant_id = order.restaurant_id
        if data.restaurant_id and data.restaurant_id != target_restaurant_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant mismatch: Order does not belong to the specified restaurant."
            )

        # 2. Enforce Order Eligibility: Must be COMPLETED or SERVED, and PAID
        order_status_val = order.status.value if hasattr(order.status, "value") else str(order.status)
        payment_status_val = order.payment_status.value if hasattr(order.payment_status, "value") else str(order.payment_status)

        if order_status_val not in ["COMPLETED", "SERVED"] or payment_status_val != "PAID":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback can only be submitted after an order has been completed and paid."
            )

        is_verified_dining = True

    # Resolve fallback restaurant by slug or default; reject unknown slug with 404
    if data.restaurant_slug is not None and data.restaurant_slug.strip():
        r = db.query(Restaurant).filter(
            Restaurant.slug == data.restaurant_slug.strip(),
            Restaurant.is_active == True,
        ).first()
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")
        if target_restaurant_id and target_restaurant_id != r.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant mismatch: restaurant_slug does not match target restaurant",
            )
        target_restaurant_id = r.id
    if not target_restaurant_id:
        target_restaurant_id = 1

    # 3. Resolve Restaurant Profile
    restaurant = db.query(Restaurant).filter(Restaurant.id == target_restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # 4. Check for Duplicate Submission on this Order (if order is provided)
    if order:
        existing = db.query(Feedback).filter(Feedback.order_id == order.id).first()
        if existing:
            # Check if edits are permitted
            allows_edit = restaurant.allow_feedback_edits or data.allow_edit_if_exists
            if not allows_edit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A rating has already been submitted for this order. Duplicate submissions are not permitted."
                )
            
            # Update existing feedback record
            final_rating = data.overall_rating or data.rating or existing.overall_rating
            final_ambience = data.ambience_rating or data.ambiance_rating or existing.ambience_rating
            final_comment = data.comment if data.comment is not None else (data.comments or existing.comment)

            existing.overall_rating = final_rating
            existing.food_rating = data.food_rating or existing.food_rating
            existing.service_rating = data.service_rating or existing.service_rating
            existing.ambience_rating = final_ambience
            existing.cleanliness_rating = data.cleanliness_rating or existing.cleanliness_rating
            existing.comment = final_comment
            existing.customer_name = data.customer_name or existing.customer_name
            existing.customer_phone = data.customer_phone or existing.customer_phone
            existing.updated_at = datetime.now(timezone.utc)

            # Clear previous dish ratings and replace with new ones
            db.query(FeedbackDishRating).filter(FeedbackDishRating.feedback_id == existing.id).delete()
            if data.dish_ratings:
                for dish_item in data.dish_ratings:
                    dr = FeedbackDishRating(
                        feedback_id=existing.id,
                        menu_item_id=dish_item.menu_item_id,
                        dish_name=dish_item.dish_name,
                        rating=dish_item.rating,
                        comment=dish_item.comment
                    )
                    db.add(dr)

            db.commit()
            db.refresh(existing)
            return format_feedback_response(existing, restaurant.google_review_url)

    # 5. Create New Feedback
    final_rating = data.overall_rating or data.rating or 5
    final_ambience = data.ambience_rating or data.ambiance_rating or 5
    final_comment = data.comment if data.comment is not None else (data.comments or "")

    # Run Anti-Spam Check
    is_spam, spam_reason = check_anti_spam(final_comment)
    feedback_status = "FLAGGED" if is_spam else "APPROVED"
    is_published = False if is_spam else True

    feedback = Feedback(
        restaurant_id=target_restaurant_id,
        order_id=order.id if order else None,
        table_id=data.table_id or (order.table_id if order else None),
        customer_name=data.customer_name or (order.customer_name if order else "Dining Guest"),
        customer_phone=data.customer_phone or (order.customer_phone if order else None),
        overall_rating=final_rating,
        food_rating=data.food_rating or 5,
        service_rating=data.service_rating or 5,
        ambience_rating=final_ambience,
        cleanliness_rating=data.cleanliness_rating or 5,
        comment=final_comment,
        status=feedback_status,
        is_published=is_published,
        is_verified_dining=is_verified_dining,
        flag_reason=spam_reason
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # 6. Add Individual Dish Ratings
    if data.dish_ratings:
        for dish_item in data.dish_ratings:
            dr = FeedbackDishRating(
                feedback_id=feedback.id,
                menu_item_id=dish_item.menu_item_id,
                dish_name=dish_item.dish_name,
                rating=dish_item.rating,
                comment=dish_item.comment
            )
            db.add(dr)

    # 7. Add Attached Photo URLs
    if data.photo_urls:
        for p_url in data.photo_urls:
            photo = FeedbackPhoto(
                feedback_id=feedback.id,
                photo_url=p_url,
                moderation_status="APPROVED" if not is_spam else "FLAGGED"
            )
            db.add(photo)

    db.commit()
    db.refresh(feedback)

    return format_feedback_response(feedback, restaurant.google_review_url)

# 2. Upload Review Photo Endpoint with strict file validation & persistent storage
@router.post("/upload-photo")
async def upload_review_photo(file: UploadFile = File(...)):
    """
    Secure customer photo upload for reviews.
    Validates MIME type, file extension, magic bytes, and enforces 5MB size limit.
    Stores photo either on persistent cloud object storage (S3/Cloudflare R2) or local storage.
    """
    return await storage_service.save_image(file, folder="feedback", prefix="review")

# 3. Public Reviews for a Given Restaurant
@router.get("/restaurant/{restaurant_id}", response_model=List[FeedbackResponse])
def get_restaurant_public_feedbacks(restaurant_id: int, db: Session = Depends(get_db)):
    """Public customer reviews for a given restaurant (only approved & published)."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    google_url = restaurant.google_review_url if restaurant else None

    feedbacks = db.query(Feedback).filter(
        Feedback.restaurant_id == restaurant_id,
        Feedback.is_published == True,
        Feedback.status == "APPROVED"
    ).order_by(Feedback.created_at.desc()).limit(50).all()

    return [format_feedback_response(f, google_url) for f in feedbacks]

# 4. Authenticated Staff/Owner Reviews List
@router.get("/", response_model=List[FeedbackResponse])
def list_feedback(
    restaurant_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    min_rating: Optional[int] = Query(None, ge=1, le=5),
    max_rating: Optional[int] = Query(None, ge=1, le=5),
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

    if status_filter:
        query = query.filter(Feedback.status == status_filter.upper())
    if min_rating:
        query = query.filter(Feedback.overall_rating >= min_rating)
    if max_rating:
        query = query.filter(Feedback.overall_rating <= max_rating)

    feedbacks = query.order_by(Feedback.created_at.desc()).limit(100).all()
    return [format_feedback_response(f) for f in feedbacks]

# 5. Restaurant Owner Feedback Analytics Dashboard
@router.get("/analytics", response_model=FeedbackAnalyticsResponse)
def get_feedback_analytics(
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
    """
    Computes comprehensive feedback analytics: overall average, multi-attribute scores,
    dish-level ratings, review distribution, trends, moderation stats, and Google review configuration.
    """
    target_id = resolve_explicit_tenant_id(current_user, restaurant_id)

    restaurant = db.query(Restaurant).filter(Restaurant.id == target_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    feedbacks = db.query(Feedback).filter(Feedback.restaurant_id == target_id).all()
    total_reviews = len(feedbacks)

    if total_reviews == 0:
        return FeedbackAnalyticsResponse(
            restaurant_id=restaurant.id,
            restaurant_name=restaurant.name,
            total_reviews=0,
            verified_dining_percentage=100.0,
            average_overall=5.0,
            average_food=5.0,
            average_service=5.0,
            average_ambience=5.0,
            average_cleanliness=5.0,
            rating_breakdown={"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
            dish_ratings=[],
            top_rated_dishes=[],
            low_rated_dishes=[],
            review_trends=[],
            google_review_url=restaurant.google_review_url,
            allow_feedback_edits=bool(restaurant.allow_feedback_edits),
            moderation_counts={"APPROVED": 0, "FLAGGED": 0, "REJECTED": 0}
        )

    # Multi-attribute averages
    avg_overall = sum(f.overall_rating for f in feedbacks) / total_reviews
    avg_food = sum(f.food_rating or 5 for f in feedbacks) / total_reviews
    avg_service = sum(f.service_rating or 5 for f in feedbacks) / total_reviews
    avg_ambience = sum(f.ambience_rating or 5 for f in feedbacks) / total_reviews
    avg_cleanliness = sum(f.cleanliness_rating or 5 for f in feedbacks) / total_reviews

    # Rating breakdown
    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for f in feedbacks:
        star_str = str(f.overall_rating)
        if star_str in breakdown:
            breakdown[star_str] += 1

    # Moderation counts
    mod_counts = {"APPROVED": 0, "FLAGGED": 0, "REJECTED": 0}
    for f in feedbacks:
        st = f.status or "APPROVED"
        mod_counts[st] = mod_counts.get(st, 0) + 1

    # Dish-level aggregation
    feedback_ids = [f.id for f in feedbacks]
    dish_ratings_raw = db.query(FeedbackDishRating).filter(
        FeedbackDishRating.feedback_id.in_(feedback_ids)
    ).all() if feedback_ids else []

    dish_map: Dict[str, Dict[str, Any]] = {}
    for dr in dish_ratings_raw:
        name = dr.dish_name
        if name not in dish_map:
            dish_map[name] = {
                "menu_item_id": dr.menu_item_id,
                "dish_name": name,
                "ratings": []
            }
        dish_map[name]["ratings"].append(dr.rating)

    dish_analytics_list: List[DishRatingAnalytics] = []
    for d_name, d_data in dish_map.items():
        ratings = d_data["ratings"]
        count = len(ratings)
        avg = sum(ratings) / count
        pos = (sum(1 for r in ratings if r >= 4) / count) * 100.0
        dish_analytics_list.append(
            DishRatingAnalytics(
                menu_item_id=d_data["menu_item_id"],
                dish_name=d_name,
                average_rating=round(avg, 2),
                review_count=count,
                positive_percentage=round(pos, 1)
            )
        )

    # Sort dish analytics
    dish_analytics_list.sort(key=lambda x: (x.average_rating, x.review_count), reverse=True)
    top_dishes = dish_analytics_list[:5]
    low_dishes = [d for d in dish_analytics_list if d.average_rating < 3.5]

    # Review Trends (past 30 days)
    trends_map: Dict[str, List[int]] = {}
    for f in feedbacks:
        if f.created_at:
            date_key = f.created_at.strftime("%Y-%m-%d")
            trends_map.setdefault(date_key, []).append(f.overall_rating)

    review_trends: List[ReviewTrendPoint] = []
    for d_str in sorted(trends_map.keys())[-30:]:
        ratings = trends_map[d_str]
        review_trends.append(
            ReviewTrendPoint(
                date=d_str,
                average_rating=round(sum(ratings) / len(ratings), 2),
                review_count=len(ratings)
            )
        )

    return FeedbackAnalyticsResponse(
        restaurant_id=restaurant.id,
        restaurant_name=restaurant.name,
        total_reviews=total_reviews,
        verified_dining_percentage=100.0,
        average_overall=round(avg_overall, 2),
        average_food=round(avg_food, 2),
        average_service=round(avg_service, 2),
        average_ambience=round(avg_ambience, 2),
        average_cleanliness=round(avg_cleanliness, 2),
        rating_breakdown=breakdown,
        dish_ratings=dish_analytics_list,
        top_rated_dishes=top_dishes,
        low_rated_dishes=low_dishes,
        review_trends=review_trends,
        google_review_url=restaurant.google_review_url,
        allow_feedback_edits=bool(restaurant.allow_feedback_edits),
        moderation_counts=mod_counts
    )

# 6. Moderate Review (Staff/Owner/Admin)
@router.patch("/{feedback_id}/moderate", response_model=FeedbackResponse)
def moderate_feedback(
    feedback_id: int,
    data: FeedbackModerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER
    ]))
):
    """Moderate a review: change status, flag reason, and publication state."""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    # Tenant boundary enforcement
    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and feedback.restaurant_id != current_user.restaurant_id:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot moderate feedback for another restaurant")

    feedback.status = data.status
    if data.flag_reason is not None:
        feedback.flag_reason = data.flag_reason
    if data.is_published is not None:
        feedback.is_published = data.is_published
    else:
        feedback.is_published = (data.status == "APPROVED")

    feedback.moderated_by_id = current_user.id
    feedback.moderated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(feedback)

    return format_feedback_response(feedback)

# 7. Report Review for Spam or Abuse
@router.post("/{feedback_id}/report")
def report_feedback(
    feedback_id: int,
    data: FeedbackReportRequest,
    db: Session = Depends(get_db)
):
    """Allows diners or staff to report an inappropriate or spam review for moderator review."""
    feedback = db.query(Feedback).filter(Feedback.id == feedback_id).first()
    if not feedback:
        raise HTTPException(status_code=404, detail="Feedback not found")

    feedback.status = "FLAGGED"
    feedback.flag_reason = f"Reported: {data.reason.strip()}"
    feedback.is_published = False
    db.commit()

    return {
        "message": "Feedback has been flagged and submitted for moderator inspection.",
        "feedback_id": feedback.id,
        "status": feedback.status
    }
