"""Create data/customers.xlsx with 50 sample customers and rule-based scores.

Run:  python generate_sample_data.py
"""
import os
import random
from datetime import date, datetime, timedelta

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "creditproject.settings")
import django
django.setup()

from scoring import excel_store as store
from scoring import scoring_engine

random.seed(42)

FIRST = ["Arjun", "Priya", "Karthik", "Divya", "Rahul", "Ananya", "Vikram", "Meera", "Suresh", "Lakshmi",
         "Aditya", "Sneha", "Rohan", "Kavya", "Manoj", "Pooja", "Naveen", "Deepa", "Siddharth", "Nisha",
         "Harish", "Swathi", "Gautam", "Ritu", "Prakash"]
LAST = ["Sharma", "Iyer", "Reddy", "Nair", "Kumar", "Patel", "Menon", "Rao", "Singh", "Krishnan",
        "Gupta", "Pillai", "Verma", "Das", "Mehta"]
CITIES = ["Chennai", "Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Pune", "Kolkata", "Coimbatore", "Kochi", "Ahmedabad"]


def make_customer(i):
    # quality 0 (risky) .. 1 (excellent); spread across the full range
    q = min(1, max(0, random.betavariate(3.4, 1.4) if i % 5 else random.random()))
    age = random.randint(24, 62)
    dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))
    name = f"{random.choice(FIRST)} {random.choice(LAST)}"

    total_payments = random.randint(24, 180)
    on_time_ratio = 0.55 + 0.45 * q ** 0.5 - random.uniform(0, 0.04)
    on_time = min(total_payments, round(total_payments * on_time_ratio))
    if q > 0.9:
        on_time = total_payments
    late = total_payments - on_time
    late_90 = int(late * (1 - q) * 0.3)
    late_60 = int((late - late_90) * 0.3)
    late_30 = max(0, late - late_90 - late_60)
    late_30, late_60, late_90 = min(late_30, 12), min(late_60, 6), min(late_90, 4)
    collections = random.choice([0, 0, 0, 1, 2]) if q < 0.35 else 0
    bankruptcy = "Yes" if q < 0.08 else "No"

    limit = random.choice([80000, 150000, 250000, 400000, 600000, 900000, 1500000])
    util = max(0.02, min(1.1, (1 - q) * 0.95 + random.uniform(-0.05, 0.1)))
    balance = round(limit * util, -2)

    oldest = round(random.uniform(2, min(25, age - 20)), 0)
    avg_age = round(max(0.5, oldest * random.uniform(0.5, 0.9)), 1)
    newest_m = random.randint(1, 60)
    revolving = random.randint(0, 6)
    installment = random.randint(0, 4)
    if q > 0.6:
        revolving, installment = max(1, revolving), max(1, installment)
    inquiries = random.randint(0, 2) if q > 0.5 else random.randint(1, 7)
    new_accts = min(inquiries, random.randint(0, 3))

    c = {
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}{i}@example.com",
        "phone": f"+91 9{random.randint(100000000, 999999999)}",
        "dob": dob.isoformat(),
        "city": random.choice(CITIES),
        "on_time_payments": on_time, "total_payments": total_payments,
        "late_30": late_30, "late_60": late_60, "late_90": late_90,
        "collections": collections, "bankruptcy": bankruptcy,
        "total_balance": balance, "total_credit_limit": limit,
        "oldest_account_years": oldest, "newest_account_months": newest_m,
        "avg_account_age_years": avg_age,
        "revolving_accounts": revolving, "installment_accounts": installment,
        "hard_inquiries_12m": inquiries, "new_accounts_12m": new_accts,
    }
    return c


rows = []
for i in range(1, 51):
    c = make_customer(i)
    c["customer_id"] = f"C{1000 + i}"
    r = scoring_engine.calculate(c)
    c["local_score"], c["local_tier"] = r["score"], r["tier"]
    c["calculated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    c["created_at"] = (datetime.now() - timedelta(days=random.randint(0, 90))).strftime("%Y-%m-%d %H:%M")
    rows.append(c)

store.bulk_write(rows)
scores = [r["local_score"] for r in rows]
tiers = {}
for r in rows:
    tiers[r["local_tier"]] = tiers.get(r["local_tier"], 0) + 1
print(f"Wrote {len(rows)} customers to {store._path()}")
print(f"Score range {min(scores)}-{max(scores)}, avg {sum(scores)//len(scores)}")
print("Tier counts:", tiers)
