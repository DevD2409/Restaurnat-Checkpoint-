import io
import time
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.restaurant import Restaurant
from app.models.table import Table
from app.models.menu import MenuItem, MenuCategory
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.feedback import Feedback, FeedbackDishRating, FeedbackPhoto
from app.core.security import create_access_token

client = TestClient(app)

@pytest.fixture
def auth_tokens():
    db = SessionLocal()
    # Owner for Tenant 1 (The Royal Saffron)
    owner_1 = db.query(User).filter(User.username == "admin").first()
    if not owner_1:
        owner_1 = db.query(User).filter(User.role.in_([UserRole.ADMIN, UserRole.RESTAURANT_OWNER])).first()

    # Owner for Tenant 2 (The Spice Pavilion)
    owner_2 = db.query(User).filter(User.username == "owner_spice").first()
    if not owner_2:
        owner_2 = db.query(User).filter(User.restaurant_id == 2).first()

    # Super Admin
    superadmin = db.query(User).filter(User.username == "superadmin").first()

    t1_token = create_access_token(
        subject=str(owner_1.id),
        role=owner_1.role.value,
        restaurant_id=1
    )
    t2_token = create_access_token(
        subject=str(owner_2.id),
        role=owner_2.role.value,
        restaurant_id=2
    )
    sa_token = create_access_token(
        subject=str(superadmin.id),
        role=superadmin.role.value,
        restaurant_id=None
    )
    db.close()
    return {
        "tenant_1": t1_token,
        "tenant_2": t2_token,
        "superadmin": sa_token
    }

# Helper to create a test order in database
def create_test_order(restaurant_id: int, status: OrderStatus, payment_status: PaymentStatus) -> Order:
    db = SessionLocal()
    order_num = f"ORD-FB-TEST-{int(time.time() * 1000)}"
    order = Order(
        order_number=order_num,
        restaurant_id=restaurant_id,
        table_id=1 if restaurant_id == 1 else 11,
        customer_name="Test Diner",
        customer_phone="+919876543210",
        status=status,
        payment_status=payment_status,
        subtotal=1200.0,
        tax_amount=60.0,
        service_charge=60.0,
        total_amount=1320.0
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # Add items
    item = OrderItem(
        order_id=order.id,
        item_name="Tandoori Smoked Paneer",
        unit_price=600.0,
        quantity=2,
        total_price=1200.0,
        status="SERVED"
    )
    db.add(item)
    db.commit()
    db.refresh(order)
    order_id = order.id
    db.close()
    return order_id

# 1. Test Order Eligibility Enforcement
def test_order_eligibility_enforcement():
    # Case A: Order still in PREPARING status and UNPAID -> Must be rejected
    unready_order_id = create_test_order(1, OrderStatus.PREPARING, PaymentStatus.UNPAID)
    res_a = client.post("/api/v1/feedback/", json={
        "order_id": unready_order_id,
        "overall_rating": 5,
        "comment": "Food was great!"
    })
    assert res_a.status_code == 400
    assert "completed and paid" in res_a.json()["detail"].lower()

    # Case B: Order is COMPLETED but UNPAID -> Must be rejected
    unpaid_order_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.UNPAID)
    res_b = client.post("/api/v1/feedback/", json={
        "order_id": unpaid_order_id,
        "overall_rating": 5,
        "comment": "Nice meal!"
    })
    assert res_b.status_code == 400
    assert "completed and paid" in res_b.json()["detail"].lower()

    # Case C: Order is SERVED / COMPLETED and PAID -> Must be accepted
    eligible_order_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)
    res_c = client.post("/api/v1/feedback/", json={
        "order_id": eligible_order_id,
        "overall_rating": 5,
        "food_rating": 5,
        "service_rating": 4,
        "ambience_rating": 5,
        "cleanliness_rating": 5,
        "comment": "Exemplary dining experience!"
    })
    assert res_c.status_code == 201
    data = res_c.json()
    assert data["order_id"] == eligible_order_id
    assert data["overall_rating"] == 5
    assert data["is_verified_dining"] is True

# 2. Test Duplicate Reviews Prevention and Edit Permissions
def test_duplicate_reviews_prevention():
    order_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)

    # 1. First review submission succeeds
    res_first = client.post("/api/v1/feedback/", json={
        "order_id": order_id,
        "overall_rating": 4,
        "food_rating": 4,
        "comment": "Initial review"
    })
    assert res_first.status_code == 201
    initial_id = res_first.json()["id"]

    # 2. Duplicate submission on same order without permission must be blocked
    res_dup = client.post("/api/v1/feedback/", json={
        "order_id": order_id,
        "overall_rating": 5,
        "comment": "Duplicate attempt"
    })
    assert res_dup.status_code == 400
    assert "already been submitted" in res_dup.json()["detail"]

    # 3. Explicit edit permission allows updating the existing record without duplicate creation
    res_edit = client.post("/api/v1/feedback/", json={
        "order_id": order_id,
        "overall_rating": 5,
        "comment": "Updated review with edit permission",
        "allow_edit_if_exists": True
    })
    assert res_edit.status_code == 201
    assert res_edit.json()["id"] == initial_id
    assert res_edit.json()["overall_rating"] == 5
    assert res_edit.json()["comment"] == "Updated review with edit permission"

