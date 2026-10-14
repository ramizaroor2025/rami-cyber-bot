"""
👑 Rami Cyber Academy - بوت المدير
لوحة تحكم كاملة للمنصة
"""

import logging
import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    Bot,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters,
)
from config import ADMIN_BOT_TOKEN, ADMIN_IDS, CUSTOMER_BOT_TOKEN, ITEMS_PER_PAGE
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

ADMIN_STATE = {}

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


# ============================================================
# حماية الأدمن (فقط على الدوال الأساسية)
# ============================================================
def is_admin(uid):
    return uid in ADMIN_IDS


def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        if not is_admin(uid):
            if update.callback_query:
                try:
                    await update.callback_query.answer("⛔ غير مصرح", show_alert=True)
                except Exception:
                    pass
            elif update.message:
                await update.message.reply_text("⛔ هذا البوت للمدير فقط.")
            return
        return await func(update, context)
    return wrapper


# ============================================================
# الأزرار
# ============================================================
def home_kb():
    stats = db.get_stats()
    pending = stats["pending"]
    pending_label = f"💳 مدفوعات بانتظار التأكيد ({pending})" if pending else "💳 مدفوعات بانتظار التأكيد"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats"),
         InlineKeyboardButton("📦 الطلبات", callback_data="orders:all:0")],
        [InlineKeyboardButton(pending_label, callback_data="pending_payments")],
        [InlineKeyboardButton("📚 إدارة المنتجات", callback_data="manage_products")],
        [InlineKeyboardButton("👥 المستخدمين", callback_data="users")],
        [InlineKeyboardButton("🎟️ الكوبونات", callback_data="coupons")],
        [InlineKeyboardButton("📩 رسائل الدعم", callback_data="support:open")],
    ])


def back_home_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")]
    ])


# ============================================================
# /start
# ============================================================
@admin_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    ADMIN_STATE.pop(user.id, None)
    context.user_data.pop("waiting_for", None)

    text = (
        f"👑 *لوحة تحكم المدير*\n"
        f"🛡️ Rami Cyber Academy\n\n"
        f"أهلاً {user.first_name} 👋\n\n"
        f"اختر من القائمة:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=home_kb(), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=home_kb(), parse_mode="Markdown"
        )


# ============================================================
# الإحصائيات
# ============================================================
@admin_only
async def stats_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    s = db.get_stats()

    text = (
        f"📊 *إحصائيات المنصة*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 *المستخدمون:* {s['users']}\n"
        f"📚 *المنتجات:* {s['products']}\n"
        f"📦 *إجمالي الطلبات:* {s['orders']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🟡 *بانتظار الدفع:* {s['pending']}\n"
        f"🟢 *مدفوعة:* {s['paid']}\n"
        f"✅ *مُسلّمة:* {s['delivered']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *الإيرادات:* ${s['revenue']:.2f}\n"
    )
    await q.edit_message_text(text, reply_markup=back_home_kb(), parse_mode="Markdown")


