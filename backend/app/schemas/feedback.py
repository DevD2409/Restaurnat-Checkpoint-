from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class DishRatingCreate(BaseModel):
    menu_item_id: Optional[int] = None
    dish_name: str
    rating: int = Field(5, ge=1, le=5)
    comment: Optional[str] = None

class DishRatingResponse(BaseModel):
    id: int
    menu_item_id: Optional[int] = None
    dish_name: str
    rating: int
    comment: Optional[str] = None

    class Config:
        from_attributes = True

class PhotoResponse(BaseModel):
    id: int
    photo_url: str
    file_size_bytes: int
    mime_type: str
    moderation_status: str

    class Config:
        from_attributes = True

class FeedbackCreate(BaseModel):
    restaurant_id: Optional[int] = None
    restaurant_slug: Optional[str] = None
    order_id: Optional[int] = None  # Optional for general feedback, required for verified dining reviews
    table_id: Optional[int] = None
    customer_name: Optional[str] = "Dining Guest"
    customer_phone: Optional[str] = None
    
    # Core multi-attribute ratings (1 to 5)
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    food_rating: Optional[int] = Field(5, ge=1, le=5)
    service_rating: Optional[int] = Field(5, ge=1, le=5)
    ambience_rating: Optional[int] = Field(5, ge=1, le=5)
    cleanliness_rating: Optional[int] = Field(5, ge=1, le=5)
    
    # Backwards compatibility fields
    rating: Optional[int] = Field(None, ge=1, le=5)
    ambiance_rating: Optional[int] = Field(None, ge=1, le=5)
    comments: Optional[str] = None
    comment: Optional[str] = None
    
    # Dish ratings & photos
    dish_ratings: Optional[List[DishRatingCreate]] = []
    photo_urls: Optional[List[str]] = []
    
    allow_edit_if_exists: Optional[bool] = False

class FeedbackResponse(BaseModel):
    id: int
    restaurant_id: int
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    table_id: Optional[int] = None
    customer_name: str
    customer_phone: Optional[str] = None
    overall_rating: int
    rating: int  # alias
    food_rating: Optional[int] = None
    service_rating: Optional[int] = None
    ambience_rating: Optional[int] = None
    cleanliness_rating: Optional[int] = None
    comment: Optional[str] = None
    comments: Optional[str] = None
    status: str = "APPROVED"
    is_published: bool = True
    is_verified_dining: bool = True
    flag_reason: Optional[str] = None
    dish_ratings: List[DishRatingResponse] = []
    photos: List[PhotoResponse] = []
    google_review_url: Optional[str] = None
    google_review_notice: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True

class FeedbackModerateRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|FLAGGED|REJECTED)$")
    flag_reason: Optional[str] = None
    is_published: Optional[bool] = None

class FeedbackReportRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)

class DishRatingAnalytics(BaseModel):
    menu_item_id: Optional[int] = None
    dish_name: str
    average_rating: float
    review_count: int
    positive_percentage: float

class ReviewTrendPoint(BaseModel):
    date: str
    average_rating: float
    review_count: int

class FeedbackAnalyticsResponse(BaseModel):
    restaurant_id: int
    restaurant_name: str
    total_reviews: int
    verified_dining_percentage: float
    average_overall: float
    average_food: float
    average_service: float
    average_ambience: float
    average_cleanliness: float
    rating_breakdown: Dict[str, int]
    dish_ratings: List[DishRatingAnalytics]
    top_rated_dishes: List[DishRatingAnalytics]
    low_rated_dishes: List[DishRatingAnalytics]
    review_trends: List[ReviewTrendPoint]
    google_review_url: Optional[str] = None
    allow_feedback_edits: bool = False
    moderation_counts: Dict[str, int]
