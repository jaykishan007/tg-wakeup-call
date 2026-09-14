"""
One-off interactive login. Run this on your laptop, NOT on the server —
it needs phone -> code -> 2FA input, which the server can't do.

Creates session.session in this directory, then prints every dialog
(chat/channel/group) you're in with its ID, so you can find CHANNEL_ID
for .env.

Usage:
    python login.py
"""
import asyncio
import os

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_NAME = "session"


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()  # prompts for phone, code, 2FA password as needed

    print("\nLogged in. Your dialogs:\n")
    print(f"{'ID':>15}  {'Type':<10}  Title")
    print("-" * 60)
    async for dialog in client.iter_dialogs():
        kind = "channel" if dialog.is_channel else ("group" if dialog.is_group else "user")
        print(f"{dialog.id:>15}  {kind:<10}  {dialog.name}")

    print("\nFind the channel you want above, copy its ID into CHANNEL_ID in .env.")
    print(f"session.session has been written to: {os.path.abspath(SESSION_NAME + '.session')}")
    print("Copy that file to the server alongside .env, then chmod 600 both.")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
