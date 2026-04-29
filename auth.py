#!/usr/bin/env python3
"""One-time login via QR code. Run this first before run.py."""

import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

API_ID = 34637824
API_HASH = "dc757e40852cb404c8b56624823eb53f"
SESSION = "hiro_test"


async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already logged in as {me.first_name} (@{me.username})")
        await client.disconnect()
        return

    print("\nGenerating QR code...")
    print("Open Telegram Desktop → Settings → Devices → Link Desktop Device\n")

    while True:
        qr = await client.qr_login()

        # Print as text QR using qrcode library
        import qrcode
        qr_img = qrcode.make(qr.url)
        # ASCII render
        import io
        qr_ascii = qrcode.QRCode()
        qr_ascii.add_data(qr.url)
        qr_ascii.make(fit=True)
        f = io.StringIO()
        qr_ascii.print_ascii(out=f, invert=True)
        print(f.getvalue())
        print(f"(waiting up to 30s for scan...)\n")

        try:
            await asyncio.wait_for(qr.wait(), timeout=30)
            break  # scanned successfully
        except asyncio.TimeoutError:
            print("QR expired — generating new one...\n")
            continue
        except SessionPasswordNeededError:
            pwd = input("2FA password: ")
            await client.sign_in(password=pwd)
            break
        except Exception as e:
            print(f"Retrying ({e})...")
            continue

    me = await client.get_me()
    print(f"\n✓ Logged in as {me.first_name} (@{me.username})")
    print(f"Session saved to {SESSION}.session — run.py will use it automatically.\n")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
