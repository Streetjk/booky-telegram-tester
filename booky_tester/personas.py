"""10 trade personas with realistic multi-turn conversation flows.

Each flow is a list of turns. A turn is:
  message       str   — what the user types
  expect        str   — substring expected somewhere in the bot reply (case-insensitive)
  button        str|None — label substring of an inline button to click (if any)
  label         str   — human-readable description of this turn
  optional      bool  — if True, a miss here doesn't fail the scenario
"""

from typing import TypedDict


class Turn(TypedDict):
    message: str
    expect: str
    label: str
    button: str | None
    optional: bool


class Flow(TypedDict):
    name: str
    turns: list[Turn]


class Persona(TypedDict):
    name: str
    business: str
    trade: str
    flows: list[Flow]


def T(message: str, expect: str, label: str, button: str | None = None, optional: bool = False) -> Turn:
    return {"message": message, "expect": expect, "label": label, "button": button, "optional": optional}


def TClick(expect: str, label: str, button: str = "✅") -> Turn:
    """Button-only turn — clicks an inline button from the previous reply, sends no text."""
    return {"message": "", "expect": expect, "label": label, "button": button, "optional": False}


PERSONAS: list[Persona] = [
    {
        "name": "Dave",
        "business": "Dave's Plumbing Services",
        "trade": "plumber",
        "flows": [
            {
                "name": "quote_create_confirm",
                "turns": [
                    T("Hey, can you make a quote for Riverside Apartments for 3 hours of hot water system repair at $145 per hour?",
                      "145", "create quote"),
                    TClick("QU-", "confirm quote"),
                    T("Thanks, what's my latest quote number?", "QU-", "recall quote number"),
                ],
            },
            {
                "name": "expense_then_invoice",
                "turns": [
                    T("Spent $87.50 on copper fittings at Reece Plumbing today", "87.50", "log expense"),
                    T("Now create an invoice for Johnson Building for emergency leak repair, 2.5 hours at $160",
                      "160", "create invoice"),
                    TClick("INV-", "confirm invoice"),
                ],
            },
        ],
    },
    {
        "name": "Sarah",
        "business": "Spark Electrical Solutions",
        "trade": "electrician",
        "flows": [
            {
                "name": "invoice_edit_price",
                "turns": [
                    T("Invoice Western Commercial for switchboard upgrade, 4 hours at $185 per hour plus $320 materials",
                      "185", "create invoice"),
                    TClick("185", "dismiss pending, see preview"),
                    T("Actually change the materials to $450", "450", "edit price"),
                    TClick("INV-", "confirm invoice"),
                ],
            },
            {
                "name": "gst_question_then_quote",
                "turns": [
                    T("Quick question — do I charge GST on labour and materials separately or combined?",
                      "GST", "tax question"),
                    T("Ok cool. Create a quote for Riverside Cafe for LED lighting upgrade, 6 hours at $175",
                      "175", "quote after question"),
                    TClick("QU-", "confirm quote"),
                ],
            },
        ],
    },
    {
        "name": "Mike",
        "business": "GreenScape Landscaping",
        "trade": "landscaper",
        "flows": [
            {
                "name": "quote_qty_edit",
                "turns": [
                    T("Quote for Hillside Estate for garden design consultation 2 hours at $95 and mulching 4 hours at $75",
                      "95", "create multi-item quote"),
                    TClick("95", "confirm initial quote"),
                    T("Update the Hillside Estate quote: set garden design consultation to 3 hours and mulching to 3 hours",
                      "3", "qty update"),
                    TClick("QU-", "confirm updated quote"),
                ],
            },
            {
                "name": "expense_tracking",
                "turns": [
                    T("Bought $230 worth of native plants from Bunnings for the Oakwood job", "230", "log expense"),
                    T("Also $45 fuel for the trailer", "45", "second expense"),
                    T("What did I spend today?", "230", "recall expenses", optional=True),
                ],
            },
        ],
    },
    {
        "name": "Emma",
        "business": "Paws & Claws Grooming",
        "trade": "dog groomer",
        "flows": [
            {
                "name": "invoice_series",
                "turns": [
                    T("Invoice Mrs Henderson for full groom on Max $85 and nail trim $15", "85", "create invoice"),
                    TClick("INV-", "confirm invoice"),
                    T("Now invoice the Nguyen family for 2 cats groomed at $65 each", "65", "second invoice"),
                ],
            },
            {
                "name": "product_expense",
                "turns": [
                    T("Spent $180 on grooming supplies at PetBarn, shampoo and conditioner", "180", "log supply expense"),
                    T("And $320 on a new grooming table from Amazon", "320", "log equipment expense"),
                ],
            },
        ],
    },
    {
        "name": "Tom",
        "business": "TechFix IT Consulting",
        "trade": "IT consultant",
        "flows": [
            {
                "name": "quote_with_description_edit",
                "turns": [
                    T("Create a quote for Baxter Law for network security audit, 8 hours at $220", "220", "create quote"),
                    TClick("220", "confirm initial"),
                    T("Rename the item to 'Cybersecurity Assessment'", "Cybersecurity", "rename item"),
                    TClick("QU-", "confirm renamed quote"),
                ],
            },
            {
                "name": "monthly_software_expense",
                "turns": [
                    T("Paid $299 monthly subscription for Microsoft 365 Business", "299", "log subscription"),
                    T("Also $49 for Malwarebytes license renewal", "49", "log second subscription"),
                ],
            },
        ],
    },
    {
        "name": "Jake",
        "business": "SolidBase Concreting",
        "trade": "concreter",
        "flows": [
            {
                "name": "large_job_quote",
                "turns": [
                    T("Quote for Morrison Developments for 180sqm driveway, materials $2400 and labour 12 hours at $95",
                      "2400", "large quote"),
                    TClick("QU-", "confirm quote"),
                    T("Can you send me that quote again?", "QU-", "recall quote", optional=True),
                ],
            },
            {
                "name": "multi_expense_day",
                "turns": [
                    T("Bought concrete sealer from Bunnings $156", "156", "expense 1"),
                    T("Hired a concrete saw for the day $280", "280", "expense 2"),
                    T("Fuel $67.40", "67.40", "expense 3"),
                ],
            },
        ],
    },
    {
        "name": "Lisa",
        "business": "FitLife Personal Training",
        "trade": "personal trainer",
        "flows": [
            {
                "name": "recurring_client_invoice",
                "turns": [
                    T("Invoice James Cooper for 4 personal training sessions at $80 each", "80", "create invoice"),
                    TClick("INV-", "confirm invoice"),
                    T("Now invoice Rachel Wong for 8 sessions at $75", "75", "second client invoice"),
                ],
            },
            {
                "name": "equipment_expense",
                "turns": [
                    T("Bought resistance bands and foam rollers $145 from Rebel Sport", "145", "equipment expense"),
                    T("What are my business expenses so far this month?", "145", "recall expenses", optional=True),
                ],
            },
        ],
    },
    {
        "name": "Chen",
        "business": "SparkleClean Services",
        "trade": "cleaner",
        "flows": [
            {
                "name": "weekly_client_invoices",
                "turns": [
                    T("Invoice Pinnacle Tower for commercial cleaning 3 hours at $65 per hour", "65", "invoice client 1"),
                    TClick("INV-", "confirm invoice"),
                    T("Invoice Sunrise Childcare for deep clean 5 hours at $70", "70", "invoice client 2"),
                ],
            },
            {
                "name": "cleaning_supplies",
                "turns": [
                    T("Spent $89 on cleaning chemicals from Officeworks", "89", "expense"),
                    T("And $34 for mop heads and cloths", "34", "second expense"),
                ],
            },
        ],
    },
    {
        "name": "Raj",
        "business": "City Rides Transport",
        "trade": "rideshare driver",
        "flows": [
            {
                "name": "vehicle_expenses",
                "turns": [
                    T("Car service and oil change today $285 at Midas", "285", "service expense"),
                    T("New tyres $680 from Bob Jane", "680", "tyre expense"),
                    T("Fuel this week $123.60", "123.60", "fuel expense"),
                ],
            },
            {
                "name": "gst_advice",
                "turns": [
                    T("Am I supposed to register for GST as a rideshare driver?", "GST", "gst question"),
                    T("How do I claim car expenses?", "expense", "follow-up question"),
                ],
            },
        ],
    },
    {
        "name": "Amy",
        "business": "Pixel Perfect Design",
        "trade": "graphic designer",
        "flows": [
            {
                "name": "project_quote",
                "turns": [
                    T("Quote for Bloom Cafe for brand identity package — logo design 6 hours at $150 and style guide 4 hours at $150",
                      "150", "create quote"),
                    TClick("QU-", "confirm quote"),
                    T("What's the total on that quote?", "1500", "recall total", optional=True),
                ],
            },
            {
                "name": "software_subscriptions",
                "turns": [
                    T("Adobe Creative Cloud renewal $87.99 per month", "87.99", "software expense"),
                    T("Figma Pro subscription $20 USD — that's about $31 AUD", "31", "second software expense"),
                ],
            },
        ],
    },
]
