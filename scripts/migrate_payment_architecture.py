import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = "backend/smart_restaurant.db"

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("--- Migrating Payment & Subscription Architecture ---")

    # 1. Update 'restaurants' table
    cur.execute("PRAGMA table_info(restaurants)")
    rest_cols = [c[1] for c in cur.fetchall()]
    
    new_rest_cols = [
        ("razorpay_webhook_secret_enc", "VARCHAR(255)"),
        ("razorpay_account_id", "VARCHAR(100)"),
        ("payment_gateway_mode", "VARCHAR(50) DEFAULT 'DIRECT_MERCHANT'"),
        ("settlement_bank_account_verified", "BOOLEAN DEFAULT 0"),
        ("subscription_expires_at", "DATETIME")
    ]
    for col_name, col_type in new_rest_cols:
        if col_name not in rest_cols:
            print(f"Adding column '{col_name}' to restaurants table...")
            cur.execute(f"ALTER TABLE restaurants ADD COLUMN {col_name} {col_type}")

    # 2. Update 'payments' table
    cur.execute("PRAGMA table_info(payments)")
    payment_cols = [c[1] for c in cur.fetchall()]

    new_payment_cols = [
        ("restaurant_id", "INTEGER DEFAULT 1"),
        ("currency", "VARCHAR(10) DEFAULT 'INR'"),
        ("error_code", "VARCHAR(100)"),
        ("error_description", "VARCHAR(255)"),
        ("settlement_status", "VARCHAR(50) DEFAULT 'PENDING'"),
        ("settlement_id", "VARCHAR(100)"),
        ("transfer_id", "VARCHAR(100)"),
        ("refund_id", "VARCHAR(100)"),
        ("refund_amount", "FLOAT DEFAULT 0.0"),
        ("refunded_at", "DATETIME")
    ]
    for col_name, col_type in new_payment_cols:
        if col_name not in payment_cols:
            print(f"Adding column '{col_name}' to payments table...")
            cur.execute(f"ALTER TABLE payments ADD COLUMN {col_name} {col_type}")

    # 3. Create 'payment_webhook_events' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS payment_webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id VARCHAR(100) UNIQUE NOT NULL,
        event_type VARCHAR(100) NOT NULL,
        restaurant_id INTEGER,
        entity_id VARCHAR(100),
        status VARCHAR(50) DEFAULT 'PROCESSED',
        payload TEXT,
        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_pwe_event_id ON payment_webhook_events (event_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_pwe_restaurant_id ON payment_webhook_events (restaurant_id)")

    # 4. Create 'subscription_plans' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_plans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_code VARCHAR(50) UNIQUE NOT NULL,
        name VARCHAR(100) NOT NULL,
        billing_cycle VARCHAR(20) DEFAULT 'MONTHLY',
        price FLOAT NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        features TEXT,
        max_tables INTEGER DEFAULT 25,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_sp_plan_code ON subscription_plans (plan_code)")

    # 5. Create 'subscription_coupons' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code VARCHAR(50) UNIQUE NOT NULL,
        discount_percentage FLOAT DEFAULT 0.0,
        discount_amount FLOAT DEFAULT 0.0,
        valid_until DATETIME,
        max_uses INTEGER DEFAULT 100,
        times_used INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_sc_code ON subscription_coupons (code)")

    # 6. Create 'subscription_invoices' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_number VARCHAR(50) UNIQUE NOT NULL,
        restaurant_id INTEGER NOT NULL,
        plan_id INTEGER NOT NULL,
        billing_cycle VARCHAR(20) DEFAULT 'MONTHLY',
        subtotal FLOAT NOT NULL,
        discount_amount FLOAT DEFAULT 0.0,
        coupon_id INTEGER,
        tax_percentage FLOAT DEFAULT 18.0,
        tax_amount FLOAT DEFAULT 0.0,
        final_amount FLOAT NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        status VARCHAR(50) DEFAULT 'UNPAID',
        billing_start_date DATETIME,
        billing_end_date DATETIME,
        paid_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id),
        FOREIGN KEY (plan_id) REFERENCES subscription_plans (id),
        FOREIGN KEY (coupon_id) REFERENCES subscription_coupons (id)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_si_invoice_number ON subscription_invoices (invoice_number)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_si_restaurant_id ON subscription_invoices (restaurant_id)")

    # 7. Create 'subscription_payments' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        restaurant_id INTEGER NOT NULL,
        razorpay_order_id VARCHAR(100),
        razorpay_payment_id VARCHAR(100) UNIQUE,
        razorpay_signature VARCHAR(255),
        amount FLOAT NOT NULL,
        currency VARCHAR(10) DEFAULT 'INR',
        payment_method VARCHAR(50) DEFAULT 'RAZORPAY',
        status VARCHAR(50) DEFAULT 'SUCCESS',
        refund_id VARCHAR(100),
        refund_amount FLOAT DEFAULT 0.0,
        refunded_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (invoice_id) REFERENCES subscription_invoices (id),
        FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_sp_payment_id ON subscription_payments (razorpay_payment_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_sp_invoice_id ON subscription_payments (invoice_id)")

    # 8. Create 'subscription_webhook_events' table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS subscription_webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id VARCHAR(100) UNIQUE NOT NULL,
        event_type VARCHAR(100) NOT NULL,
        invoice_id INTEGER,
        restaurant_id INTEGER,
        status VARCHAR(50) DEFAULT 'PROCESSED',
        payload TEXT,
        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_swe_event_id ON subscription_webhook_events (event_id)")

    # 9. Seed default subscription plans if empty
    cur.execute("SELECT count(*) FROM subscription_plans")
    if cur.fetchone()[0] == 0:
        print("Seeding default subscription tiers (STARTER, PRO, ENTERPRISE)...")
        plans = [
            ("STARTER", "Starter Bistro Plan", "MONTHLY", 1999.0, "INR", "Digital QR Menu, 10 Tables, Order Management, Basic Analytics", 10),
            ("PRO", "Professional Restaurant & Bar Plan", "MONTHLY", 4999.0, "INR", "Digital QR Menu, Kitchen Display KDS, Split Billing, 35 Tables, Advanced Analytics, SMS Notifications", 35),
            ("ENTERPRISE", "Enterprise Multi-Outlet & Hotel Plan", "MONTHLY", 9999.0, "INR", "Unlimited Tables, Multi-Branch, Room Service, Custom Branding, Dedicated Manager, Route Transfer", 999)
        ]
        cur.executemany("""
        INSERT INTO subscription_plans (plan_code, name, billing_cycle, price, currency, features, max_tables, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, plans)

    # 10. Seed default promotional coupons if empty
    cur.execute("SELECT count(*) FROM subscription_coupons")
    if cur.fetchone()[0] == 0:
        print("Seeding launch discount coupons (LAUNCH50, WELCOME20)...")
        expiry = datetime.now() + timedelta(days=365)
        coupons = [
            ("LAUNCH50", 50.0, 0.0, expiry.isoformat(), 500),
            ("WELCOME20", 20.0, 0.0, expiry.isoformat(), 1000)
        ]
        cur.executemany("""
        INSERT INTO subscription_coupons (code, discount_percentage, discount_amount, valid_until, max_uses, times_used, is_active)
        VALUES (?, ?, ?, ?, ?, 0, 1)
        """, coupons)

    # Update existing payments to link to restaurant_id = 1
    cur.execute("UPDATE payments SET restaurant_id = 1 WHERE restaurant_id IS NULL")

    conn.commit()
    conn.close()
    print("--- Migration completed successfully ---")

if __name__ == "__main__":
    run_migration()

