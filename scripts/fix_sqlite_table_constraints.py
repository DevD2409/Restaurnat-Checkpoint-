import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

for db_path in [BASE_DIR / "backend" / "smart_restaurant.db", BASE_DIR / "smart_restaurant.db"]:
    if not db_path.exists():
        continue
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='tables'")
    row = cur.fetchone()
    if row and row[0]:
        print(f"[{db_path.name}] Table DDL:")
        print(row[0])
        # Check indices
        cur.execute("PRAGMA index_list('tables')")
        indices = cur.fetchall()
        print("Indices:", indices)

        # If table_number has a unique constraint or index that is not composite
        needs_migration = False
        for idx in indices:
            idx_name = idx[1]
            is_unique = idx[2]
            if is_unique and "table_number" in idx_name and "uq_restaurant_table_number" not in idx_name:
                cur.execute(f"PRAGMA index_info('{idx_name}')")
                cols = [c[2] for c in cur.fetchall()]
                if cols == ["table_number"]:
                    print(f"Found non-composite unique index on table_number: {idx_name}")
                    needs_migration = True

        if "table_number VARCHAR(50) UNIQUE" in row[0] or needs_migration:
            print(f"Migrating {db_path.name} to remove global unique constraint on tables.table_number...")
            # Recreate table without single-column unique constraint
            cur.execute("PRAGMA foreign_keys=OFF;")
            cur.execute("""
                CREATE TABLE tables_new (
                    id INTEGER PRIMARY KEY,
                    restaurant_id INTEGER NOT NULL DEFAULT 1,
                    table_number VARCHAR(50) NOT NULL,
                    service_type VARCHAR(50) DEFAULT 'TABLE',
                    capacity INTEGER NOT NULL DEFAULT 4,
                    section VARCHAR(50) DEFAULT 'Main Dining',
                    status VARCHAR(50) NOT NULL DEFAULT 'AVAILABLE',
                    qr_token VARCHAR(255) UNIQUE,
                    pos_x INTEGER DEFAULT 100,
                    pos_y INTEGER DEFAULT 100,
                    current_session_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME,
                    updated_at DATETIME,
                    CONSTRAINT uq_restaurant_table_number UNIQUE (restaurant_id, table_number),
                    FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
                );
            """)
            cur.execute("""
                INSERT INTO tables_new (id, restaurant_id, table_number, service_type, capacity, section, status, qr_token, pos_x, pos_y, current_session_id, is_active, created_at, updated_at)
                SELECT id, restaurant_id, table_number, service_type, capacity, section, status, qr_token, pos_x, pos_y, current_session_id, is_active, created_at, updated_at
                FROM tables;
            """)
            cur.execute("DROP TABLE tables;")
            cur.execute("ALTER TABLE tables_new RENAME TO tables;")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_tables_id ON tables (id);")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_tables_restaurant_id ON tables (restaurant_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS ix_tables_table_number ON tables (table_number);")
            cur.execute("PRAGMA foreign_keys=ON;")
            con.commit()
            print(f"Migration completed successfully for {db_path.name}!")
    con.close()
