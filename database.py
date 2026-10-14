"""
قاعدة بيانات منصة Rami Cyber Academy
تشمل: المستخدمين، المنتجات، الطلبات، المدفوعات، الكوبونات، التقييمات، الدعم
"""

import sqlite3
from datetime import datetime, timezone
from config import DB_PATH


# ============================================================
# الاتصال بقاعدة البيانات
# ============================================================
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ============================================================
# إنشاء الجداول
# ============================================================
def init_db():
    """ينشئ كل الجداول إن لم تكن موجودة (آمن للتشغيل المتكرر)."""
    with db() as conn:
        # 👥 المستخدمون
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                balance REAL DEFAULT 0,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                is_banned INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        # 📚 المنتجات (كتب + دورات)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('book', 'course')),
                title TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL DEFAULT 0,
                category TEXT,
                level TEXT CHECK(level IN ('beginner', 'intermediate', 'advanced') OR level IS NULL),
                file_path TEXT,
                cover_image TEXT,
                stock INTEGER DEFAULT 999,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        # 🛒 الطلبات
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_code TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                total REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                final_total REAL NOT NULL DEFAULT 0,
                coupon_code TEXT,
                status TEXT NOT NULL DEFAULT 'pending_payment'
                    CHECK(status IN ('pending_payment','paid','delivered','cancelled')),
                payment_method TEXT,
                payment_proof TEXT,
                admin_note TEXT,
                created_at TEXT NOT NULL,
                paid_at TEXT,
                delivered_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        # 📦 عناصر الطلب
        conn.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                price REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # 💳 طرق الدفع
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_methods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                details TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        # 🎟️ الكوبونات
        conn.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_percent REAL DEFAULT 0,
                discount_amount REAL DEFAULT 0,
                max_uses INTEGER DEFAULT 100,
                used_count INTEGER DEFAULT 0,
                expires_at TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        # 🎓 تسجيلات الدورات
        conn.execute("""
            CREATE TABLE IF NOT EXISTS course_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                completed_at TEXT,
                certificate_issued INTEGER DEFAULT 0,
                enrolled_at TEXT NOT NULL,
                UNIQUE(user_id, product_id)
            )
        """)

        # 📝 التقييمات
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, product_id)
            )
        """)

        # 🛒 سلة المشتريات
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cart_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 1,
                added_at TEXT NOT NULL,
                UNIQUE(user_id, product_id)
            )
        """)

        # 📩 رسائل الدعم
        conn.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT,
                body TEXT NOT NULL,
                status TEXT DEFAULT 'open'
                    CHECK(status IN ('open','replied','closed')),
                admin_reply TEXT,
                created_at TEXT NOT NULL,
                replied_at TEXT
            )
        """)

        # ⚙️ الإعدادات العامة
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

    # إضافة طرق دفع افتراضية إذا ما في
    _seed_payment_methods()
    _seed_settings()


def _seed_payment_methods():
    """يضيف طرق دفع افتراضية (مرة واحدة)."""
    defaults = [
        ("فودافون كاش", "09XXXXXXXX - الاسم: رامي"),
        ("زين كاش", "07XXXXXXXX - الاسم: رامي"),
        ("USDT (TRC20)", "أرسل رسالة للأدمن لمعرفة العنوان"),
    ]
    with db() as conn:
        for name, details in defaults:
            conn.execute(
                "INSERT OR IGNORE INTO payment_methods (name, details) VALUES (?, ?)",
                (name, details),
            )


def _seed_settings():
    """قيم إعدادات افتراضية."""
    defaults = {
        "platform_name": "Rami Cyber Academy",
        "welcome_message": "أهلاً بك في منصة رامي للأمن السيبراني 🛡️",
        "support_username": "@RamiSupport",
    }
    with db() as conn:
        for k, v in defaults.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))


# ============================================================
# 👥 المستخدمون
# ============================================================
def save_user(user_id, username, full_name, phone=None):
    """يضيف أو يحدّث مستخدم."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        existing = conn.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET username=?, full_name=? WHERE user_id=?",
                (username or "", full_name or "", user_id),
            )
        else:
            # إنشاء كود إحالة فريد
            ref_code = f"REF{user_id % 1000000}"
            conn.execute(
                """INSERT INTO users (user_id, username, full_name, phone, referral_code, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, username or "", full_name or "", phone, ref_code, now),
            )


def get_user(user_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def count_users():
    with db() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


# ============================================================
# 📚 المنتجات
# ============================================================
def add_product(type_, title, description, price, category=None,
                level=None, file_path=None, cover_image=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO products
               (type, title, description, price, category, level, file_path, cover_image, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (type_, title, description, price, category, level, file_path, cover_image, now),
        )
        return cur.lastrowid


def get_product(product_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
    return dict(row) if row else None


def get_products(type_=None, category=None, only_active=True, limit=50):
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    if only_active:
        query += " AND is_active=1"
    if type_:
        query += " AND type=?"
        params.append(type_)
    if category:
        query += " AND category=?"
        params.append(category)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_product(product_id, **fields):
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [product_id]
    with db() as conn:
        conn.execute(f"UPDATE products SET {sets} WHERE id=?", values)


def delete_product(product_id):
    with db() as conn:
        conn.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))


def count_products():
    with db() as conn:
        return conn.execute("SELECT COUNT(*) c FROM products WHERE is_active=1").fetchone()["c"]


# ============================================================
# 🛒 سلة المشتريات
# ============================================================
def add_to_cart(user_id, product_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO cart_items (user_id, product_id, added_at)
               VALUES (?, ?, ?)""",
            (user_id, product_id, now),
        )


