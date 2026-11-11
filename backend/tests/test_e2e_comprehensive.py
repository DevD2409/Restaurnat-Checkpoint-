import pytest
import time
import json
import uuid
import concurrent.futures
from fastapi.testclient import TestClient
from sqlalchemy import func
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User, UserRole
from app.models.table import Table, TableStatus, TableSession
from app.models.menu import MenuItem, MenuCategory
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus
from app.models.billing import Bill, BillSplit, Payment, BillStatus, SplitType, PaymentRecordStatus
from app.models.service_request import ServiceRequest, ServiceRequestType, ServiceRequestStatus
from app.models.reservation import Reservation, ReservationStatus
from app.core.security import generate_table_qr_token

client = TestClient(app)

def _create_test_order(table_number: str = None):
    """Helper to create a standard order and return (order_id, table_id)."""
    tables = client.get("/api/v1/tables/").json()
    if table_number:
        t = next(tbl for tbl in tables if tbl["table_number"] == table_number)
    else:
        t = tables[0]
    
    items = client.get("/api/v1/menu/items").json()
    item1 = items[0]
    item2 = items[1]

    customizations_payload = []
    addon_cost = 0.0
    if item1.get("customization_groups"):
        opt = item1["customization_groups"][0]["options"][0]
        customizations_payload.append({
            "group_name": item1["customization_groups"][0]["group_name"],
            "option_name": opt["name"],
            "additional_price": opt["additional_price"]
        })
        addon_cost = opt["additional_price"]

    qty1 = 2
    qty2 = 1
    unit1_effective = item1["price"] + addon_cost
    unit2_effective = item2["price"]
    subtotal = round((unit1_effective * qty1) + (unit2_effective * qty2), 2)
    tax = round(subtotal * 0.05, 2)
    sc = round(subtotal * 0.05, 2)
    tip = 30.0
    total = round(subtotal + tax + sc + tip, 2)

    order_payload = {
        "restaurant_id": t["restaurant_id"],
        "table_id": t["id"],
        "customer_name": f"Customer {uuid.uuid4().hex[:6]}",
        "customer_phone": "+919876500001",
        "items": [
            {
                "menu_item_id": item1["id"],
                "item_name": item1["name"],
                "unit_price": item1["price"],
                "quantity": qty1,
                "customizations": customizations_payload,
                "special_instructions": "Make it extra crisp"
            },
            {
                "menu_item_id": item2["id"],
                "item_name": item2["name"],
                "unit_price": item2["price"],
                "quantity": qty2,
                "customizations": [],
                "special_instructions": "Less oil please"
            }
        ],
        "tip_amount": tip,
        "special_instructions": "Table order"
    }

    resp = client.post("/api/v1/orders/", json=order_payload)
    assert resp.status_code == 201, f"Failed to place order: {resp.text}"
    order = resp.json()
    return order["id"], t["id"]

# ==============================================================================
# SCENARIO 1: Login using every seeded staff role
# ==============================================================================
def test_scenario_01_seeded_roles_login():
    """Verify authentication and JWT generation for all 5 seeded staff roles."""
    roles_credentials = [
        ("admin", "admin123", "ADMIN"),
        ("manager", "manager123", "MANAGER"),
        ("waiter", "waiter123", "WAITER"),
        ("chef", "chef123", "KITCHEN"),
        ("cashier", "cashier123", "CASHIER"),
    ]
    
    for username, password, expected_role in roles_credentials:
        response = client.post("/api/v1/auth/login", json={
            "username": username,
            "password": password
        })
        assert response.status_code == 200, f"Login failed for {username}: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == expected_role
        assert data["username"] == username
        
        # Verify /auth/me with the issued JWT
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_resp = client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["username"] == username
        assert me_data["role"] == expected_role

