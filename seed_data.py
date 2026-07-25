"""Seed coffeeshop.db from the original data/category.csv and data/product.csv files."""
import csv
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "coffeeshop.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
CATEGORY_CSV = BASE_DIR / "data" / "category.csv"
PRODUCT_CSV = BASE_DIR / "data" / "product.csv"

ADMIN_EMAIL = "admin@coffeeshop.vn"
ADMIN_PASSWORD = "Admin@123"

SAMPLE_CUSTOMERS = [
    ("Nguyễn Văn An", "an.nguyen@example.com", "0901234501"),
    ("Trần Thị Bình", "binh.tran@example.com", "0901234502"),
    ("Lê Hoàng Cường", "cuong.le@example.com", "0901234503"),
    ("Phạm Thu Dung", "dung.pham@example.com", "0901234504"),
    ("Hoàng Minh Đức", "duc.hoang@example.com", "0901234505"),
    ("Vũ Ngọc Hà", "ha.vu@example.com", "0901234506"),
]

ORDER_STATUSES = ["completed", "completed", "confirmed", "pending", "cancelled"]

SAMPLE_NOTES = [
    "Giao trước 18h giúp mình.",
    "Không cho đường.",
    "Ít đá.",
    "Gọi trước khi giao.",
    "Thêm 1 muỗng đường riêng.",
]


def seed():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    with open(CATEGORY_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        conn.executemany(
            "INSERT INTO category (id, name, description) VALUES (:id, :name, :description)",
            rows,
        )

    with open(PRODUCT_CSV, encoding="utf-8") as f:
        product_rows = list(csv.DictReader(f))
        conn.executemany(
            """INSERT INTO product
               (id, name, price, image, description, published_date, category_id)
               VALUES (:id, :name, :price, :image, :description, :published_date, :category_id)""",
            product_rows,
        )

    now = datetime.now()

    conn.execute(
        "INSERT INTO user (name, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, 1, ?)",
        ("Quản trị viên", ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), now.isoformat()),
    )

    customer_ids = []
    for name, email, phone in SAMPLE_CUSTOMERS:
        cur = conn.execute(
            "INSERT INTO user (name, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, 0, ?)",
            (name, email, generate_password_hash("Customer@123"), now.isoformat()),
        )
        customer_ids.append((cur.lastrowid, name, email, phone))

    products = conn.execute("SELECT id, name, price FROM product").fetchall()

    rng = random.Random(42)
    for _ in range(30):
        user_id, name, email, phone = rng.choice(customer_ids)
        order_items = rng.sample(products, k=rng.randint(1, 3))
        days_ago = rng.randint(0, 89)
        created_at = (now - timedelta(days=days_ago, hours=rng.randint(0, 23))).isoformat()
        status = rng.choice(ORDER_STATUSES)

        total = 0
        item_rows = []
        for prod_id, prod_name, price in order_items:
            qty = rng.randint(1, 3)
            total += price * qty
            item_rows.append((prod_id, prod_name, price, qty))

        note = rng.choice(SAMPLE_NOTES) if rng.random() < 0.4 else None

        cur = conn.execute(
            """INSERT INTO orders (user_id, customer_name, customer_email, customer_phone, status, total_amount, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, email, phone, status, total, note, created_at),
        )
        order_id = cur.lastrowid
        conn.executemany(
            """INSERT INTO order_item (order_id, product_id, product_name, price, quantity)
               VALUES (?, ?, ?, ?, ?)""",
            [(order_id, *item) for item in item_rows],
        )

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with {len(product_rows)} products.")
    print(f"Admin account -> email: {ADMIN_EMAIL}  password: {ADMIN_PASSWORD}")


if __name__ == "__main__":
    seed()
