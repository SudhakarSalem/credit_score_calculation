from django import forms

INT = dict(min_value=0)


class CustomerForm(forms.Form):
    # Customer details
    name = forms.CharField(max_length=100)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)
    dob = forms.DateField(label="Date of birth", widget=forms.DateInput(attrs={"type": "date"}))
    city = forms.CharField(max_length=60)
    # Payment history
    on_time_payments = forms.IntegerField(label="On-time payments", **INT)
    total_payments = forms.IntegerField(label="Total payments", **INT)
    late_30 = forms.IntegerField(label="30-day late", initial=0, **INT)
    late_60 = forms.IntegerField(label="60-day late", initial=0, **INT)
    late_90 = forms.IntegerField(label="90+ day late", initial=0, **INT)
    collections = forms.IntegerField(label="Collections", initial=0, **INT)
    bankruptcy = forms.ChoiceField(choices=[("No", "No"), ("Yes", "Yes")])
    # Amounts owed
    total_balance = forms.FloatField(label="Total balance (₹)", **INT)
    total_credit_limit = forms.FloatField(label="Total credit limit (₹)", **INT)
    # History length
    oldest_account_years = forms.FloatField(label="Oldest account (years)", **INT)
    newest_account_months = forms.FloatField(label="Newest account (months)", **INT)
    avg_account_age_years = forms.FloatField(label="Average account age (years)", **INT)
    # Mix & new credit
    revolving_accounts = forms.IntegerField(label="Revolving accounts (cards)", **INT)
    installment_accounts = forms.IntegerField(label="Installment loans", **INT)
    hard_inquiries_12m = forms.IntegerField(label="Hard inquiries (12 mo)", initial=0, **INT)
    new_accounts_12m = forms.IntegerField(label="New accounts (12 mo)", initial=0, **INT)

    def clean(self):
        d = super().clean()
        if d.get("on_time_payments") is not None and d.get("total_payments") is not None \
                and d["on_time_payments"] > d["total_payments"]:
            raise forms.ValidationError("On-time payments cannot exceed total payments.")
        return d


class CalculateForm(forms.Form):
    customer = forms.ChoiceField()
    method = forms.ChoiceField(choices=[
        ("local", "Rule-based engine"),
        ("gemini", "Gemini AI"),
        ("both", "Both (compare)"),
    ], initial="both", widget=forms.RadioSelect)

    def __init__(self, *a, customers=(), **kw):
        super().__init__(*a, **kw)
        self.fields["customer"].choices = [
            (c["customer_id"], f'{c["customer_id"]} - {c["name"]}') for c in customers
        ]
