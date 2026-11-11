from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=True, index=True)
    
    customer_name = Column(String(100), default="Dining Guest")
    customer_phone = Column(String(50), nullable=True)
    
    # Core multi-attribute ratings (1 to 5)
    overall_rating = Column(Integer, nullable=False, default=5)
    food_rating = Column(Integer, nullable=True, default=5)
    service_rating = Column(Integer, nullable=True, default=5)
    ambience_rating = Column(Integer, nullable=True, default=5)
    cleanliness_rating = Column(Integer, nullable=True, default=5)
    
    # Written feedback
    comment = Column(Text, nullable=True)
    
    # Moderation, Verification & Anti-Spam
    status = Column(String(50), default="APPROVED", index=True)  # APPROVED, FLAGGED, REJECTED, PENDING
    is_published = Column(Boolean, default=True, index=True)
    is_verified_dining = Column(Boolean, default=True)  # True if linked to a completed & paid order
    flag_reason = Column(Text, nullable=True)
    moderated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    restaurant = relationship("Restaurant", back_populates="feedbacks")
    order = relationship("Order", back_populates="feedback")
    dish_ratings = relationship("FeedbackDishRating", back_populates="feedback", cascade="all, delete-orphan")
    photos = relationship("FeedbackPhoto", back_populates="feedback", cascade="all, delete-orphan")


class FeedbackDishRating(Base):
    __tablename__ = "feedback_dish_ratings"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(Integer, ForeignKey("feedbacks.id"), nullable=False, index=True)
    menu_item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=True, index=True)
    dish_name = Column(String(150), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 to 5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feedback = relationship("Feedback", back_populates="dish_ratings")
    menu_item = relationship("MenuItem")


class FeedbackPhoto(Base):
    __tablename__ = "feedback_photos"

    id = Column(Integer, primary_key=True, index=True)
    feedback_id = Column(Integer, ForeignKey("feedbacks.id"), nullable=False, index=True)
    photo_url = Column(String(500), nullable=False)
    file_size_bytes = Column(Integer, default=0)
    mime_type = Column(String(50), default="image/jpeg")
    moderation_status = Column(String(50), default="APPROVED")  # APPROVED, FLAGGED, REJECTED
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feedback = relationship("Feedback", back_populates="photos")
