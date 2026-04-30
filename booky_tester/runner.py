"""Telegram-based human-pace test runner using Telethon."""

import asyncio
import os
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message, ReplyInlineMarkup, KeyboardButtonCallback

from .timing import (
    human_type, human_read, REPLY_TIMEOUT,
    BURST_QUIET_SECONDS, BUTTON_BURST_QUIET_SECONDS, MAX_BURST_SECONDS,
    set_speed, flow_pause,
)
from .personas import PERSONAS, Turn
from .reporter import Report, TurnResult

logger = logging.getLogger("booky_tester")

TRIAL_LIMIT_PATTERNS = (
    "50-message",
    "daily message limit",
    "message limit",
    "free trial",
    "trial limit",
    "try again tomorrow",
    "limit resets",
)


def _is_trial_limit(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in TRIAL_LIMIT_PATTERNS)


def _seconds_until_midnight_utc() -> float:
    now = datetime.now(timezone.utc)
    reset = (now + timedelta(days=1)).replace(hour=0, minute=1, second=0, microsecond=0)
    return max(60.0, (reset - now).total_seconds())


class TrialRateLimitReached(Exception):
    pass


async def _flush_hiro_sessions() -> None:
    """Delete Hiro's Redis session keys so each persona starts fresh."""
    try:
        import redis.asyncio as aioredis
    except ImportError:
        logger.warning("redis package not installed — skipping session flush")
        return

    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", "6379"))
    password = os.getenv("REDIS_PASSWORD") or None
    user_ids = (os.getenv("HIRO_USER_IDS") or "").split()

    if not user_ids:
        logger.debug("HIRO_USER_IDS not set — skipping session flush")
        return

    try:
        r = aioredis.Redis(host=host, port=port, password=password, decode_responses=True)
        deleted = 0
        for uid in user_ids:
            for prefix in ("session", "session_snapshot", "pending_action",
                           "mem", "graph_ctx", "memctx"):
                key = f"{prefix}:{uid}"
                deleted += await r.delete(key)
        await r.aclose()
        logger.info("Flushed %d Redis session keys for Hiro", deleted)
    except Exception as e:
        logger.warning("Session flush failed: %s", e)


