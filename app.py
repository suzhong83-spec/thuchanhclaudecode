import re
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "coffeeshop.db"
PRODUCT_IMAGE_DIR = BASE_DIR / "static" / "images" / "products"
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

ORDER_STATUSES = ["pending", "confirmed", "completed", "cancelled"]
ORDER_STATUS_LABELS = {
    "pending": "Chờ xác nhận",
    "confirmed": "Đã xác nhận",
    "completed": "Hoàn thành",
    "cancelled": "Đã hủy",
}

PHONE_PATTERN = re.compile(r"^[0-9]{9,11}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

app = Flask(__name__)
app.secret_key = "dev-only-secret-key-change-in-production"


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db_if_needed():
    if DB_PATH.exists():
        return
    from seed_data import seed

    seed()


@app.template_filter("vnd")
def format_vnd(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value
    return f"{value:,.0f}".replace(",", ".") + "₫"


@app.template_filter("datetimevi")
def format_datetimevi(value):
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return dt.strftime("%d/%m/%Y %H:%M")


@app.template_filter("username")
def format_username(email):
    if not email or "@" not in email:
        return email
    return email.split("@", 1)[0]


@app.context_processor
def inject_order_status_meta():
    return {"ORDER_STATUSES": ORDER_STATUSES, "ORDER_STATUS_LABELS": ORDER_STATUS_LABELS}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/products")
def products_page():
    return render_template("products.html")


@app.route("/contact")
def contact_page():
    return render_template("contact.html")


@app.route("/api/categories")
def api_categories():
    db = get_db()
    rows = db.execute("SELECT id, name, description FROM category ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/products")
def api_products():
    db = get_db()
    category_id = request.args.get("category_id")
    if category_id and category_id != "all":
        rows = db.execute(
            "SELECT * FROM product WHERE category_id = ? ORDER BY published_date DESC",
            (category_id,),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM product ORDER BY published_date DESC").fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/contact", methods=["POST"])
def api_contact():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip()
    message = (data.get("message") or "").strip()

    if not name or not email or len(message) < 10:
        return jsonify({"error": "Dữ liệu không hợp lệ."}), 400

    db = get_db()
    db.execute(
        "INSERT INTO feedback (name, email, message, created_at) VALUES (?, ?, ?, ?)",
        (name, email, message, datetime.now().isoformat()),
    )
    db.commit()
    return jsonify({"message": f"Cảm ơn {name}, chúng tôi đã nhận được góp ý của bạn!"})


@app.route("/api/orders", methods=["POST"])
def api_create_order():
    data = request.get_json(silent=True) or {}
    name = (data.get("customer_name") or "").strip()
    phone = (data.get("customer_phone") or "").strip()
    email = (data.get("customer_email") or "").strip()
    note = (data.get("note") or "").strip()
    raw_items = data.get("items") or []

    if not name:
        return jsonify({"error": "Vui lòng nhập họ tên."}), 400
    if not PHONE_PATTERN.match(phone):
        return jsonify({"error": "Số điện thoại không hợp lệ."}), 400
    if email and not EMAIL_PATTERN.match(email):
        return jsonify({"error": "Email không hợp lệ."}), 400
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"error": "Giỏ hàng đang trống."}), 400

    db = get_db()
    total = 0
    item_rows = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        try:
            product_id = int(raw.get("product_id"))
            quantity = int(raw.get("quantity"))
        except (TypeError, ValueError):
            continue
        if quantity <= 0:
            continue
        product = db.execute("SELECT id, name, price FROM product WHERE id = ?", (product_id,)).fetchone()
        if product is None:
            continue
        total += product["price"] * quantity
        item_rows.append((product["id"], product["name"], product["price"], quantity))

    if not item_rows:
        return jsonify({"error": "Không có sản phẩm hợp lệ trong giỏ hàng."}), 400

    cur = db.execute(
        """INSERT INTO orders (user_id, customer_name, customer_email, customer_phone, status, total_amount, note, created_at)
           VALUES (NULL, ?, ?, ?, 'pending', ?, ?, ?)""",
        (name, email or None, phone, total, note or None, datetime.now().isoformat()),
    )
    order_id = cur.lastrowid
    db.executemany(
        """INSERT INTO order_item (order_id, product_id, product_name, price, quantity)
           VALUES (?, ?, ?, ?, ?)""",
        [(order_id, *item) for item in item_rows],
    )
    db.commit()

    return jsonify({"order_id": order_id, "message": "Đặt hàng thành công!"})


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin_dashboard"))

    error = None
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""

        db = get_db()
        user = db.execute("SELECT * FROM user WHERE email = ? AND is_admin = 1", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["is_admin"] = True
            session["admin_name"] = user["name"]
            return redirect(request.args.get("next") or url_for("admin_dashboard"))

        error = "Email hoặc mật khẩu không đúng."

    return render_template("admin/login.html", error=error)


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    db = get_db()

    total_orders = db.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_revenue = db.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'completed'"
    ).fetchone()[0]
    total_customers = db.execute("SELECT COUNT(*) FROM user WHERE is_admin = 0").fetchone()[0]
    total_products = db.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    pending_orders = db.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'").fetchone()[0]

    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    revenue_30d = db.execute(
        "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'completed' AND created_at >= ?",
        (thirty_days_ago,),
    ).fetchone()[0]
    orders_30d = db.execute(
        "SELECT COUNT(*) FROM orders WHERE created_at >= ?", (thirty_days_ago,)
    ).fetchone()[0]

    recent_orders = db.execute(
        """SELECT id, customer_name, status, total_amount, created_at
           FROM orders ORDER BY created_at DESC LIMIT 8"""
    ).fetchall()

    top_products = db.execute(
        """SELECT product_name, SUM(quantity) AS qty, SUM(price * quantity) AS revenue
           FROM order_item
           JOIN orders ON orders.id = order_item.order_id
           WHERE orders.status = 'completed'
           GROUP BY product_name
           ORDER BY qty DESC
           LIMIT 5"""
    ).fetchall()

    stats = {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "total_customers": total_customers,
        "total_products": total_products,
        "pending_orders": pending_orders,
        "revenue_30d": revenue_30d,
        "orders_30d": orders_30d,
    }

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_orders=recent_orders,
        top_products=top_products,
        active_page="dashboard",
    )