# ============================================================
# الطلبات (بدون admin_only)
# ============================================================
async def orders_cb(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    status: str, page: int):
    q = update.callback_query

    filter_status = None if status == "all" else status
    orders = db.get_orders(status=filter_status, limit=100)

    title_map = {
        "all": "📦 كل الطلبات",
        "pending_payment": "🟡 بانتظار الدفع",
        "paid": "🟢 مدفوعة",
        "delivered": "✅ مُسلّمة",
        "cancelled": "❌ ملغية",
    }
    title = title_map.get(status, "📦 الطلبات")

    if not orders:
        await q.edit_message_text(
            f"*{title}*\n\nلا توجد طلبات.",
            reply_markup=back_home_kb(),
            parse_mode="Markdown",
        )
        return

    total_pages = (len(orders) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    page_items = orders[page * ITEMS_PER_PAGE:(page + 1) * ITEMS_PER_PAGE]

    buttons = []
    for o in page_items:
        status_icon = STATUS_AR.get(o["status"], o["status"])
        buttons.append([
            InlineKeyboardButton(
                f"{status_icon} | {o['order_code']} | ${o['final_total']:.0f}",
                callback_data=f"order:{o['id']}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ السابق", callback_data=f"orders:{status}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("التالي ➡️", callback_data=f"orders:{status}:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([
        InlineKeyboardButton("🟡 بانتظار", callback_data="orders:pending_payment:0"),
        InlineKeyboardButton("🟢 مدفوع", callback_data="orders:paid:0"),
    ])
    buttons.append([
        InlineKeyboardButton("✅ مُسلّم", callback_data="orders:delivered:0"),
        InlineKeyboardButton("❌ ملغي", callback_data="orders:cancelled:0"),
    ])
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])

    text = f"*{title}*\n\nالصفحة {page + 1} من {total_pages}\nالإجمالي: {len(orders)}"
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def order_detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    q = update.callback_query

    o = db.get_order(order_id)
    if not o:
        try:
            await q.answer("الطلب غير موجود", show_alert=True)
        except Exception:
            pass
        return

    items = db.get_order_items(order_id)
    user = db.get_user(o["user_id"])
    status = STATUS_AR.get(o["status"], o["status"])

    text = (
        f"📦 *الطلب {o['order_code']}*\n\n"
        f"📌 *الحالة:* {status}\n"
        f"🕐 *التاريخ:* {o['created_at'][:16]}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *الزبون:*\n"
        f"  الاسم: {user['full_name'] if user else '—'}\n"
        f"  المستخدم: @{user['username'] if user and user['username'] else '—'}\n"
        f"  المعرف: `{o['user_id']}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📚 *المنتجات:*\n"
    )
    for it in items:
        text += f"  • {it['title']} × {it['quantity']} — ${it['price']:.2f}\n"

    text += (
        f"\n━━━━━━━━━━━━━━━━━━━\n"
        f"💰 *الإجمالي:* ${o['total']:.2f}\n"
        f"🎟️ *الخصم:* ${o['discount']:.2f}\n"
        f"💵 *المطلوب:* ${o['final_total']:.2f}\n"
        f"💳 *طريقة الدفع:* {o['payment_method'] or '—'}\n"
    )

    if o.get("admin_note"):
        text += f"\n🗒️ *ملاحظة:* {o['admin_note']}\n"

    # 💡 حالة إشعار الدفع
    if o.get("payment_proof"):
        text += f"\n✅ *الزبون أرسل إشعار الدفع*\n"
    else:
        text += f"\n⏳ *لم يُرسل إشعار الدفع بعد*\n"

    buttons = []

    # زر عرض إشعار الدفع
    if o.get("payment_proof"):
        buttons.append([InlineKeyboardButton("📸 عرض إشعار الدفع",
                                             callback_data=f"view_proof:{order_id}")])

    # أزرار الحالة
    if o["status"] == "pending_payment":
        buttons.append([InlineKeyboardButton("✅ تأكيد الدفع",
                                             callback_data=f"confirm_pay:{order_id}")])
        buttons.append([InlineKeyboardButton("❌ إلغاء الطلب",
                                             callback_data=f"cancel_order:{order_id}")])
    elif o["status"] == "paid":
        buttons.append([InlineKeyboardButton("📦 تسليم المنتجات",
                                             callback_data=f"deliver:{order_id}")])

    buttons.append([InlineKeyboardButton("✉️ مراسلة الزبون",
                                         url=f"tg://user?id={o['user_id']}")])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="orders:all:0")])

    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def view_proof_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    """يعرض إشعار الدفع للأدمن (من الملف المحلي)."""
    q = update.callback_query
    o = db.get_order(order_id)
    if not o:
        try:
            await q.answer("الطلب غير موجود", show_alert=True)
        except Exception:
            pass
        return

    proof_path = o.get("payment_proof")
    if not proof_path:
        try:
            await q.answer("لا يوجد إشعار دفع", show_alert=True)
        except Exception:
            pass
        return

    # تحقق أن الملف موجود
    if not os.path.exists(proof_path):
        try:
            await q.answer(f"⚠️ الملف غير موجود:\n{proof_path}", show_alert=True)
        except Exception:
            pass
        return

    try:
        with open(proof_path, "rb") as photo:
            await context.bot.send_photo(
                chat_id=q.from_user.id,
                photo=photo,
                caption=(
                    f"📸 *إشعار دفع الطلب* `{o['order_code']}`\n"
                    f"💰 المبلغ: ${o['final_total']:.2f}\n"
                    f"💳 الطريقة: {o['payment_method'] or '—'}"
                ),
                parse_mode="Markdown",
            )
    except Exception as e:
        log.exception("Could not send proof photo")
        try:
            await q.answer(f"خطأ: {e}", show_alert=True)
        except Exception:
            pass


