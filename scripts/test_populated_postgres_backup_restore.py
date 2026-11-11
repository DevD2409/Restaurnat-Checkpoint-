#!/usr/bin/env python3
"""
Test Populated PostgreSQL Backup & Restore with Complete Multi-Tenant Entity Sets:
- Restaurants, Tables, Staff Users, Menu Categories, Menu Items
- Orders, Order Items, Bills, Payments
- SaaS Subscription Plans, Coupons, Invoices, Subscription Payments
- Customer Feedbacks, Dish Ratings, Feedback Photos
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BACKEND_DIR))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pgserver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic.config import Config
from alembic import command

from app.models.restaurant import Restaurant
from app.models.user import User, UserRole
from app.models.table import Table, TableStatus
from app.models.menu import MenuCategory, MenuItem
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus as OrdPayStatus
from app.models.billing import Bill, Payment, BillStatus, PaymentRecordStatus
from app.models.subscription import (
    SubscriptionPlan, SubscriptionCoupon, SubscriptionInvoice,
    SubscriptionPayment, SubscriptionCouponRedemption
)
from app.models.feedback import Feedback, FeedbackDishRating, FeedbackPhoto
from app.utils.seed_data import seed_database
from scripts.backup_db import backup_postgres, compute_sha256
from scripts.restore_db import restore_postgres

def run_populated_backup_restore_test():
    print("=" * 75)
    print("  SRMP POPULATED POSTGRESQL BACKUP & RESTORATION AUDIT (REQUIREMENT 15)")
    print("=" * 75)

    pg_data_dir = BASE_DIR / "staging_pgdata"
    pg_srv = pgserver.get_server(str(pg_data_dir))
    pg_base_uri = pg_srv.get_uri()
    print(f"[INFO] Connected to PostgreSQL 16 server at: {pg_base_uri}")

    conn = psycopg2.connect(pg_base_uri)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    src_db = "srmp_populated_staging"
    dst_db = "srmp_populated_restore_target"

    for db_name in [src_db, dst_db]:
        cur.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
        if cur.fetchone():
            cur.execute(f"DROP DATABASE {db_name} WITH (FORCE)")
            print(f"[INFO] Dropped existing {db_name}")
        cur.execute(f"CREATE DATABASE {db_name}")
        print(f"[INFO] Created fresh {db_name}")

    cur.close()
    conn.close()

    src_db_url = pg_base_uri.rsplit("/", 1)[0] + f"/{src_db}"
    dst_db_url = pg_base_uri.rsplit("/", 1)[0] + f"/{dst_db}"

    print(f"[INFO] Applying Alembic migration chain online against {src_db_url}...")
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", src_db_url)
    command.upgrade(cfg, "head")
    print("[SUCCESS] Alembic migration head applied!")

    engine = create_engine(src_db_url, pool_pre_ping=True)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()

    print("[INFO] Seeding primary restaurant and foundational entities...")
    seed_database(db=db)

    # 1. Populate SaaS Subscription Plans & Sample Promo Coupon
    print("[INFO] Populating SaaS Subscription plans, coupons, receipts & payments...")
    plan_monthly = SubscriptionPlan(
        plan_code="MONTHLY",
        name="Monthly Plan",
        billing_cycle="MONTHLY",
        price_paise=99900,  # ₹999 tax-inclusive
        currency="INR",
        duration_days=30,
        features="Unlimited Digital Menus, KDS Access, Table Operations, Analytics, All Taxes Included",
        entitlements_json=json.dumps({"max_tables": 100, "kds_access": True, "advanced_analytics": True}),
        max_tables=100,
        is_active=True
    )
    plan_yearly = SubscriptionPlan(
        plan_code="YEARLY",
        name="Yearly Plan",
        billing_cycle="YEARLY",
        price_paise=999900,  # ₹9,999 tax-inclusive
        currency="INR",
        duration_days=365,
        features="All Monthly Features, Unlimited Tables, Priority Onboarding, All Taxes Included",
        entitlements_json=json.dumps({"max_tables": 250, "kds_access": True, "advanced_analytics": True}),
        max_tables=250,
        is_active=True
    )
    db.add(plan_monthly)
    db.add(plan_yearly)
    db.commit()
    db.refresh(plan_monthly)
    db.refresh(plan_yearly)

    coupon_launch = SubscriptionCoupon(
        code="LAUNCH20",
        discount_paise=20000,  # ₹200 off
        discount_type="FIXED_AMOUNT",
        eligible_plan_codes="MONTHLY",
        start_date=datetime.now(timezone.utc) - timedelta(days=5),
        end_date=datetime.now(timezone.utc) + timedelta(days=360),
        max_uses_global=500,
        max_uses_per_restaurant=1,
        is_active=True
    )
    db.add(coupon_launch)
    db.commit()
    db.refresh(coupon_launch)

    rest = db.query(Restaurant).first()
    sub_inv = SubscriptionInvoice(
        invoice_number=f"R2627/001-{int(time.time()) % 90000:05d}",
        restaurant_id=rest.id,
        plan_id=plan_monthly.id,
        billing_cycle="MONTHLY",
        subtotal_paise=99900,
        discount_paise=20000,
        tax_percentage=0.0,
        tax_paise=0,
        final_amount_paise=79900,
        currency="INR",
        status="PAID",
        coupon_id=coupon_launch.id,
        paid_at=datetime.now(timezone.utc)
    )
    db.add(sub_inv)
    db.commit()
    db.refresh(sub_inv)

    sub_pay = SubscriptionPayment(
        invoice_id=sub_inv.id,
        restaurant_id=rest.id,
        amount_paise=79900,
        currency="INR",
        razorpay_order_id=f"order_saas_pop_{int(time.time())}",
        razorpay_payment_id=f"pay_saas_pop_{int(time.time())}",
        razorpay_signature="mock_pop_signature_saas",
        payment_method="RAZORPAY",
        status="SUCCESS"
    )
    db.add(sub_pay)
    db.commit()

    # 2. Populate Customer Feedback & Ratings
    print("[INFO] Populating Customer Feedback, Dish Ratings & Photos...")
    first_order = db.query(Order).first()
    first_table = db.query(Table).filter(Table.restaurant_id == rest.id).first()
    first_item = db.query(MenuItem).filter(MenuItem.restaurant_id == rest.id).first()

    fb = Feedback(
        restaurant_id=rest.id,
        order_id=first_order.id if first_order else None,
        table_id=first_table.id if first_table else None,
        customer_name="Priya Sharma",
        customer_phone="+91 98765 11223",
        food_rating=5,
        service_rating=5,
        ambience_rating=5,
        cleanliness_rating=5,
        overall_rating=5,
        comment="Incredible saffron biryani and attentive hospitality! Highly recommend.",
        status="APPROVED",
        is_published=True,
        is_verified_dining=True
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    if first_item:
        dish_rating = FeedbackDishRating(
            feedback_id=fb.id,
            menu_item_id=first_item.id,
            dish_name=first_item.name,
            rating=5,
            comment="Outstanding flavor profile!"
        )
        db.add(dish_rating)

    fb_photo = FeedbackPhoto(
        feedback_id=fb.id,
        photo_url="https://pub-srmp-media.r2.dev/uploads/feedback/stg_pop_saffron.jpg",
        moderation_status="APPROVED",
        mime_type="image/jpeg"
    )
    db.add(fb_photo)
    db.commit()

    print("[SUCCESS] All multi-tenant entity sets populated successfully in source PostgreSQL!")
    db.close()

    # 3. Create native backup via pg_dump
    print(f"\n[INFO] Executing native pg_dump (-Fc) of populated database {src_db_url}...")
    backup_meta = backup_postgres(src_db_url)
    backup_file = BASE_DIR / "backups" / backup_meta["backup_file"]
    backup_size = backup_file.stat().st_size
    backup_sha = compute_sha256(backup_file)
    print(f"[SUCCESS] Native PostgreSQL dump created: {backup_file.name} ({backup_size} bytes, SHA: {backup_sha[:16]}...)")

    # 4. Restore into clean database via pg_restore
    print(f"[INFO] Restoring dump into isolated PostgreSQL database: {dst_db_url}...")
    restore_postgres(backup_file, dst_db_url)
    print("[SUCCESS] pg_restore executed successfully!")

    # 5. Comparative Audit across ALL 16 core tables
    src_conn = psycopg2.connect(src_db_url)
    dst_conn = psycopg2.connect(dst_db_url)
    src_cur = src_conn.cursor()
    dst_cur = dst_conn.cursor()

    audit_tables = [
        "restaurants", "users", "tables", "menu_categories", "menu_items",
        "orders", "order_items", "bills", "payments",
        "subscription_plans", "subscription_coupons", "subscription_invoices", "subscription_payments",
        "feedbacks", "feedback_dish_ratings", "feedback_photos"
    ]

    print("\n" + "=" * 75)
    print(f"  {'TABLE NAME':<30} | {'SOURCE':<10} | {'RESTORED':<10} | {'STATUS':<15}")
    print("=" * 75)

    comparison_results = {}
    all_matched = True

    for tbl in audit_tables:
        src_cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        s_cnt = src_cur.fetchone()[0]
        dst_cur.execute(f"SELECT COUNT(*) FROM {tbl};")
        d_cnt = dst_cur.fetchone()[0]

        matched = (s_cnt == d_cnt and s_cnt > 0)
        status_str = "MATCH (PASS)" if matched else "MISMATCH (FAIL)"
        if not matched:
            all_matched = False

        comparison_results[tbl] = {
            "source_records": s_cnt,
            "restored_records": d_cnt,
            "matched": (s_cnt == d_cnt)
        }
        print(f"  {tbl:<30} | {s_cnt:<10} | {d_cnt:<10} | {status_str:<15}")

    src_cur.close()
    src_conn.close()
    dst_cur.close()
    dst_conn.close()

    print("=" * 75)
    verdict = "PASS" if all_matched else "FAIL"
    print(f"  OVERALL POPULATED BACKUP & RESTORE VERDICT: {verdict}")
    print("=" * 75)

    result_payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test": "Requirement 15: Populated PostgreSQL Backup and Restoration Audit",
        "verdict": verdict,
        "backup_filename": backup_file.name,
        "backup_size_bytes": backup_size,
        "backup_sha256": backup_sha,
        "table_audits": comparison_results
    }

    out_file = BASE_DIR / "POPULATED_POSTGRES_BACKUP_RESTORE_EVIDENCE.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result_payload, f, indent=2)

    return all_matched

if __name__ == "__main__":
    success = run_populated_backup_restore_test()
    sys.exit(0 if success else 1)
