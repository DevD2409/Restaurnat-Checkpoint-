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
    overall_rating = Column(Integer, nullable=False, default=5)
    food_rating = Column(Integer, nullable=True, default=5)
    service_rating = Column(Integer, nullable=True, default=5)
    ambience_rating = Column(Integer, nullable=True, default=5)
    cleanliness_rating = Column(Integer, nullable=True, default=5)
    comment = Column(Text, nullable=True)
    is_published = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="feedbacks")
