"""Vercel serverless webhook endpoint for the Telegram bot.

Telegram sends updates as POST requests to this endpoint. Each request
builds the application, processes a single update, and returns 200.
"""

import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

# Make the project root importable (Vercel only adds api/ by default)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update  # noqa: E402

from bot import build_application  # noqa: E402


async def process_update(data: dict) -> None:
    application = build_application()
    async with application:
        update = Update.de_json(data, application.bot)
        if update:
            await application.process_update(update)


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        asyncio.run(process_update(data))
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        # Health check so you can verify the deployment in a browser
        token_set = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(
            b"Bot is running. Telegram webhooks should POST here.\n"
            b"TELEGRAM_BOT_TOKEN configured: %s\n" % (b"yes" if token_set else b"NO - set it in Vercel env vars")
        )

    def log_message(self, format, *args):
        pass
