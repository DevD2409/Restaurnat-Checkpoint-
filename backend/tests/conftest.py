"""Pytest session initialization for SRMP backend tests."""

import os
import pytest
from app.core.database import Base, SessionLocal, engine
from app.models.user import User
from app.utils.seed_data import seed_database


_TEST_FIXTURE_ENV = {
    "SUPERADMIN_INITIAL_PASSWORD": "superadmin123",
    "SEED_DEMO_ADMIN_PASSWORD": "admin123",
    "SEED_DEMO_MANAGER_PASSWORD": "manager123",
    "SEED_DEMO_WAITER_PASSWORD": "waiter123",
    "SEED_DEMO_CHEF_PASSWORD": "chef123",
    "SEED_DEMO_CASHIER_PASSWORD": "cashier123",
}


@pytest.fixture(scope="session", autouse=True)
def ensure_test_database_seeded():
    """
    Create schema and seed non-production test fixtures only when the database is empty.
    Leaves an existing local smart_restaurant.db untouched.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        has_users = db.query(User.id).first() is not None
    finally:
        db.close()

    if has_users:
        return

    previous = {k: os.environ.get(k) for k in _TEST_FIXTURE_ENV}
    os.environ.update(_TEST_FIXTURE_ENV)
    try:
        seed_database()
    finally:
        for key, old_val in previous.items():
            if old_val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_val
