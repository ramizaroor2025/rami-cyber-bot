"""يضيف منتجات تجريبية + كوبونات للاختبار (آمن للتشغيل المتكرر)."""
import database as db

db.init_db()

# احذف المنتجات القديمة
with db.db() as conn:
    conn.execute("DELETE FROM products")
    conn.execute("DELETE FROM coupons")
    print("🗑️ تم حذف المنتجات والكوبونات القديمة")

# 📚 كتب
books = [
    ("book", "أساسيات الأمن السيبراني", "كتاب شامل يشرح أساسيات الأمن السيبراني من الصفر حتى الاحتراف.", 15.0, "أساسيات", "beginner"),
    ("book", "الاختراق الأخلاقي", "دليل عملي لاختبار الاختراق باستخدام Kali Linux وأدواته.", 25.0, "اختراق", "intermediate"),
    ("book", "التشفير وعلم التعمية", "شرح مفصل للتشفير المتماثل وغير المتماثل وخوارزمياته.", 20.0, "تشفير", "advanced"),
]

# 🎓 دورات
courses = [
    ("course", "مقدمة في الأمن السيبراني", "دورة تأسيسية تشرح المفاهيم الأساسية والمصطلحات.", 50.0, "أساسيات", "beginner"),
    ("course", "اختبار الاختراق الاحترافي", "دورة متقدمة تغطي OWASP Top 10 و Metasploit و Burp Suite.", 120.0, "اختراق", "advanced"),
    ("course", "تحليل البرمجيات الخبيثة", "دورة متخصصة في تحليل Malware وعزلها.", 90.0, "تحليل جنائي", "advanced"),
]

for type_, title, desc, price, cat, level in books + courses:
    pid = db.add_product(type_, title, desc, price, cat, level)
    print(f"✅ أضفت: {title} (ID={pid})")

# 🎟️ كوبونات
db.create_coupon("CYBER20", discount_percent=20, max_uses=100)
db.create_coupon("WELCOME10", discount_percent=10, max_uses=200)
print("✅ أضفت كوبونات: CYBER20 (20%)، WELCOME10 (10%)")

print(f"\n📊 الإحصائيات: {db.get_stats()}")