def save_product_image(file_storage):
    """Save an uploaded product image and return its DB-relative path, or None if absent/invalid."""
    if not file_storage or not file_storage.filename:
        return None

    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False

    filename = secure_filename(file_storage.filename)
    unique_name = f"{int(datetime.now().timestamp() * 1000)}_{filename}"
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    file_storage.save(PRODUCT_IMAGE_DIR / unique_name)
    return f"images/products/{unique_name}"


def validate_product_form(form_data):
    errors = {}

    name = (form_data.get("name") or "").strip()
    if not name:
        errors["name"] = "Vui lòng nhập tên sản phẩm."

    price_raw = (form_data.get("price") or "").strip()
    price_value = None
    if not price_raw.isdigit() or int(price_raw) <= 0:
        errors["price"] = "Giá phải là số nguyên dương."
    else:
        price_value = int(price_raw)

    category_id = form_data.get("category_id") or ""
    if not category_id:
        errors["category_id"] = "Vui lòng chọn danh mục."

    return errors, name, price_value, category_id


@app.route("/admin/products")
@admin_required
def admin_products():
    db = get_db()
    q = (request.args.get("q") or "").strip()
    category_id = request.args.get("category_id") or ""

    query = """SELECT product.*, category.name AS category_name
               FROM product JOIN category ON category.id = product.category_id
               WHERE 1=1"""
    params = []
    if q:
        query += " AND product.name LIKE ?"
        params.append(f"%{q}%")
    if category_id:
        query += " AND product.category_id = ?"
        params.append(category_id)
    query += " ORDER BY product.published_date DESC"

    products = db.execute(query, params).fetchall()
    categories = db.execute("SELECT id, name FROM category ORDER BY name").fetchall()

    return render_template(
        "admin/products.html",
        products=products,
        categories=categories,
        q=q,
        selected_category=category_id,
        active_page="products",
    )


