import sqlite3
import os

DB_PATH = "backend/smart_restaurant.db"

def run_migration():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("--- Migrating Customer Feedback & Restaurant Rating System ---")

    # 1. Update restaurants table with google_review_url & allow_feedback_edits
    cur.execute("PRAGMA table_info(restaurants)")
    rest_cols = [c[1] for c in cur.fetchall()]
    if "google_review_url" not in rest_cols:
        print("Adding column 'google_review_url' to restaurants...")
        cur.execute("ALTER TABLE restaurants ADD COLUMN google_review_url VARCHAR(500)")
    if "allow_feedback_edits" not in rest_cols:
        print("Adding column 'allow_feedback_edits' to restaurants...")
        cur.execute("ALTER TABLE restaurants ADD COLUMN allow_feedback_edits BOOLEAN DEFAULT 0")

    # Seed an example google_review_url for The Royal Saffron
    cur.execute("""
        UPDATE restaurants 
        SET google_review_url = 'https://g.page/r/the-royal-saffron-mumbai/review'
        WHERE id = 1 AND (google_review_url IS NULL OR google_review_url = '')
    """)

    # 2. Update feedbacks table
    cur.execute("PRAGMA table_info(feedbacks)")
    fb_cols = [c[1] for c in cur.fetchall()]
    new_fb_cols = [
        ("customer_phone", "VARCHAR(50)"),
        ("status", "VARCHAR(50) DEFAULT 'APPROVED'"),
        ("is_verified_dining", "BOOLEAN DEFAULT 1"),
        ("flag_reason", "TEXT"),
        ("moderated_by_id", "INTEGER"),
        ("moderated_at", "DATETIME"),
        ("updated_at", "DATETIME")
    ]
    for col_name, col_type in new_fb_cols:
        if col_name not in fb_cols:
            print(f"Adding '{col_name}' to feedbacks...")
            cur.execute(f"ALTER TABLE feedbacks ADD COLUMN {col_name} {col_type}")

    # 3. Create feedback_dish_ratings table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback_dish_ratings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feedback_id INTEGER NOT NULL,
        menu_item_id INTEGER,
        dish_name VARCHAR(150) NOT NULL,
        rating INTEGER NOT NULL,
        comment TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (feedback_id) REFERENCES feedbacks (id) ON DELETE CASCADE,
        FOREIGN KEY (menu_item_id) REFERENCES menu_items (id) ON DELETE SET NULL
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_fdr_feedback_id ON feedback_dish_ratings (feedback_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS ix_fdr_menu_item_id ON feedback_dish_ratings (menu_item_id)")

    # 4. Create feedback_photos table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback_photos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feedback_id INTEGER NOT NULL,
        photo_url VARCHAR(500) NOT NULL,
        file_size_bytes INTEGER DEFAULT 0,
        mime_type VARCHAR(50) DEFAULT 'image/jpeg',
        moderation_status VARCHAR(50) DEFAULT 'APPROVED',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (feedback_id) REFERENCES feedbacks (id) ON DELETE CASCADE
    )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS ix_fp_feedback_id ON feedback_photos (feedback_id)")

    conn.commit()
    conn.close()
    print("--- Feedback & Rating Migration completed successfully ---")

if __name__ == "__main__":
    run_migration()