# ==============================================================================
# SCENARIO 2: Open customer table using its QR code
# ==============================================================================
def test_scenario_02_qr_table_validation_and_session():
    """Verify customer QR code scanning, tamper detection, and active session creation."""
    # Fetch Table T-01
    tables_resp = client.get("/api/v1/tables/")
    assert tables_resp.status_code == 200
    tables = tables_resp.json()
    assert len(tables) > 0
    t1 = next(t for t in tables if t["table_number"] == "T-01")
    qr_token = t1["qr_token"]
    assert qr_token is not None

    # Validate valid QR code token
    val_resp = client.post("/api/v1/tables/validate-qr", json={"qr_token": qr_token})
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["valid"] is True
    assert val_data["table_id"] == t1["id"]
    assert val_data["table_number"] == "T-01"
    assert "session_token" in val_data
    assert val_data["session_token"].startswith("sess_")

    # Table status should now be Occupied or Order Pending
    updated_tables = client.get("/api/v1/tables/").json()
    t1_updated = next(t for t in updated_tables if t["id"] == t1["id"])
    assert t1_updated["status"] in [
        TableStatus.OCCUPIED.value,
        TableStatus.ORDER_PENDING.value,
        TableStatus.BILL_REQUESTED.value
    ]

# ==============================================================================
# SCENARIO 3: Browse menu and customise a food item
# ==============================================================================
def test_scenario_03_menu_browsing_and_customization():
    """Verify menu categories, item retrieval, and rich customization options."""
    cat_resp = client.get("/api/v1/menu/categories")
    assert cat_resp.status_code == 200
    categories = cat_resp.json()
    assert len(categories) >= 4
    cat_names = [c["name"] for c in categories]
    assert "Starters & Appetizers" in cat_names
    assert "Main Course" in cat_names

    # Fetch items and find an item with customization groups
    items_resp = client.get("/api/v1/menu/items")
    assert items_resp.status_code == 200
    items = items_resp.json()
    customizable_item = next((i for i in items if len(i.get("customization_groups", [])) > 0), None)
    assert customizable_item is not None, "At least one item must have customization groups"
    
    group = customizable_item["customization_groups"][0]
    assert "group_name" in group
    assert len(group["options"]) > 0
    option = group["options"][0]
    assert "name" in option
    assert "additional_price" in option

# ==============================================================================
# SCENARIO 4 & 5: Add multiple items to cart and place an order
# ==============================================================================
def test_scenario_04_and_05_cart_and_place_order():
    """Verify multi-item order placement with customizations, GST, and service charge."""
    # Use Table T-03
    tables = client.get("/api/v1/tables/").json()
    t3 = next(t for t in tables if t["table_number"] == "T-03")
    
    # Establish customer session
    val_resp = client.post("/api/v1/tables/validate-qr", json={"qr_token": t3["qr_token"]}).json()
    session_token = val_resp["session_token"]
    
    # Select 2 distinct menu items
    items = client.get("/api/v1/menu/items").json()
    item1 = items[0]
    item2 = items[1]

    customizations_payload = []
    addon_cost = 0.0
    if item1.get("customization_groups"):
        opt = item1["customization_groups"][0]["options"][0]
        customizations_payload.append({
            "group_name": item1["customization_groups"][0]["group_name"],
            "option_name": opt["name"],
            "additional_price": opt["additional_price"]
        })
        addon_cost = opt["additional_price"]

    qty1 = 2
    qty2 = 1
    unit1_effective = item1["price"] + addon_cost
    unit2_effective = item2["price"]
    expected_subtotal = round((unit1_effective * qty1) + (unit2_effective * qty2), 2)
    expected_tax = round(expected_subtotal * 0.05, 2)
    expected_sc = round(expected_subtotal * 0.05, 2)
    tip = 30.0
    expected_total = round(expected_subtotal + expected_tax + expected_sc + tip, 2)

    order_payload = {
        "restaurant_id": t3["restaurant_id"],
        "table_id": t3["id"],
        "customer_name": "Dr. Emily Watson",
        "customer_phone": "+919876500001",
        "items": [
            {
                "menu_item_id": item1["id"],
                "item_name": item1["name"],
                "unit_price": item1["price"],
                "quantity": qty1,
                "customizations": customizations_payload,
                "special_instructions": "Make it extra crisp"
            },
            {
                "menu_item_id": item2["id"],
                "item_name": item2["name"],
                "unit_price": item2["price"],
                "quantity": qty2,
                "customizations": [],
                "special_instructions": "Less oil please"
            }
        ],
        "tip_amount": tip,
        "special_instructions": "Table by the window"
    }

    order_resp = client.post("/api/v1/orders/", json=order_payload)
    assert order_resp.status_code == 201, f"Failed to place order: {order_resp.text}"
    order = order_resp.json()
    
    assert order["id"] is not None
    assert order["order_number"].startswith("ORD-")
    assert order["status"] == "PLACED"
    assert order["payment_status"] == "UNPAID"
    assert order["subtotal"] == expected_subtotal
    assert order["tax_amount"] == expected_tax
    assert order["service_charge"] == expected_sc
    assert order["total_amount"] == expected_total
    assert len(order["items"]) == 2

