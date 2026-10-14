"""
🛡️ Rami Cyber Academy - بوت الزبون
منصة بيع كتب ودورات الأمن السيبراني
"""

import logging
import os
from threading import Thread
from flask import Flask

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)
from config import CUSTOMER_BOT_TOKEN, ADMIN_IDS, ITEMS_PER_PAGE
import database as db

# ============================================================
# الإعدادات
# ============================================================
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

# حالة المستخدم
USER_STATE = {}

KIND_AR = {
    "book": "📚 كتاب",
    "course": "🎓 دورة",
}

LEVEL_AR = {
    "beginner": "🟢 مبتدئ",
    "intermediate": "🟡 متوسط",
    "advanced": "🔴 متقدم",
}

STATUS_AR = {
    "pending_payment": "🟡 بانتظار الدفع",
    "paid": "🟢 تم الدفع",
    "delivered": "✅ تم التسليم",
    "cancelled": "❌ ملغي",
}

# 📁 مجلد حفظ إشعارات الدفع
RECEIPTS_DIR = "data/receipts"


# ============================================================
# الأزرار
# ============================================================
def main_menu_kb(user_id=None):
    cart_count = db.cart_count(user_id) if user_id else 0
    cart_label = f"🛒 سلة المشتريات ({cart_count})" if cart_count else "🛒 سلة المشتريات"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 الكتب", callback_data="books:0"),
         InlineKeyboardButton("🎓 الدورات", callback_data="courses:0")],
        [InlineKeyboardButton(cart_label, callback_data="cart")],
        [InlineKeyboardButton("👤 حسابي", callback_data="account")],
        [InlineKeyboardButton("📩 الدعم الفني", callback_data="support")],
        [InlineKeyboardButton("ℹ️ عن المنصة", callback_data="about")],
    ])


def back_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]
    ])


# ============================================================
# /start
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.save_user(user.id, user.username, user.full_name)
    USER_STATE.pop(user.id, None)
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("order_id", None)

    name = user.first_name or "صديقي"
    text = (
        f"🛡️ *Rami Cyber Academy*\n\n"
        f"أهلاً بك {name} 👋\n\n"
        f"منصة متخصصة في بيع الكتب والدورات\n"
        f"في مجال الأمن السيبراني.\n\n"
        f"اختر من القائمة:"
    )
    await update.message.reply_text(
        text, reply_markup=main_menu_kb(user.id), parse_mode="Markdown"
    )


# ============================================================
# القائمة الرئيسية
# ============================================================
async def home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    db.save_user(user_id, q.from_user.username, q.from_user.full_name)
    USER_STATE.pop(user_id, None)
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("order_id", None)

    await q.edit_message_text(
        "🛡️ *Rami Cyber Academy*\n\nاختر من القائمة:",
        reply_markup=main_menu_kb(user_id),
        parse_mode="Markdown",
    )


