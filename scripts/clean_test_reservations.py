import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "backend", "smart_restaurant.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()
rows = c.execute("SELECT id, customer_name, reservation_date, reservation_time FROM reservations WHERE customer_name = 'Lord Robert Crawly'").fetchall()
print("Found test reservations:", rows)
c.execute("DELETE FROM reservations WHERE customer_name = 'Lord Robert Crawly'")
conn.commit()
print("Deleted count:", c.rowcount)
conn.close()
