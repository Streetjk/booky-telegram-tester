# Booky Telegram Human-Pace Tester

End-to-end test suite for [Booky](https://booky.au) — an AI bookkeeping assistant
for Australian tradespeople. Tests the full Telegram → bot → Xero stack using a
real Telegram account, with human-realistic typing and reading delays.

## What it does

- Connects as a real Telegram user (not a mock) using [Telethon](https://github.com/LonamiWebs/Telethon)
- Sends messages to the bot at ~50 WPM typing speed with jitter
- Waits for bot replies, then pauses as if reading (proportional to reply length)
- Clicks inline buttons when the bot presents them (Yes/No, contact selection, etc.)
- Runs 10 trade personas across 20 conversation flows, 3 turns each
- Outputs pass/fail per turn + saves `results.json`

## Personas

| Persona | Trade | Flows |
|---------|-------|-------|
| Dave | Plumber | Quote create/confirm, expense + invoice |
| Sarah | Electrician | Invoice edit price, GST question then quote |
| Mike | Landscaper | Quote qty edit, expense tracking |
| Emma | Dog groomer | Invoice series, product expenses |
| Tom | IT consultant | Quote description edit, subscriptions |
| Jake | Concreter | Large job quote, multi-expense day |
| Lisa | Personal trainer | Recurring client invoices, equipment |
| Chen | Cleaner | Weekly invoices, cleaning supplies |
| Raj | Rideshare driver | Vehicle expenses, GST advice |
| Amy | Graphic designer | Project quote, software subscriptions |

## Setup

### 1. Get Telegram API credentials

Go to [my.telegram.org/apps](https://my.telegram.org/apps), log in with the test
account phone number, and create an application. Copy the **API ID** and **API Hash**.

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your API ID, API hash, test phone, and bot username
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Authenticate (first run only)

```bash
python run.py --quick
```

Telegram will send a verification code via SMS to `TELEGRAM_PHONE`. Enter it when
prompted. The session is saved locally — subsequent runs skip this step.

## Usage

```bash
# Full suite (~30–45 min at human pace)
python run.py

# Quick smoke test: Dave + Sarah, 1 flow each (~5 min)
python run.py --quick

# Specific personas
python run.py --personas Dave Tom Amy

# Specific flow name
python run.py --flows quote_create_confirm expense_then_invoice
```

## Output

```
==============================
PERSONA: Dave — Dave's Plumbing Services

  → Dave / quote_create_confirm
  [PASS] Dave/quote_create_confirm T1 (8.3s) — create quote
  [PASS] Dave/quote_create_confirm T2 (4.1s) [clicked: Yes] — confirm quote
  [PASS] Dave/quote_create_confirm T3 (6.2s) — recall quote number
```

Results are also saved to `results.json`.

## Timing model

| Event | Formula |
|-------|---------|
| Typing delay | `len(message) / 4.2 chars/s` ± 20% jitter |
| Reading delay | `len(reply) / 20.8 chars/s`, capped 1–10s |
| Thinking pause | 1.5–5s random |
| Between flows | 30s + (turns × 5s) |
| Reply timeout | 45s |

## Adding scenarios

Edit `booky_tester/personas.py`. Each turn is:

```python
T(
    message="Create a quote for Smith Co for 2 hours at $95",
    expect="95",          # substring expected in bot reply
    label="create quote", # shown in output
    button="Yes",         # inline button to click after reply (optional)
    optional=False,       # if True, failure here doesn't count as a fail
)
```