async def confirm_pay_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    q = update.callback_query
    db.update_order_status(order_id, "paid")
    try:
        await q.answer("✅ تم تأكيد الدفع")
    except Exception:
        pass

    # إشعار للزبون
    o = db.get_order(order_id)
    if o and CUSTOMER_BOT_TOKEN:
        try:
            customer_bot = Bot(token=CUSTOMER_BOT_TOKEN)
            await customer_bot.initialize()
            await customer_bot.send_message(
                chat_id=o["user_id"],
                text=(
                    f"✅ *تم تأكيد دفعتك!*\n\n"
                    f"📦 الطلب: `{o['order_code']}`\n"
                    f"💰 المبلغ: ${o['final_total']:.2f}\n\n"
                    f"سيتم تسليمك المنتجات قريباً."
                ),
                parse_mode="Markdown",
            )
            await customer_bot.shutdown()
        except Exception:
            log.exception("Could not notify customer")

    await order_detail_cb(update, context, order_id)


async def cancel_order_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    q = update.callback_query
    db.update_order_status(order_id, "cancelled")
    try:
        await q.answer("❌ تم إلغاء الطلب")
    except Exception:
        pass
    await order_detail_cb(update, context, order_id)


async def deliver_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, order_id: int):
    q = update.callback_query
    db.update_order_status(order_id, "delivered")
    try:
        await q.answer("✅ تم التسليم")
    except Exception:
        pass

    o = db.get_order(order_id)
    if o and CUSTOMER_BOT_TOKEN:
        try:
            customer_bot = Bot(token=CUSTOMER_BOT_TOKEN)
            await customer_bot.initialize()
            await customer_bot.send_message(
                chat_id=o["user_id"],
                text=(
                    f"🎉 *تم تسليم طلبك!*\n\n"
                    f"📦 الطلب: `{o['order_code']}`\n\n"
                    f"شكراً لثقتك بـ Rami Cyber Academy 🛡️"
                ),
                parse_mode="Markdown",
            )
            await customer_bot.shutdown()
        except Exception:
            log.exception("Could not notify customer")

    await order_detail_cb(update, context, order_id)


