"""
Telegram Finance Tracker Bot
=============================
Bot Telegram untuk mencatat pengeluaran harian dengan penyimpanan di Google Sheets.

Fitur:
- Catat pengeluaran dengan mengirim nominal (contoh: "50000 makan siang")
- Summary on-demand (/summary)
- Laporan bulanan otomatis tiap tanggal 1
- Set budget limit & warning (/setbudget 5000000)

Cara pakai:
1. Buat bot di @BotFather, ambil TOKEN
2. Buat Google Sheets & service account (lihat README.md)
3. Isi .env file
4. Jalankan: python bot.py
"""

import os
import re
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

import gspread
from google.oauth2.service_account import Credentials

# ─── Config ──────────────────────────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Makassar"))  # WITA default
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Google Sheets Service ───────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheets_client() -> gspread.Client:
    """Buat Google Sheets client dari service account credentials."""
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_monthly_sheet(gc: gspread.Client, month_str: str) -> gspread.Worksheet:
    """
    Ambil atau buat worksheet untuk bulan tertentu.
    month_str format: "2026-03" (YYYY-MM)
    """
    spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)

    try:
        worksheet = spreadsheet.worksheet(month_str)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=month_str, rows=1000, cols=5)
        worksheet.append_row(["Tanggal", "Waktu", "Nominal", "Keterangan", "Running Total"])
        # Format header bold (optional, bisa di-style manual di Sheets)
        worksheet.format("A1:E1", {"textFormat": {"bold": True}})

    return worksheet


# ─── Helper Functions ────────────────────────────────────────────────────────


def format_rupiah(amount: int) -> str:
    """Format angka ke format Rupiah: Rp 1.500.000"""
    return f"Rp {amount:,.0f}".replace(",", ".")


def parse_expense(text: str) -> tuple[int, str] | None:
    """
    Parse pesan pengeluaran. Format yang diterima:
    - "50000"
    - "50000 makan siang"
    - "50.000 makan siang"
    - "50k makan siang"
    - "1.5jt renovasi"

    Returns: (nominal, keterangan) atau None jika tidak valid
    """
    text = text.strip()

    # Pattern: angka (bisa pakai titik/koma) + optional k/jt/rb + optional keterangan
    pattern = r"^(\d[\d.,]*)\s*(k|rb|jt|m)?\s*(.*)$"
    match = re.match(pattern, text, re.IGNORECASE)

    if not match:
        return None

    num_str = match.group(1).replace(".", "").replace(",", ".")
    multiplier_str = (match.group(2) or "").lower()
    keterangan = match.group(3).strip() or "-"

    try:
        amount = float(num_str)
    except ValueError:
        return None

    multipliers = {"k": 1_000, "rb": 1_000, "jt": 1_000_000, "m": 1_000_000}
    amount *= multipliers.get(multiplier_str, 1)

    if amount <= 0:
        return None

    return int(amount), keterangan


def is_authorized(user_id: int) -> bool:
    """Cek apakah user diizinkan menggunakan bot."""
    if not ALLOWED_USER_IDS:
        return True  # Jika tidak di-set, semua user boleh
    return user_id in ALLOWED_USER_IDS


