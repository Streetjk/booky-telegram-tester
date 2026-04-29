#!/usr/bin/env python3
"""
Booky Telegram Human-Pace Tester
---------------------------------
Connects as a real Telegram user (Hiro's test account) and runs realistic
multi-turn conversations with the Booky bot at human typing/reading speed.

Usage:
    python run.py                          # all personas, all flows
    python run.py --personas Dave Sarah    # specific personas only
    python run.py --flows quote_create_confirm  # specific flow only
    python run.py --quick                  # 2 personas, 1 flow each (smoke test)

First run: Telegram will SMS a verification code to TELEGRAM_PHONE.
Subsequent runs: uses the saved session file (no code needed).
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy telethon logs
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
    p.add_argument("--quick", action="store_true", help="Quick mode: Dave + Sarah, first flow each")
    p.add_argument("--session", default="hiro_test", help="Telethon session file name")
    return p.parse_args()


async def main():
    args = parse_args()

    from booky_tester import BookyTester

    persona_filter = args.personas
    flow_filter = args.flows

    if args.quick:
        persona_filter = ["Dave", "Sarah"]
        flow_filter = None
        # Only first flow per persona — done in runner by slicing
        print("Quick mode: Dave + Sarah, first flow each\n")

    tester = BookyTester(
        api_id=int(get_env("TELEGRAM_API_ID")),
        api_hash=get_env("TELEGRAM_API_HASH"),
        phone=get_env("TELEGRAM_PHONE"),
        bot_username=get_env("BOT_USERNAME"),
        session_name=args.session,
        persona_filter=persona_filter,
        flow_filter=flow_filter,
    )

    if args.quick:
        # Limit to 1 flow per persona in quick mode
        from booky_tester.personas import PERSONAS
        for p in PERSONAS:
            if p["flows"]:
                p["flows"] = p["flows"][:1]

    report = await tester.run()
    passed = sum(1 for t in report.turns if t.passed)
    total = len(report.turns)
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
