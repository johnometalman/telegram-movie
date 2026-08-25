#!/usr/bin/env python3
"""
Telegram Streaming Availability Bot
Tells the user in which countries a movie/series is available
on their streaming services (Netflix, HBO Max, Amazon Prime, Disney+, Apple TV+).
"""

import asyncio
import logging
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from simplejustwatchapi import search, offers_for_countries

# ─── Configuration ───────────────────────────────────────────────────────────

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# User's streaming services with their short names
USER_SERVICES = {
    "nfx": "Netflix",
    "mxx": "HBO Max",
    "amp": "Amazon Prime Video",
    "dnp": "Disney+",
    "atp": "Apple TV+",
    "MP":"Mercado Play", 
    "CV":"Claro Video"
}

# Also match variants/channels of these services
SERVICE_VARIANTS = {
    "nfx": ["nfx"],
    "mxx": ["mxx", "hbm"],
    "amp": ["amp", "prv", "amz"],
    "dnp": ["dnp"],
    "atp": ["atp", "itu"],
    "MP": ["mp"],
    "CV": ["cv"],
}

# Countries to check (major regions)
COUNTRIES = [
    "US", "GB", "CA", "AU", "DE", "FR", "ES", "IT", "MX", "BR",
    "AR", "CO", "CL", "PE", "JP", "KR", "IN", "NL", "SE", "NO",
    "DK", "FI", "BE", "AT", "CH", "PT", "IE", "NZ", "PL", "CZ",
    "HU", "RO", "GR", "TR", "ZA", "TH", "PH", "SG", "MY", "ID","EC"
]

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "CA": "Canada",
    "AU": "Australia", "DE": "Germany", "FR": "France", "ES": "Spain",
    "IT": "Italy", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina",
    "CO": "Colombia", "CL": "Chile", "PE": "Peru", "JP": "Japan",
    "KR": "South Korea", "IN": "India", "NL": "Netherlands", "SE": "Sweden",
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "BE": "Belgium",
    "AT": "Austria", "CH": "Switzerland", "PT": "Portugal", "IE": "Ireland",
    "NZ": "New Zealand", "PL": "Poland", "CZ": "Czech Republic",
    "HU": "Hungary", "RO": "Romania", "GR": "Greece", "TR": "Turkey",
    "ZA": "South Africa", "TH": "Thailand", "PH": "Philippines",
    "SG": "Singapore", "MY": "Malaysia", "ID": "Indonesia", "EC": "Ecuador"
}

# ─── Logging ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx logs full request URLs at INFO level, which include the bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


# ─── Helper functions ────────────────────────────────────────────────────────

def is_user_service(short_name: str) -> Optional[str]:
    """Check if a provider short_name matches one of the user's services. Returns display name or None."""
    for key, variants in SERVICE_VARIANTS.items():
        if short_name in variants:
            return USER_SERVICES[key]
    return None


def check_availability(entry_id: str) -> dict:
    """
    Check which countries have the title available on user's streaming services.
    Returns: {service_name: [list of country names]}
    """
    result = {}
    try:
        country_offers = offers_for_countries(entry_id, COUNTRIES, "en", True)
    except Exception as e:
        logger.error("Error fetching offers: %s", e)
        return result

    for country_code, offers in country_offers.items():
        for offer in offers:
            if offer.monetization_type != "FLATRATE":
                continue
            service_name = is_user_service(offer.package.short_name)
            if service_name:
                if service_name not in result:
                    result[service_name] = []
                country_name = COUNTRY_NAMES.get(country_code, country_code)
                if country_name not in result[service_name]:
                    result[service_name].append(country_name)

    return result


