"""Rule-based, simplified FICO Score 8 style engine (300-850).

Each category gets a 0-1 sub-score. Points = sub_score * weight * 550.
Final score = 300 + sum(points).
"""

WEIGHTS = {
    "payment_history": 0.35,
    "amounts_owed": 0.30,
    "credit_history_length": 0.15,
    "credit_mix": 0.10,
    "new_credit": 0.10,
}
RANGE = 550  # 850 - 300

LABELS = {
    "payment_history": "Payment History (35%)",
    "amounts_owed": "Amounts Owed (30%)",
    "credit_history_length": "Credit History Length (15%)",
    "credit_mix": "Credit Mix (10%)",
    "new_credit": "New Credit (10%)",
}


def tier_for(score: int) -> str:
    if score >= 800: return "Exceptional"
    if score >= 740: return "Very Good"
    if score >= 670: return "Good"
    if score >= 580: return "Fair"
    return "Poor"


def risk_text(score: int) -> str:
    return {
        "Exceptional": "Very low likelihood of default; borrower qualifies for the best available terms.",
        "Very Good": "Low likelihood of default; reliable repayment behaviour with minor room to improve.",
        "Good": "Moderate-to-low default risk; generally acceptable for standard lending products.",
        "Fair": "Elevated default risk; likely to face higher rates or tighter approval criteria.",
        "Poor": "High likelihood of default; significant delinquency or utilization concerns.",
    }[tier_for(score)]


def _f(c, key, default=0.0):
    try:
        return float(c.get(key) or default)
    except (TypeError, ValueError):
        return default


def payment_sub(c):
    total = _f(c, "total_payments")
    ratio = (_f(c, "on_time_payments") / total) if total > 0 else 0.5
    sub = min(1.0, ratio) ** 3
    sub -= 0.03 * _f(c, "late_30") + 0.06 * _f(c, "late_60") + 0.10 * _f(c, "late_90")
    sub -= 0.12 * _f(c, "collections")
    if str(c.get("bankruptcy", "No")).strip().lower() in ("yes", "true", "1"):
        sub -= 0.40
    return max(0.0, min(1.0, sub)), ratio


def utilization(c):
    limit = _f(c, "total_credit_limit")
    return (_f(c, "total_balance") / limit) if limit > 0 else 1.0


def owed_sub(c):
    u = utilization(c)
    if u <= 0.10: s = 1.0
    elif u <= 0.30: s = 1.0 - (u - 0.10) * 0.5
    elif u <= 0.50: s = 0.9 - (u - 0.30) * 1.5
    elif u <= 0.75: s = 0.6 - (u - 0.50) * 1.4
    elif u <= 1.00: s = 0.25 - (u - 0.75) * 0.6
    else: s = 0.05
    return max(0.0, s), u


def length_sub(c):
    avg = _f(c, "avg_account_age_years")
    oldest = _f(c, "oldest_account_years")
    newest_m = _f(c, "newest_account_months")
    return 0.6 * min(1, avg / 10) + 0.3 * min(1, oldest / 20) + 0.1 * min(1, newest_m / 24)


def mix_sub(c):
    rev = _f(c, "revolving_accounts")
    inst = _f(c, "installment_accounts")
    if rev > 0 and inst > 0:
        return 0.8 + 0.2 * min(1, (rev + inst - 2) / 4)
    if rev > 0:
        return 0.55
    if inst > 0:
        return 0.45
    return 0.2


def new_sub(c):
    return max(0.0, 1.0 - 0.15 * _f(c, "hard_inquiries_12m") - 0.10 * _f(c, "new_accounts_12m"))


def calculate(c: dict) -> dict:
    pay, ratio = payment_sub(c)
    owed, util = owed_sub(c)
    subs = {
        "payment_history": pay,
        "amounts_owed": owed,
        "credit_history_length": length_sub(c),
        "credit_mix": mix_sub(c),
        "new_credit": new_sub(c),
    }
    points = {k: round(subs[k] * WEIGHTS[k] * RANGE) for k in subs}
    score = max(300, min(850, 300 + sum(points.values())))

    notes = {
        "payment_history": f"{ratio:.0%} on-time; {int(_f(c,'late_30'))}x30, {int(_f(c,'late_60'))}x60, "
                           f"{int(_f(c,'late_90'))}x90 late; {int(_f(c,'collections'))} collections; "
                           f"bankruptcy: {c.get('bankruptcy','No')}",
        "amounts_owed": f"Utilization {util:.1%} (target < 30%)",
        "credit_history_length": f"Avg age {_f(c,'avg_account_age_years'):.1f}y, oldest {_f(c,'oldest_account_years'):.0f}y, "
                                 f"newest {_f(c,'newest_account_months'):.0f} months",
        "credit_mix": f"{int(_f(c,'revolving_accounts'))} revolving, {int(_f(c,'installment_accounts'))} installment",
        "new_credit": f"{int(_f(c,'hard_inquiries_12m'))} hard inquiries, {int(_f(c,'new_accounts_12m'))} new accounts in 12 months",
    }
    breakdown = [
        {"key": k, "label": LABELS[k], "points": points[k],
         "max_points": round(WEIGHTS[k] * RANGE), "note": notes[k]}
        for k in WEIGHTS
    ]
    return {
        "score": score, "tier": tier_for(score), "risk": risk_text(score),
        "utilization": round(util * 100, 1), "breakdown": breakdown,
    }
