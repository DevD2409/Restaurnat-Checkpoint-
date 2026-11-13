import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.security import create_access_token, generate_table_qr_token, get_password_hash
from app.main import app
from app.models.menu import MenuCategory, MenuItem
from app.models.reservation import Reservation, ReservationStatus
from app.models.restaurant import Restaurant
from app.models.table import Table, TableSession, TableStatus
from app.models.user import User, UserRole

client = TestClient(app)


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _auth_header(user: User) -> dict:
    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        restaurant_id=user.restaurant_id,
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_tenant_bundle(db, tag: str, *, gst_number=None):
    """Create an isolated tenant with staff, table, menu category/item, and reservation."""
    restaurant = Restaurant(
        name=f"Tenant Bistro {tag}",
        slug=f"tenant-bistro-{tag}",
        email=f"owner-{tag}@example.com",
        gst_number=gst_number,
        subscription_plan="PRO",
        subscription_status="ACTIVE",
        is_active=True,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    owner = User(
        restaurant_id=restaurant.id,
        email=f"owner-{tag}@example.com",
        username=f"p3a_owner_{tag}",
        hashed_password=get_password_hash("StrongPass#2026!"),
        full_name=f"Owner {tag}",
        role=UserRole.RESTAURANT_OWNER,
        is_active=True,
        must_change_password=False,
    )
    chef = User(
        restaurant_id=restaurant.id,
        email=f"chef-{tag}@example.com",
        username=f"p3a_chef_{tag}",
        hashed_password=get_password_hash("StrongPass#2026!"),
        full_name=f"Chef {tag}",
        role=UserRole.KITCHEN,
        is_active=True,
        must_change_password=False,
    )
    waiter = User(
        restaurant_id=restaurant.id,
        email=f"waiter-{tag}@example.com",
        username=f"p3a_waiter_{tag}",
        hashed_password=get_password_hash("StrongPass#2026!"),
        full_name=f"Waiter {tag}",
        role=UserRole.WAITER,
        is_active=True,
        must_change_password=False,
    )
    customer = User(
        restaurant_id=restaurant.id,
        email=f"cust-{tag}@example.com",
        username=f"p3a_cust_{tag}",
        hashed_password=get_password_hash("StrongPass#2026!"),
        full_name=f"Customer {tag}",
        role=UserRole.CUSTOMER,
        is_active=True,
        must_change_password=False,
    )
    db.add_all([owner, chef, waiter, customer])
    db.commit()
    for u in (owner, chef, waiter, customer):
        db.refresh(u)

    short_tag = tag.replace("_", "")[:6]
    table1 = Table(
        restaurant_id=restaurant.id,
        table_number=f"T-{short_tag}-1",
        capacity=4,
        section="Main",
        status=TableStatus.AVAILABLE,
        is_active=True,
    )
    table2 = Table(
        restaurant_id=restaurant.id,
        table_number=f"T-{short_tag}-2",
        capacity=2,
        section="Patio",
        status=TableStatus.AVAILABLE,
        is_active=True,
    )
    db.add_all([table1, table2])
    db.commit()
    db.refresh(table1)
    db.refresh(table2)

    table1.qr_token = generate_table_qr_token(restaurant.id, table1.id, table1.table_number)
    table2.qr_token = generate_table_qr_token(restaurant.id, table2.id, table2.table_number)

    cat = MenuCategory(
        restaurant_id=restaurant.id,
        name=f"Category {tag}",
        is_active=True,
    )
    db.add(cat)
    db.commit()
    db.refresh(cat)

    menu_item = MenuItem(
        restaurant_id=restaurant.id,
        category_id=cat.id,
        name=f"Dish {tag}",
        price=250.0,
        is_available=True,
    )
    db.add(menu_item)
    db.commit()
    db.refresh(menu_item)

    reservation = Reservation(
        restaurant_id=restaurant.id,
        customer_name=f"Guest {tag}",
        customer_phone="+919999900000",
        guest_count=2,
        reservation_date="2026-12-20",
        reservation_time="19:30",
        table_id=table1.id,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    return {
        "restaurant": restaurant,
        "owner": owner,
        "chef": chef,
        "waiter": waiter,
        "customer": customer,
        "table1": table1,
        "table2": table2,
        "menu_item": menu_item,
        "reservation": reservation,
    }


def _place_qr_order(table: Table, menu_item: MenuItem):
    val_resp = client.post("/api/v1/tables/validate-qr", json={"qr_token": table.qr_token})
    assert val_resp.status_code == 200, val_resp.text
    session_token = val_resp.json()["session_token"]

    order_resp = client.post(
        "/api/v1/orders/",
        json={
            "restaurant_id": table.restaurant_id,
            "table_id": table.id,
            "customer_name": "QR Diner",
            "customer_phone": "+919876543210",
            "items": [
                {
                    "menu_item_id": menu_item.id,
                    "item_name": menu_item.name,
                    "unit_price": menu_item.price,
                    "quantity": 1,
                    "customizations": [],
                }
            ],
            "tip_amount": 0.0,
        },
        headers={"X-Table-Session": session_token},
    )
    assert order_resp.status_code == 201, order_resp.text
    return order_resp.json(), session_token


def test_anonymous_calls_rejected_across_protected_endpoints():
    """Anonymous callers must receive 401 on protected kitchen, order, service-request, billing, analytics, reservation, and table endpoints."""
    db = SessionLocal()
    try:
        tenant = _seed_tenant_bundle(db, f"anon_{_uid()}")
        order, session_token = _place_qr_order(tenant["table1"], tenant["menu_item"])
        item_id = order["items"][0]["id"]

        # Create bill using authenticated owner first
        bill_resp = client.get(f"/api/v1/billing/order/{order['id']}", headers=_auth_header(tenant["owner"]))
        assert bill_resp.status_code == 200
        bill_id = bill_resp.json()["id"]

        # Create service request via public QR path
        sr_resp = client.post(
            "/api/v1/service-requests/",
            json={"restaurant_id": 999999, "table_id": tenant["table1"].id, "request_type": "WATER"},
        )
        assert sr_resp.status_code == 201
        sr_data = sr_resp.json()
        # Authoritative tenant derived from table, ignoring forged restaurant_id
        assert sr_data["restaurant_id"] == tenant["restaurant"].id

        checks = [
            ("GET", "/api/v1/analytics/overview", None),
            ("GET", "/api/v1/kitchen/active", None),
            ("PATCH", f"/api/v1/kitchen/item/{item_id}/status?status_str=COOKING", None),
            ("POST", "/api/v1/kitchen/update-status", {"order_id": order["id"], "status": "PREPARING"}),
            ("GET", "/api/v1/orders/", None),
            ("GET", f"/api/v1/orders/{order['id']}", None),
            ("PATCH", f"/api/v1/orders/{order['id']}/status", {"status": "ACCEPTED"}),
            ("PATCH", f"/api/v1/orders/{order['id']}/priority", {"priority": "URGENT"}),
            ("GET", "/api/v1/service-requests/", None),
            ("PATCH", f"/api/v1/service-requests/{sr_data['id']}/status", {"status": "ACKNOWLEDGED"}),
            ("GET", f"/api/v1/billing/order/{order['id']}", None),
            ("GET", f"/api/v1/billing/{bill_id}", None),
            ("POST", f"/api/v1/billing/{bill_id}/splits", [{"split_type": "EQUAL", "person_name": "A", "amount": 50.0}]),
            ("GET", f"/api/v1/billing/{bill_id}/receipt", None),
            ("GET", "/api/v1/reservations/", None),
            ("GET", "/api/v1/tables/", None),
            ("GET", f"/api/v1/tables/{tenant['table1'].id}/qr-code-image", None),
        ]

        for method, path, payload in checks:
            if payload is not None:
                res = client.request(method, path, json=payload)
            else:
                res = client.request(method, path)
            assert res.status_code == 401, f"Expected 401 for anonymous {method} {path}, got {res.status_code}: {res.text}"

        # Also validate invalid X-Table-Session fails with 401
        bad_sess = client.get(f"/api/v1/orders/{order['id']}", headers={"X-Table-Session": "sess_invalid_token"})
        assert bad_sess.status_code == 401
        assert session_token.startswith("sess_")
    finally:
        db.close()


def test_cross_tenant_staff_isolation_and_menu_ownership():
    """Tenant A staff cannot read or mutate Tenant B orders, kitchen items, bills, service requests, analytics, reservations, or tables."""
    db = SessionLocal()
    try:
        t_a = _seed_tenant_bundle(db, f"ta_{_uid()}")
        t_b = _seed_tenant_bundle(db, f"tb_{_uid()}")

        order_a, _ = _place_qr_order(t_a["table1"], t_a["menu_item"])
        order_b, _ = _place_qr_order(t_b["table1"], t_b["menu_item"])

        headers_a_owner = _auth_header(t_a["owner"])
        headers_a_chef = _auth_header(t_a["chef"])

        bill_b = client.get(f"/api/v1/billing/order/{order_b['id']}", headers=_auth_header(t_b["owner"])).json()
        sr_b_res = client.post(
            "/api/v1/service-requests/",
            json={"restaurant_id": t_b["restaurant"].id, "table_id": t_b["table1"].id, "request_type": "CALL_WAITER"},
        )
        assert sr_b_res.status_code == 201, sr_b_res.text
        sr_b = sr_b_res.json()

        # Cross-tenant Order / Kitchen / Billing / Service Request / Analytics / Reservation / Table isolation
        assert client.get(f"/api/v1/kitchen/active?restaurant_id={t_b['restaurant'].id}", headers=headers_a_chef).status_code == 403
        assert client.patch(
            f"/api/v1/kitchen/item/{order_b['items'][0]['id']}/status?status_str=COOKING",
            headers=headers_a_chef,
        ).status_code == 403
        assert client.post(
            "/api/v1/kitchen/update-status",
            json={"order_id": order_b["id"], "status": "PREPARING"},
            headers=headers_a_chef,
        ).status_code == 403
        assert client.post(
            "/api/v1/kitchen/update-status",
            json={"order_id": order_a["id"], "restaurant_id": t_b["restaurant"].id, "status": "PREPARING"},
            headers=headers_a_chef,
        ).status_code == 403

        assert client.get(f"/api/v1/orders/?restaurant_id={t_b['restaurant'].id}", headers=headers_a_owner).status_code == 403
        assert client.get(f"/api/v1/orders/{order_b['id']}", headers=headers_a_owner).status_code == 403
        assert client.patch(
            f"/api/v1/orders/{order_b['id']}/status",
            json={"status": "ACCEPTED"},
            headers=headers_a_owner,
        ).status_code == 403
        assert client.patch(
            f"/api/v1/orders/{order_b['id']}/priority",
            json={"priority": "URGENT"},
            headers=headers_a_owner,
        ).status_code == 403

        # Order creation must reject MenuItem from another restaurant (no global fallback)
        bad_order = client.post(
            "/api/v1/orders/",
            json={
                "restaurant_id": t_a["restaurant"].id,
                "table_id": t_a["table1"].id,
                "customer_name": "Cross Tenant Menu Probe",
                "items": [
                    {
                        "menu_item_id": t_b["menu_item"].id,
                        "item_name": t_b["menu_item"].name,
                        "unit_price": t_b["menu_item"].price,
                        "quantity": 1,
                        "customizations": [],
                    }
                ],
                "tip_amount": 0.0,
            },
        )
        assert bad_order.status_code == 400

        # Service requests cross-tenant & invalid assignee checks
        sr_a = client.post(
            "/api/v1/service-requests/",
            json={"restaurant_id": t_a["restaurant"].id, "table_id": t_a["table1"].id, "request_type": "WATER"},
        ).json()
        assert client.get(f"/api/v1/service-requests/?restaurant_id={t_b['restaurant'].id}", headers=headers_a_owner).status_code == 403
        assert client.patch(
            f"/api/v1/service-requests/{sr_b['id']}/status",
            json={"status": "ACKNOWLEDGED"},
            headers=headers_a_owner,
        ).status_code == 403
        # Assigning staff from Tenant B to Tenant A service request must fail (403)
        assert client.patch(
            f"/api/v1/service-requests/{sr_a['id']}/status",
            json={"status": "ACKNOWLEDGED", "assigned_staff_id": t_b["waiter"].id},
            headers=headers_a_owner,
        ).status_code == 403
        # Assigning CUSTOMER role as staff must fail (400)
        assert client.patch(
            f"/api/v1/service-requests/{sr_a['id']}/status",
            json={"status": "ACKNOWLEDGED", "assigned_staff_id": t_a["customer"].id},
            headers=headers_a_owner,
        ).status_code == 400

        # Billing cross-tenant isolation
        assert client.get(f"/api/v1/billing/order/{order_b['id']}", headers=headers_a_owner).status_code == 403
        assert client.get(f"/api/v1/billing/{bill_b['id']}", headers=headers_a_owner).status_code == 403
        assert client.post(
            f"/api/v1/billing/{bill_b['id']}/splits",
            json=[{"split_type": "EQUAL", "person_name": "Attacker", "amount": 100.0}],
            headers=headers_a_owner,
        ).status_code == 403
        assert client.get(f"/api/v1/billing/{bill_b['id']}/receipt", headers=headers_a_owner).status_code == 403

        # Analytics, reservations, and tables cross-tenant isolation
        assert client.get(f"/api/v1/analytics/overview?restaurant_id={t_b['restaurant'].id}", headers=headers_a_owner).status_code == 403
        assert client.get(f"/api/v1/reservations/?restaurant_id={t_b['restaurant'].id}", headers=headers_a_owner).status_code == 403
        assert client.patch(
            f"/api/v1/reservations/{t_b['reservation'].id}/status",
            json={"status": "CONFIRMED"},
            headers=headers_a_owner,
        ).status_code == 403
        assert client.patch(
            f"/api/v1/reservations/{t_a['reservation'].id}/status",
            json={"status": "CONFIRMED", "table_id": t_b["table1"].id},
            headers=headers_a_owner,
        ).status_code == 403
        assert client.post(
            "/api/v1/reservations/",
            json={
                "restaurant_id": t_a["restaurant"].id,
                "customer_name": "Probe",
                "customer_phone": "+919999900001",
                "guest_count": 2,
                "reservation_date": "2026-12-25",
                "reservation_time": "20:00",
                "table_id": t_b["table1"].id,
            },
        ).status_code == 403

        assert client.get(f"/api/v1/tables/?restaurant_id={t_b['restaurant'].id}", headers=headers_a_owner).status_code == 403
        assert client.get(f"/api/v1/tables/{t_b['table1'].id}/qr-code-image", headers=headers_a_owner).status_code == 403
    finally:
        db.close()


def test_role_enforcement_and_password_rotation_blocking():
    """Verify WAITER/CUSTOMER role boundaries and must_change_password enforcement on newly secured endpoints."""
    db = SessionLocal()
    try:
        tenant = _seed_tenant_bundle(db, f"role_{_uid()}")
        order, _ = _place_qr_order(tenant["table1"], tenant["menu_item"])

        # WAITER cannot read analytics overview or invoke kitchen write endpoints
        waiter_headers = _auth_header(tenant["waiter"])
        assert client.get("/api/v1/analytics/overview", headers=waiter_headers).status_code == 403
        assert client.patch(
            f"/api/v1/kitchen/item/{order['items'][0]['id']}/status?status_str=COOKING",
            headers=waiter_headers,
        ).status_code == 403
        assert client.post(
            "/api/v1/kitchen/update-status",
            json={"order_id": order["id"], "status": "PREPARING"},
            headers=waiter_headers,
        ).status_code == 403

        # CUSTOMER role cannot use staff endpoints
        cust_headers = _auth_header(tenant["customer"])
        assert client.get("/api/v1/kitchen/active", headers=cust_headers).status_code == 403
        assert client.get("/api/v1/orders/", headers=cust_headers).status_code == 403
        assert client.get("/api/v1/reservations/", headers=cust_headers).status_code == 403
        assert client.get("/api/v1/service-requests/", headers=cust_headers).status_code == 403

        # User pending mandatory password rotation is blocked on billing & orders
        tenant["owner"].must_change_password = True
        db.commit()
        owner_headers = _auth_header(tenant["owner"])
        assert client.get(f"/api/v1/billing/order/{order['id']}", headers=owner_headers).status_code == 403
        assert client.get(f"/api/v1/orders/{order['id']}", headers=owner_headers).status_code == 403
    finally:
        db.close()


def test_table_session_scoping_anonymous_table_redaction_and_dynamic_receipt():
    """Verify QR table sessions, session isolation across tables/sessions, anonymous table redaction, and receipt GST."""
    db = SessionLocal()
    try:
        unreg = _seed_tenant_bundle(db, f"nogst_{_uid()}", gst_number=None)
        reg = _seed_tenant_bundle(db, f"gst_{_uid()}", gst_number="29ABCDE1234F1Z5")

        # Validate QR sets current_session_id in DB cleanly
        order1, sess1 = _place_qr_order(unreg["table1"], unreg["menu_item"])
        order2, sess2 = _place_qr_order(unreg["table2"], unreg["menu_item"])
        order_reg, sess_reg = _place_qr_order(reg["table1"], reg["menu_item"])

        db.refresh(unreg["table1"])
        assert unreg["table1"].current_session_id is not None

        # Table 1 session CAN access its own orders/bill/splits/receipt (with customer_phone masked)
        h_s1 = {"X-Table-Session": sess1}
        own_list = client.get("/api/v1/orders/", headers=h_s1)
        assert own_list.status_code == 200
        assert [o["id"] for o in own_list.json()] == [order1["id"]]
        assert own_list.json()[0]["customer_phone"] is None

        own_order = client.get(f"/api/v1/orders/{order1['id']}", headers=h_s1)
        assert own_order.status_code == 200
        assert own_order.json()["customer_phone"] is None

        bill1_res = client.get(f"/api/v1/billing/order/{order1['id']}", headers=h_s1)
        assert bill1_res.status_code == 200
        bill1 = bill1_res.json()

        splits_res = client.post(
            f"/api/v1/billing/{bill1['id']}/splits",
            json=[
                {"split_type": "EQUAL", "person_name": "Diner 1", "amount": round(bill1["final_amount"] / 2, 2)},
                {"split_type": "EQUAL", "person_name": "Diner 2", "amount": round(bill1["final_amount"] / 2, 2)},
            ],
            headers=h_s1,
        )
        assert splits_res.status_code == 200

        receipt_unreg = client.get(f"/api/v1/billing/{bill1['id']}/receipt", headers=h_s1)
        assert receipt_unreg.status_code == 200
        rec_unreg_json = receipt_unreg.json()
        assert rec_unreg_json["restaurant_name"] == unreg["restaurant"].name
        assert rec_unreg_json["restaurant_gst"] is None
        assert "Royal Saffron" not in rec_unreg_json["restaurant_name"]

        # Registered restaurant receipt shows real GST number
        bill_reg = client.get(f"/api/v1/billing/order/{order_reg['id']}", headers={"X-Table-Session": sess_reg}).json()
        receipt_reg = client.get(f"/api/v1/billing/{bill_reg['id']}/receipt", headers={"X-Table-Session": sess_reg})
        assert receipt_reg.status_code == 200
        assert receipt_reg.json()["restaurant_name"] == reg["restaurant"].name
        assert receipt_reg.json()["restaurant_gst"] == "29ABCDE1234F1Z5"

        # Table 1 session CANNOT access Table 2 order/bill/receipt or another tenant's resources
        assert client.get(f"/api/v1/orders/{order2['id']}", headers=h_s1).status_code == 403
        assert client.get(f"/api/v1/orders/?table_id={unreg['table2'].id}", headers=h_s1).status_code == 403
        bill2 = client.get(f"/api/v1/billing/order/{order2['id']}", headers={"X-Table-Session": sess2}).json()
        assert client.get(f"/api/v1/billing/{bill2['id']}", headers=h_s1).status_code == 403
        assert client.get(f"/api/v1/billing/{bill2['id']}/receipt", headers=h_s1).status_code == 403
        assert client.get(f"/api/v1/orders/{order_reg['id']}", headers=h_s1).status_code == 403

        # Anonymous public table lookup via slug redacts QR tokens, session IDs, order IDs, and bill amounts
        anon_tables = client.get(f"/api/v1/tables/?slug={unreg['restaurant'].slug}")
        assert anon_tables.status_code == 200
        rows = anon_tables.json()
        assert len(rows) == 2
        for row in rows:
            assert row["qr_token"] is None
            assert row["qr_code_url"] is None
            assert row["current_session_id"] is None
            assert row["active_order_id"] is None
            assert row["active_bill_amount"] is None
            assert row["session_start_time"] is None

        # Ending the session invalidates future X-Table-Session use
        end_res = client.post(
            f"/api/v1/tables/{unreg['table1'].id}/session/end",
            headers=_auth_header(unreg["owner"]),
        )
        assert end_res.status_code == 200
        assert client.get(f"/api/v1/orders/{order1['id']}", headers=h_s1).status_code == 401
        assert client.get(f"/api/v1/billing/{bill1['id']}/receipt", headers=h_s1).status_code == 401

        # New session on the same table cannot read the previous diner's order
        new_val = client.post("/api/v1/tables/validate-qr", json={"qr_token": unreg["table1"].qr_token})
        assert new_val.status_code == 200
        new_sess = new_val.json()["session_token"]
        assert client.get(f"/api/v1/orders/{order1['id']}", headers={"X-Table-Session": new_sess}).status_code == 403
    finally:
        db.close()
