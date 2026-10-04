# Credit Score Studio (Django + Gemini AI + Excel)

Simplified FICO Score 8 style credit scoring (300-850). Customers and score details live in
`data/customers.xlsx` (no SQL database). Scores come from a rule-based engine and/or Google Gemini.

## Setup
```bash
pip install -r requirements.txt
cp .env.example .env            # add your GEMINI_API_KEY (https://aistudio.google.com/apikey)
python generate_sample_data.py  # creates 50 sample customers in data/customers.xlsx
python manage.py runserver
```
Open http://127.0.0.1:8000/

## Pages
- `/` Customer list with search, tier filter, stats, and "Recalculate all"
- `/customers/new/` Customer creation page (auto-scores on save)
- `/customers/<id>/` Credit score details and weighted breakdown
- `/calculate/` Credit score calculation page (rule-based, Gemini, or both)
- `/download/` Download the Excel file

## Files
- `scoring/scoring_engine.py` rule-based engine (all formulas below)
- `scoring/gemini_client.py` Gemini prompt + REST call (model set by `GEMINI_MODEL`)
- `scoring/excel_store.py` Excel read/write

---

## How the credit score is calculated

This is an approximation of the FICO Score 8 idea, not the real (proprietary) FICO formula.

### Step 1: score each category from 0 to 1
Each of the five categories produces a **sub-score** between 0 (worst) and 1 (best).

### Step 2: convert to points
```
points = sub_score x weight x 550
```
550 is the size of the score range (850 - 300). Points are rounded per category.

| Category | Weight | Max points |
|---|---|---|
| Payment History | 35% | 192.5 (about 193) |
| Amounts Owed (utilization) | 30% | 165 |
| Length of Credit History | 15% | 82.5 (about 83) |
| Credit Mix | 10% | 55 |
| New Credit | 10% | 55 |

### Step 3: final score
```
score = 300 + sum of the five category points      (clamped to 300-850)
```

### Credit tiers
| Score | Tier |
|---|---|
| 800-850 | Exceptional |
| 740-799 | Very Good |
| 670-739 | Good |
| 580-669 | Fair |
| 300-579 | Poor |

---

### 1. Payment History (35%)
Inputs: on-time payments, total payments, 30/60/90+ day lates, collections, bankruptcy.
```
on_time_ratio = on_time_payments / total_payments        (0.5 if total_payments = 0)
sub = on_time_ratio ^ 3
sub = sub - 0.03 x late_30 - 0.06 x late_60 - 0.10 x late_90
sub = sub - 0.12 x collections
sub = sub - 0.40 if bankruptcy = Yes
sub = limited to the range 0..1
```
The cube makes small slips costly: 95% on-time gives 0.857, and 90% gives 0.729.
Deeper delinquencies and collections are penalized more heavily than short lates.

### 2. Amounts Owed / Utilization (30%)
```
utilization = total_balance / total_credit_limit         (treated as 100% if limit = 0)
```
| Utilization | Sub-score |
|---|---|
| 0% - 10% | 1.00 |
| 10% - 30% | falls from 1.00 to 0.90 (loses 0.5 per 1.0 of utilization) |
| 30% - 50% | falls from 0.90 to 0.60 (loses 1.5 per 1.0) |
| 50% - 75% | falls from 0.60 to 0.25 (loses 1.4 per 1.0) |
| 75% - 100% | falls from 0.25 to 0.10 (loses 0.6 per 1.0) |
| above 100% | 0.05 |

The 30% mark is the target. Beyond it, the score drops much faster.

### 3. Length of Credit History (15%)
```
sub = 0.6 x min(1, average_account_age_years / 10)
    + 0.3 x min(1, oldest_account_years / 20)
    + 0.1 x min(1, newest_account_months / 24)
```
Average age matters most. It maxes out at 10 years, the oldest account at 20 years,
and the newest account at 24 months (a very recent account lowers the score slightly).

### 4. Credit Mix (10%)
| Accounts | Sub-score |
|---|---|
| Revolving and installment | 0.80 + 0.20 x min(1, (total accounts - 2) / 4) |
| Revolving only (cards) | 0.55 |
| Installment only (loans) | 0.45 |
| None | 0.20 |

Having both types earns at least 0.80, and more accounts raise it toward 1.0 (reached at 6 accounts).

### 5. New Credit (10%)
```
sub = 1 - 0.15 x hard_inquiries_12m - 0.10 x new_accounts_12m      (minimum 0)
```
Each hard inquiry costs 0.15 and each newly opened account costs 0.10. The sub-score hits 0 at
about 7 inquiries.

---

### Worked example
Customer: 60 of 62 payments on time, two 30-day lates, no collections or bankruptcy;
balance 20,000 on a limit of 200,000; average account age 5.5 years, oldest 9 years, newest 14 months;
2 cards and 1 loan; 1 hard inquiry and no new accounts.

| Category | Sub-score calculation | Sub-score | Points |
|---|---|---|---|
| Payment History | (60/62)^3 = 0.906, minus 2 x 0.03 | 0.846 | 0.846 x 0.35 x 550 = **163** |
| Amounts Owed | utilization 10% | 1.000 | 1.000 x 0.30 x 550 = **165** |
| History Length | 0.6 x 0.55 + 0.3 x 0.45 + 0.1 x 0.583 | 0.523 | 0.523 x 0.15 x 550 = **43** |
| Credit Mix | 0.80 + 0.20 x (1/4) | 0.850 | 0.850 x 0.10 x 550 = **47** |
| New Credit | 1 - 0.15 x 1 | 0.850 | 0.850 x 0.10 x 550 = **47** |

```
score = 300 + 163 + 165 + 43 + 47 + 47 = 765   ->  Very Good
```

### How to improve a score (what the model rewards)
1. Never miss payments. Payment history is the biggest lever, and 90+ day lates and collections hurt most.
2. Keep utilization under 30%, and ideally under 10%.
3. Keep old accounts open. Age is worth up to 83 points.
4. Hold both cards and loans.
5. Avoid applying for many new accounts in a short period.

### Gemini scoring
When you choose Gemini (or Both) on the calculation page, the app sends the same customer data and the
same weights and tier definitions to the Gemini model. It asks for JSON containing the score, tier, a
1-2 sentence default-risk assessment, and a short note per category. Gemini reasons freely rather than
using the formulas above, so its score will differ somewhat from the rule-based result. Use
**Both (compare)** to see the two side by side. Both results are saved to Excel.

### Limitations
- Simplified model: real FICO also considers factors such as account types, balances per account,
  and the age of specific delinquencies.
- The thresholds and penalty values above are illustrative design choices and can be tuned in
  `scoring/scoring_engine.py`.
- Sample data is synthetic. Do not use this for real lending decisions.