# ─── Bot Handlers ────────────────────────────────────────────────────────────


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /start"""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Kamu tidak memiliki akses ke bot ini.")
        return

    welcome = (
        "💰 *Finance Tracker Bot*\n\n"
        "Kirim nominal pengeluaran untuk mencatat:\n"
        "• `50000` atau `50k` — catat Rp 50.000\n"
        "• `50000 makan siang` — catat dengan keterangan\n"
        "• `1.5jt sewa kos` — catat Rp 1.500.000\n\n"
        "📋 *Perintah:*\n"
        "/summary — Ringkasan hari ini\n"
        "/monthly — Ringkasan bulan ini\n"
        "/setbudget 5000000 — Set budget bulanan\n"
        "/budget — Cek sisa budget\n"
        "/undo — Hapus catatan terakhir\n"
        "/help — Bantuan"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk /help"""
    if not is_authorized(update.effective_user.id):
        return

    help_text = (
        "📖 *Panduan Penggunaan*\n\n"
        "*Format Input:*\n"
        "• `50000` — Rp 50.000\n"
        "• `50.000` — Rp 50.000\n"
        "• `50k` atau `50rb` — Rp 50.000\n"
        "• `1.5jt` — Rp 1.500.000\n"
        "• Tambahkan keterangan setelah nominal\n\n"
        "*Perintah:*\n"
        "/summary — Total pengeluaran hari ini\n"
        "/monthly — Total pengeluaran bulan ini\n"
        "/setbudget `nominal` — Set budget bulanan\n"
        "/budget — Lihat sisa budget bulan ini\n"
        "/undo — Hapus catatan terakhir\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def handle_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk pesan teks biasa (input pengeluaran)."""
    if not is_authorized(update.effective_user.id):
        return

    result = parse_expense(update.message.text)
    if result is None:
        # Bukan format pengeluaran yang valid, abaikan saja
        return

    nominal, keterangan = result
    now = datetime.now(TIMEZONE)
    month_str = now.strftime("%Y-%m")
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")

    try:
        gc = get_sheets_client()
        ws = get_or_create_monthly_sheet(gc, month_str)

        # Hitung running total
        all_values = ws.get_all_values()
        if len(all_values) > 1:
            last_row = all_values[-1]
            try:
                running_total = int(str(last_row[4]).replace(".", "").replace(",", "")) + nominal
            except (ValueError, IndexError):
                running_total = nominal
        else:
            running_total = nominal

        # Tulis ke sheet
        ws.append_row([date_str, time_str, nominal, keterangan, running_total])

        # Response
        reply = (
            f"✅ *Tercatat!*\n"
            f"💸 {format_rupiah(nominal)}\n"
            f"📝 {keterangan}\n"
            f"📊 Total hari ini: {format_rupiah(get_today_total(ws, date_str))}"
        )

        # Cek budget warning
        budget = context.user_data.get("monthly_budget")
        if budget:
            percentage = (running_total / budget) * 100
            if percentage >= 100:
                reply += f"\n\n🚨 *BUDGET TERLAMPAUI!* ({percentage:.0f}%)"
            elif percentage >= 80:
                reply += f"\n\n⚠️ *Budget sudah {percentage:.0f}%* — sisa {format_rupiah(budget - running_total)}"

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error recording expense: {e}")
        await update.message.reply_text("❌ Gagal mencatat. Coba lagi nanti.")


def get_today_total(ws: gspread.Worksheet, date_str: str) -> int:
    """Hitung total pengeluaran hari ini dari worksheet."""
    all_values = ws.get_all_values()
    total = 0
    for row in all_values[1:]:  # Skip header
        if row[0] == date_str:
            try:
                total += int(row[2])
            except (ValueError, IndexError):
                pass
    return total


async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /summary — ringkasan pengeluaran hari ini."""
    if not is_authorized(update.effective_user.id):
        return

    now = datetime.now(TIMEZONE)
    month_str = now.strftime("%Y-%m")
    date_str = now.strftime("%Y-%m-%d")

    try:
        gc = get_sheets_client()
        ws = get_or_create_monthly_sheet(gc, month_str)

        all_values = ws.get_all_values()
        today_expenses = []
        today_total = 0

        for row in all_values[1:]:
            if row[0] == date_str:
                try:
                    nominal = int(row[2])
                    keterangan = row[3]
                    waktu = row[1]
                    today_expenses.append((waktu, nominal, keterangan))
                    today_total += nominal
                except (ValueError, IndexError):
                    pass

        if not today_expenses:
            await update.message.reply_text(
                f"📋 *Summary {now.strftime('%d %B %Y')}*\n\nBelum ada pengeluaran hari ini.",
                parse_mode="Markdown",
            )
            return

        lines = [f"📋 *Summary {now.strftime('%d %B %Y')}*\n"]
        for i, (waktu, nominal, ket) in enumerate(today_expenses, 1):
            lines.append(f"{i}. `{waktu}` — {format_rupiah(nominal)} ({ket})")
        lines.append(f"\n💰 *Total: {format_rupiah(today_total)}*")

        # Tambahkan info budget jika ada
        budget = context.user_data.get("monthly_budget")
        if budget:
            monthly_total = sum(
                int(row[2]) for row in all_values[1:] if row[2].isdigit()
            )
            sisa = budget - monthly_total
            lines.append(f"📊 Budget bulan ini: {format_rupiah(sisa)} tersisa dari {format_rupiah(budget)}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in summary: {e}")
        await update.message.reply_text("❌ Gagal mengambil summary.")


async def cmd_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /monthly — ringkasan bulanan."""
    if not is_authorized(update.effective_user.id):
        return

    now = datetime.now(TIMEZONE)
    month_str = now.strftime("%Y-%m")

    try:
        gc = get_sheets_client()
        ws = get_or_create_monthly_sheet(gc, month_str)

        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            await update.message.reply_text(
                f"📊 *Laporan {now.strftime('%B %Y')}*\n\nBelum ada pengeluaran bulan ini.",
                parse_mode="Markdown",
            )
            return

        # Agregasi per hari
        daily_totals = {}
        grand_total = 0

        for row in all_values[1:]:
            try:
                date = row[0]
                nominal = int(row[2])
                daily_totals[date] = daily_totals.get(date, 0) + nominal
                grand_total += nominal
            except (ValueError, IndexError):
                pass

        lines = [f"📊 *Laporan {now.strftime('%B %Y')}*\n"]

        for date, total in sorted(daily_totals.items()):
            lines.append(f"📅 `{date}` — {format_rupiah(total)}")

        lines.append(f"\n💰 *Grand Total: {format_rupiah(grand_total)}*")

        # Rata-rata per hari
        if daily_totals:
            avg = grand_total // len(daily_totals)
            lines.append(f"📈 Rata-rata/hari: {format_rupiah(avg)}")

        # Info budget
        budget = context.user_data.get("monthly_budget")
        if budget:
            sisa = budget - grand_total
            days_left = (now.replace(month=now.month % 12 + 1, day=1) - timedelta(days=1) - now).days
            if days_left > 0 and sisa > 0:
                daily_budget = sisa // days_left
                lines.append(f"\n💳 *Budget:* {format_rupiah(budget)}")
                lines.append(f"📍 Sisa: {format_rupiah(sisa)}")
                lines.append(f"💡 Sisa {days_left} hari — max {format_rupiah(daily_budget)}/hari")
            elif sisa <= 0:
                lines.append(f"\n🚨 *Budget {format_rupiah(budget)} sudah TERLAMPAUI!*")
                lines.append(f"Over: {format_rupiah(abs(sisa))}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in monthly report: {e}")
        await update.message.reply_text("❌ Gagal mengambil laporan bulanan.")


async def cmd_setbudget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /setbudget — set budget bulanan."""
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text(
            "Penggunaan: `/setbudget 5000000`\nContoh: `/setbudget 3jt`",
            parse_mode="Markdown",
        )
        return

    result = parse_expense(context.args[0])
    if result is None:
        await update.message.reply_text("❌ Format budget tidak valid.")
        return

    budget, _ = result
    context.user_data["monthly_budget"] = budget

    await update.message.reply_text(
        f"✅ Budget bulanan di-set: *{format_rupiah(budget)}*",
        parse_mode="Markdown",
    )


async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /budget — cek sisa budget."""
    if not is_authorized(update.effective_user.id):
        return

    budget = context.user_data.get("monthly_budget")
    if not budget:
        await update.message.reply_text(
            "Belum ada budget. Set dengan `/setbudget 5000000`",
            parse_mode="Markdown",
        )
        return

    now = datetime.now(TIMEZONE)
    month_str = now.strftime("%Y-%m")

    try:
        gc = get_sheets_client()
        ws = get_or_create_monthly_sheet(gc, month_str)
        all_values = ws.get_all_values()

        total_spent = sum(int(row[2]) for row in all_values[1:] if row[2].isdigit())
        sisa = budget - total_spent
        percentage = (total_spent / budget) * 100

        # Progress bar visual
        filled = int(percentage // 10)
        bar = "█" * min(filled, 10) + "░" * max(10 - filled, 0)

        reply = (
            f"💳 *Budget Bulan Ini*\n\n"
            f"Budget: {format_rupiah(budget)}\n"
            f"Terpakai: {format_rupiah(total_spent)}\n"
            f"Sisa: {format_rupiah(sisa)}\n\n"
            f"[{bar}] {percentage:.1f}%"
        )

        await update.message.reply_text(reply, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error in budget check: {e}")
        await update.message.reply_text("❌ Gagal mengecek budget.")


async def cmd_undo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /undo — hapus catatan terakhir."""
    if not is_authorized(update.effective_user.id):
        return

    now = datetime.now(TIMEZONE)
    month_str = now.strftime("%Y-%m")

    try:
        gc = get_sheets_client()
        ws = get_or_create_monthly_sheet(gc, month_str)
        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            await update.message.reply_text("Tidak ada catatan untuk dihapus.")
            return

        last_row = all_values[-1]
        row_index = len(all_values)

        ws.delete_rows(row_index)

        # Recalculate running total for remaining rows
        # (simplified — just report the deletion)

        await update.message.reply_text(
            f"🗑 *Dihapus:*\n"
            f"📅 {last_row[0]} {last_row[1]}\n"
            f"💸 {format_rupiah(int(last_row[2]))}\n"
            f"📝 {last_row[3]}",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Error in undo: {e}")
        await update.message.reply_text("❌ Gagal menghapus catatan terakhir.")


# ─── Scheduled Jobs ──────────────────────────────────────────────────────────


async def monthly_report_job(context: ContextTypes.DEFAULT_TYPE):
    """
    Job yang jalan tiap tanggal 1 jam 08:00 — kirim laporan bulan lalu.
    """
    now = datetime.now(TIMEZONE)

    # Hitung bulan lalu
    first_of_month = now.replace(day=1)
    last_month = first_of_month - timedelta(days=1)
    month_str = last_month.strftime("%Y-%m")

    try:
        gc = get_sheets_client()
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)

        try:
            ws = spreadsheet.worksheet(month_str)
        except gspread.WorksheetNotFound:
            return  # Tidak ada data bulan lalu

        all_values = ws.get_all_values()
        if len(all_values) <= 1:
            return

        grand_total = sum(int(row[2]) for row in all_values[1:] if row[2].isdigit())
        total_days = len(set(row[0] for row in all_values[1:]))
        avg_daily = grand_total // max(total_days, 1)

        report = (
            f"📊 *Laporan Bulanan — {last_month.strftime('%B %Y')}*\n\n"
            f"💰 Total Pengeluaran: *{format_rupiah(grand_total)}*\n"
            f"📅 Hari aktif: {total_days} hari\n"
            f"📈 Rata-rata/hari: {format_rupiah(avg_daily)}\n"
            f"📝 Total transaksi: {len(all_values) - 1}\n\n"
            f"Detail lengkap bisa dilihat di Google Sheets."
        )

        # Kirim ke semua allowed users
        for user_id in ALLOWED_USER_IDS:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=report,
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Failed to send monthly report to {user_id}: {e}")

    except Exception as e:
        logger.error(f"Error in monthly report job: {e}")


# ─── Main ────────────────────────────────────────────────────────────────────


async def post_init(application: Application):
    """Set bot commands setelah init."""
    commands = [
        BotCommand("start", "Mulai bot"),
        BotCommand("summary", "Ringkasan hari ini"),
        BotCommand("monthly", "Laporan bulan ini"),
        BotCommand("setbudget", "Set budget bulanan"),
        BotCommand("budget", "Cek sisa budget"),
        BotCommand("undo", "Hapus catatan terakhir"),
        BotCommand("help", "Bantuan"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    """Entry point."""
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN belum di-set di .env")
    if not GOOGLE_SHEET_ID:
        raise ValueError("GOOGLE_SHEET_ID belum di-set di .env")

    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("monthly", cmd_monthly))
    app.add_handler(CommandHandler("setbudget", cmd_setbudget))
    app.add_handler(CommandHandler("budget", cmd_budget))
    app.add_handler(CommandHandler("undo", cmd_undo))

    # Message handler — tangkap semua pesan teks biasa sebagai expense
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_expense))

    # Scheduled job: laporan bulanan tiap tanggal 1 jam 08:00 WITA
    job_queue = app.job_queue
    if job_queue:
        # Hitung waktu target: tanggal 1 bulan depan jam 08:00
        now = datetime.now(TIMEZONE)
        if now.month == 12:
            next_first = now.replace(year=now.year + 1, month=1, day=1, hour=8, minute=0, second=0)
        else:
            next_first = now.replace(month=now.month + 1, day=1, hour=8, minute=0, second=0)

        # Jalankan sekali, lalu reschedule di dalam job (atau pakai interval 30 hari)
        job_queue.run_repeating(
            monthly_report_job,
            interval=timedelta(days=1),  # Cek tiap hari
            first=next_first,
            name="monthly_report",
        )
        logger.info(f"Monthly report job scheduled. Next run: {next_first}")

    logger.info("Bot started! Tekan Ctrl+C untuk stop.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()


