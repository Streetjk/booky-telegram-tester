"""Telegram-based human-pace test runner using Telethon.

Connects as a real Telegram user (Hiro's test account), sends messages to
the bot at human typing speed, waits for replies at human reading speed,
and optionally clicks inline buttons.
"""

import asyncio
import os
import time
import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.types import Message, ReplyInlineMarkup, KeyboardButtonCallback

from .timing import human_type, human_read, REPLY_TIMEOUT
from .personas import PERSONAS, Turn
from .reporter import Report, TurnResult

logger = logging.getLogger("booky_tester")


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
    ):
        self.client = TelegramClient(session_name, api_id, api_hash)
        self.phone = phone
        self.bot_username = bot_username
        self.persona_filter = persona_filter
        self.flow_filter = flow_filter
        self.report = Report()
        self._reply_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._bot_entity = None

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

        @self.client.on(events.NewMessage(from_users=self._bot_entity))
        async def _on_bot_message(event):
            await self._reply_queue.put(event.message)

    async def _send(self, text: str) -> Message:
        """Simulate human typing then send the message."""
        await human_type(text)
        sent = await self.client.send_message(self._bot_entity, text)
        logger.debug("→ sent: %s", text[:80])
        return sent

    async def _wait_reply(self) -> Optional[Message]:
        """Wait for the bot's reply, collecting all messages within a burst window."""
        try:
            # Wait for the first message
            first = await asyncio.wait_for(self._reply_queue.get(), timeout=REPLY_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("Timed out waiting for bot reply")
            return None

        # Collect any additional messages sent in quick succession (e.g. split replies)
        combined_text = first.text or ""
        last_message = first
        while True:
            try:
                extra = await asyncio.wait_for(self._reply_queue.get(), timeout=2.0)
                combined_text += "\n" + (extra.text or "")
                last_message = extra
            except asyncio.TimeoutError:
                break

        # Return a synthesised message with combined text but last message's buttons
        last_message.message = combined_text
        logger.debug("← reply: %s", combined_text[:120])
        return last_message

    def _extract_buttons(self, msg: Message) -> dict[str, KeyboardButtonCallback]:
        """Return {button_label: button_object} from an inline keyboard."""
        buttons = {}
        if not msg.reply_markup:
            return buttons
        if isinstance(msg.reply_markup, ReplyInlineMarkup):
            for row in msg.reply_markup.rows:
                for btn in row.buttons:
                    if isinstance(btn, KeyboardButtonCallback):
                        buttons[btn.text] = btn
        return buttons

    async def _click_button(self, msg: Message, label_substr: str) -> Optional[Message]:
        """Click the first inline button whose label contains label_substr."""
        buttons = self._extract_buttons(msg)
        for label, btn in buttons.items():
            if label_substr.lower() in label.lower():
                logger.debug("Clicking button: %s", label)
                await msg.click(data=btn.data)
                return await self._wait_reply()
        logger.warning("Button %r not found in %s", label_substr, list(buttons.keys()))
        return None

    async def _run_turn(self, persona_name: str, flow_name: str, idx: int, turn: Turn) -> TurnResult:
        t0 = time.time()
        reply_msg = None
        button_clicked = None
        passed = False
        reason = ""
        reply_text = ""

        # Send the user message
        sent = await self._send(turn["message"])

        # Wait for bot reply
        reply_msg = await self._wait_reply()
        if reply_msg is None:
            reason = "No reply received (timeout)"
            return TurnResult(
                persona=persona_name, flow=flow_name, turn=idx + 1,
                label=turn["label"], message=turn["message"],
                reply="", passed=False, expect=turn["expect"],
                button_clicked=None, elapsed_s=time.time() - t0, reason=reason,
            )

        reply_text = reply_msg.message or ""

        # Click inline button if requested
        if turn.get("button") and reply_msg:
            button_reply = await self._click_button(reply_msg, turn["button"])
            if button_reply:
                reply_text += "\n" + (button_reply.message or "")
                button_clicked = turn["button"]
                reply_msg = button_reply

        # Evaluate pass/fail
        expect = turn["expect"]
        passed = expect.lower() in reply_text.lower()
        if not passed and not turn.get("optional"):
            reason = f"Expected {expect!r} not found"

        # Simulate human reading the reply before next turn
        await human_read(reply_text)

        return TurnResult(
            persona=persona_name, flow=flow_name, turn=idx + 1,
            label=turn["label"], message=turn["message"],
            reply=reply_text, passed=passed or bool(turn.get("optional")),
            expect=expect, button_clicked=button_clicked,
            elapsed_s=time.time() - t0,
            reason="" if (passed or turn.get("optional")) else reason,
        )

    async def _run_flow(self, persona_name: str, flow_name: str, turns: list[Turn]) -> None:
        print(f"\n  → {persona_name} / {flow_name}")
        for idx, turn in enumerate(turns):
            result = await self._run_turn(persona_name, flow_name, idx, turn)
            self.report.add(result)

    async def run(self) -> Report:
        # Use `async with` so Telethon starts its update receiver loop,
        # which is required for event handlers to fire.
        async with self.client:
            if not await self.client.is_user_authorized():
                await self._qr_login()

            self._bot_entity = await self.client.get_entity(self.bot_username)
            me = await self.client.get_me()
            logger.info("Connected as %s (@%s), bot: %s", me.first_name, me.username, self.bot_username)

            # Register event handler inside the running context
            @self.client.on(events.NewMessage(from_users=self._bot_entity))
            async def _on_bot_message(event):
                await self._reply_queue.put(event.message)

            personas = PERSONAS
            if self.persona_filter:
                personas = [p for p in personas if p["name"] in self.persona_filter]

            for persona in personas:
                print(f"\n{'='*60}")
                print(f"PERSONA: {persona['name']} — {persona['business']}")
                flows = persona["flows"]
                if self.flow_filter:
                    flows = [f for f in flows if f["name"] in self.flow_filter]
                for flow in flows:
                    await self._run_flow(persona["name"], flow["name"], flow["turns"])
                    gap = 30 + (len(flow["turns"]) * 5)
                    logger.info("Pausing %ds between flows...", gap)
                    await asyncio.sleep(gap)

        self.report.summary()
        self.report.save()
        return self.report
