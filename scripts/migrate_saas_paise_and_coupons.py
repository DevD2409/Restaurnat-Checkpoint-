import sqlite3
import os
import json
from datetime import datetime, timedelta

DB_PATH = "backend/smart_restaurant.db"

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("--- Migrating SaaS Subscription Engine to Integer Paise & Enhanced Coupons ---")

    # 1. Update restaurants table with grace_period_days
    cur.execute("PRAGMA table_info(restaurants)")
    rest_cols = [c[1] for c in cur.fetchall()]
    if "grace_period_days" not in rest_cols:
        print("Adding column 'grace_period_days' to restaurants...")
        cur.execute("ALTER TABLE restaurants ADD COLUMN grace_period_days INTEGER DEFAULT 7")

    # 2. Recreate subscription_plans table with price_paise
    cur.execute("DROP TABLE IF EXISTS subscription_plans")
    cur.execute("""
    CREATE TABLE subscription_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_code VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        billing_cycle VARCHAR(20) DEFAULT 'MONTHLY',
        price_paise INTEGER NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        duration_days INTEGER DEFAULT 30,
        features TEXT,
        entitlements_json TEXT,
        max_tables INTEGER DEFAULT 30,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Seed the exact Monthly (₹1,999) & Yearly (₹11,999) plans
    plans = [
        (
            "MONTHLY",
            "Monthly Growth Plan",
            "MONTHLY",
            199900,  # ₹1,999 in paise
            "INR",
            30,
            "Digital QR Menu, KDS Access, Table Operations, Analytics, Split Billing",
            json.dumps({"max_tables": 30, "kds_access": True, "advanced_analytics": True, "custom_branding": True, "multi_branch": False}),
            30,
            1
        ),
        (
            "YEARLY",
            "Yearly Enterprise Value Plan",
            "YEARLY",
            1199900,  # ₹11,999 in paise (12 months)
            "INR",
            365,
            "Unlimited Tables, Multi-Branch Management, Custom Theme Branding, Priority Support, Dedicated Account Manager",
            json.dumps({"max_tables": 999, "kds_access": True, "advanced_analytics": True, "custom_branding": True, "multi_branch": True, "priority_support": True}),
            999,
            1
        )
    ]
    cur.executemany("""
    INSERT INTO subscription_plans (plan_code, name, billing_cycle, price_paise, currency, duration_days, features, entitlements_json, max_tables, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, plans)

    # 3. Recreate subscription_coupons table
    cur.execute("DROP TABLE IF EXISTS subscription_coupons")
    cur.execute("""
    CREATE TABLE subscription_coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR(50) UNIQUE NOT NULL,
        discount_paise INTEGER DEFAULT 0,
        discount_type VARCHAR(20) DEFAULT 'FIXED_AMOUNT',
        discount_percentage FLOAT DEFAULT 0.0,
        eligible_plan_codes VARCHAR(255) DEFAULT '*',
        start_date DATETIME,
        end_date DATETIME,
        max_uses_global INTEGER DEFAULT 500,
        max_uses_per_restaurant INTEGER DEFAULT 1,
        times_used INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    expiry = datetime.now() + timedelta(days=365)
    start = datetime.now() - timedelta(days=1)
    coupons = [
        (
            "MONTHLY999",
            100000,  # ₹1,000 off -> reduces ₹1,999 to ₹999
            "FIXED_AMOUNT",
            0.0,
            "MONTHLY",
            start.isoformat(),
            expiry.isoformat(),
            500,
            1,
            0,
            1
        ),
        (
            "YEARLY9999",
            200000,  # ₹2,000 off -> reduces ₹11,999 to ₹9,999
            "FIXED_AMOUNT",
            0.0,
            "YEARLY",
            start.isoformat(),
            expiry.isoformat(),
            500,
            1,
            0,
            1
        ),
        (
            "LAUNCH50",
            0,
            "PERCENTAGE",
            50.0,
            "*",
            start.isoformat(),
            expiry.isoformat(),
            500,
            1,
            0,
            1
        )
    ]
    cur.executemany("""
    INSERT INTO subscription_coupons (code, discount_paise, discount_type, discount_percentage, eligible_plan_codes, start_date, end_date, max_uses_global, max_uses_per_restaurant, times_used, is_active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, coupons)

    # 4. Create subscription_coupon_redemptions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_coupon_redemptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        coupon_id INTEGER NOT NULL,
        restaurant_id INTEGER NOT NULL,
        invoice_id INTEGER,
        redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (coupon_id) REFERENCES subscription_coupons (id),
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_scr_coupon_rest ON subscription_coupon_redemptions (coupon_id, restaurant_id)")

    # 5. Create or maintain subscription_invoices table for paise
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number VARCHAR(50) UNIQUE NOT NULL,
        restaurant_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        billing_cycle VARCHAR(20) DEFAULT 'MONTHLY',
        subtotal_paise INTEGER NOT NULL,
        discount_paise INTEGER DEFAULT 0,
        tax_percentage FLOAT DEFAULT 18.0,
        tax_paise INTEGER DEFAULT 0,
        final_amount_paise INTEGER NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        status VARCHAR(50) DEFAULT 'UNPAID',
        coupon_id INTEGER,
        billing_start_date DATETIME,
        billing_end_date DATETIME,
        paid_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id),
        FOREIGN KEY (plan_id) REFERENCES subscription_plans (id),
        FOREIGN KEY (coupon_id) REFERENCES subscription_coupons (id)
    )
    """)

    # 6. Create or maintain subscription_payments table for paise
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        restaurant_id INTEGER NOT NULL,
        razorpay_order_id VARCHAR(100),
        razorpay_payment_id VARCHAR(100) UNIQUE,
        razorpay_signature VARCHAR(255),
        amount_paise INTEGER NOT NULL,
        refund_amount_paise INTEGER DEFAULT 0,
        currency VARCHAR(10) DEFAULT 'INR',
        payment_method VARCHAR(50) DEFAULT 'RAZORPAY',
        status VARCHAR(50) DEFAULT 'SUCCESS',
        refund_id VARCHAR(100),
        refunded_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES subscription_invoices (id),
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
    )
    """)

    # 7. Create subscription_notifications table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL,
        notification_type VARCHAR(50) NOT NULL,
        title VARCHAR(255) NOT NULL,
        message TEXT NOT NULL,
        is_read BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_snotif_rest ON subscription_notifications (restaurant_id)")

    conn.commit()
    conn.close()
    print("--- Migration completed successfully ---")

if __name__ == "__main__":
    run_migration()
