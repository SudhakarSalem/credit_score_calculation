# Credit Score Studio (Django + Gemini AI + Excel)

Simplified FICO Score 8 style scoring (300-850). Customers and score details live in `data/customers.xlsx`
(no SQL database). Scores come from a rule-based engine and/or Google Gemini.

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

## Weights
Payment History 35% | Amounts Owed 30% | History Length 15% | Credit Mix 10% | New Credit 10%

## Files
- `scoring/scoring_engine.py` rule-based engine
- `scoring/gemini_client.py` Gemini prompt + REST call (model set by `GEMINI_MODEL`)
- `scoring/excel_store.py` Excel read/write
