"""
Telegram channel -> phone call alert.

Watches one Telegram channel (as a userbot, via Telethon) and places a
Twilio voice call to a fixed mobile number whenever a new post looks like
an actionable trade instruction (open/close/cancel/stoploss/entry/etc,
see is_actionable), subject to a cooldown so that a burst of channel
activity doesn't trigger a burst of calls (which Indian carriers flag as
spam/robocall behavior).

Run with: python listener.py
Requires session.session (from login.py) in the same directory, and a
populated .env (see .env.example).
"""
import asyncio
import logging
import os
import re
import time
from xml.sax.saxutils import escape as xml_escape

from dotenv import load_dotenv
from telethon import TelegramClient, events
from twilio.rest import Client as TwilioClient

load_dotenv()

TG_API_ID = int(os.environ["TG_API_ID"])
TG_API_HASH = os.environ["TG_API_HASH"]
CHANNEL_ID = int(os.environ["CHANNEL_ID"])

TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM = os.environ["TWILIO_FROM"]
TWILIO_TO = os.environ["TWILIO_TO"]

COOLDOWN_MINUTES = float(os.environ.get("COOLDOWN_MINUTES", "10"))
COOLDOWN_SECONDS = COOLDOWN_MINUTES * 60
RING_TIMEOUT_SECONDS = 30
MAX_MESSAGE_CHARS = 200

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
SESSION_NAME = "session"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("tg-alert")

# Surface Telethon's own reconnect/network logging so a silent death is
# visible in the systemd journal instead of the process just going quiet.
logging.getLogger("telethon").setLevel(logging.INFO)

twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
client = TelegramClient(SESSION_NAME, TG_API_ID, TG_API_HASH)

_last_call_ts = 0.0

# Only call for messages that look like actual trade instructions, not PnL
# brags, commentary, or rhetorical noise. Derived from + validated against
# 2 weeks of real channel history.
_ACTIONABLE_PATTERNS = [
    re.compile(p)
    for p in (
        r"\bopen long\b",
        r"\bopen short\b",
        r"\border limit\b",
        r"\bclose\b",
        r"\bcancel\b",
        r"\bstop[- ]?loss\b",
        r"\bentry\b",
        r"\bbuy\b",
        r"\badd\b",
    )
]
_VOL_RE = re.compile(r"\bvol\b")
_CAPITAL_RE = re.compile(r"\bcapital\b")
# bare "short"/"long" directly attached to a ticker, e.g. "Short #Lab", "long $ZEC"
_TICKER_RE = re.compile(r"\b(short|long)\s*[#$]\w+")
_BARE_DIRECTION_RE = re.compile(r"\b(short|long)\b")
# re-entry, e.g. "Round 2", "Movr round2"; but not PnL like "Round 2 +25%"
_ROUND_RE = re.compile(r"\bround\s*\d+\b(?!\s*\+\d)")
# re-entry signals are terse; longer "round 2" posts are commentary
ROUND_MAX_WORDS = 10


def is_actionable(text: str | None) -> bool:
    if not text:
        return False
    t = text.lower()
    if any(p.search(t) for p in _ACTIONABLE_PATTERNS):
        return True
    if _TICKER_RE.search(t):
        return True
    if _BARE_DIRECTION_RE.search(t) and (_VOL_RE.search(t) or _CAPITAL_RE.search(t)):
        return True
    if _ROUND_RE.search(t) and len(t.split()) <= ROUND_MAX_WORDS:
        return True
    return False


def build_twiml(channel_title: str, message_text: str | None) -> str:
    say_text = f"Alert. New post in {channel_title}."
    if message_text:
        snippet = re.sub(r"\s+", " ", message_text).strip()[:MAX_MESSAGE_CHARS]
        if snippet:
            say_text += f" Message: {snippet}"
    say_text = xml_escape(say_text)
    return f"<Response><Say>{say_text}</Say></Response>"


def place_call(channel_title: str, message_text: str | None) -> None:
    twiml = build_twiml(channel_title, message_text)

    if DRY_RUN:
        log.info("DRY_RUN: would call %s from %s with twiml=%s", TWILIO_TO, TWILIO_FROM, twiml)
        return

    try:
        call = twilio_client.calls.create(
            to=TWILIO_TO,
            from_=TWILIO_FROM,
            timeout=RING_TIMEOUT_SECONDS,
            twiml=twiml,
        )
        log.info("Call placed: sid=%s to=%s", call.sid, TWILIO_TO)
    except Exception:
        log.exception("Failed to place Twilio call")


@client.on(events.NewMessage(chats=CHANNEL_ID))
async def on_new_message(event):
    global _last_call_ts

    chat = await event.get_chat()
    channel_title = getattr(chat, "title", "the channel")

    if not is_actionable(event.raw_text):
        log.info("New message in %s, skipping (not an actionable trade signal)", channel_title)
        return

    now = time.monotonic()
    elapsed = now - _last_call_ts
    if elapsed < COOLDOWN_SECONDS:
        remaining = COOLDOWN_SECONDS - elapsed
        log.info(
            "New actionable message in %s, but skipping call (cooldown active, %.0fs remaining)",
            channel_title,
            remaining,
        )
        return

    log.info("New actionable message in %s, triggering call", channel_title)
    _last_call_ts = now
    place_call(channel_title, event.raw_text)


async def main():
    log.info("Starting listener (DRY_RUN=%s, cooldown=%s min)", DRY_RUN, COOLDOWN_MINUTES)
    await client.start()
    log.info("Connected. Listening for new messages in channel %s", CHANNEL_ID)
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