# ==============================================================================
# SCENARIO 6: Verify order is saved in the database
# ==============================================================================
def test_scenario_06_verify_order_in_database():
    """Verify that order record and order line items are persistently stored in database."""
    order_id, table_id = _create_test_order()
    
    db = SessionLocal()
    try:
        db_order = db.query(Order).filter(Order.id == order_id).first()
        assert db_order is not None
        assert db_order.table_id == table_id
        assert len(db_order.items) == 2
        assert db_order.status == OrderStatus.PLACED
        assert len(db_order.status_history) >= 1
        assert db_order.status_history[0].new_status == "PLACED"
    finally:
        db.close()

# ==============================================================================
# SCENARIO 7: Order appears immediately in kitchen dashboard
# ==============================================================================
def test_scenario_07_kitchen_dashboard_active_orders():
    """Verify kitchen display system (KDS) receives newly placed orders."""
    order_id, _ = _create_test_order()
    
    kds_resp = client.get("/api/v1/kitchen/active")
    assert kds_resp.status_code == 200
    kds_data = kds_resp.json()
    assert "new_orders" in kds_data
    assert "preparing" in kds_data
    assert "ready" in kds_data
    assert "completed" in kds_data
    
    placed_in_kds = next((o for o in kds_data["new_orders"] if o["id"] == order_id), None)
    assert placed_in_kds is not None, f"Order {order_id} not found in kitchen new_orders"
    assert placed_in_kds["status"] == "PLACED"
    assert len(placed_in_kds["items"]) == 2

# ==============================================================================
# SCENARIO 8: Change status from Accepted to Preparing
# ==============================================================================
def test_scenario_08_order_status_placed_to_preparing():
    """Verify kitchen staff can advance order status to PREPARING."""
    order_id, _ = _create_test_order()

    update_payload = {
        "order_id": order_id,
        "status": "PREPARING",
        "chef_name": "Executive Chef Sanjeev"
    }
    update_resp = client.post("/api/v1/kitchen/update-status", json=update_payload)
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "PREPARING"

    kds_data = client.get("/api/v1/kitchen/active").json()
    prep_order = next((o for o in kds_data["preparing"] if o["id"] == order_id), None)
    assert prep_order is not None
    assert prep_order["status"] == "PREPARING"

# ==============================================================================
# SCENARIO 9: Customer order tracking updates automatically
# ==============================================================================
def test_scenario_09_customer_order_tracking_updates():
    """Verify customer order tracking view reflects status and history."""
    order_id, _ = _create_test_order()

    # Move to PREPARING
    client.post("/api/v1/kitchen/update-status", json={
        "order_id": order_id,
        "status": "PREPARING",
        "chef_name": "Executive Chef Sanjeev"
    })

    track_resp = client.get(f"/api/v1/orders/{order_id}")
    assert track_resp.status_code == 200
    track_data = track_resp.json()
    assert track_data["status"] == "PREPARING"
    assert len(track_data["status_history"]) >= 2
    statuses = [h["new_status"] for h in track_data["status_history"]]
    assert "PLACED" in statuses
    assert "PREPARING" in statuses