class BookyTester:
    def __init__(
        self,
        api_id: int,
        api_hash: str,
        bot_username: str,
        phone: str = "",
        session_name: str = "hiro_test",
        persona_filter: Optional[list[str]] = None,
        flow_filter: Optional[list[str]] = None,
        quick_flow_limit: Optional[int] = None,
        no_wait_on_limit: bool = False,
        iterations: int = 1,
        speed: float = 1.0,
    ):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.phone = phone
        self.bot_username = bot_username
        self.persona_filter = persona_filter
        self.flow_filter = flow_filter
        self.quick_flow_limit = quick_flow_limit
        self.no_wait_on_limit = no_wait_on_limit
        self.iterations = iterations
        set_speed(speed)
        self.report = Report()
        self._reply_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._bot_entity = None
        self._last_reply: Optional[Message] = None

    async def _qr_login(self) -> None:
        """Log in via QR code — scan with Telegram Desktop or mobile app."""
        import qrcode, io
        from telethon.errors import SessionPasswordNeededError
        print("\n" + "=" * 60)
        print("First-time login — scan the QR code with Telegram Desktop")
        print("(Settings → Devices → Link Desktop Device)")
        print("=" * 60 + "\n")
        while True:
            qr = await self.client.qr_login()
            qr_obj = qrcode.QRCode()
            qr_obj.add_data(qr.url)
            qr_obj.make(fit=True)
            f = io.StringIO()
            qr_obj.print_ascii(out=f, invert=True)
            print(f.getvalue())
            print("(waiting up to 30s for scan...)\n")
            try:
                await asyncio.wait_for(qr.wait(), timeout=30)
                break
            except asyncio.TimeoutError:
                print("QR expired — generating new one...\n")
                continue
            except SessionPasswordNeededError:
                pwd = input("2FA password: ")
                await self.client.sign_in(password=pwd)
                break
            except Exception as e:
                logger.debug("QR wait error: %s, retrying", e)
                continue
        print("✓ Logged in! Session saved — no scan needed next time.\n")

    async def _send(self, text: str) -> Message:
        await human_type(text)
        sent = await self.client.send_message(self._bot_entity, text)
        logger.debug("→ sent: %s", text[:80])
        return sent

    async def _wait_reply(self, quiet_s: float = BURST_QUIET_SECONDS) -> Optional[tuple[str, Message]]:
        """Wait for the bot's reply, collecting burst messages within a quiet window.

        Returns (combined_text, clickable_message) or None on timeout.
        The clickable_message is the last message that has inline buttons, or
        the last message overall if none have buttons.
        """
        try:
            first = await asyncio.wait_for(self._reply_queue.get(), timeout=REPLY_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for bot reply")
            return None

        messages = [first]
        deadline = time.monotonic() + MAX_BURST_SECONDS
        while time.monotonic() < deadline:
            try:
                extra = await asyncio.wait_for(
                    self._reply_queue.get(),
                    timeout=min(quiet_s, max(0.1, deadline - time.monotonic())),
                )
                messages.append(extra)
            except asyncio.TimeoutError:
                break

        combined_text = "\n".join(m.text or "" for m in messages)
        # Prefer the last message with inline buttons as the clickable one
        clickable = next(
            (m for m in reversed(messages) if self._extract_buttons(m)),
            messages[-1],
        )
        logger.debug("← reply (%d msgs): %s", len(messages), combined_text[:120])
        return combined_text, clickable

    def _extract_buttons(self, msg: Message) -> dict[str, KeyboardButtonCallback]:
        buttons = {}
        if not msg or not msg.reply_markup:
            return buttons
        if isinstance(msg.reply_markup, ReplyInlineMarkup):
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if isinstance(btn, KeyboardButtonCallback):
                        buttons[btn.text] = btn
        return buttons

    async def _click_button(self, msg: Message, label_substr: str) -> Optional[tuple[str, Message]]:
        """Click the first inline button whose label contains label_substr."""
        buttons = self._extract_buttons(msg)
        for label, btn in buttons.items():
            if label_substr.lower() in label.lower():
                logger.debug("Clicking button: %s", label)
                await msg.click(data=btn.data)
                return await self._wait_reply(quiet_s=BUTTON_BURST_QUIET_SECONDS)
        logger.warning("Button %r not found in %s", label_substr, list(buttons.keys()))
        return None

    def _drain_queue(self) -> None:
        """Discard stale replies from a previous timed-out turn."""
        drained = 0
        while not self._reply_queue.empty():
            try:
                self._reply_queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained:
            logger.debug("Drained %d stale reply(s) from queue", drained)

    async def _run_turn(self, persona_name: str, flow_name: str, idx: int, turn: Turn) -> TurnResult:
        t0 = time.time()
        button_clicked = None
        reply_text = ""
        reply_msg = None

        self._drain_queue()

        if not turn.get("message") and turn.get("button"):
            # Button-only turn: click button on last reply, no text sent
            if self._last_reply:
                result = await self._click_button(self._last_reply, turn["button"])
                if result:
                    reply_text, reply_msg = result
                    button_clicked = turn["button"]
                else:
                    return TurnResult(
                        persona=persona_name, flow=flow_name, turn=idx + 1,
                        label=turn["label"], message="",
                        reply="", passed=False, expect=turn["expect"],
                        button_clicked=None, elapsed_s=time.time() - t0,
                        reason=f"Button {turn['button']!r} not found or no reply after click",
                    )
            else:
                logger.warning("Button-only turn but no last reply to click")
                return TurnResult(
                    persona=persona_name, flow=flow_name, turn=idx + 1,
                    label=turn["label"], message="",
                    reply="", passed=False, expect=turn["expect"],
                    button_clicked=None, elapsed_s=time.time() - t0,
                    reason="Button-only turn but no previous reply to click",
                )
        else:
            # Normal turn: send text, wait for reply
            await self._send(turn["message"])
            result = await self._wait_reply()
            if result is None:
                return TurnResult(
                    persona=persona_name, flow=flow_name, turn=idx + 1,
                    label=turn["label"], message=turn["message"],
                    reply="", passed=False, expect=turn["expect"],
                    button_clicked=None, elapsed_s=time.time() - t0,
                    reason="No reply received (timeout)",
                )
            reply_text, reply_msg = result

            # Check for trial limit before clicking any button
            if _is_trial_limit(reply_text):
                raise TrialRateLimitReached(reply_text)

            # Optionally click a button on this reply
            if turn.get("button"):
                btn_result = await self._click_button(reply_msg, turn["button"])
                if btn_result:
                    extra_text, reply_msg = btn_result
                    reply_text += "\n" + extra_text
                    button_clicked = turn["button"]

        # Check for trial limit in any collected reply
        if _is_trial_limit(reply_text):
            raise TrialRateLimitReached(reply_text)

        self._last_reply = reply_msg

        expect = turn["expect"]
        passed = expect.lower() in reply_text.lower()
        reason = "" if (passed or turn.get("optional")) else f"Expected {expect!r} not found"

        await human_read(reply_text)

        return TurnResult(
            persona=persona_name, flow=flow_name, turn=idx + 1,
            label=turn["label"], message=turn["message"],
            reply=reply_text, passed=passed or bool(turn.get("optional")),
            expect=expect, button_clicked=button_clicked,
            elapsed_s=time.time() - t0, reason=reason,
        )

    async def _run_flow(self, persona_name: str, flow_name: str, turns: list[Turn]) -> None:
        print(f"\n  → {persona_name} / {flow_name}")
        self._last_reply = None
        for idx, turn in enumerate(turns):
            while True:
                try:
                    result = await self._run_turn(persona_name, flow_name, idx, turn)
                    break
                except TrialRateLimitReached:
                    if self.no_wait_on_limit:
                        result = TurnResult(
                            persona=persona_name, flow=flow_name, turn=idx + 1,
                            label=turn["label"], message=turn.get("message", ""),
                            reply="TRIAL LIMIT REACHED", passed=False,
                            expect=turn["expect"], button_clicked=None,
                            elapsed_s=0, reason="Trial daily message limit reached",
                        )
                        break
                    wait_s = _seconds_until_midnight_utc()
                    h, m = divmod(int(wait_s), 3600)
                    m //= 60
                    print(f"\n  ⏸  TRIAL LIMIT HIT — pausing {h}h {m}m until midnight UTC reset")
                    logger.warning("Trial cap hit. Sleeping %.0fs until midnight UTC.", wait_s)
                    await asyncio.sleep(wait_s)
                    self._drain_queue()
                    await _flush_hiro_sessions()
                    await asyncio.sleep(3)
                    continue
            self.report.add(result)

    async def run(self) -> Report:
        async with self.client:
            if not await self.client.is_user_authorized():
                await self._qr_login()

            self._bot_entity = await self.client.get_entity(self.bot_username)
            me = await self.client.get_me()
            logger.info("Connected as %s (@%s), bot: %s", me.first_name, me.username, self.bot_username)

            @self.client.on(events.NewMessage(from_users=self._bot_entity))
            async def _on_bot_message(event):
                await self._reply_queue.put(event.message)

            personas = PERSONAS
            if self.persona_filter:
                personas = [p for p in personas if p["name"] in self.persona_filter]

            for iteration in range(1, self.iterations + 1):
                if self.iterations > 1:
                    print(f"\n{'#'*60}")
                    print(f"ITERATION {iteration}/{self.iterations}")
                    print(f"{'#'*60}")
                for persona in personas:
                    await _flush_hiro_sessions()
                    await asyncio.sleep(3)

                    print(f"\n{'='*60}")
                    print(f"PERSONA: {persona['name']} — {persona['business']}")

                    flows = list(persona["flows"])  # copy — never mutate the module-level list
                    if self.quick_flow_limit is not None:
                        flows = flows[:self.quick_flow_limit]
                    if self.flow_filter:
                        flows = [f for f in flows if f["name"] in self.flow_filter]

                    for flow in flows:
                        await self._run_flow(persona["name"], flow["name"], flow["turns"])
                        gap = flow_pause(len(flow["turns"]))
                        logger.info("Pausing %.0fs between flows...", gap)
                        await asyncio.sleep(gap)

        self.report.summary()
        self.report.save()
        return self.report
