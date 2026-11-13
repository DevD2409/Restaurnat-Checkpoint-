from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class MenuCustomizationOptionSchema(BaseModel):
    id: Optional[int] = None
    name: str
    additional_price: float = 0.0
    is_default: bool = False

    class Config:
        from_attributes = True

class MenuCustomizationGroupSchema(BaseModel):
    id: Optional[int] = None
    group_name: str
    is_required: bool = False
    min_select: int = 0
    max_select: int = 5
    options: List[MenuCustomizationOptionSchema] = []

    class Config:
        from_attributes = True

class MenuItemBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    is_veg: bool = True
    is_bestseller: bool = False
    is_available: bool = True
    preparation_time: int = 15
    calories: Optional[int] = None
    dietary_tags: Optional[str] = "Gluten-Free,Organic"
    spice_level: Optional[str] = "Medium"
    image_url: Optional[str] = None

class MenuItemCreate(MenuItemBase):
    category_id: int
    customization_groups: Optional[List[MenuCustomizationGroupSchema]] = []

class MenuItemUpdate(BaseModel):
    category_id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_veg: Optional[bool] = None
    is_bestseller: Optional[bool] = None
    is_available: Optional[bool] = None
    preparation_time: Optional[int] = None
    calories: Optional[int] = None
    dietary_tags: Optional[str] = None
    spice_level: Optional[str] = None
    image_url: Optional[str] = None

class MenuItemResponse(MenuItemBase):
    id: int
    category_id: int
    created_at: Optional[datetime] = None
    customization_groups: List[MenuCustomizationGroupSchema] = []

    class Config:
        from_attributes = True

class MenuCategoryBase(BaseModel):
    name: str
    description: Optional[str] = None
    icon: str = "Utensils"
    display_order: int = 0
    is_active: bool = True

class MenuCategoryCreate(MenuCategoryBase):
    restaurant_id: Optional[int] = None

class MenuCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

class MenuCategoryResponse(MenuCategoryBase):
    id: int
    restaurant_id: int
    items: List[MenuItemResponse] = []

    class Config:
        from_attributes = True

