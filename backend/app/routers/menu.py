from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.core.database import get_db
from app.core.dependencies import require_roles, get_current_user
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.menu import MenuCategory, MenuItem, MenuCustomizationGroup, MenuCustomizationOption
from app.schemas.menu import (
    MenuCategoryCreate, MenuCategoryUpdate, MenuCategoryResponse,
    MenuItemCreate, MenuItemUpdate, MenuItemResponse
)

router = APIRouter(prefix="/menu", tags=["Menu Management"])

MENU_MANAGERS = [
    UserRole.PLATFORM_SUPER_ADMIN,
    UserRole.RESTAURANT_OWNER,
    UserRole.ADMIN,
    UserRole.RESTAURANT_MANAGER,
    UserRole.MANAGER
]

@router.get("/categories", response_model=List[MenuCategoryResponse])
def get_categories(
    restaurant_id: Optional[int] = Query(None),
    slug: Optional[str] = Query(None),
    include_inactive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Returns menu categories and dishes for a specific restaurant tenant.
    Enforces tenant isolation by resolving restaurant_id or slug.
    """
    target_id = restaurant_id
    if slug:
        r = db.query(Restaurant).filter(Restaurant.slug == slug).first()
        if r:
            target_id = r.id
    
    query = db.query(MenuCategory).options(
        joinedload(MenuCategory.items).joinedload(MenuItem.customization_groups).joinedload(MenuCustomizationGroup.options)
    ).order_by(MenuCategory.display_order.asc())

    if target_id is not None:
        query = query.filter(MenuCategory.restaurant_id == target_id)
    else:
        # Default fallback to primary tenant
        query = query.filter(MenuCategory.restaurant_id == 1)

    if not include_inactive:
        query = query.filter(MenuCategory.is_active == True)

    categories = query.all()
    if not include_inactive:
        for cat in categories:
            cat.items = [item for item in cat.items if item.is_available]
    return categories

@router.post("/categories", response_model=MenuCategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    cat_data: MenuCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    target_restaurant_id = current_user.restaurant_id
    if current_user.role == UserRole.PLATFORM_SUPER_ADMIN and cat_data.restaurant_id:
        target_restaurant_id = cat_data.restaurant_id
    if not target_restaurant_id:
        target_restaurant_id = 1

    cat = MenuCategory(
        restaurant_id=target_restaurant_id,
        name=cat_data.name,
        description=cat_data.description,
        icon=cat_data.icon,
        display_order=cat_data.display_order,
        is_active=cat_data.is_active
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat

@router.put("/categories/{cat_id}", response_model=MenuCategoryResponse)
def update_category(
    cat_id: int,
    cat_data: MenuCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    cat = db.query(MenuCategory).filter(MenuCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and cat.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot modify category of another restaurant"
        )

    update_dict = cat_data.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(cat, k, v)

    db.commit()
    db.refresh(cat)
    return cat

@router.delete("/categories/{cat_id}")
def delete_category(
    cat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    cat = db.query(MenuCategory).filter(MenuCategory.id == cat_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and cat.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot delete category of another restaurant"
        )

    db.delete(cat)
    db.commit()
    return {"message": "Category deleted successfully"}

@router.get("/items", response_model=List[MenuItemResponse])
def get_items(
    restaurant_id: Optional[int] = None,
    category_id: Optional[int] = None,
    is_veg: Optional[bool] = None,
    search: Optional[str] = None,
    available_only: bool = True,
    db: Session = Depends(get_db)
):
    query = db.query(MenuItem).options(
        joinedload(MenuItem.customization_groups).joinedload(MenuCustomizationGroup.options)
    )

    if restaurant_id:
        query = query.filter(MenuItem.restaurant_id == restaurant_id)
    if category_id:
        query = query.filter(MenuItem.category_id == category_id)
    if is_veg is not None:
        query = query.filter(MenuItem.is_veg == is_veg)
    if available_only:
        query = query.filter(MenuItem.is_available == True)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (MenuItem.name.ilike(search_filter)) | (MenuItem.description.ilike(search_filter))
        )

    return query.order_by(MenuItem.name.asc()).all()

@router.get("/items/{item_id}", response_model=MenuItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(MenuItem).options(
        joinedload(MenuItem.customization_groups).joinedload(MenuCustomizationGroup.options)
    ).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Menu item not found")
    return item

@router.post("/items", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
def create_menu_item(
    item_data: MenuItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    category = db.query(MenuCategory).filter(MenuCategory.id == item_data.category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category_id")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and category.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot add items to another restaurant's category"
        )

    new_item = MenuItem(
        restaurant_id=category.restaurant_id,
        category_id=item_data.category_id,
        name=item_data.name,
        description=item_data.description,
        price=item_data.price,
        is_veg=item_data.is_veg,
        is_bestseller=item_data.is_bestseller,
        is_available=item_data.is_available,
        preparation_time=item_data.preparation_time,
        calories=item_data.calories,
        dietary_tags=item_data.dietary_tags,
        spice_level=item_data.spice_level,
        image_url=item_data.image_url
    )
    db.add(new_item)
    db.commit()
    db.refresh(new_item)

    if item_data.customization_groups:
        for grp in item_data.customization_groups:
            cgroup = MenuCustomizationGroup(
                item_id=new_item.id,
                group_name=grp.group_name,
                is_required=grp.is_required,
                min_select=grp.min_select,
                max_select=grp.max_select
            )
            db.add(cgroup)
            db.commit()
            db.refresh(cgroup)

            for opt in grp.options:
                copt = MenuCustomizationOption(
                    group_id=cgroup.id,
                    name=opt.name,
                    extra_price=opt.extra_price if hasattr(opt, 'extra_price') else getattr(opt, 'additional_price', 0.0),
                    is_default=opt.is_default
                )
                db.add(copt)
            db.commit()

    db.refresh(new_item)
    return new_item

@router.put("/items/{item_id}", response_model=MenuItemResponse)
def update_menu_item(
    item_id: int,
    item_update: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and item.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot update items of another restaurant"
        )

    update_dict = item_update.model_dump(exclude_unset=True)
    for k, v in update_dict.items():
        setattr(item, k, v)

    db.commit()
    db.refresh(item)
    return item

@router.patch("/items/{item_id}/toggle-availability")
def toggle_item_availability(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles([
        UserRole.PLATFORM_SUPER_ADMIN,
        UserRole.RESTAURANT_OWNER,
        UserRole.ADMIN,
        UserRole.RESTAURANT_MANAGER,
        UserRole.MANAGER,
        UserRole.KITCHEN
    ]))
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and item.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot toggle availability for another restaurant's item"
        )

    item.is_available = not item.is_available
    db.commit()
    return {"id": item.id, "name": item.name, "is_available": item.is_available}

@router.delete("/items/{item_id}")
def delete_menu_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(MENU_MANAGERS))
):
    item = db.query(MenuItem).filter(MenuItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if current_user.role != UserRole.PLATFORM_SUPER_ADMIN and item.restaurant_id != current_user.restaurant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Cannot delete item from another restaurant"
        )

    db.delete(item)
    db.commit()
    return {"message": "Menu item deleted successfully"}
