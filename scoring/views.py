import json
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from . import excel_store as store
from . import gemini_client, scoring_engine
from .forms import CalculateForm, CustomerForm

TIERS = ["Exceptional", "Very Good", "Good", "Fair", "Poor"]


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _gemini_view(customer):
    """Parse stored Gemini breakdown JSON into a template-friendly list."""
    if customer.get("gemini_score") is None:
        return None
    try:
        raw = json.loads(customer.get("gemini_breakdown") or "{}")
    except ValueError:
        raw = {}
    return [{"label": scoring_engine.LABELS[k], "text": raw.get(k, "")} for k in scoring_engine.WEIGHTS]


def customer_list(request):
    rows = store.all_customers()
    q = request.GET.get("q", "").strip().lower()
    tier = request.GET.get("tier", "")
    if q:
        rows = [r for r in rows if q in f'{r["customer_id"]} {r["name"]} {r["email"]} {r["city"]}'.lower()]
    if tier:
        rows = [r for r in rows if r["local_tier"] == tier]
    scored = [r["local_score"] for r in store.all_customers() if r["local_score"]]
    stats = {
        "count": len(store.all_customers()),
        "avg": round(sum(scored) / len(scored)) if scored else "-",
        "min": min(scored) if scored else "-",
        "max": max(scored) if scored else "-",
    }
    return render(request, "scoring/customer_list.html",
                  {"customers": rows, "q": q, "tier": tier, "tiers": TIERS, "stats": stats})


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in form.cleaned_data.items()}
        result = scoring_engine.calculate(data)
        data.update(local_score=result["score"], local_tier=result["tier"], calculated_at=_now())
        saved = store.add_customer(data)
        messages.success(request, f'Customer {saved["customer_id"]} created. '
                                  f'Estimated score {result["score"]} ({result["tier"]}).')
        return redirect("customer_detail", cid=saved["customer_id"])
    sections = [
        ("Customer details", ["name", "email", "phone", "dob", "city"]),
        ("Payment history (35%)", ["on_time_payments", "total_payments", "late_30", "late_60",
                                   "late_90", "collections", "bankruptcy"]),
        ("Amounts owed (30%)", ["total_balance", "total_credit_limit"]),
        ("Credit history length (15%)", ["oldest_account_years", "newest_account_months",
                                         "avg_account_age_years"]),
        ("Credit mix (10%) & new credit (10%)", ["revolving_accounts", "installment_accounts",
                                                 "hard_inquiries_12m", "new_accounts_12m"]),
    ]
    grouped = [(title, [form[f] for f in fields]) for title, fields in sections]
    return render(request, "scoring/customer_form.html", {"form": form, "sections": grouped})


def customer_detail(request, cid):
    c = store.get_customer(cid)
    if not c:
        raise Http404("Customer not found")
    local = scoring_engine.calculate(c)
    return render(request, "scoring/customer_detail.html", {
        "c": c, "local": local, "gemini": _gemini_view(c),
        "profile_fields": [("Phone", c["phone"]), ("Date of birth", c["dob"]), ("City", c["city"]),
                           ("Created", c["created_at"]), ("Last calculated", c["calculated_at"])],
    })


def calculate_view(request):
    customers = store.all_customers()
    initial = {"customer": request.GET.get("customer")} if request.GET.get("customer") else {}
    form = CalculateForm(request.POST or None, customers=customers, initial=initial)
    ctx = {"form": form, "has_key": bool(settings.GEMINI_API_KEY)}

    if request.method == "POST" and form.is_valid():
        c = store.get_customer(form.cleaned_data["customer"])
        method = form.cleaned_data["method"]
        updates = {"calculated_at": _now()}
        if method in ("local", "both"):
            local = scoring_engine.calculate(c)
            updates.update(local_score=local["score"], local_tier=local["tier"])
            ctx["local"] = local
        if method in ("gemini", "both"):
            try:
                g = gemini_client.evaluate(c)
                updates.update(gemini_score=g["score"], gemini_tier=g["tier"], gemini_risk=g["risk"],
                               gemini_breakdown=json.dumps(g["breakdown"]))
                ctx["gemini"] = g
                ctx["gemini_rows"] = [{"label": scoring_engine.LABELS[k], "text": g["breakdown"].get(k, "")}
                                      for k in scoring_engine.WEIGHTS]
            except gemini_client.GeminiError as e:
                messages.error(request, str(e))
        store.update_customer(c["customer_id"], updates)
        ctx["customer"] = store.get_customer(c["customer_id"])
        if "local" in ctx or "gemini" in ctx:
            messages.success(request, "Results saved to Excel.")
    return render(request, "scoring/calculate.html", ctx)


def calculate_all(request):
    if request.method != "POST":
        return redirect("customer_list")
    n = 0
    for c in store.all_customers():
        r = scoring_engine.calculate(c)
        store.update_customer(c["customer_id"], {"local_score": r["score"], "local_tier": r["tier"],
                                                 "calculated_at": _now()})
        n += 1
    messages.success(request, f"Recalculated rule-based scores for {n} customers.")
    return redirect("customer_list")


def download_excel(request):
    p = settings.EXCEL_PATH
    if not p.exists():
        raise Http404("No Excel file yet")
    return FileResponse(open(p, "rb"), as_attachment=True, filename="customers.xlsx")
