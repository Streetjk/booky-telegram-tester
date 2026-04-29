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
REPLY_TIMEOUT = 45


def typing_delay(message: str, jitter: float = 0.2) -> float:
    """Seconds to wait before sending, simulating human typing."""
    base = len(message) / CHARS_PER_SEC
    # Add jitter ±20%
    return base * random.uniform(1 - jitter, 1 + jitter)


def reading_delay(response: str, jitter: float = 0.2) -> float:
    """Seconds to wait after receiving a response, simulating reading."""
    base = len(response) / READ_CHARS_PER_SEC
    # At least 1 second, cap at 10 seconds
    base = max(1.0, min(base, 10.0))
    return base * random.uniform(1 - jitter, 1 + jitter)


def thinking_delay() -> float:
    """Random pause between reading a response and composing the next message."""
    return random.uniform(THINK_MIN, THINK_MAX)


async def human_type(message: str) -> None:
    """Wait as if a human is typing the message."""
    delay = typing_delay(message)
    await asyncio.sleep(delay)


async def human_read(response: str) -> None:
    """Wait as if a human is reading the bot's response, then thinking."""
    delay = reading_delay(response) + thinking_delay()
    await asyncio.sleep(delay)