# ============================================================
# عرض المنتجات
# ============================================================
async def show_products_cb(update: Update, context: ContextTypes.DEFAULT_TYPE,
                           type_: str, page: int):
    q = update.callback_query

    products = db.get_products(type_=type_, limit=100)
    if not products:
        await q.edit_message_text(
            f"لا توجد {KIND_AR.get(type_, 'منتجات')} حالياً.",
            reply_markup=back_main_kb(),
        )
        return

    total_pages = (len(products) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start_idx = page * ITEMS_PER_PAGE
    page_items = products[start_idx:start_idx + ITEMS_PER_PAGE]

    kind_title = "📚 الكتب المتوفرة" if type_ == "book" else "🎓 الدورات المتوفرة"

    buttons = []
    for p in page_items:
        rating = db.get_product_rating(p["id"])
        star = f"⭐ {rating['avg']}" if rating["count"] > 0 else "⭐ جديد"
        buttons.append([
            InlineKeyboardButton(
                f"{KIND_AR.get(p['type'], '')} {p['title'][:30]} | ${p['price']:.0f} | {star}",
                callback_data=f"product:{p['id']}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"{type_}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"{type_}:{page + 1}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")])

    text = f"*{kind_title}*\n\nالصفحة {page + 1} من {total_pages}\nالإجمالي: {len(products)} منتج"
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ============================================================
# تفاصيل منتج
# ============================================================
async def product_detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query

    p = db.get_product(product_id)
    if not p or not p["is_active"]:
        await q.edit_message_text("❌ المنتج غير متوفر.", reply_markup=back_main_kb())
        return

    kind = KIND_AR.get(p["type"], "")
    level = LEVEL_AR.get(p["level"], "") if p["level"] else ""
    rating = db.get_product_rating(product_id)

    stars = "⭐" * int(round(rating["avg"])) if rating["count"] > 0 else "—"
    rating_text = f"{stars} {rating['avg']} ({rating['count']} مراجعة)" if rating["count"] > 0 else "لا توجد مراجعات بعد"

    text = (
        f"{kind} *{p['title']}*\n\n"
        f"📝 *الوصف:*\n{p['description'] or '—'}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *السعر:* ${p['price']:.2f}\n"
    )
    if level:
        text += f"📊 *المستوى:* {level}\n"
    if p["category"]:
        text += f"📂 *التصنيف:* {p['category']}\n"
    text += f"⭐ *التقييم:* {rating_text}\n"

    cart = db.get_cart(q.from_user.id)
    in_cart = any(it["id"] == product_id for it in cart)

    buttons = []
    if in_cart:
        buttons.append([InlineKeyboardButton("✅ في السلة — إزالة",
                                             callback_data=f"cart_del:{product_id}")])
    else:
        buttons.append([InlineKeyboardButton("🛒 إضافة للسلة",
                                             callback_data=f"cart_add:{product_id}")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data=f"{p['type']}:0")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ============================================================
# السلة
# ============================================================
async def cart_add_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    user_id = q.from_user.id
    db.add_to_cart(user_id, product_id)
    await product_detail_cb(update, context, product_id)


async def cart_del_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    user_id = q.from_user.id
    db.remove_from_cart(user_id, product_id)
    await show_cart_cb(update, context)


async def show_cart_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    items = db.get_cart(user_id)

    if not items:
        await q.edit_message_text(
            "🛒 *السلة فارغة*\n\nابدأ بإضافة كتب أو دورات.",
            reply_markup=back_main_kb(),
            parse_mode="Markdown",
        )
        return

    total = sum(it["price"] * it["quantity"] for it in items)

    text = "🛒 *سلة المشتريات*\n\n"
    for i, it in enumerate(items, 1):
        kind = "📚" if it["type"] == "book" else "🎓"
        text += f"{i}. {kind} {it['title'][:40]}\n   💰 ${it['price']:.2f}\n\n"
    text += f"━━━━━━━━━━━━━━━━━━━\n💵 *الإجمالي:* ${total:.2f}"

    buttons = []
    for it in items:
        buttons.append([
            InlineKeyboardButton(f"❌ إزالة: {it['title'][:30]}",
                                 callback_data=f"cart_del:{it['id']}")
        ])
    buttons.append([InlineKeyboardButton("💳 إتمام الشراء", callback_data="checkout")])
    buttons.append([InlineKeyboardButton("🗑️ تفريغ السلة", callback_data="cart_clear")])
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def cart_clear_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    db.clear_cart(q.from_user.id)
    await show_cart_cb(update, context)


# ============================================================
# إتمام الشراء
# ============================================================
async def checkout_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    items = db.get_cart(user_id)

    if not items:
        await q.edit_message_text("السلة فارغة.", reply_markup=back_main_kb())
        return

    methods = db.get_payment_methods()
    if not methods:
        await q.edit_message_text(
            "❌ لا توجد طرق دفع متاحة حالياً. تواصل مع الدعم.",
            reply_markup=back_main_kb(),
        )
        return

    total = sum(it["price"] * it["quantity"] for it in items)
    text = (
        f"💳 *إتمام الشراء*\n\n"
        f"💰 الإجمالي: *${total:.2f}*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"اختر طريقة الدفع:"
    )

    buttons = []
    for m in methods:
        buttons.append([InlineKeyboardButton(f"💳 {m['name']}",
                                             callback_data=f"paymethod:{m['id']}")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع للسلة", callback_data="cart")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def paymethod_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, method_id: int):
    q = update.callback_query
    user_id = q.from_user.id
    items = db.get_cart(user_id)

    if not items:
        await q.edit_message_text("السلة فارغة.", reply_markup=back_main_kb())
        return

    methods = db.get_payment_methods()
    method = next((m for m in methods if m["id"] == method_id), None)
    if not method:
        await q.edit_message_text("طريقة دفع غير متوفرة.", reply_markup=back_main_kb())
        return

    order_items = [
        {"product_id": it["id"], "title": it["title"],
         "price": it["price"], "quantity": it["quantity"]}
        for it in items
    ]
    order_id, order_code = db.create_order(
        user_id, order_items, payment_method=method["name"]
    )

    total_amount = sum(it["price"] * it["quantity"] for it in items)
    db.clear_cart(user_id)

    context.user_data["order_id"] = order_id
    context.user_data["waiting_for"] = "payment_proof"

    text = (
        f"✅ *تم إنشاء طلبك بنجاح*\n\n"
        f"📦 *رقم الطلب:* `{order_code}`\n"
        f"💰 *المبلغ:* ${total_amount:.2f}\n"
        f"💳 *طريقة الدفع:* {method['name']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📋 *معلومات الدفع:*\n"
        f"`{method['details'] or '—'}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📸 *الخطوة التالية:*\n"
        f"حوّل المبلغ على المعلومات أعلاه،\n"
        f"ثم أرسل صورة إشعار التحويل هنا.\n\n"
        f"⏳ بعد التأكد، سيتم تسليمك المنتجات."
    )

    buttons = [
        [InlineKeyboardButton("👤 حسابي", callback_data="account")],
        [InlineKeyboardButton("🏠 القائمة الرئيسية", callback_data="home")],
    ]

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ============================================================
# حسابي
# ============================================================
async def account_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id

    orders = db.get_orders(user_id=user_id, limit=10)
    courses = db.get_user_courses(user_id)

    text = f"👤 *حسابي*\n\n"
    text += f"🆔 المعرف: `{user_id}`\n"
    text += f"📦 الطلبات: {len(orders)}\n"
    text += f"🎓 الدورات: {len(courses)}\n\n"

    if orders:
        text += "━━━━━━━━━━━━━━━━━━━\n*آخر الطلبات:*\n"
        for o in orders[:5]:
            status = STATUS_AR.get(o["status"], o["status"])
            text += f"• `{o['order_code']}` — ${o['final_total']:.2f} — {status}\n"

    buttons = [
        [InlineKeyboardButton("🎓 دوراتي", callback_data="my_courses")],
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
    ]

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def my_courses_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    courses = db.get_user_courses(q.from_user.id)

    if not courses:
        await q.edit_message_text(
            "🎓 *دوراتي*\n\nلم تسجّل في أي دورة بعد.",
            reply_markup=back_main_kb(),
            parse_mode="Markdown",
        )
        return

    text = "🎓 *دوراتي*\n\n"
    for c in courses:
        text += f"• {c['title']}\n  التقدم: {c['progress']}%\n\n"

    await q.edit_message_text(
        text, reply_markup=back_main_kb(), parse_mode="Markdown"
    )


# ============================================================
# عن المنصة + الدعم
# ============================================================
async def about_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    text = (
        "ℹ️ *عن Rami Cyber Academy*\n\n"
        "🛡️ منصة متخصصة في بيع الكتب والدورات\n"
        "في مجال الأمن السيبراني.\n\n"
        "📚 *كتبنا:* تغطي مواضيع مثل الاختراق الأخلاقي،\n"
        "التشفير، الشبكات، والتحليل الجنائي الرقمي.\n\n"
        "🎓 *دوراتنا:* مسجلة ومباشرة، مع شهادات إتمام.\n\n"
        "💳 *الدفع:* يدوي — تحويل + صورة إشعار.\n"
        "📦 *التسليم:* فوري بعد التأكد من الدفع.\n\n"
        "🌐 للتواصل: اضغط زر الدعم."
    )
    await q.edit_message_text(
        text, reply_markup=back_main_kb(), parse_mode="Markdown"
    )


async def support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    user_id = q.from_user.id
    USER_STATE[user_id] = {"action": "support"}
    context.user_data["waiting_for"] = "support"

    text = (
        "📩 *الدعم الفني*\n\n"
        "اكتب رسالتك الآن وسيتم الرد عليك في أقرب وقت.\n\n"
        "لإلغاء العملية أرسل /cancel."
    )
    await q.edit_message_text(
        text, reply_markup=back_main_kb(), parse_mode="Markdown"
    )


# ============================================================
# استقبال النصوص
# ============================================================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return

    waiting = context.user_data.get("waiting_for")

    if waiting == "support":
        msg_id = db.create_support_message(user.id, text)
        context.user_data.pop("waiting_for", None)
        USER_STATE.pop(user.id, None)

        uname = f"@{user.username}" if user.username else "—"
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📩 *رسالة دعم #{msg_id}*\n\n"
                        f"👤 {user.full_name} ({uname})\n"
                        f"🆔 `{user.id}`\n\n"
                        f"{text}"
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                log.exception("Could not notify admin %s", admin_id)

        await update.message.reply_text(
            "✅ وصلت رسالتك للدعم. سيتم الرد قريباً.",
            reply_markup=main_menu_kb(user.id),
        )
        return

    if waiting == "payment_proof":
        await update.message.reply_text(
            "📸 الرجاء إرسال *صورة* إشعار التحويل (وليس نصاً).\n\n"
            "لإلغاء العملية أرسل /cancel.",
            parse_mode="Markdown",
            reply_markup=main_menu_kb(user.id),
        )
        return

    await update.message.reply_text(
        "اختر من القائمة 👇",
        reply_markup=main_menu_kb(user.id),
    )


# ============================================================
# استقبال صورة إشعار الدفع
# ============================================================
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يستقبل صورة إشعار الدفع من الزبون، ينزّلها ويخزّن المسار."""
    user = update.effective_user
    waiting = context.user_data.get("waiting_for")

    if waiting != "payment_proof":
        await update.message.reply_text(
            "📸 لم أتوقع صورة الآن. اختر من القائمة:",
            reply_markup=main_menu_kb(user.id),
        )
        return

    order_id = context.user_data.get("order_id")
    if not order_id:
        await update.message.reply_text(
            "❌ لم يتم العثور على الطلب. ابدأ من جديد.",
            reply_markup=main_menu_kb(user.id),
        )
        context.user_data.pop("waiting_for", None)
        return

    # 📥 تنزيل الصورة إلى مجلد data/receipts/
    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    photo = update.message.photo[-1]

    try:
        tg_file = await photo.get_file()
        file_path = f"{RECEIPTS_DIR}/order_{order_id}_{photo.file_unique_id}.jpg"
        await tg_file.download_to_drive(file_path)
    except Exception:
        log.exception("Could not download payment proof")
        await update.message.reply_text(
            "❌ تعذر تنزيل الصورة. حاول مرة أخرى.",
            reply_markup=main_menu_kb(user.id),
        )
        return

    # 💾 نخزّن المسار في قاعدة البيانات
    db.attach_payment_proof(order_id, file_path)

    context.user_data.pop("waiting_for", None)
    context.user_data.pop("order_id", None)

    await update.message.reply_text(
        "✅ *استلمنا إشعار الدفع!*\n\n"
        "⏳ سيتم مراجعته من قبل الإدارة.\n"
        "سيصلك إشعار عند التأكيد.",
        reply_markup=main_menu_kb(user.id),
        parse_mode="Markdown",
    )

    # إشعار للأدمن مع الصورة
    order = db.get_order(order_id)
    if not order:
        return

    uname = f"@{user.username}" if user.username else "—"
    admin_text = (
        f"🔔 *إشعار دفع جديد*\n\n"
        f"📦 الطلب: `{order['order_code']}`\n"
        f"👤 الزبون: {user.full_name} ({uname})\n"
        f"🆔 `{user.id}`\n"
        f"💰 المبلغ: ${order['final_total']:.2f}\n"
        f"💳 الطريقة: {order['payment_method']}\n\n"
        f"⏳ سيتم التأكد من طرف مدير البوت على إشعار الدفع."
    )
    for admin_id in ADMIN_IDS:
        try:
            with open(file_path, "rb") as f:
                await context.bot.send_photo(
                    chat_id=admin_id,
                    photo=f,
                    caption=admin_text,
                    parse_mode="Markdown",
                )
        except Exception:
            log.exception("Could not notify admin %s", admin_id)


# ============================================================
# /cancel
# ============================================================
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_STATE.pop(user_id, None)
    context.user_data.pop("waiting_for", None)
    context.user_data.pop("order_id", None)
    await update.message.reply_text(
        "تم الإلغاء.",
        reply_markup=main_menu_kb(user_id),
    )


# ============================================================
# موجّه الأزرار
# ============================================================
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""

    try:
        await q.answer()
    except Exception:
        pass

    if data == "home":
        await home_cb(update, context)
    elif data == "cart":
        await show_cart_cb(update, context)
    elif data == "cart_clear":
        await cart_clear_cb(update, context)
    elif data == "checkout":
        await checkout_cb(update, context)
    elif data == "account":
        await account_cb(update, context)
    elif data == "my_courses":
        await my_courses_cb(update, context)
    elif data == "about":
        await about_cb(update, context)
    elif data == "support":
        await support_cb(update, context)
    elif data.startswith("books:"):
        page = int(data.split(":")[1])
        await show_products_cb(update, context, "book", page)
    elif data.startswith("courses:"):
        page = int(data.split(":")[1])
        await show_products_cb(update, context, "course", page)
    elif data.startswith("product:"):
        pid = int(data.split(":")[1])
        await product_detail_cb(update, context, pid)
    elif data.startswith("cart_add:"):
        pid = int(data.split(":")[1])
        await cart_add_cb(update, context, pid)
    elif data.startswith("cart_del:"):
        pid = int(data.split(":")[1])
        await cart_del_cb(update, context, pid)
    elif data.startswith("paymethod:"):
        mid = int(data.split(":")[1])
        await paymethod_cb(update, context, mid)


# ============================================================
# معالج الأخطاء
# ============================================================
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    err_name = type(err).__name__

    if err_name in ("BadRequest",):
        msg = str(err)
        if "Query is too old" in msg or "query id is invalid" in msg:
            return
        if "message is not modified" in msg:
            return

    log.warning("⚠️ خطأ غير معالج: %s — %s", err_name, err)


# ============================================================
# Flask server (مطلوب لـ Render)
# ============================================================
health_app = Flask(__name__)


@health_app.route("/")
@health_app.route("/health")
def health():
    return "Bot is running ✅", 200


def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    health_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)


# ============================================================
# main
# ============================================================
def main():
    if not CUSTOMER_BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN غير مضبوط في .env")

    db.init_db()
    os.makedirs(RECEIPTS_DIR, exist_ok=True)

    app = Application.builder().token(CUSTOMER_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    # 🚀 شغّل Flask في Thread خلفي (مطلوب لـ Render)
    Thread(target=run_health_server, daemon=True).start()

    log.info("🛡️ Rami Cyber Academy bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
