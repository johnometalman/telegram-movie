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
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from dotenv import load_dotenv
from simplejustwatchapi import JustWatchError, offers_for_countries, search, seasons
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─── Configuration ───────────────────────────────────────────────────────────

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SERVER_ENDPOINT = os.getenv("SERVER_ENDPOINT")

# User's streaming services with their short names
USER_SERVICES = {
    "nfx": "Netflix",
    "mxx": "HBO Max",
    "amp": "Amazon Prime Video",
    "dnp": "Disney+",
    "atp": "Apple TV+",
    "pmp": "Paramount+"
}

# Also match variants/channels of these services
SERVICE_VARIANTS = {
    "nfx": ["nfx"],
    "mxx": ["mxx", "hbm"],
    "amp": ["amp", "prv", "amz"],
    "dnp": ["dnp"],
    "atp": ["atp", "itu"],
    "pmp": ["pmp", "p+", "paramount", "paramount+"]
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

def is_user_service(short_name: str) -> str | None:
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
    except JustWatchError as e:
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
            "(Netflix, HBO Max, Amazon Prime, Disney+, Apple TV+, Paramount+) "
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
    # Ping the server to wake it up (non-blocking)
    asyncio.create_task(ping_server())
    
    await update.message.reply_text(
        "🎬 Welcome to the Streaming Availability Bot!\n\n"
        "Send me the name of a movie or TV show, and I'll tell you "
        "in which countries you can watch it on your streaming services:\n\n"
        "• Netflix\n"
        "• HBO Max\n"
        "• Amazon Prime Video\n"
        "• Disney+\n"
        "• Apple TV+\n"
        "• Paramount+\n\n"
        "Just type a title and I'll search for it!"
    )


async def ping_server():
    """Ping the server to wake it up."""
    if not SERVER_ENDPOINT:
        logger.warning("SERVER_ENDPOINT not set, skipping ping")
        return
    
    try:
        async with httpx.AsyncClient() as client:
            await client.get(SERVER_ENDPOINT, timeout=5.0)
            logger.info("Server ping successful")
    except (httpx.HTTPError, httpx.TimeoutException) as e:
        logger.warning("Server ping failed: %s", e)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages - search for the title."""
    query = update.message.text.strip()
    if not query:
        await update.message.reply_text("Please send me a movie or TV show title to search for.")
        return

    await update.message.reply_text(f"🔍 Searching for \"{query}\"...")

    try:
        results = await asyncio.to_thread(search, query, "US", "en", 5, True)
    except JustWatchError as e:
        logger.error("Search error: %s", e)
        await update.message.reply_text(f"❌ Error searching: {e}")
        return

    if not results:
        await update.message.reply_text("No results found. Try a different title.")
        return

    # If only one result or exact match, go directly
    if len(results) == 1:
        entry = results[0]
        await process_entry(update, context, entry.entry_id, entry.title, entry.release_year, entry.object_type)
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
        entry.entry_id: {"title": entry.title, "year": entry.release_year, "object_type": entry.object_type}
        for entry in results[:5]
    }
    # Also store the entry_id for the select callback to work
    context.user_data["last_search_entry_id"] = results[0].entry_id


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("select:"):
        entry_id = data.split(":", 1)[1]
        results = context.user_data.get("search_results", {})
        info = results.get(entry_id, {})
        
        # If not in search results, try to get from stored show info
        if not info:
            info = context.user_data.get("show_info", {})
            # Update entry_id in show_info
            context.user_data["show_info"]["entry_id"] = entry_id
        
        title = info.get("title", "Unknown")
        year = info.get("year", 0)
        object_type = info.get("object_type", "MOVIE")

        await query.edit_message_text(f"⏳ Checking availability for *{title}* ({year}) across 40 countries...", parse_mode="Markdown")
        await process_entry_from_callback(query, context, entry_id, title, year, object_type)
    elif data.startswith("seasons:"):
        parts = data.split(":")
        entry_id = parts[1]
        title = parts[2]
        year = parts[3]
        # Store show info for back navigation
        context.user_data["show_info"] = {"entry_id": entry_id, "title": title, "year": int(year), "object_type": "SHOW"}
        await show_seasons(query, context, entry_id, title, year)
    elif data.startswith("season_availability:"):
        season_entry_id = data.split(":", 1)[1]
        
        # Get season data from context
        seasons_data = context.user_data.get("seasons_data", {})
        season_info = seasons_data.get(season_entry_id, {})
        season_title = season_info.get("title", "Unknown Season")
        season_year = season_info.get("year", "Unknown")
        
        # Get show info from context
        show_info = context.user_data.get("show_info", {})
        show_entry_id = show_info.get("entry_id", season_entry_id)
        show_title = show_info.get("title", "Unknown")
        show_year = show_info.get("year", "Unknown")
        
        await process_season_availability(query, context, season_entry_id, season_title, season_year, show_entry_id, show_title, show_year)


async def process_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, entry_id: str, title: str, year: int, object_type: str | None = None):
    """Process a single entry and send availability info."""
    msg = await update.message.reply_text(
        f"⏳ Checking availability for *{title}* ({year}) across 40 countries...",
        parse_mode="Markdown",
    )

    availability = await asyncio.to_thread(check_availability, entry_id)
    response = format_availability(title, year, availability)

    # If it's a TV show, add a button to view seasons
    if object_type == "SHOW":
        # Store show info for back navigation
        context.user_data["show_info"] = {"entry_id": entry_id, "title": title, "year": year, "object_type": "SHOW"}
        keyboard = [[InlineKeyboardButton("📺 View Seasons", callback_data=f"seasons:{entry_id}:{title}:{year}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(response, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await msg.edit_text(response, parse_mode="Markdown")


async def process_entry_from_callback(query, context: ContextTypes.DEFAULT_TYPE, entry_id: str, title: str, year: int, object_type: str | None = None):
    """Process entry from a callback query."""
    availability = await asyncio.to_thread(check_availability, entry_id)
    response = format_availability(title, year, availability)

    # If it's a TV show, add a button to view seasons
    if object_type == "SHOW":
        # Store show info for back navigation
        context.user_data["show_info"] = {"entry_id": entry_id, "title": title, "year": year, "object_type": "SHOW"}
        keyboard = [[InlineKeyboardButton("📺 View Seasons", callback_data=f"seasons:{entry_id}:{title}:{year}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await query.edit_message_text(response, parse_mode="Markdown")


async def show_seasons(query, context: ContextTypes.DEFAULT_TYPE, entry_id: str, title: str, year: int):
    """Show seasons for a TV show as clickable buttons."""
    await query.edit_message_text(f"⏳ Fetching seasons for *{title}*...", parse_mode="Markdown")
    
    try:
        seasons_data = await asyncio.to_thread(seasons, entry_id, "US", "en", True)
        
        if not seasons_data:
            await query.edit_message_text(f"📺 *{title}* ({year})\n\nNo season information available.", parse_mode="Markdown")
            return
        
        msg = f"📺 *{title}* ({year}) - Select a Season\n\n"
        msg += "Choose a season to check its availability:\n"
        
        # Create keyboard with season buttons
        keyboard = []
        for season in seasons_data:
            season_num = season.season_number if hasattr(season, 'season_number') else "Unknown"
            season_title = season.title if hasattr(season, 'title') else f"Season {season_num}"
            release_year = season.release_year if hasattr(season, 'release_year') else "Unknown"
            
            # Use the season's entry_id for availability checking
            season_entry_id = season.entry_id if hasattr(season, 'entry_id') else entry_id
            
            label = f"📺 {season_title} ({release_year})"
            # Store season data in context and use entry_id in callback
            callback_data = f"season_availability:{season_entry_id}"
            keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
        
        # Add back button
        keyboard.append([InlineKeyboardButton("🔙 Back to Show Availability", callback_data=f"select:{entry_id}")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(msg, parse_mode="Markdown", reply_markup=reply_markup)
        
        # Store seasons data for callback
        context.user_data["seasons_data"] = {
            season.entry_id: {
                "title": season.title if hasattr(season, 'title') else f"Season {season.season_number}",
                "year": season.release_year if hasattr(season, 'release_year') else "Unknown",
                "season_number": season.season_number if hasattr(season, 'season_number') else "Unknown"
            }
            for season in seasons_data if hasattr(season, 'entry_id')
        }
        # Store show info for back navigation
        context.user_data["show_info"] = {"entry_id": entry_id, "title": title, "year": year}
        
    except JustWatchError as e:
        logger.error("Error fetching seasons: %s", e)
        await query.edit_message_text(f"❌ Error fetching seasons: {e}", parse_mode="Markdown")


async def process_season_availability(query, context: ContextTypes.DEFAULT_TYPE, season_entry_id: str, season_title: str, season_year: str, show_entry_id: str, show_title: str, show_year: str):
    """Process availability for a specific season."""
    logger.info(f"Checking availability for season: {season_title} with entry_id: {season_entry_id}")
    await query.edit_message_text(f"⏳ Checking availability for *{season_title}* across 40 countries...", parse_mode="Markdown")
    
    availability = await asyncio.to_thread(check_availability, season_entry_id)
    logger.info(f"Availability result for {season_title}: {availability}")
    
    # Handle year conversion - it might be string or int
    try:
        year_int = int(season_year) if isinstance(season_year, str) else season_year
    except (ValueError, TypeError):
        year_int = 0
    
    response = format_availability(season_title, year_int, availability)
    
    # Add navigation buttons
    keyboard = [
        [InlineKeyboardButton("🔙 Back to Seasons", callback_data=f"seasons:{show_entry_id}:{show_title}:{show_year}")],
        [InlineKeyboardButton("📺 Back to Show Availability", callback_data=f"select:{show_entry_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(response, parse_mode="Markdown", reply_markup=reply_markup)


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
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"Health check server running on port {port}")
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