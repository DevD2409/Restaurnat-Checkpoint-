import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _staff_headers(username: str = "admin", password: str = "admin123") -> dict:
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, f"Staff login failed for {username}: {res.text}"
    return {"Authorization": f"Bearer {res.json()['access_token']}"}

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Smart Restaurant Management Platform" in data["service"]

def test_admin_and_staff_login():
    # Admin login
    res_admin = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"})
    assert res_admin.status_code == 200
    data_admin = res_admin.json()
    assert "access_token" in data_admin
    assert data_admin["role"] == "ADMIN"

    # Waiter login
    res_waiter = client.post("/api/v1/auth/login", json={"username": "waiter", "password": "waiter123"})
    assert res_waiter.status_code == 200
    data_waiter = res_waiter.json()
    assert data_waiter["role"] == "WAITER"

    # Invalid login
    res_invalid = client.post("/api/v1/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert res_invalid.status_code == 401

def test_menu_categories_and_items():
    res = client.get("/api/v1/menu/categories")
    assert res.status_code == 200
    categories = res.json()
    assert len(categories) >= 4
    # Check that first category has items
    assert len(categories[0]["items"]) > 0

    # Test item search
    search_res = client.get("/api/v1/menu/items?search=Biryani")
    assert search_res.status_code == 200
    items = search_res.json()
    assert any("Biryani" in item["name"] for item in items)

def test_table_qr_validation():
    # Retrieve tables as authenticated staff to inspect QR tokens
    tables_res = client.get("/api/v1/tables/", headers=_staff_headers())
    assert tables_res.status_code == 200
    tables = tables_res.json()
    assert len(tables) > 0

    first_table = tables[0]
    qr_token = first_table["qr_token"]
    assert qr_token is not None

    # Validate valid QR
    val_res = client.post("/api/v1/tables/validate-qr", json={"qr_token": qr_token})
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["valid"] is True
    assert val_data["table_number"] == first_table["table_number"]
    assert val_data["session_token"] is not None

    # Validate forged QR (must fail)
    bad_val = client.post("/api/v1/tables/validate-qr", json={"qr_token": "forged_tampered_qr_code"})
    assert bad_val.status_code == 400

def test_order_creation_and_lifecycle():
    # 1. Place order for Table 2
    order_payload = {
        "restaurant_id": 1,
        "table_id": 2,
        "customer_name": "Test Diner",
        "customer_phone": "+91 99999 88888",
        "special_instructions": "Extra spicy",
        "tip_amount": 50.0,
        "items": [
            {
                "menu_item_id": 1,
                "item_name": "Truffle Paneer Tikka",
                "unit_price": 380.0,
                "quantity": 2,
                "customizations": [
                    {"group_name": "Spice Level", "option_name": "Extra Spicy", "additional_price": 0.0}
                ]
            }
        ]
    }

    create_res = client.post("/api/v1/orders/", json={
        "restaurant_id": 1,
        "table_id": 2,
        "customer_name": "Test Diner",
        "customer_phone": "+91 99999 88888",
        "special_instructions": "Extra spicy",
        "tip_amount": 50.0,
        "items": [
            {
                "menu_item_id": 1,
                "item_name": "Truffle Paneer Tikka",
                "unit_price": 380.0,
                "quantity": 2,
                "customizations": [
                    {"group_name": "Spice Level", "option_name": "Extra Spicy", "additional_price": 0.0}
                ]
            }
        ]
    })
    assert create_res.status_code == 201
    order_data = create_res.json()
    order_id = order_data["id"]
    assert order_data["status"] == "PLACED"
    assert order_data["subtotal"] == 760.0
    assert order_data["tax_amount"] == 38.0  # 5% GST
    assert order_data["service_charge"] == 38.0  # 5% Service Charge
    assert order_data["tip_amount"] == 50.0
    assert order_data["total_amount"] == 886.0  # 760 + 38 + 38 + 50

    # 2. Kitchen advances status to PREPARING
    chef_headers = _staff_headers("chef", "chef123")
    waiter_headers = _staff_headers("waiter", "waiter123")
    kitchen_res = client.post("/api/v1/kitchen/update-status", json={
        "order_id": order_id,
        "status": "PREPARING",
        "chef_name": "Chef Kabir Sen"
    }, headers=chef_headers)
    assert kitchen_res.status_code == 200

    # 3. Advance to READY
    ready_res = client.post("/api/v1/kitchen/update-status", json={
        "order_id": order_id,
        "status": "READY"
    }, headers=chef_headers)
    assert ready_res.status_code == 200

    # 4. Advance to SERVED
    served_res = client.patch(f"/api/v1/orders/{order_id}/status", json={
        "status": "SERVED",
        "changed_by": "Head Waiter"
    }, headers=waiter_headers)
    assert served_res.status_code == 200
    assert served_res.json()["status"] == "SERVED"

def test_service_request_flow():
    waiter_headers = _staff_headers("waiter", "waiter123")
    # Customer requests water
    req_res = client.post("/api/v1/service-requests/", json={
        "restaurant_id": 1,
        "table_id": 2,
        "request_type": "WATER",
        "customer_notes": "Warm drinking water"
    })
    assert req_res.status_code == 201
    req_id = req_res.json()["id"]
    assert req_res.json()["status"] == "PENDING"

    # Staff acknowledges request
    ack_res = client.patch(f"/api/v1/service-requests/{req_id}/status", json={
        "status": "ACKNOWLEDGED",
        "staff_notes": "Waiter is serving now"
    }, headers=waiter_headers)
    assert ack_res.status_code == 200
    assert ack_res.json()["status"] == "ACKNOWLEDGED"

    # Staff resolves request
    resolve_res = client.patch(f"/api/v1/service-requests/{req_id}/status", json={
        "status": "RESOLVED"
    }, headers=waiter_headers)
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "RESOLVED"

def test_billing_and_payment(monkeypatch):
    import hmac
    import hashlib
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.restaurant import Restaurant
    from app.services.payment_service import PaymentService

    monkeypatch.setattr(settings, "EMERGENCY_DISABLE_PAYMENTS", False)
    monkeypatch.setattr(settings, "FLOW_A_ENABLED", True)

    admin_headers = _staff_headers("admin", "admin123")
    db_init = SessionLocal()
    try:
        from app.models.billing import Bill, BillStatus
        b_init = db_init.query(Bill).filter(Bill.order_id == 1).first()
        if b_init and b_init.status == BillStatus.PAID:
            b_init.status = BillStatus.UNPAID
            db_init.commit()
    finally:
        db_init.close()

    # Retrieve bill for order 1
    bill_res = client.get("/api/v1/billing/order/1", headers=admin_headers)
    assert bill_res.status_code == 200
    bill = bill_res.json()
    bill_id = bill["id"]
    assert bill["final_amount"] > 0

    # Configure 3 equal splits
    splits_payload = [
        {"split_type": "EQUAL", "person_name": "Alice", "amount": round(bill["final_amount"] / 3, 2)},
        {"split_type": "EQUAL", "person_name": "Bob", "amount": round(bill["final_amount"] / 3, 2)},
        {"split_type": "EQUAL", "person_name": "Charlie", "amount": round(bill["final_amount"] / 3, 2)},
    ]
    split_res = client.post(f"/api/v1/billing/{bill_id}/splits", json=splits_payload, headers=admin_headers)
    assert split_res.status_code == 200
    assert len(split_res.json()) == 3

    # Create Razorpay sandbox order
    rzp_res = client.post("/api/v1/payments/razorpay-order", json={
        "bill_id": bill_id,
        "amount": bill["final_amount"]
    })
    assert rzp_res.status_code == 200
    rzp_data = rzp_res.json()
    assert "razorpay_order_id" in rzp_data

    import time
    # Generate real HMAC-SHA256 signature against tenant's configured test secret
    db = SessionLocal()
    restaurant = db.query(Restaurant).filter(Restaurant.id == bill["restaurant_id"]).first()
    secret = PaymentService.get_restaurant_credentials(restaurant)["key_secret"]
    db.close()
    assert secret

    unique_pay_id = f"pay_test_sandbox_{int(time.time() * 1000)}"
    valid_sig = hmac.new(
        secret.encode(),
        f"{rzp_data['razorpay_order_id']}|{unique_pay_id}".encode(),
        hashlib.sha256,
    ).hexdigest()

    verify_res = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": rzp_data["razorpay_order_id"],
        "razorpay_payment_id": unique_pay_id,
        "razorpay_signature": valid_sig,
        "amount": bill["final_amount"]
    })
    assert verify_res.status_code == 200
    assert verify_res.json()["success"] is True

def test_analytics_kpi_computation():
    res = client.get("/api/v1/analytics/overview", headers=_staff_headers("admin", "admin123"))
    assert res.status_code == 200
    data = res.json()
    kpis = data["kpis"]

    # Verify dynamic computation (not static strings!)
    assert isinstance(kpis["total_revenue"], (int, float))
    assert kpis["total_revenue"] > 0
    assert isinstance(kpis["total_orders"], int)
    assert kpis["total_orders"] > 0
    assert isinstance(kpis["occupancy_rate"], (int, float))
    assert len(data["daily_sales"]) > 0
    assert len(data["category_sales"]) > 0
    assert len(data["top_selling_dishes"]) > 0
