import os
import logging

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sheet import get_schedule
from master import get_klasemen, get_skor, get_time_evaluasi
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
SHEET_ID = os.getenv("SHEET_ID")
HOUR_BEFORE = os.getenv("HOUR_BEFORE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot aktif & scheduler jalan ✅")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(update.message.text)

async def send_message(app, chat_id, message):
    await app.bot.send_message(
        chat_id=chat_id,
        text=message
    )
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_message(context.application, "151065522", 'ini hanya test')

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_klasemen(HOUR_BEFORE)

async def skor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_skor()

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    start, finish, hour = args
    get_time_evaluasi(start=start, finish=finish, hour_before=hour)

def main():
    if not BOT_TOKEN or not SHEET_ID:
        raise RuntimeError("BOT_TOKEN / SHEET_ID belum diset")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("skor", skor))
    app.add_handler(CommandHandler("time", time))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
    def reload_jobs(scheduler, app):
        scheduler.remove_all_jobs()
        schedules = get_schedule(SHEET_ID)

        for i, s in enumerate(schedules):
            scheduler.add_job(
                send_message,
                trigger="cron",
                hour=s["hour"],
                minute=s["minute"],
                args=[app, s["chat_id"], s["message"]],
                id=f"sheet-job-{i}",
                replace_existing=True,
            )

    schedules = get_schedule(SHEET_ID)

    for i, s in enumerate(schedules):
        scheduler.add_job(
            send_message,
            trigger="cron",
            hour=s["hour"],
            minute=s["minute"],
            args=[app, s["chat_id"], s["message"]],
            id=f"sheet-job-{i}",
            replace_existing=True,
        )
    scheduler.add_job(
        reload_jobs,
        trigger="interval",
        minutes=5,
        args=[scheduler, app],
    )
    scheduler.start()

    logging.info("📅 Loaded %s schedules from Google Sheet", len(schedules))
    app.run_polling()

if __name__ == "__main__":
    main()
