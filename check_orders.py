import database as db

orders = db.get_orders(limit=10)

if not orders:
    print("❌ لا توجد طلبات")
else:
    print(f"📦 إجمالي الطلبات: {len(orders)}\n")
    for o in orders:
        proof = o.get("payment_proof")
        proof_status = f"✅ موجود ({proof[:30]}...)" if proof else "❌ غير موجود"
        print(f"#{o['id']} | {o['order_code']} | {o['status']}")
        print(f"   💳 {o['payment_method'] or '—'}")
        print(f"   📸 إشعار الدفع: {proof_status}")
        print()