import os
import sqlite3

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "smart_restaurant.db")
print(f"Connecting to database at: {db_path}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"Found tables: {tables}")

# Check and add columns for restaurants
if "restaurants" in tables:
    existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(restaurants)").fetchall()]
    print(f"Existing columns in restaurants: {existing_cols}")
    
    needed = {
        "slug": "VARCHAR(100)",
        "timezone": "VARCHAR(50) DEFAULT 'Asia/Kolkata'",
        "logo_url": "VARCHAR(500)",
        "cover_image_url": "VARCHAR(500)",
        "primary_color": "VARCHAR(30) DEFAULT '#f97316'",
        "secondary_color": "VARCHAR(30) DEFAULT '#090a0f'",
        "facilities": "TEXT DEFAULT 'High-Speed Wi-Fi, Valet Parking, Wheelchair Accessible, Air Conditioned, Live Music, Outdoor Seating'",
        "service_types": "VARCHAR(255) DEFAULT 'DINE_IN,TAKEAWAY,ROOM_SERVICE,DELIVERY'",
        "razorpay_key_id": "VARCHAR(100)",
        "razorpay_key_secret_enc": "VARCHAR(255)",
        "subscription_plan": "VARCHAR(50) DEFAULT 'PRO'",
        "subscription_status": "VARCHAR(50) DEFAULT 'ACTIVE'",
        "owner_id": "INTEGER"
    }
    for col, coltype in needed.items():
        if col not in existing_cols:
            print(f"Adding column {col} to restaurants")
            cursor.execute(f"ALTER TABLE restaurants ADD COLUMN {col} {coltype}")

    # Set default slug for existing restaurant
    cursor.execute("UPDATE restaurants SET slug = 'royal-saffron' WHERE slug IS NULL OR slug = ''")

# Check and add columns for users
if "users" in tables:
    existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(users)").fetchall()]
    print(f"Existing columns in users: {existing_cols}")
    
    if "shift" not in existing_cols:
        print("Adding column shift to users")
        cursor.execute("ALTER TABLE users ADD COLUMN shift VARCHAR(50) DEFAULT 'General Shift'")

# Check and add columns for tables
if "tables" in tables:
    existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(tables)").fetchall()]
    print(f"Existing columns in tables: {existing_cols}")
    
    if "service_type" not in existing_cols:
        print("Adding column service_type to tables")
        cursor.execute("ALTER TABLE tables ADD COLUMN service_type VARCHAR(50) DEFAULT 'TABLE'")

# Check and add columns for menu_items
if "menu_items" in tables:
    existing_cols = [c[1] for c in cursor.execute("PRAGMA table_info(menu_items)").fetchall()]
    print(f"Existing columns in menu_items: {existing_cols}")
    
    if "restaurant_id" not in existing_cols:
        print("Adding column restaurant_id to menu_items")
        cursor.execute("ALTER TABLE menu_items ADD COLUMN restaurant_id INTEGER DEFAULT 1")
    else:
        cursor.execute("UPDATE menu_items SET restaurant_id = 1 WHERE restaurant_id IS NULL")

# Create feedbacks table if not exists
if "feedbacks" not in tables:
    print("Creating feedbacks table")
    cursor.execute("""
    CREATE TABLE feedbacks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        restaurant_id INTEGER NOT NULL REFERENCES restaurants(id),
        order_id INTEGER REFERENCES orders(id),
        table_id INTEGER REFERENCES tables(id),
        customer_name VARCHAR(100) DEFAULT 'Guest',
        overall_rating INTEGER NOT NULL,
        food_rating INTEGER,
        service_rating INTEGER,
        ambience_rating INTEGER,
        cleanliness_rating INTEGER,
        comment TEXT,
        is_published BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_feedbacks_restaurant_id ON feedbacks(restaurant_id)")

conn.commit()
conn.close()
print("Migration completed successfully!")