# ============================================================
# إدارة المنتجات (رئيسية - admin_only)
# ============================================================
@admin_only
async def manage_products_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query

    products = db.get_products(only_active=False, limit=100)
    buttons = [
        [InlineKeyboardButton("➕ إضافة كتاب", callback_data="add:book")],
        [InlineKeyboardButton("➕ إضافة دورة", callback_data="add:course")],
        [InlineKeyboardButton("📚 عرض الكتب", callback_data="list:book")],
        [InlineKeyboardButton("🎓 عرض الدورات", callback_data="list:course")],
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
    ]
    text = (
        f"📚 *إدارة المنتجات*\n\n"
        f"إجمالي المنتجات: {len(products)}\n\n"
        f"اختر إجراء:"
    )
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def list_products_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, type_: str):
    q = update.callback_query

    products = db.get_products(type_=type_, only_active=False, limit=100)
    title = "📚 الكتب" if type_ == "book" else "🎓 الدورات"

    if not products:
        await q.edit_message_text(
            f"*{title}*\n\nلا توجد منتجات.",
            reply_markup=back_home_kb(),
            parse_mode="Markdown",
        )
        return

    buttons = []
    for p in products:
        status = "✅" if p["is_active"] else "❌"
        buttons.append([
            InlineKeyboardButton(
                f"{status} {p['title'][:35]} | ${p['price']:.0f}",
                callback_data=f"edit_product:{p['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("⬅️ رجوع", callback_data="manage_products")])

    await q.edit_message_text(
        f"*{title}* — {len(products)} منتج\n\nاضغط منتج للتعديل:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def edit_product_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query

    p = db.get_product(product_id)
    if not p:
        try:
            await q.answer("المنتج غير موجود", show_alert=True)
        except Exception:
            pass
        return

    kind = KIND_AR.get(p["type"], "")
    level = LEVEL_AR.get(p["level"], "—")
    status = "✅ نشط" if p["is_active"] else "❌ معطّل"

    text = (
        f"{kind} *{p['title']}*\n\n"
        f"📝 {p['description'] or '—'}\n\n"
        f"💰 السعر: ${p['price']:.2f}\n"
        f"📊 المستوى: {level}\n"
        f"📂 التصنيف: {p['category'] or '—'}\n"
        f"📌 الحالة: {status}\n"
        f"🆔 ID: {p['id']}"
    )

    toggle_label = "❌ تعطيل" if p["is_active"] else "✅ تنشيط"
    buttons = [
        [InlineKeyboardButton("✏️ تعديل السعر", callback_data=f"edit_price:{product_id}")],
        [InlineKeyboardButton("📝 تعديل الوصف", callback_data=f"edit_desc:{product_id}")],
        [InlineKeyboardButton(toggle_label, callback_data=f"toggle_product:{product_id}")],
        [InlineKeyboardButton("🗑️ حذف نهائي", callback_data=f"delete_product:{product_id}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data=f"list:{p['type']}")],
    ]
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


async def toggle_product_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    p = db.get_product(product_id)
    if not p:
        try:
            await q.answer("المنتج غير موجود", show_alert=True)
        except Exception:
            pass
        return
    db.update_product(product_id, is_active=0 if p["is_active"] else 1)
    try:
        await q.answer("✅ تم التحديث")
    except Exception:
        pass
    await edit_product_cb(update, context, product_id)


async def delete_product_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, product_id: int):
    q = update.callback_query
    db.delete_product(product_id)
    try:
        await q.answer("🗑️ تم الحذف")
    except Exception:
        pass
    await manage_products_cb(update, context)


async def add_product_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, type_: str):
    q = update.callback_query
    user_id = q.from_user.id

    ADMIN_STATE[user_id] = {"action": "add_product", "type": type_, "step": "title"}
    context.user_data["waiting_for"] = "add_product"

    kind = "الكتاب" if type_ == "book" else "الدورة"
    await q.edit_message_text(
        f"➕ *إضافة {kind}*\n\n"
        f"📝 أرسل *اسم* {kind}:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ إلغاء", callback_data="manage_products")]
        ]),
        parse_mode="Markdown",
    )


