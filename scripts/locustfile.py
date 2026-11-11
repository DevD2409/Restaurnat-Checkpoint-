import os
import random
import time
from locust import HttpUser, task, between, events

class CustomerUser(HttpUser):
    """
    Simulates dining customers at restaurant tables.
    Represents ~85% of total system traffic.
    No staff login required - customers access directly via table context.
    """
    weight = 85
    wait_time = between(0.5, 1.5)

    def on_start(self):
        self.table_id = random.randint(1, 10)
        self.active_order_id = None

    @task(5)
    def browse_menu(self):
        """Browse menu categories and items."""
        self.client.get("/api/v1/menu/categories?include_inactive=false", name="/menu/categories")

    @task(3)
    def place_order(self):
        """Simulate placing an order."""
        order_payload = {
            "restaurant_id": 1,
            "table_id": self.table_id,
            "customer_name": f"Customer_T{self.table_id}_{random.randint(100, 999)}",
            "items": [
                {
                    "menu_item_id": random.randint(1, 5),
                    "item_name": "Truffle Paneer Tikka",
                    "unit_price": 380.0,
                    "quantity": random.randint(1, 2)
                }
            ],
            "tip_amount": 0.0
        }
        resp = self.client.post("/api/v1/orders/", json=order_payload, name="/orders/place")
        if resp.status_code == 201:
            data = resp.json()
            self.active_order_id = data.get("id")

    @task(4)
    def track_order(self):
        """Simulate customer polling order progress."""
        if self.active_order_id:
            self.client.get(f"/api/v1/orders/{self.active_order_id}", name="/orders/{id}/track")
        else:
            self.client.get("/api/v1/orders/1", name="/orders/{id}/track")

    @task(2)
    def check_order_bill(self):
        """Simulate customer checking current order bill."""
        order_id = self.active_order_id or 1
        self.client.get(f"/api/v1/billing/order/{order_id}", name="/billing/order/{id}")


class StaffUser(HttpUser):
    """
    Simulates restaurant staff: waiters, chefs, and managers.
    Represents ~15% of total traffic.
    Logs in once and performs operational management actions.
    """
    weight = 15
    wait_time = between(0.8, 2.0)

    def on_start(self):
        self.auth_token = None
        self.headers = {}
        staff_username = os.getenv("LOCUST_STAFF_USERNAME", "")
        staff_password = os.getenv("LOCUST_STAFF_PASSWORD", "")
        if not (staff_username and staff_password):
            return
        try:
            resp = self.client.post("/api/v1/auth/login", json={
                "username": staff_username,
                "password": staff_password
            }, name="/auth/login")
            if resp.status_code == 200:
                self.auth_token = resp.json().get("access_token")
                self.headers = {"Authorization": f"Bearer {self.auth_token}"}
        except Exception:
            pass

    @task(4)
    def view_kitchen_kds(self):
        """Kitchen display system polling active orders."""
        self.client.get("/api/v1/kitchen/active", headers=self.headers, name="/kitchen/active")

    @task(3)
    def view_tables_floor(self):
        """Waiter floor plan viewing live table statuses."""
        self.client.get("/api/v1/tables/", headers=self.headers, name="/tables/")

    @task(2)
    def manage_orders(self):
        """Staff listing and progressing order statuses."""
        resp = self.client.get("/api/v1/orders/?limit=10", headers=self.headers, name="/orders/list")
        if resp.status_code == 200:
            orders = resp.json()
            if orders:
                target = random.choice(orders)
                self.client.patch(
                    f"/api/v1/orders/{target['id']}/status",
                    json={"status": "PREPARING", "changed_by": "HeadChef"},
                    headers=self.headers,
                    name="/orders/{id}/status"
                )

    @task(2)
    def view_analytics_kpi(self):
        """Manager reviewing restaurant KPIs."""
        self.client.get("/api/v1/analytics/overview", headers=self.headers, name="/analytics/overview")
