#!/usr/bin/env python3
"""
Telegram Authentication Helper

Run this script once to authenticate with Telegram and create a session file.
After successful authentication, the session file persists and the bot can
use Telegram without re-authentication.

Usage:
    python -m services.socials.telegram_auth

Requirements:
    - TELEGRAM_API_ID: From https://my.telegram.org/apps
    - TELEGRAM_API_HASH: From https://my.telegram.org/apps
    - TELEGRAM_PHONE: Your phone number (with country code, e.g., +1234567890)

The script will:
1. Connect to Telegram
2. Send a verification code to your Telegram app
3. Ask you to enter the code
4. Create a session file for future use
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def authenticate():
    """Interactive Telegram authentication."""
    try:
        from telethon import TelegramClient
    except ImportError:
        print("ERROR: Telethon not installed. Run: pip install Telethon")
        sys.exit(1)

    # Get credentials
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")
    phone = os.getenv("TELEGRAM_PHONE")

    if not api_id or not api_hash:
        print("\nERROR: Missing Telegram API credentials!")
        print("\nTo get credentials:")
        print("1. Go to https://my.telegram.org/apps")
        print("2. Log in with your phone number")
        print("3. Create a new application")
        print("4. Copy the api_id and api_hash")
        print("\nThen add to your .env file:")
        print("  TELEGRAM_API_ID=your_api_id")
        print("  TELEGRAM_API_HASH=your_api_hash")
        print("  TELEGRAM_PHONE=+1234567890")
        sys.exit(1)

    if not phone:
        print("\nERROR: Missing phone number!")
        print("Add TELEGRAM_PHONE=+1234567890 to your .env file")
        print("(Include country code, e.g., +1 for US)")
        sys.exit(1)

    # Session file location
    bot_dir = Path(__file__).parent.parent.parent
    session_path = bot_dir / "contrarian_bot"

    print("\n" + "=" * 50)
    print("Telegram Authentication")
    print("=" * 50)
    print(f"\nAPI ID: {api_id[:4]}...")
    print(f"Phone: {phone[:4]}...{phone[-4:]}")
    print(f"Session: {session_path}.session")
    print()

    # Create client
    client = TelegramClient(str(session_path), int(api_id), api_hash)

    await client.connect()

    if await client.is_user_authorized():
        print("Already authenticated! Session is valid.")
        me = await client.get_me()
        print(f"Logged in as: {me.first_name} (@{me.username})")
    else:
        print("Sending verification code to your Telegram app...")
        print("(Check your Telegram messages for the code)")
        print()

        await client.send_code_request(phone)

        code = input("Enter the code you received: ").strip()

        try:
            await client.sign_in(phone, code)
            print("\nAuthentication successful!")
            me = await client.get_me()
            print(f"Logged in as: {me.first_name} (@{me.username})")
        except Exception as e:
            if "two-step" in str(e).lower() or "password" in str(e).lower():
                # 2FA enabled
                password = input("Enter your 2FA password: ").strip()
                await client.sign_in(password=password)
                print("\nAuthentication successful!")
                me = await client.get_me()
                print(f"Logged in as: {me.first_name} (@{me.username})")
            else:
                print(f"\nAuthentication failed: {e}")
                await client.disconnect()
                sys.exit(1)

    # Test fetching from a channel
    print("\n" + "-" * 50)
    print("Testing channel access...")

    test_channels = ["CoinDesk", "Cointelegraph", "bitcoinmagazine"]
    for channel in test_channels:
        try:
            entity = await client.get_entity(channel)
            messages = await client.get_messages(entity, limit=1)
            if messages:
                print(f"  [OK] @{channel} - accessible")
            else:
                print(f"  [OK] @{channel} - no recent messages")
        except Exception as e:
            print(f"  [--] @{channel} - {type(e).__name__}")

    await client.disconnect()

    print("\n" + "=" * 50)
    print("Setup complete!")
    print(f"Session saved to: {session_path}.session")
    print("\nThe bot can now fetch Telegram messages automatically.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(authenticate())
