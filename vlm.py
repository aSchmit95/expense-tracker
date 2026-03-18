import json
import re
from datetime import date

from llm.llm import make_image_call

CATEGORIES = [
    "Groceries",
    "Dining Out",
    "Transport",
    "Health & Pharmacy",
    "Entertainment",
    "Clothing",
    "Home & Garden",
    "Technology",
    "Travel",
    "Other",
]

PROMPT = f"""Analyze this receipt image and extract the purchase information.

Respond ONLY with a valid JSON object — no markdown, no explanation, nothing else.

{{
  "amount": <total amount paid as a number, e.g. 12.50>,
  "merchant": "<store or restaurant name, or 'Unknown' if not visible>",
  "date": "<purchase date in YYYY-MM-DD format, or null if not visible>",
  "category": "<one of: {", ".join(CATEGORIES)}>",
  "notes": "<one short sentence describing what was bought, max 60 chars>"
}}"""


def analyze_receipt(image_b64: str) -> dict:
    response = make_image_call(PROMPT, image_b64)
    content = response.content.strip()

    # Parse JSON — handle model wrapping it in markdown fences
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse VLM response: {content!r}")

    # Fill defaults
    data["amount"]   = float(data.get("amount") or 0.0)
    data["merchant"] = str(data.get("merchant") or "Unknown").strip()
    data["category"] = data.get("category", "Other")
    if data["category"] not in CATEGORIES:
        data["category"] = "Other"
    data["date"]  = data.get("date") or date.today().isoformat()
    data["notes"] = str(data.get("notes") or "")

    return data