@app.route("/admin/products/new", methods=["GET", "POST"])
@admin_required
def admin_product_new():
    db = get_db()
    categories = db.execute("SELECT id, name FROM category ORDER BY name").fetchall()
    errors = {}
    form = {"name": "", "price": "", "category_id": "", "description": ""}

    if request.method == "POST":
        form = {
            "name": request.form.get("name") or "",
            "price": request.form.get("price") or "",
            "category_id": request.form.get("category_id") or "",
            "description": request.form.get("description") or "",
        }
        errors, name, price_value, category_id = validate_product_form(request.form)

        image_path = save_product_image(request.files.get("image"))
        if image_path is False:
            errors["image"] = "Định dạng ảnh không hợp lệ (chỉ nhận jpg, png, gif, webp)."
            image_path = None

        if not errors:
            db.execute(
                """INSERT INTO product (name, price, image, description, published_date, category_id)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, price_value, image_path, form["description"], datetime.now().isoformat(), category_id),
            )
            db.commit()
            return redirect(url_for("admin_products"))

    return render_template(
        "admin/product_form.html",
        categories=categories,
        form=form,
        errors=errors,
        mode="new",
        product=None,
        active_page="products",
    )


@app.route("/admin/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_product_edit(product_id):
    db = get_db()
    product = db.execute("SELECT * FROM product WHERE id = ?", (product_id,)).fetchone()
    if product is None:
        abort(404)

    categories = db.execute("SELECT id, name FROM category ORDER BY name").fetchall()
    errors = {}
    form = {
        "name": product["name"],
        "price": str(product["price"]),
        "category_id": str(product["category_id"]),
        "description": product["description"] or "",
    }

    if request.method == "POST":
        form = {
            "name": request.form.get("name") or "",
            "price": request.form.get("price") or "",
            "category_id": request.form.get("category_id") or "",
            "description": request.form.get("description") or "",
        }
        errors, name, price_value, category_id = validate_product_form(request.form)

        image_path = save_product_image(request.files.get("image"))
        if image_path is False:
            errors["image"] = "Định dạng ảnh không hợp lệ (chỉ nhận jpg, png, gif, webp)."
            image_path = product["image"]
        elif image_path is None:
            image_path = product["image"]

        if not errors:
            db.execute(
                """UPDATE product SET name = ?, price = ?, image = ?, description = ?, category_id = ?
                   WHERE id = ?""",
                (name, price_value, image_path, form["description"], category_id, product_id),
            )
            db.commit()
            return redirect(url_for("admin_products"))

    return render_template(
        "admin/product_form.html",
        categories=categories,
        form=form,
        errors=errors,
        mode="edit",
        product=product,
        active_page="products",
    )


@app.route("/admin/products/<int:product_id>/delete", methods=["POST"])
@admin_required
def admin_product_delete(product_id):
    db = get_db()
    db.execute("DELETE FROM product WHERE id = ?", (product_id,))
    db.commit()
    return redirect(
        url_for(
            "admin_products",
            q=request.form.get("q") or None,
            category_id=request.form.get("category_id") or None,
        )
    )


@app.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_db()
    status = request.args.get("status") or ""

    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status in ORDER_STATUSES:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"

    orders = db.execute(query, params).fetchall()

    return render_template(
        "admin/orders.html",
        orders=orders,
        selected_status=status,
        active_page="orders",
    )


@app.route("/admin/orders/<int:order_id>")
@admin_required
def admin_order_detail(order_id):
    db = get_db()
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        abort(404)

    items = db.execute("SELECT * FROM order_item WHERE order_id = ? ORDER BY id", (order_id,)).fetchall()

    return render_template(
        "admin/order_detail.html",
        order=order,
        items=items,
        active_page="orders",
    )


@app.route("/admin/orders/<int:order_id>/status", methods=["POST"])
@admin_required
def admin_order_status(order_id):
    db = get_db()
    order = db.execute("SELECT id FROM orders WHERE id = ?", (order_id,)).fetchone()
    if order is None:
        abort(404)

    new_status = request.form.get("status") or ""
    if new_status in ORDER_STATUSES:
        db.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        db.commit()

    if request.form.get("redirect_to") == "list":
        return redirect(url_for("admin_orders", status=request.form.get("status_filter") or None))

    return redirect(url_for("admin_order_detail", order_id=order_id))


@app.route("/admin/customers")
@admin_required
def admin_customers():
    db = get_db()
    q = (request.args.get("q") or "").strip()

    query = """
        SELECT
            user.*,
            COUNT(orders.id) AS order_count,
            COALESCE(SUM(CASE WHEN orders.status = 'completed' THEN orders.total_amount ELSE 0 END), 0) AS total_spent
        FROM user
        LEFT JOIN orders ON orders.user_id = user.id
        WHERE user.is_admin = 0
    """
    params = []
    if q:
        query += " AND (user.name LIKE ? OR user.email LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])
    query += " GROUP BY user.id ORDER BY user.created_at DESC"

    customers = db.execute(query, params).fetchall()

    return render_template(
        "admin/customers.html",
        customers=customers,
        q=q,
        active_page="customers",
    )


@app.route("/admin/customers/<int:customer_id>")
@admin_required
def admin_customer_detail(customer_id):
    db = get_db()
    customer = db.execute(
        "SELECT * FROM user WHERE id = ? AND is_admin = 0", (customer_id,)
    ).fetchone()
    if customer is None:
        abort(404)

    orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (customer_id,)
    ).fetchall()

    order_count = len(orders)
    total_spent = sum(o["total_amount"] for o in orders if o["status"] == "completed")

    return render_template(
        "admin/customer_detail.html",
        customer=customer,
        orders=orders,
        order_count=order_count,
        total_spent=total_spent,
        active_page="customers",
    )


init_db_if_needed()

if __name__ == "__main__":
    app.run(debug=True)
