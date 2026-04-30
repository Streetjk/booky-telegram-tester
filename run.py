#!/usr/bin/env python3
"""
Booky Telegram Human-Pace Tester
---------------------------------
Connects as a real Telegram user (Hiro) and runs realistic multi-turn
conversations with the Booky bot at human typing/reading speed.

Usage:
    python run.py                          # all personas, all flows
    python run.py --personas Dave Sarah    # specific personas only
    python run.py --flows quote_create_confirm  # specific flow only
    python run.py --quick                  # Dave + Sarah, 1 flow each (~5 min)
    python run.py --no-wait-on-limit       # fail immediately on trial cap (for CI)

First run: a QR code prints in the terminal.
  → Open Telegram Desktop → Settings → Devices → Link Desktop Device → scan.
  Session saved to hiro_test.session — no scan needed on subsequent runs.
"""

import argparse
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("telethon").setLevel(logging.WARNING)


def get_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"ERROR: {key} not set. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    return val


def parse_args():
    p = argparse.ArgumentParser(description="Booky Telegram Human-Pace Tester")
    p.add_argument("--personas", nargs="+", help="Run only these personas (e.g. Dave Sarah)")
    p.add_argument("--flows", nargs="+", help="Run only these flows (e.g. quote_create_confirm)")
    p.add_argument("--quick", action="store_true", help="Quick mode: Dave + Sarah, first flow each (~5 min)")
    p.add_argument("--no-wait-on-limit", action="store_true", help="Fail immediately on trial limit instead of sleeping until midnight UTC (for CI)")
    p.add_argument("--session", default="hiro_test", help="Telethon session file name")
    return p.parse_args()


async def main():
    args = parse_args()

    from booky_tester import BookyTester

    persona_filter = args.personas
    flow_filter = args.flows
    quick_flow_limit = None

    if args.quick:
        persona_filter = persona_filter or ["Dave", "Sarah"]
        quick_flow_limit = 1
        print("Quick mode: Dave + Sarah, first flow each\n")

    tester = BookyTester(
        api_id=int(get_env("TELEGRAM_API_ID")),
        api_hash=get_env("TELEGRAM_API_HASH"),
        bot_username=get_env("BOT_USERNAME"),
        session_name=args.session,
        persona_filter=persona_filter,
        flow_filter=flow_filter,
        quick_flow_limit=quick_flow_limit,
        no_wait_on_limit=args.no_wait_on_limit,
    )

    report = await tester.run()
    passed = sum(1 for t in report.turns if t.passed)
    total = len(report.turns)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