# ==============================================================================
# SCENARIO 10 & 11: Mark order Ready to Serve and waiter visibility
# ==============================================================================
def test_scenario_10_and_11_ready_to_serve_and_waiter_view():
    """Verify advancing order to READY and SERVED, and waiter dashboard synchronization."""
    order_id, table_id = _create_test_order("T-07")

    # Chef marks READY
    client.post("/api/v1/kitchen/update-status", json={
        "order_id": order_id,
        "status": "READY",
        "chef_name": "Executive Chef Sanjeev"
    })

    kds_data = client.get("/api/v1/kitchen/active").json()
    ready_order = next((o for o in kds_data["ready"] if o["id"] == order_id), None)
    assert ready_order is not None
    assert ready_order["status"] == "READY"

    waiter_login = client.post("/api/v1/auth/login", json={"username": "waiter", "password": "waiter123"}).json()
    waiter_headers = {"Authorization": f"Bearer {waiter_login['access_token']}"}
    
    tables_resp = client.get("/api/v1/tables/", headers=waiter_headers).json()
    table = next(t for t in tables_resp if t["id"] == table_id)
    assert table["active_order_id"] == order_id

    # Waiter marks order as SERVED
    serve_resp = client.patch(f"/api/v1/orders/{order_id}/status", json={
        "status": "SERVED",
        "notes": "Delivered hot to table"
    }, headers=waiter_headers)
    assert serve_resp.status_code == 200
    assert serve_resp.json()["status"] == "SERVED"

