import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.models.table import Table
from app.models.order import Order
from app.core.security import generate_table_qr_token

client = TestClient(app)

def test_multi_tenant_onboarding_and_slug_check():
    """Verify tenant registration, slug uniqueness check, and initial provisioning."""
    # 1. Check existing slug for Royal Saffron
    resp_royal = client.get("/api/v1/onboarding/check-slug?slug=royal-saffron")
    assert resp_royal.status_code == 200
    assert resp_royal.json()["available"] is False

    # 2. Check fresh slug for an unregistered bistro
    resp_avail = client.get("/api/v1/onboarding/check-slug?slug=fresh-unique-cafe-2026")
    assert resp_avail.status_code == 200
    assert resp_avail.json()["available"] is True

    # 3. Complete onboarding wizard
    onboard_payload = {
        "restaurant_name": "The Spice Bistro & Cafe",
        "slug": "spice-bistro",
        "tagline": "Authentic Coastal & Chettinad Delicacies",
        "address": "99 Marine Drive, Mumbai, Maharashtra",
        "phone": "+91 98200 11223",
        "email": "contact@spicebistro.in",
        "gst_number": "27AAACB2233M1Z5",
        "tax_percentage": 5.0,
        "service_charge_percentage": 5.0,
        "currency": "INR",
        "currency_symbol": "₹",
        "subscription_plan": "PRO",
        "table_count": 6,
        "owner_full_name": "Vikram Sethi",
        "owner_username": "owner_spice",
        "owner_email": "vikram@spicebistro.in",
        "owner_password": "SpicePass@2026",
        "owner_phone": "+91 98200 11223"
    }

    reg_resp = client.post("/api/v1/onboarding/register", json=onboard_payload)
    if reg_resp.status_code == 201:
        data = reg_resp.json()
        assert (data.get("restaurant_slug") or data.get("slug")) == "spice-bistro"
        assert data.get("table_count", 6) >= 5
        assert data["owner_username"] == "owner_spice"
    else:
        assert reg_resp.status_code == 400
        assert "already registered" in reg_resp.json().get("detail", "")


def test_tenant_owner_auth_and_profile_isolation():
    """Verify Tenant 2 owner receives scoped JWT and cannot tamper with Tenant 1."""
    # Login as Tenant 2 owner
    login_resp = client.post("/api/v1/auth/login", json={
        "username": "owner_spice",
        "password": "SpicePass@2026"
    })
    assert login_resp.status_code == 200
    tenant2_auth = login_resp.json()
    token_t2 = tenant2_auth["access_token"]
    assert tenant2_auth["restaurant_slug"] == "spice-bistro"
    t2_restaurant_id = tenant2_auth["restaurant_id"]
    headers_t2 = {"Authorization": f"Bearer {token_t2}"}

    # Verify /me endpoint returns Tenant 2 restaurant profile
    me_resp = client.get("/api/v1/restaurants/me", headers=headers_t2)
    assert me_resp.status_code == 200
    t2_profile = me_resp.json()
    assert t2_profile["slug"] == "spice-bistro"
    assert t2_profile["id"] == t2_restaurant_id

    # Attempt cross-tenant mutation: Tenant 2 owner tries to edit Tenant 1 (Royal Saffron, id=1)
    hack_resp = client.put("/api/v1/restaurants/1", json={
        "name": "Hacked Saffron Bistro",
        "tagline": "Malicious takeover attempt"
    }, headers=headers_t2)
    assert hack_resp.status_code == 403
    assert "not authorized to update another restaurant" in hack_resp.json()["detail"].lower()


def test_staff_cross_tenant_isolation():
    """Verify Tenant 2 owner can only see and manage Tenant 2 staff members."""
    # Login as Tenant 2 owner
    t2_login = client.post("/api/v1/auth/login", json={
        "username": "owner_spice",
        "password": "SpicePass@2026"
    }).json()
    headers_t2 = {"Authorization": f"Bearer {t2_login['access_token']}"}

    # 1. List staff: Tenant 2 owner must NOT see Tenant 1 staff (e.g. Arjun Verma, Priya Sharma)
    staff_resp = client.get("/api/v1/auth/staff", headers=headers_t2)
    assert staff_resp.status_code == 200
    staff_members = staff_resp.json()
    usernames = [s["username"] for s in staff_members]
    assert "admin" not in usernames
    assert "manager" not in usernames
    assert "chef" not in usernames
    assert "waiter" not in usernames

    # 2. Add a staff member for Tenant 2
    add_staff_resp = client.post("/api/v1/auth/staff", json={
        "username": "spice_waiter_1",
        "email": "waiter1@spicebistro.in",
        "password": "WaiterPass@123",
        "full_name": "Rohan Nair",
        "role": "WAITER",
        "phone_number": "+91 98000 11111",
        "shift": "Evening Shift"
    }, headers=headers_t2)
    assert add_staff_resp.status_code in [201, 400]  # 400 if already created in repeated test run

    # 3. Attempt to delete Tenant 1 staff member (e.g. user_id=2 or 3) using Tenant 2 token
    del_resp = client.delete("/api/v1/auth/staff/2", headers=headers_t2)
    assert del_resp.status_code == 403
    assert "another restaurant" in del_resp.json()["detail"].lower()


