"""Human-like timing simulation for Telegram interactions."""

import asyncio
import random

# Average human typing speed: ~50 WPM = ~250 chars/min = ~4.2 chars/sec
CHARS_PER_SEC = 4.2
# Average reading speed: ~250 WPM = ~1250 chars/min = ~20.8 chars/sec
READ_CHARS_PER_SEC = 20.8

# Thinking time before composing a reply (seconds)
THINK_MIN = 1.5
THINK_MAX = 5.0

# Minimum/maximum time to wait for a bot reply before timing out
REPLY_TIMEOUT = 90

# Burst collection: quiet window after last message before declaring "done"
BURST_QUIET_SECONDS = 8.0
# Longer quiet window after a button click (bot may send more messages)
BUTTON_BURST_QUIET_SECONDS = 12.0
# Absolute cap on burst collection regardless of quiet window
MAX_BURST_SECONDS = 45.0

# Global speed multiplier — set via BookyTester(speed=N). N=1 is human pace.
# N=3 means 3× faster typing/reading/thinking; inter-flow pauses also scale.
_speed: float = 1.0


def set_speed(multiplier: float) -> None:
    global _speed
    _speed = max(0.1, float(multiplier))


def typing_delay(message: str, jitter: float = 0.2) -> float:
    base = len(message) / CHARS_PER_SEC / _speed
    return max(0.3, base * random.uniform(1 - jitter, 1 + jitter))


def reading_delay(response: str, jitter: float = 0.2) -> float:
    base = len(response) / READ_CHARS_PER_SEC / _speed
    base = max(0.3, min(base, 10.0 / _speed))
    return base * random.uniform(1 - jitter, 1 + jitter)


def thinking_delay() -> float:
    return random.uniform(THINK_MIN / _speed, THINK_MAX / _speed)


def flow_pause(n_turns: int) -> float:
    """Inter-flow gap scaled by speed. Minimum 5s to avoid hammering the bot."""
    base = 20 + (n_turns * 5)
    return max(5.0, base / _speed)


async def human_type(message: str) -> None:
    await asyncio.sleep(typing_delay(message))


async def human_read(response: str) -> None:
    await asyncio.sleep(reading_delay(response) + thinking_delay())
