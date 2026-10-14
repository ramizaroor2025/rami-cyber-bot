import sqlite3

conn = sqlite3.connect("cyber.db")
tables = [r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
)]
conn.close()

print("📋 الجداول في قاعدة البيانات:")
for t in tables:
    print(f"   ✅ {t}")
print(f"\n📊 المجموع: {len(tables)} جدول")