# ==============================================================================
# SCENARIO 12: Test Call Waiter and Request Bill service requests
# ==============================================================================
def test_scenario_12_service_requests_flow():
    """Verify service requests creation, table status update, and staff acknowledgment."""
    tables = client.get("/api/v1/tables/").json()
    table = tables[0]

    # Customer calls waiter for water
    req1 = client.post("/api/v1/service-requests/", json={
        "restaurant_id": table["restaurant_id"],
        "table_id": table["id"],
        "request_type": "WATER",
        "customer_notes": "Two glasses of chilled water please"
    })
    assert req1.status_code == 201
    r1_data = req1.json()
    assert r1_data["request_type"] == "WATER"
    assert r1_data["status"] == "PENDING"

    # Customer requests bill
    req2 = client.post("/api/v1/service-requests/", json={
        "restaurant_id": table["restaurant_id"],
        "table_id": table["id"],
        "request_type": "BILL",
        "customer_notes": "Please bring final bill"
    })
    assert req2.status_code == 201
    r2_data = req2.json()

    # Table status should have automatically updated to Bill Requested
    updated_table = next(t for t in client.get("/api/v1/tables/").json() if t["id"] == table["id"])
    assert updated_table["status"] in ["Bill Requested", TableStatus.BILL_REQUESTED.value]

    waiter_login = client.post("/api/v1/auth/login", json={"username": "waiter", "password": "waiter123"}).json()
    waiter_headers = {"Authorization": f"Bearer {waiter_login['access_token']}"}

    active_requests = client.get("/api/v1/service-requests/?status=PENDING").json()
    assert any(r["id"] == r1_data["id"] for r in active_requests)

    # Waiter acknowledges request 1
    ack_resp = client.patch(f"/api/v1/service-requests/{r1_data['id']}/status", json={
        "status": "ACKNOWLEDGED",
        "staff_notes": "On my way with water"
    }, headers=waiter_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"

    # Waiter completes request 1
    res_resp = client.patch(f"/api/v1/service-requests/{r1_data['id']}/status", json={
        "status": "RESOLVED",
        "staff_notes": "Water served"
    }, headers=waiter_headers)
    assert res_resp.status_code == 200
    assert res_resp.json()["status"] == "RESOLVED"

# ==============================================================================
# SCENARIO 13: Test table status lifecycle changes
# ==============================================================================
def test_scenario_13_table_status_lifecycle():
    """Verify table transitions through Available -> Occupied -> Order Pending -> Bill Requested -> Cleaning -> Available."""
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()
    headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # Pick Table T-05
    tables = client.get("/api/v1/tables/").json()
    t5 = next(t for t in tables if t["table_number"] == "T-05")
    table_id = t5["id"]

    statuses_to_cycle = [
        TableStatus.AVAILABLE.value,
        TableStatus.OCCUPIED.value,
        TableStatus.ORDER_PENDING.value,
        TableStatus.BILL_REQUESTED.value,
        TableStatus.CLEANING.value,
        TableStatus.AVAILABLE.value
    ]

    for st in statuses_to_cycle:
        res = client.put(f"/api/v1/tables/{table_id}", json={"status": st}, headers=headers)
        assert res.status_code == 200, f"Failed transition to {st}: {res.text}"
        assert res.json()["status"] == st

# ==============================================================================
# SCENARIO 14: Generate a bill and verify GST, service charges and totals
# ==============================================================================
def test_scenario_14_generate_bill_and_verify_taxes():
    """Verify automatic bill calculation: Subtotal + 5% GST + 5% Service Charge + Tip."""
    order_id, _ = _create_test_order()

    bill_resp = client.get(f"/api/v1/billing/order/{order_id}")
    assert bill_resp.status_code == 200
    bill = bill_resp.json()

    assert bill["order_id"] == order_id
    assert bill["bill_number"].startswith("INV-")
    assert bill["tax_percentage"] == 5.0
    assert bill["service_charge_percentage"] == 5.0

    calc_gst = round(bill["subtotal"] * 0.05, 2)
    calc_sc = round(bill["subtotal"] * 0.05, 2)
    calc_final = round(bill["subtotal"] + calc_gst + calc_sc + bill["tip_amount"] - bill["discount_amount"], 2)

    assert bill["tax_amount"] == calc_gst
    assert bill["service_charge"] == calc_sc
    assert bill["final_amount"] == calc_final

# ==============================================================================
# SCENARIO 15: Test equal and item-based bill splitting
# ==============================================================================
def test_scenario_15_bill_splitting_equal_and_item_based():
    """Verify split bill computation for equal portions and itemized allocations."""
    order_id, _ = _create_test_order()
    bill = client.get(f"/api/v1/billing/order/{order_id}").json()
    bill_id = bill["id"]
    total = bill["final_amount"]

    # 1. Equal Split for 3 persons
    equal_share = round(total / 3.0, 2)
    diff = round(total - (equal_share * 2), 2)
    equal_splits_payload = [
        {"split_type": "EQUAL", "person_name": "Alice", "amount": equal_share},
        {"split_type": "EQUAL", "person_name": "Bob", "amount": equal_share},
        {"split_type": "EQUAL", "person_name": "Charlie", "amount": diff},
    ]

    split_resp1 = client.post(f"/api/v1/billing/{bill_id}/splits", json=equal_splits_payload)
    assert split_resp1.status_code == 200
    splits1 = split_resp1.json()
    assert len(splits1) == 3
    assert sum(s["amount"] for s in splits1) == pytest.approx(total, 0.01)

    # 2. Item-based Split for 2 persons
    item_splits_payload = [
        {"split_type": "BY_ITEM", "person_name": "Alice", "amount": round(total * 0.6, 2)},
        {"split_type": "BY_ITEM", "person_name": "Bob", "amount": round(total * 0.4, 2)},
    ]
    split_resp2 = client.post(f"/api/v1/billing/{bill_id}/splits", json=item_splits_payload)
    assert split_resp2.status_code == 200
    splits2 = split_resp2.json()
    assert len(splits2) == 2
    assert splits2[0]["split_type"] == "BY_ITEM"

# ==============================================================================
# SCENARIO 16 & 17: Razorpay sandbox payment verification & completion
# ==============================================================================
def test_scenario_16_and_17_razorpay_payment_and_completion():
    """Verify Razorpay sandbox order creation, payment verification, and table status update."""
    order_id, table_id = _create_test_order()
    bill = client.get(f"/api/v1/billing/order/{order_id}").json()
    bill_id = bill["id"]
    final_amount = bill["final_amount"]

    # 1. Create Razorpay order
    rzp_order_resp = client.post("/api/v1/payments/razorpay-order", json={
        "bill_id": bill_id,
        "amount": final_amount,
        "currency": "INR"
    })
    assert rzp_order_resp.status_code == 200
    rzp_order_data = rzp_order_resp.json()
    assert "razorpay_order_id" in rzp_order_data
    assert rzp_order_data["amount_paise"] == int(final_amount * 100)
    order_mock_id = rzp_order_data["razorpay_order_id"]

    # 2. Verify Razorpay payment
    unique_pay_id = f"pay_{uuid.uuid4().hex[:12]}"
    verify_resp = client.post("/api/v1/payments/verify-razorpay-payment", json={
        "bill_id": bill_id,
        "razorpay_order_id": order_mock_id,
        "razorpay_payment_id": unique_pay_id,
        "razorpay_signature": "mock_signature_valid_sandbox",
        "amount": final_amount
    })
    assert verify_resp.status_code == 200
    ver_data = verify_resp.json()
    assert ver_data["success"] is True
    assert ver_data["bill_status"] == "PAID"

    # 3. Check updated Bill, Order and Table state in DB
    updated_bill = client.get(f"/api/v1/billing/{bill_id}").json()
    assert updated_bill["status"] == "PAID"
    assert len(updated_bill["payments"]) >= 1

    updated_order = client.get(f"/api/v1/orders/{order_id}").json()
    assert updated_order["payment_status"] == "PAID"
    assert updated_order["status"] == "COMPLETED"

    tables = client.get("/api/v1/tables/").json()
    table = next(t for t in tables if t["id"] == table_id)
    assert table["status"] in ["Cleaning", TableStatus.CLEANING.value]

# ==============================================================================
# SCENARIO 18: Create and manage a reservation
# ==============================================================================
def test_scenario_18_reservation_creation_and_management():
    """Verify reservation booking, conflict detection, and status management."""
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()
    headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    unique_slot_time = f"{int(time.time() % 10) + 10}:{int((time.time() * 100) % 60):02d}"
    unique_date = f"2026-12-{(int(time.time()) % 25) + 1:02d}"
    res_payload = {
        "restaurant_id": 1,
        "customer_name": "Lord Robert Crawly",
        "customer_email": "crawly@downton.org",
        "customer_phone": "+919876543210",
        "guest_count": 4,
        "reservation_date": unique_date,
        "reservation_time": unique_slot_time,
        "table_id": 1,
        "special_requests": "Window table, anniversary celebration"
    }

    create_resp = client.post("/api/v1/reservations/", json=res_payload)
    assert create_resp.status_code == 201
    res_data = create_resp.json()
    assert res_data["status"] == "PENDING"
    res_id = res_data["id"]

    # Manager approves reservation
    status_resp = client.patch(f"/api/v1/reservations/{res_id}/status", json={
        "status": "CONFIRMED"
    }, headers=headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "CONFIRMED"

    # Verify conflict detection on same table, date, and time
    conflict_resp = client.post("/api/v1/reservations/", json=res_payload)
    assert conflict_resp.status_code == 400
    assert "already booked" in conflict_resp.json()["detail"].lower()

# ==============================================================================
# SCENARIO 19: Add, edit, toggle availability, and delete a menu item
# ==============================================================================
def test_scenario_19_admin_menu_item_crud():
    """Verify administrator menu lifecycle: Create -> Edit -> Toggle Availability -> Delete."""
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()
    headers = {"Authorization": f"Bearer {admin_login['access_token']}"}

    # 1. Create dish
    dish_payload = {
        "category_id": 1,
        "name": f"Chef Signature Truffle Samosa {uuid.uuid4().hex[:6]}",
        "description": "Crisp flaky pastry stuffed with wild black truffles and spiced potatoes",
        "price": 320.0,
        "is_veg": True,
        "is_bestseller": True,
        "is_available": True,
        "preparation_time": 15,
        "calories": 280,
        "dietary_tags": "Vegetarian, Truffle",
        "spice_level": "Medium",
        "image_url": "https://images.unsplash.com/photo-example-samosa"
    }
    create_resp = client.post("/api/v1/menu/items", json=dish_payload, headers=headers)
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    # 2. Edit dish price and description
    edit_resp = client.put(f"/api/v1/menu/items/{item_id}", json={
        "price": 350.0,
        "description": "Updated gourmet truffle samosa with gold leaf garnishing"
    }, headers=headers)
    assert edit_resp.status_code == 200
    assert edit_resp.json()["price"] == 350.0

    # 3. Toggle availability to False
    toggle_resp = client.patch(f"/api/v1/menu/items/{item_id}/toggle-availability", headers=headers)
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_available"] is False

    # Verify customer menu (available_only=True) excludes this item
    customer_items = client.get("/api/v1/menu/items?available_only=true").json()
    assert not any(i["id"] == item_id for i in customer_items)

    # 4. Delete dish
    del_resp = client.delete(f"/api/v1/menu/items/{item_id}", headers=headers)
    assert del_resp.status_code == 200

    # Verify 404 on fetch
    assert client.get(f"/api/v1/menu/items/{item_id}").status_code == 404

# ==============================================================================
# SCENARIO 20: Verify admin analytics reflect actual database transactions
# ==============================================================================
def test_scenario_20_analytics_reflect_database_transactions():
    """Verify sales analytics and operational KPIs match exact database aggregate queries."""
    admin_login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin123"}).json()
    headers = {"Authorization": f"Bearer {admin_login['access_token']}"}
    restaurant_id = admin_login.get("restaurant_id", 1)

    analytics_resp = client.get("/api/v1/analytics/overview", headers=headers)
    assert analytics_resp.status_code == 200
    data = analytics_resp.json()
    kpis = data["kpis"]

    db = SessionLocal()
    try:
        # Check total revenue against Payment table for this restaurant
        db_revenue = db.query(func.coalesce(func.sum(Payment.amount), 0.0)).join(
            Bill, Payment.bill_id == Bill.id
        ).filter(
            Bill.restaurant_id == restaurant_id,
            Payment.status == PaymentRecordStatus.SUCCESS
        ).scalar()
        assert float(kpis["total_revenue"]) == pytest.approx(float(db_revenue), 0.01)

        # Check total orders count for this restaurant
        db_order_count = db.query(Order).filter(Order.restaurant_id == restaurant_id).count()
        assert kpis["total_orders"] == db_order_count

        # Check pending orders count for this restaurant
        db_pending = db.query(Order).filter(
            Order.restaurant_id == restaurant_id,
            Order.status.in_([OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.PREPARING])
        ).count()
        assert kpis["pending_orders"] == db_pending

        # Check total tables count strictly for this restaurant
        db_tables = db.query(Table).filter(Table.restaurant_id == restaurant_id, Table.is_active == True).count()
        assert kpis["total_tables"] == db_tables
    finally:
        db.close()

# ==============================================================================
# ADDITIONAL VALIDATION 1: Invalid QR tokens
# ==============================================================================
def test_additional_invalid_qr_tokens():
    """Verify invalid, forged, or tampered QR tokens are rejected with 400 Bad Request."""
    invalid_tokens = [
        "invalid_base64_garbage",
        "table.1.restaurant.1.tampered_hmac_signature",
        "",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.badpayload.signature"
    ]
    for token in invalid_tokens:
        resp = client.post("/api/v1/tables/validate-qr", json={"qr_token": token})
        assert resp.status_code in [400, 422], f"Expected rejection for token '{token}' but got {resp.status_code}"

# ==============================================================================
# ADDITIONAL VALIDATION 2: Unauthorised API access
# ==============================================================================
def test_additional_unauthorised_api_access():
    """Verify role-based access control enforces 401 for unauthenticated and 403 for unauthorized roles."""
    # 1. Unauthenticated request to staff management
    resp_no_auth = client.get("/api/v1/auth/staff")
    assert resp_no_auth.status_code == 401

    # 2. Waiter role accessing admin-only staff management
    waiter_login = client.post("/api/v1/auth/login", json={"username": "waiter", "password": "waiter123"}).json()
    waiter_token = waiter_login["access_token"]
    resp_waiter_forbidden = client.get("/api/v1/auth/staff", headers={"Authorization": f"Bearer {waiter_token}"})
    assert resp_waiter_forbidden.status_code == 403

    # 3. Waiter role attempting to delete a menu category (Admin only)
    resp_cat_del = client.delete("/api/v1/menu/categories/1", headers={"Authorization": f"Bearer {waiter_token}"})
    assert resp_cat_del.status_code == 403

# ==============================================================================
# ADDITIONAL VALIDATION 3: Incorrect passwords
# ==============================================================================
def test_additional_incorrect_passwords():
    """Verify failed authentication on incorrect password, non-existent username, or empty password."""
    test_cases = [
        ("admin", "wrongpassword123"),
        ("non_existent_staff", "any_password"),
        ("waiter", "12345"),
        ("chef", "")
    ]
    for user, pwd in test_cases:
        resp = client.post("/api/v1/auth/login", json={"username": user, "password": pwd})
        assert resp.status_code in [400, 401, 422], f"Expected auth failure for {user} but got {resp.status_code}"

# ==============================================================================
# ADDITIONAL VALIDATION 4: WebSocket disconnections and reconnections
# ==============================================================================
def test_additional_websocket_connection_and_reconnection():
    """Verify real-time WebSocket channel connection, ping-pong communication, disconnect, and reconnect."""
    # Connect to kitchen channel
    with client.websocket_connect("/ws/kitchen") as ws1:
        ws1.send_text("PING")
        reply = ws1.receive_text()
        data = json.loads(reply)
        assert data.get("type") == "PONG"
        assert data.get("channel") == "kitchen"

    # Connect to table-specific channel
    with client.websocket_connect("/ws/table/1") as ws2:
        ws2.send_text("PING")
        reply = ws2.receive_text()
        data = json.loads(reply)
        assert data.get("type") == "PONG"
        assert data.get("table_id") == 1

    # Reconnect to kitchen channel
    with client.websocket_connect("/ws/kitchen") as ws3:
        ws3.send_text("PING2")
        reply = ws3.receive_text()
        assert "PONG" in reply

# ==============================================================================
# ADDITIONAL VALIDATION 5: Duplicate payment callbacks
# ==============================================================================
def test_additional_duplicate_payment_callbacks():
    """Verify idempotency on duplicate payment callbacks: no duplicate deduction or crash."""
    order_id, _ = _create_test_order()
    bill = client.get(f"/api/v1/billing/order/{order_id}").json()
    bill_id = bill["id"]
    amount = bill["final_amount"]

    unique_tx = f"pay_idempotent_{uuid.uuid4().hex[:10]}"
    payload = {
        "bill_id": bill_id,
        "razorpay_order_id": f"order_mock_{int(time.time())}",
        "razorpay_payment_id": unique_tx,
        "razorpay_signature": "valid_signature_sandbox",
        "amount": amount
    }

    # First callback
    resp1 = client.post("/api/v1/payments/verify-razorpay-payment", json=payload)
    assert resp1.status_code == 200
    assert resp1.json()["success"] is True

    # Duplicate callback with identical transaction ID
    resp2 = client.post("/api/v1/payments/verify-razorpay-payment", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["success"] is True
    assert data2.get("is_duplicate") is True

# ==============================================================================
# ADDITIONAL VALIDATION 6: Simultaneous orders concurrency
# ==============================================================================
def test_additional_simultaneous_orders_concurrency():
    """Verify simultaneous multi-threaded order submissions are safely persisted without race conditions."""
    tables = client.get("/api/v1/tables/").json()
    items = client.get("/api/v1/menu/items").json()
    item = items[0]

    def place_single_order(index):
        target_table = tables[index % len(tables)]
        payload = {
            "restaurant_id": target_table["restaurant_id"],
            "table_id": target_table["id"],
            "customer_name": f"Concurrent Guest {index}",
            "customer_phone": f"+9198000000{index:02d}",
            "items": [
                {
                    "menu_item_id": item["id"],
                    "item_name": item["name"],
                    "unit_price": item["price"],
                    "quantity": 1,
                    "customizations": [],
                    "special_instructions": f"Batch test {index}"
                }
            ],
            "tip_amount": 0.0,
            "special_instructions": "Simultaneous load test"
        }
        res = client.post("/api/v1/orders/", json=payload)
        return res.status_code, res.json()

    # Dispatch 5 simultaneous orders via ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(place_single_order, i) for i in range(5)]
        results = [f.result() for f in futures]

    for status_code, data in results:
        assert status_code == 201, f"Concurrent order failed: {data}"
        assert data["order_number"].startswith("ORD-")
        assert data["status"] == "PLACED"

# ==============================================================================
# ADDITIONAL VALIDATION 7: Database transaction and validation failures
# ==============================================================================
def test_additional_database_transaction_and_validation_failures():
    """Verify database transaction integrity: invalid table or foreign keys return 404/400 cleanly."""
    # Non-existent table ID in order
    bad_order_resp = client.post("/api/v1/orders/", json={
        "restaurant_id": 1,
        "table_id": 999999,  # Non-existent
        "customer_name": "Ghost Customer",
        "items": [{"menu_item_id": 1, "item_name": "Naan", "unit_price": 50.0, "quantity": 1}],
        "tip_amount": 0.0
    })
    assert bad_order_resp.status_code == 404
    assert "table not found" in bad_order_resp.json()["detail"].lower()

    # Non-existent table in service request
    bad_sr_resp = client.post("/api/v1/service-requests/", json={
        "restaurant_id": 1,
        "table_id": 999999,
        "request_type": "WATER"
    })
    assert bad_sr_resp.status_code == 404