# ============================================================
# المدفوعات المعلّقة
# ============================================================
@admin_only
async def pending_payments_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    orders = db.get_orders(status="pending_payment", limit=50)

    if not orders:
        await q.edit_message_text(
            "💳 *مدفوعات بانتظار التأكيد*\n\nلا توجد مدفوعات معلّقة ✅",
            reply_markup=back_home_kb(),
            parse_mode="Markdown",
        )
        return

    buttons = []
    for o in orders:
        proof_icon = "📸" if o.get("payment_proof") else "⏳"
        buttons.append([
            InlineKeyboardButton(
                f"{proof_icon} {o['order_code']} | ${o['final_total']:.0f}",
                callback_data=f"order:{o['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])

    await q.edit_message_text(
        f"💳 *مدفوعات بانتظار التأكيد* — {len(orders)}\n\n"
        f"📸 = أرسل الإشعار | ⏳ = بانتظار الإشعار\n\n"
        f"اضغط للمراجعة:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


# ============================================================
# المستخدمين
# ============================================================
@admin_only
async def users_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    count = db.count_users()
    await q.edit_message_text(
        f"👥 *المستخدمون*\n\n📊 الإجمالي: *{count}* مستخدم",
        reply_markup=back_home_kb(),
        parse_mode="Markdown",
    )


# ============================================================
# الكوبونات
# ============================================================
@admin_only
async def coupons_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    coupons = db.list_coupons()

    text = f"🎟️ *الكوبونات*\n\n"
    if coupons:
        for c in coupons:
            status = "✅" if c["is_active"] else "❌"
            disc = f"{c['discount_percent']:.0f}%" if c["discount_percent"] else f"${c['discount_amount']:.0f}"
            text += f"{status} `{c['code']}` — خصم {disc} — استُخدم {c['used_count']}/{c['max_uses']}\n"
    else:
        text += "لا توجد كوبونات.\n"

    buttons = [
        [InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")],
    ]
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ============================================================
# رسائل الدعم
# ============================================================
async def support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, status: str):
    q = update.callback_query
    messages = db.get_support_messages(status=None if status == "all" else status, limit=50)

    if not messages:
        await q.edit_message_text(
            "📩 *رسائل الدعم*\n\nلا توجد رسائل.",
            reply_markup=back_home_kb(),
            parse_mode="Markdown",
        )
        return

    buttons = []
    for m in messages:
        icon = "🟡" if m["status"] == "open" else "🟢"
        preview = (m["body"] or "")[:30]
        buttons.append([
            InlineKeyboardButton(
                f"{icon} #{m['id']} | {preview}",
                callback_data=f"support_view:{m['id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("⬅️ القائمة الرئيسية", callback_data="home")])

    await q.edit_message_text(
        f"📩 *رسائل الدعم* — {len(messages)}\n\nاضغط للمراجعة:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown",
    )


async def support_view_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, msg_id: int):
    q = update.callback_query
    messages = db.get_support_messages(limit=500)
    m = next((x for x in messages if x["id"] == msg_id), None)
    if not m:
        try:
            await q.answer("الرسالة غير موجودة", show_alert=True)
        except Exception:
            pass
        return

    user = db.get_user(m["user_id"])
    status_ar = {"open": "🟡 جديدة", "replied": "🟢 تم الرد", "closed": "⚫ مغلقة"}.get(m["status"], m["status"])

    text = (
        f"📩 *رسالة دعم #{m['id']}*\n\n"
        f"📌 الحالة: {status_ar}\n"
        f"🕐 {m['created_at'][:16]}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *من:* {user['full_name'] if user else '—'}\n"
        f"🆔 `{m['user_id']}`\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 *الرسالة:*\n{m['body']}\n"
    )
    if m.get("admin_reply"):
        text += f"\n━━━━━━━━━━━━━━━━━━━\n✅ *الرد:*\n{m['admin_reply']}\n"

    buttons = [
        [InlineKeyboardButton("✉️ الرد على الزبون",
                              url=f"tg://user?id={m['user_id']}")],
        [InlineKeyboardButton("⬅️ رجوع", callback_data="support:open")],
    ]
    await q.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
    )


# ============================================================
# موجّه الأزرار (admin_only)
# ============================================================
@admin_only
async def button_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    data = q.data or ""

    # تجاهل الأزرار القديمة بهدوء
    try:
        await q.answer()
    except Exception:
        pass

    if data == "home":
        await start(update, context)
    elif data == "stats":
        await stats_cb(update, context)
    elif data.startswith("orders:"):
        _, status, page = data.split(":")
        await orders_cb(update, context, status, int(page))
    elif data.startswith("order:"):
        oid = int(data.split(":")[1])
        await order_detail_cb(update, context, oid)
    elif data.startswith("view_proof:"):
        oid = int(data.split(":")[1])
        await view_proof_cb(update, context, oid)
    elif data.startswith("confirm_pay:"):
        oid = int(data.split(":")[1])
        await confirm_pay_cb(update, context, oid)
    elif data.startswith("cancel_order:"):
        oid = int(data.split(":")[1])
        await cancel_order_cb(update, context, oid)
    elif data.startswith("deliver:"):
        oid = int(data.split(":")[1])
        await deliver_cb(update, context, oid)
    elif data == "manage_products":
        await manage_products_cb(update, context)
    elif data.startswith("list:"):
        type_ = data.split(":")[1]
        await list_products_cb(update, context, type_)
    elif data.startswith("edit_product:"):
        pid = int(data.split(":")[1])
        await edit_product_cb(update, context, pid)
    elif data.startswith("toggle_product:"):
        pid = int(data.split(":")[1])
        await toggle_product_cb(update, context, pid)
    elif data.startswith("delete_product:"):
        pid = int(data.split(":")[1])
        await delete_product_cb(update, context, pid)
    elif data.startswith("add:"):
        type_ = data.split(":")[1]
        await add_product_cb(update, context, type_)
    elif data == "pending_payments":
        await pending_payments_cb(update, context)
    elif data == "users":
        await users_cb(update, context)
    elif data == "coupons":
        await coupons_cb(update, context)
    elif data.startswith("support_view:"):
        mid = int(data.split(":")[1])
        await support_view_cb(update, context, mid)
    elif data.startswith("support:"):
        status = data.split(":")[1]
        await support_cb(update, context, status)
    # else: تجاهل


# ============================================================
# استقبال النصوص (admin_only)
# ============================================================
@admin_only
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (update.message.text or "").strip()
    if not text:
        return

    state = ADMIN_STATE.get(user.id)
    if not state:
        await update.message.reply_text("اختر من القائمة:", reply_markup=home_kb())
        return

    action = state.get("action")

    if action == "add_product":
        step = state.get("step")
        type_ = state["type"]

        if step == "title":
            state["title"] = text
            state["step"] = "description"
            await update.message.reply_text("📝 أرسل *الوصف*:", parse_mode="Markdown")
        elif step == "description":
            state["description"] = text
            state["step"] = "price"
            await update.message.reply_text("💰 أرسل *السعر* (رقم فقط):", parse_mode="Markdown")
        elif step == "price":
            try:
                price = float(text)
            except ValueError:
                await update.message.reply_text("❌ أرسل رقماً صحيحاً.")
                return
            state["price"] = price
            state["step"] = "category"
            await update.message.reply_text("📂 أرسل *التصنيف* (مثال: اختراق):", parse_mode="Markdown")
        elif step == "category":
            state["category"] = text
            state["step"] = "level"
            await update.message.reply_text(
                "📊 أرسل *المستوى*:\n• beginner\n• intermediate\n• advanced",
                parse_mode="Markdown"
            )
        elif step == "level":
            level = text.lower()
            if level not in ("beginner", "intermediate", "advanced"):
                await update.message.reply_text("❌ اختر: beginner / intermediate / advanced")
                return

            pid = db.add_product(
                type_, state["title"], state["description"],
                state["price"], state["category"], level
            )
            ADMIN_STATE.pop(user.id, None)
            context.user_data.pop("waiting_for", None)

            kind = "الكتاب" if type_ == "book" else "الدورة"
            await update.message.reply_text(
                f"✅ تم إضافة {kind}!\n\n"
                f"🆔 ID: `{pid}`\n"
                f"📚 الاسم: {state['title']}\n"
                f"💰 السعر: ${state['price']:.2f}",
                reply_markup=home_kb(),
                parse_mode="Markdown"
            )
        return

    await update.message.reply_text("اختر من القائمة:", reply_markup=home_kb())


# ============================================================
# /cancel (admin_only)
# ============================================================
@admin_only
async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ADMIN_STATE.pop(user_id, None)
    context.user_data.pop("waiting_for", None)
    await update.message.reply_text("تم الإلغاء.", reply_markup=home_kb())


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

    if err_name == "Conflict":
        log.warning("⚠️ Conflict: نسختان شغّالتان من نفس البوت!")
        return

    log.warning("⚠️ خطأ غير معالج: %s — %s", err_name, err)


# ============================================================
# main
# ============================================================
def main():
    if not ADMIN_BOT_TOKEN:
        raise SystemExit("❌ ADMIN_BOT_TOKEN غير مضبوط في .env")
    if not ADMIN_IDS:
        raise SystemExit("❌ ADMIN_IDS غير مضبوط في .env")

    db.init_db()

    app = Application.builder().token(ADMIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(CallbackQueryHandler(button_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_error_handler(error_handler)

    log.info("👑 Rami Cyber Admin bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()