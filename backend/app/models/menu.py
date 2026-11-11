from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), default="Utensils")  # Lucide icon name
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    restaurant = relationship("Restaurant", back_populates="menu_categories")
    items = relationship("MenuItem", back_populates="category", cascade="all, delete-orphan")

class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), default=1, index=True, nullable=False)
    category_id = Column(Integer, ForeignKey("menu_categories.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    is_veg = Column(Boolean, default=True)
    is_bestseller = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)
    preparation_time = Column(Integer, default=15)  # in minutes
    calories = Column(Integer, nullable=True)
    dietary_tags = Column(String(255), default="Gluten-Free,Organic")  # Comma-separated
    spice_level = Column(String(20), default="Medium")  # Mild, Medium, Hot, Extra Hot
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship("MenuCategory", back_populates="items")
    customization_groups = relationship("MenuCustomizationGroup", back_populates="item", cascade="all, delete-orphan")

class MenuCustomizationGroup(Base):
    __tablename__ = "menu_customization_groups"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("menu_items.id"), nullable=False, index=True)
    group_name = Column(String(100), nullable=False)  # e.g., "Add-ons", "Choice of Dip", "Spice Level"
    is_required = Column(Boolean, default=False)
    min_select = Column(Integer, default=0)
    max_select = Column(Integer, default=5)

    item = relationship("MenuItem", back_populates="customization_groups")
    options = relationship("MenuCustomizationOption", back_populates="group", cascade="all, delete-orphan")

class MenuCustomizationOption(Base):
    __tablename__ = "menu_customization_options"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("menu_customization_groups.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    additional_price = Column(Float, default=0.0)
    is_default = Column(Boolean, default=False)

    group = relationship("MenuCustomizationGroup", back_populates="options")
