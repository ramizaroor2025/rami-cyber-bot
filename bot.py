def build_admin_app():
    """يبني تطبيق بوت المدير (بدون تشغيل)."""
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
    return app


def main():
    """تشغيل مستقل (للتشغيل المحلي فقط)."""
    app = build_admin_app()
    Thread(target=run_health_server, daemon=True).start()
    log.info("👑 Rami Cyber Admin bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