def get_cart(user_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT c.id as cart_id, c.quantity, p.*
            FROM cart_items c
            JOIN products p ON p.id = c.product_id
            WHERE c.user_id=?
            ORDER BY c.added_at DESC
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


def cart_count(user_id):
    with db() as conn:
        return conn.execute(
            "SELECT COALESCE(SUM(quantity),0) c FROM cart_items WHERE user_id=?",
            (user_id,),
        ).fetchone()["c"]


def remove_from_cart(user_id, product_id):
    with db() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?", (user_id, product_id))


def clear_cart(user_id):
    with db() as conn:
        conn.execute("DELETE FROM cart_items WHERE user_id=?", (user_id,))


# ============================================================
# 🛒 الطلبات
# ============================================================
def create_order(user_id, items, payment_method, coupon_code=None):
    """
    items: list of dicts [{"product_id", "title", "price", "quantity"}]
    """
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total = sum(i["price"] * i["quantity"] for i in items)
    discount = 0.0

    if coupon_code:
        coupon = get_coupon(coupon_code)
        if coupon and coupon["is_active"]:
            if coupon["discount_percent"]:
                discount = total * (coupon["discount_percent"] / 100.0)
            elif coupon["discount_amount"]:
                discount = min(coupon["discount_amount"], total)
            increment_coupon_use(coupon_code)

    final_total = max(total - discount, 0)

    with db() as conn:
        # كود طلب فريد
        last = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        order_code = f"ORD-{datetime.now().year}-{last + 1:04d}"

        cur = conn.execute("""
            INSERT INTO orders
            (order_code, user_id, total, discount, final_total, coupon_code,
             payment_method, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_payment', ?)
        """, (order_code, user_id, total, discount, final_total,
              coupon_code, payment_method, now))
        order_id = cur.lastrowid

        for it in items:
            conn.execute("""
                INSERT INTO order_items (order_id, product_id, title, price, quantity)
                VALUES (?, ?, ?, ?, ?)
            """, (order_id, it["product_id"], it["title"], it["price"], it["quantity"]))

    return order_id, order_code


def get_order(order_id):
    with db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    return dict(row) if row else None


def get_order_by_code(code):
    with db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_code=?", (code,)).fetchone()
    return dict(row) if row else None


def get_order_items(order_id):
    with db() as conn:
        rows = conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()
    return [dict(r) for r in rows]


def get_orders(status=None, user_id=None, limit=50):
    query = "SELECT * FROM orders WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    if user_id:
        query += " AND user_id=?"
        params.append(user_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_order_status(order_id, status, admin_note=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    fields = {"status": status}
    if status == "paid":
        fields["paid_at"] = now
    if status == "delivered":
        fields["delivered_at"] = now
    if admin_note is not None:
        fields["admin_note"] = admin_note

    sets = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [order_id]
    with db() as conn:
        conn.execute(f"UPDATE orders SET {sets} WHERE id=?", values)


def attach_payment_proof(order_id, file_id):
    with db() as conn:
        conn.execute("UPDATE orders SET payment_proof=? WHERE id=?", (file_id, order_id))


def count_orders(status=None):
    with db() as conn:
        if status:
            return conn.execute("SELECT COUNT(*) c FROM orders WHERE status=?", (status,)).fetchone()["c"]
        return conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]


# ============================================================
# 💳 طرق الدفع
# ============================================================
def get_payment_methods():
    with db() as conn:
        rows = conn.execute("SELECT * FROM payment_methods WHERE is_active=1").fetchall()
    return [dict(r) for r in rows]


# ============================================================
# 🎟️ الكوبونات
# ============================================================
def create_coupon(code, discount_percent=0, discount_amount=0, max_uses=100, expires_at=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("""
            INSERT INTO coupons (code, discount_percent, discount_amount, max_uses, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (code.upper(), discount_percent, discount_amount, max_uses, expires_at, now))


def get_coupon(code):
    with db() as conn:
        row = conn.execute("SELECT * FROM coupons WHERE code=?", (code.upper(),)).fetchone()
    return dict(row) if row else None


def increment_coupon_use(code):
    with db() as conn:
        conn.execute("UPDATE coupons SET used_count = used_count + 1 WHERE code=?", (code.upper(),))


def list_coupons():
    with db() as conn:
        rows = conn.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ============================================================
# 🎓 تسجيلات الدورات
# ============================================================
def enroll_course(user_id, product_id):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO course_enrollments (user_id, product_id, enrolled_at)
            VALUES (?, ?, ?)
        """, (user_id, product_id, now))


def get_user_courses(user_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT e.*, p.title, p.description
            FROM course_enrollments e
            JOIN products p ON p.id = e.product_id
            WHERE e.user_id=?
            ORDER BY e.enrolled_at DESC
        """, (user_id,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# 📝 التقييمات
# ============================================================
def add_review(user_id, product_id, rating, comment=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO reviews (user_id, product_id, rating, comment, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, product_id, rating, comment, now))


def get_product_reviews(product_id):
    with db() as conn:
        rows = conn.execute("""
            SELECT r.*, u.full_name, u.username
            FROM reviews r
            LEFT JOIN users u ON u.user_id = r.user_id
            WHERE r.product_id=?
            ORDER BY r.created_at DESC
        """, (product_id,)).fetchall()
    return [dict(r) for r in rows]


def get_product_rating(product_id):
    with db() as conn:
        row = conn.execute("""
            SELECT AVG(rating) avg_r, COUNT(*) c
            FROM reviews WHERE product_id=?
        """, (product_id,)).fetchone()
    return {
        "avg": round(row["avg_r"], 1) if row["avg_r"] else 0,
        "count": row["c"],
    }


# ============================================================
# 📩 الدعم
# ============================================================
def create_support_message(user_id, body, subject=None):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO support_messages (user_id, subject, body, created_at)
            VALUES (?, ?, ?, ?)
        """, (user_id, subject, body, now))
        return cur.lastrowid


def reply_support_message(msg_id, reply):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        conn.execute("""
            UPDATE support_messages SET admin_reply=?, status='replied', replied_at=?
            WHERE id=?
        """, (reply, now, msg_id))


def get_support_messages(status=None, limit=50):
    query = "SELECT * FROM support_messages WHERE 1=1"
    params = []
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with db() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# ⚙️ الإعدادات
# ============================================================
def get_setting(key, default=None):
    with db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))


# ============================================================
# 📊 الإحصائيات
# ============================================================
def get_stats():
    with db() as conn:
        total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        total_products = conn.execute("SELECT COUNT(*) c FROM products WHERE is_active=1").fetchone()["c"]
        total_orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        pending_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='pending_payment'").fetchone()["c"]
        paid_orders = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='paid'").fetchone()["c"]
        delivered = conn.execute("SELECT COUNT(*) c FROM orders WHERE status='delivered'").fetchone()["c"]
        revenue = conn.execute("SELECT COALESCE(SUM(final_total),0) s FROM orders WHERE status IN ('paid','delivered')").fetchone()["s"]
    return {
        "users": total_users,
        "products": total_products,
        "orders": total_orders,
        "pending": pending_orders,
        "paid": paid_orders,
        "delivered": delivered,
        "revenue": revenue,
    }


# ============================================================
# 🧪 اختبار سريع (عند التشغيل المباشر)
# ============================================================
if __name__ == "__main__":
    init_db()
    print("✅ تم إنشاء قاعدة البيانات بنجاح!")
    print("📊 الإحصائيات:", get_stats())