def format_availability(title: str, year: int, availability: dict) -> str:
    """Format the availability results into a nice message."""
    if not availability:
        return (
            f"🎬 *{title}* ({year})\n\n"
            "❌ Not available on any of your streaming services "
            "(Netflix, HBO Max, Amazon Prime, Disney+, Apple TV+, Mercado Play, Claro Video) "
            "in the countries I checked."
        )

    msg = f"🎬 *{title}* ({year})\n\n"
    msg += "Here's where you can stream it:\n\n"

    for service, countries in sorted(availability.items()):
        msg += f"📺 *{service}*\n"
        msg += ", ".join(sorted(countries))
        msg += "\n\n"

    return msg


# ─── Telegram handlers ──────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    await update.message.reply_text(
        "🎬 Welcome to the Streaming Availability Bot!\n\n"
        "Send me the name of a movie or TV show, and I'll tell you "
        "in which countries you can watch it on your streaming services:\n\n"
        "• Netflix\n"
        "• HBO Max\n"
        "• Amazon Prime Video\n"
        "• Disney+\n"
        "• Apple TV+\n\n"
        "• Mercado Play\n"
        "• Claro Video\n\n"
        "Just type a title and I'll search for it!"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages - search for the title."""
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Please send me a movie or TV show title to search for.")
        return

    await update.message.reply_text(f"🔍 Searching for \"{query}\"...")

    try:
        results = await asyncio.to_thread(search, query, "US", "en", 5, True)
    except Exception as e:
        logger.error("Search error: %s", e)
        await update.message.reply_text(f"❌ Error searching: {e}")
        return

    if not results:
        await update.message.reply_text("No results found. Try a different title.")
        return

    # If only one result or exact match, go directly
    if len(results) == 1:
        entry = results[0]
        await process_entry(update, context, entry.entry_id, entry.title, entry.release_year)
        return

    # Show selection buttons
    keyboard = []
    for entry in results[:5]:
        type_emoji = "🎬" if entry.object_type == "MOVIE" else "📺"
        label = f"{type_emoji} {entry.title} ({entry.release_year})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"select:{entry.entry_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "I found multiple results. Which one did you mean?",
        reply_markup=reply_markup,
    )

    # Store results in context for callback
    context.user_data["search_results"] = {
        entry.entry_id: {"title": entry.title, "year": entry.release_year}
        for entry in results[:5]
    }


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("select:"):
        entry_id = data.split(":", 1)[1]
        results = context.user_data.get("search_results", {})
        info = results.get(entry_id, {})
        title = info.get("title", "Unknown")
        year = info.get("year", 0)

        await query.edit_message_text(f"⏳ Checking availability for *{title}* ({year}) across 40 countries...", parse_mode="Markdown")
        await process_entry_from_callback(query, context, entry_id, title, year)


async def process_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, entry_id: str, title: str, year: int):
    """Process a single entry and send availability info."""
    msg = await update.message.reply_text(
        f"⏳ Checking availability for *{title}* ({year}) across 40 countries...",
        parse_mode="Markdown",
    )

    availability = await asyncio.to_thread(check_availability, entry_id)
    response = format_availability(title, year, availability)

    await msg.edit_text(response, parse_mode="Markdown")


async def process_entry_from_callback(query, context: ContextTypes.DEFAULT_TYPE, entry_id: str, title: str, year: int):
    """Process entry from a callback query."""
    availability = await asyncio.to_thread(check_availability, entry_id)
    response = format_availability(title, year, availability)

    await query.edit_message_text(response, parse_mode="Markdown")


# ─── Health Check Server ──────────────────────────────────────────────────────

class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler for Render."""
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        # Suppress verbose HTTP logs
        pass

def run_health_server():
    """Run a minimal HTTP server for Render health checks."""
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logging.info(f"Health check server running on port {port}")
    server.serve_forever()


# ─── Main ────────────────────────────────────────────────────────────────────

def build_application() -> Application:
    """Build the telegram Application with all handlers registered."""
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app


def main():
    # Start the health check server in a background thread
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Build and run the bot
    app = build_application()

    logger.info("Streaming Availability Bot started. Polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()