# 3. Test Multi-Tenant Isolation
def test_feedback_multi_tenant_isolation(auth_tokens):
    # Order belongs to Tenant 2
    t2_order_id = create_test_order(2, OrderStatus.COMPLETED, PaymentStatus.PAID)

    # Attacking client sends Tenant 1 ID for Tenant 2's order -> Must reject
    res_mismatch = client.post("/api/v1/feedback/", json={
        "restaurant_id": 1,
        "order_id": t2_order_id,
        "overall_rating": 5
    })
    assert res_mismatch.status_code == 400
    assert "tenant mismatch" in res_mismatch.json()["detail"].lower()

    # Valid submission for Tenant 2
    res_t2 = client.post("/api/v1/feedback/", json={
        "order_id": t2_order_id,
        "overall_rating": 4,
        "comment": "Tenant 2 meal"
    })
    assert res_t2.status_code == 201
    t2_feedback_id = res_t2.json()["id"]

    # Tenant 1 owner lists feedback -> Tenant 2 feedback must NOT appear
    res_t1_list = client.get(
        "/api/v1/feedback/",
        headers={"Authorization": f"Bearer {auth_tokens['tenant_1']}"}
    )
    assert res_t1_list.status_code == 200
    t1_ids = [f["id"] for f in res_t1_list.json()]
    assert t2_feedback_id not in t1_ids

    # Tenant 2 owner lists feedback -> Tenant 2 feedback appears
    res_t2_list = client.get(
        "/api/v1/feedback/",
        headers={"Authorization": f"Bearer {auth_tokens['tenant_2']}"}
    )
    assert res_t2_list.status_code == 200
    t2_ids = [f["id"] for f in res_t2_list.json()]
    assert t2_feedback_id in t2_ids

    # Tenant 1 owner cannot moderate Tenant 2 feedback
    res_cross_mod = client.patch(
        f"/api/v1/feedback/{t2_feedback_id}/moderate",
        json={"status": "FLAGGED"},
        headers={"Authorization": f"Bearer {auth_tokens['tenant_1']}"}
    )
    assert res_cross_mod.status_code == 403

# 4. Test Individual Dish Ratings and Multi-Attribute Ratings
def test_individual_dish_and_multi_attribute_ratings():
    order_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)

    res = client.post("/api/v1/feedback/", json={
        "order_id": order_id,
        "customer_name": "Gourmet Critic",
        "overall_rating": 5,
        "food_rating": 5,
        "service_rating": 4,
        "ambience_rating": 5,
        "cleanliness_rating": 5,
        "comment": "Flawless flavors and immaculate ambience.",
        "dish_ratings": [
            {
                "dish_name": "Tandoori Smoked Paneer",
                "rating": 5,
                "comment": "Melt in mouth texture with authentic charring"
            },
            {
                "dish_name": "Dal Makhani",
                "rating": 4,
                "comment": "Rich and buttery"
            }
        ]
    })
    assert res.status_code == 201
    data = res.json()
    assert data["food_rating"] == 5
    assert data["service_rating"] == 4
    assert data["ambience_rating"] == 5
    assert data["cleanliness_rating"] == 5
    assert len(data["dish_ratings"]) == 2
    assert data["dish_ratings"][0]["dish_name"] == "Tandoori Smoked Paneer"
    assert data["dish_ratings"][0]["rating"] == 5

