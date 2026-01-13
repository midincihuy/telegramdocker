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

from apscheduler.schedulers.asyncio import AsyncIOScheduler, asyncio
from apscheduler.triggers.cron import CronTrigger
from sheet import get_schedule
from master import get_klasemen, get_skor, get_time_evaluasi
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Jakarta")

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

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")
async def run_job(func, **kwargs):
    try:
        result = func(**kwargs)
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        logging.exception("Job failed")

def reload_jobs(app):
    scheduler.remove_all_jobs()
    schedules = get_schedule(SHEET_ID)

    for i, s in enumerate(schedules):
        func_name = s["function"]
        func = FUNCTION_MAP.get(func_name)
        if not callable(func):
            logging.warning("Unknown function: %s", func_name)
            continue
        if s["interval"]:
            if not s["interval"].isdigit():
                logging.warning("Invalid interval: %s", s["interval"])
                continue
            interval = int(s["interval"])
            trigger_kwargs = {
                "minute": f"*/{interval}"
            }
            
            if s["day"]:
                trigger_kwargs["day_of_week"] = s["day"]

            scheduler.add_job(
                run_job,
                trigger=CronTrigger(**trigger_kwargs,timezone=TZ),
                kwargs={
                    "func": func,
                    **s["params"]
                },
                id=f"sheet-job-{i}",
                replace_existing=True,
            )
            logging.info("interval function: %s", func_name)
        else:
            trigger_kwargs = {
                "hour": s["hour"],
                "minute": s["minute"],
            }
            
            if s["day"]:
                trigger_kwargs["day_of_week"] = s["day"]

            scheduler.add_job(
                run_job,
                trigger=CronTrigger(**trigger_kwargs,timezone=TZ),
                kwargs={
                    "func": func,
                    **s["params"]
                },
                id=f"sheet-job-{i}",
                replace_existing=True,
            )
    logging.info("📅 Loaded %s schedules from Google Sheet", len(schedules))
    if not scheduler.running:
        scheduler.start()

async def reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reload_jobs(context.application)
        await update.message.reply_text("🔄 Scheduler berhasil di-reload")
    except Exception as e:
        logging.exception("Reload failed")
        await update.message.reply_text(f"❌ Reload gagal:\n{e}")

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_klasemen(HOUR_BEFORE)

async def skor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    get_skor()

async def time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    start, finish, hour = args
    get_time_evaluasi(start=start, finish=finish, hour_before=hour)

FUNCTION_MAP = {
    "check": get_klasemen,
    "skor": get_skor,
    "time": get_time_evaluasi,
}

def main():
    if not BOT_TOKEN or not SHEET_ID:
        raise RuntimeError("BOT_TOKEN / SHEET_ID belum diset")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reload", reload))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("skor", skor))
    app.add_handler(CommandHandler("time", time))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    reload_jobs(app)
    app.run_polling()

if __name__ == "__main__":
    main()