def test_cross_tenant_menu_and_kitchen_isolation():
    """Verify Menu items and Kitchen KDS pipeline are strictly isolated between tenants."""
    # 1. Public Menu query for Tenant 1 (Royal Saffron)
    royal_menu = client.get("/api/v1/menu/categories?restaurant_id=1")
    assert royal_menu.status_code == 200
    royal_cats = royal_menu.json()
    assert len(royal_cats) > 0
    royal_cat_names = [c["name"] for c in royal_cats]
    assert "Starters & Appetizers" in royal_cat_names

    # 2. Public Menu query for Tenant 2 (Spice Bistro)
    t2_login = client.post("/api/v1/auth/login", json={
        "username": "owner_spice",
        "password": "SpicePass@2026"
    }).json()
    t2_id = t2_login["restaurant_id"]
    headers_t2 = {"Authorization": f"Bearer {t2_login['access_token']}"}

    spice_menu = client.get(f"/api/v1/menu/categories?restaurant_id={t2_id}")
    assert spice_menu.status_code == 200
    spice_cats = spice_menu.json()
    assert len(spice_cats) > 0

    # 3. Tenant 2 Kitchen KDS check: Tenant 1 orders should NOT appear in Tenant 2's queue
    t2_kds = client.get("/api/v1/kitchen/active", headers=headers_t2)
    assert t2_kds.status_code == 200
    kds_data = t2_kds.json()
    assert kds_data["restaurant_id"] == t2_id
    # All orders in kds_data must belong to t2_id
    for ord_entry in kds_data.get("new_orders", []) + kds_data.get("preparing", []):
        assert ord_entry["restaurant_id"] == t2_id


def test_customer_public_tenant_profiles():
    """Verify customer can look up restaurant profiles by slug."""
    # Royal Saffron lookup
    rs_resp = client.get("/api/v1/restaurants/by-slug/royal-saffron")
    assert rs_resp.status_code == 200
    rs_data = rs_resp.json()
    assert rs_data["name"] == "The Royal Saffron - Smart Bistro & Lounge"
    assert rs_data["slug"] == "royal-saffron"

    # Spice Bistro lookup
    sb_resp = client.get("/api/v1/restaurants/by-slug/spice-bistro")
    assert sb_resp.status_code == 200
    sb_data = sb_resp.json()
    assert sb_data["name"] == "The Spice Bistro & Cafe"
    assert sb_data["slug"] == "spice-bistro"

    # Invalid slug lookup
    inv_resp = client.get("/api/v1/restaurants/by-slug/non-existent-restaurant-999")
    assert inv_resp.status_code == 404


def test_customer_feedback_and_ratings_scoping():
    """Verify reviews and ratings can be submitted and are scoped to the restaurant."""
    t2_login = client.post("/api/v1/auth/login", json={
        "username": "owner_spice",
        "password": "SpicePass@2026"
    }).json()
    t2_id = t2_login["restaurant_id"]

    # Submit feedback for Tenant 2
    feedback_payload = {
        "restaurant_id": t2_id,
        "customer_name": "Aarav Patel",
        "overall_rating": 5,
        "food_rating": 5,
        "service_rating": 4,
        "ambience_rating": 5,
        "cleanliness_rating": 5,
        "comment": "Exceptional spices and brilliant hospitality! Loved the Chettinad preparations."
    }
    fb_resp = client.post("/api/v1/feedback/", json=feedback_payload)
    assert fb_resp.status_code == 201
    fb_data = fb_resp.json()
    assert fb_data["overall_rating"] == 5
    assert fb_data["restaurant_id"] == t2_id

    # Retrieve published feedback for Tenant 2
    pub_resp = client.get(f"/api/v1/feedback/restaurant/{t2_id}")
    assert pub_resp.status_code == 200
    pub_items = pub_resp.json()
    assert len(pub_items) >= 1
    assert any(item["customer_name"] == "Aarav Patel" for item in pub_items)


def test_platform_super_admin_portal():
    """Verify SaaS Platform Super Administrator has global visibility and management."""
    # 1. Super Admin login
    sa_login = client.post("/api/v1/auth/login", json={
        "username": "superadmin",
        "password": "superadmin123"
    })
    assert sa_login.status_code == 200
    sa_auth = sa_login.json()
    assert sa_auth["role"] == "PLATFORM_SUPER_ADMIN"
    headers_sa = {"Authorization": f"Bearer {sa_auth['access_token']}"}

    # 2. Global platform statistics
    stats_resp = client.get("/api/v1/platform/stats", headers=headers_sa)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_restaurants"] >= 2  # Royal Saffron + Spice Bistro
    assert "subscription_breakdown" in stats

    # 3. List all tenant restaurants
    tenants_resp = client.get("/api/v1/platform/restaurants", headers=headers_sa)
    assert tenants_resp.status_code == 200
    tenants = tenants_resp.json()
    tenant_slugs = [t["slug"] for t in tenants]
    assert "royal-saffron" in tenant_slugs
    assert "spice-bistro" in tenant_slugs

    # 4. Non-super admin cannot access platform endpoint
    t2_login = client.post("/api/v1/auth/login", json={
        "username": "owner_spice",
        "password": "SpicePass@2026"
    }).json()
    headers_t2 = {"Authorization": f"Bearer {t2_login['access_token']}"}
    forbidden_resp = client.get("/api/v1/platform/stats", headers=headers_t2)
    assert forbidden_resp.status_code == 403
