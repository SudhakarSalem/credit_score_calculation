"""Calls Google Gemini (REST) to produce the FICO-8-style evaluation."""
import json
import requests
from django.conf import settings

PROMPT = """Act as an expert financial risk analyst and credit scoring engine. Calculate an estimated consumer credit
score using a simplified FICO Score 8 framework (scale 300 to 850) from the customer data below.

Weights (apply strictly):
- Payment History (35%): on-time payments, delinquencies, bankruptcies.
- Amounts Owed / Credit Utilization (30%): total debt vs available limits (target under 30%).
- Length of Credit History (15%): age of oldest/newest accounts, average age.
- Credit Mix (10%): variety of revolving and installment accounts.
- New Credit (10%): hard inquiries and recently opened accounts.

Credit tiers: Poor (300-579), Fair (580-669), Good (670-739), Very Good (740-799), Exceptional (800-850).

Customer data (JSON):
{data}

Respond ONLY with JSON in exactly this shape:
{{
  "estimated_score": <int 300-850>,
  "credit_tier": "<tier>",
  "risk_assessment": "<1-2 sentences on likelihood of default>",
  "breakdown": {{
    "payment_history": "<brief observation & point impact>",
    "amounts_owed": "<utilization ratio % & point impact>",
    "credit_history_length": "<average age assessment & point impact>",
    "credit_mix": "<loan variety assessment & point impact>",
    "new_credit": "<impact of recent hard inquiries & point impact>"
  }}
}}"""

FIELDS = [
    "on_time_payments", "total_payments", "late_30", "late_60", "late_90", "collections", "bankruptcy",
    "total_balance", "total_credit_limit", "oldest_account_years", "newest_account_months",
    "avg_account_age_years", "revolving_accounts", "installment_accounts",
    "hard_inquiries_12m", "new_accounts_12m",
]


class GeminiError(Exception):
    pass


def evaluate(customer: dict) -> dict:
    if not settings.GEMINI_API_KEY:
        raise GeminiError("GEMINI_API_KEY is not set. Add it to .env or your environment.")

    payload = {k: customer.get(k) for k in FIELDS}
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    body = {
        "contents": [{"parts": [{"text": PROMPT.format(data=json.dumps(payload, indent=2))}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    try:
        r = requests.post(url, json=body, timeout=60,
                          headers={"x-goog-api-key": settings.GEMINI_API_KEY,
                                   "Content-Type": "application/json"})
    except requests.RequestException as e:
        raise GeminiError(f"Network error calling Gemini: {e}")
    if r.status_code != 200:
        raise GeminiError(f"Gemini API error {r.status_code}: {r.text[:300]}")

    try:
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        text = text.strip().removeprefix("```json").removesuffix("```").strip()
        data = json.loads(text)
        score = max(300, min(850, int(data["estimated_score"])))
        return {
            "score": score,
            "tier": data.get("credit_tier", ""),
            "risk": data.get("risk_assessment", ""),
            "breakdown": data.get("breakdown", {}),
        }
    except (KeyError, IndexError, ValueError, TypeError) as e:
        raise GeminiError(f"Could not parse Gemini response: {e}")
