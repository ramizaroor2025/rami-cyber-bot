import os
from dotenv import load_dotenv

load_dotenv()

CUSTOMER_BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
DB_PATH = os.getenv("DB_PATH", "cyber.db")

ORDER_PAGE_SIZE = 10
ITEMS_PER_PAGE = 5

if not CUSTOMER_BOT_TOKEN:
    print("⚠️  BOT_TOKEN غير مضبوط في .env")
if not ADMIN_BOT_TOKEN:
    print("⚠️  ADMIN_BOT_TOKEN غير مضبوط في .env")
if not ADMIN_IDS:
    print("⚠️  ADMIN_IDS غير مضبوط في .env")