# 5. Test Review Moderation, Reporting and Anti-Spam Controls
def test_review_moderation_reporting_and_anti_spam(auth_tokens):
    # Case A: Spam review automatically flagged
    order_spam_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)
    res_spam = client.post("/api/v1/feedback/", json={
        "order_id": order_spam_id,
        "overall_rating": 5,
        "comment": "Click here for buy now cheap crypto casino deals http://scam-link.xyz"
    })
    assert res_spam.status_code == 201
    data_spam = res_spam.json()
    assert data_spam["status"] == "FLAGGED"
    assert data_spam["is_published"] is False
    assert "anti-spam" in data_spam["flag_reason"].lower()

    # Case B: Genuine negative review is NOT suppressed (no reward, no negative suppression)
    order_crit_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)
    res_crit = client.post("/api/v1/feedback/", json={
        "order_id": order_crit_id,
        "overall_rating": 1,
        "food_rating": 1,
        "service_rating": 2,
        "comment": "The soup was served lukewarm and waiter took 20 minutes to bring the bill."
    })
    assert res_crit.status_code == 201
    data_crit = res_crit.json()
    assert data_crit["status"] == "APPROVED"
    assert data_crit["is_published"] is True

    # Case C: Owner moderates review
    res_mod = client.patch(
        f"/api/v1/feedback/{data_spam['id']}/moderate",
        json={"status": "REJECTED", "flag_reason": "Confirmed spam link", "is_published": False},
        headers={"Authorization": f"Bearer {auth_tokens['tenant_1']}"}
    )
    assert res_mod.status_code == 200
    assert res_mod.json()["status"] == "REJECTED"
    assert res_mod.json()["is_published"] is False

    # Case D: Reporting a review
    res_report = client.post(
        f"/api/v1/feedback/{data_crit['id']}/report",
        json={"reason": "Contains abusive harassment or spam"}
    )
    assert res_report.status_code == 200
    assert res_report.json()["status"] == "FLAGGED"

# 6. Test Photo Upload File Validation
def test_photo_upload_validation():
    # 1. Valid JPEG with legitimate JPEG magic bytes (\xff\xd8\xff)
    valid_jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200
    res_valid = client.post(
        "/api/v1/feedback/upload-photo",
        files={"file": ("dish_photo.jpg", io.BytesIO(valid_jpeg_bytes), "image/jpeg")}
    )
    assert res_valid.status_code == 200
    assert "photo_url" in res_valid.json()
    assert res_valid.json()["mime_type"] == "image/jpeg"

    # 2. Disallowed executable extension
    res_exe = client.post(
        "/api/v1/feedback/upload-photo",
        files={"file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")}
    )
    assert res_exe.status_code == 400
    assert "only jpeg, png, and webp" in res_exe.json()["detail"].lower()

    # 3. Spoofed extension with corrupted magic bytes
    res_spoofed = client.post(
        "/api/v1/feedback/upload-photo",
        files={"file": ("fake.png", io.BytesIO(b"NOT_A_PNG_FILE"), "image/png")}
    )
    assert res_spoofed.status_code == 400
    assert "corrupted or invalid image header" in res_spoofed.json()["detail"].lower()

    # 4. Oversized file (> 5MB)
    oversized_bytes = b"\xff\xd8\xff" + (b"0" * (5 * 1024 * 1024 + 100))
    res_big = client.post(
        "/api/v1/feedback/upload-photo",
        files={"file": ("giant.jpg", io.BytesIO(oversized_bytes), "image/jpeg")}
    )
    assert res_big.status_code == 400
    assert "exceeds maximum allowed limit of 5mb" in res_big.json()["detail"].lower()

# 7. Test Google Review URL Configuration and Non-Automated Compliance
def test_google_review_url_configuration_and_compliance(auth_tokens):
    # 1. Update restaurant profile with Google Review URL
    google_url = "https://g.page/r/the-royal-saffron-mumbai/review"
    res_update = client.put(
        "/api/v1/restaurants/",
        json={"google_review_url": google_url},
        headers={"Authorization": f"Bearer {auth_tokens['tenant_1']}"}
    )
    assert res_update.status_code == 200

    # 2. Check public profile reflects Google Review URL
    res_pub = client.get("/api/v1/restaurants/by-slug/royal-saffron")
    assert res_pub.status_code == 200
    assert res_pub.json()["google_review_url"] == google_url

    # 3. Submit feedback and verify Google Review URL & voluntary notice
    order_id = create_test_order(1, OrderStatus.COMPLETED, PaymentStatus.PAID)
    res_fb = client.post("/api/v1/feedback/", json={
        "order_id": order_id,
        "overall_rating": 5,
        "comment": "Outstanding hospitality!"
    })
    assert res_fb.status_code == 201
    data = res_fb.json()
    assert data["google_review_url"] == google_url
    assert "voluntary and submitted independently" in data["google_review_notice"]
    assert "never automatically posts" in data["google_review_notice"]

# 8. Test Restaurant Owner Feedback Analytics Dashboard
def test_feedback_analytics_dashboard(auth_tokens):
    res = client.get(
        "/api/v1/feedback/analytics",
        headers={"Authorization": f"Bearer {auth_tokens['tenant_1']}"}
    )
    assert res.status_code == 200
    data = res.json()
    assert "total_reviews" in data
    assert "average_overall" in data
    assert "average_food" in data
    assert "average_service" in data
    assert "average_ambience" in data
    assert "average_cleanliness" in data
    assert "dish_ratings" in data
    assert "rating_breakdown" in data
    assert "google_review_url" in data
    assert data["verified_dining_percentage"] == 100.0
