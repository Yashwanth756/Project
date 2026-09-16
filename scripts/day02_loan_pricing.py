"""Week 1 Day 2 — Loan Pricing and Application class."""

INTEREST_RATE_PERCENT_BY_LOAN_TYPE = {
    "home": 8.50,
    "vehicle": 9.75,
    "gold": 11.00,
    "personal": 14.50,
}

MAXIMUM_LOAN_AMOUNTS_INR = {
    "home": 15_000_000.0,
    "vehicle": 2_500_000.0,
    "gold": 1_000_000.0,
    "personal": 1_500_000.0,
}

MINIMUM_APPLICANT_AGE_YEARS = 21
MAXIMUM_APPLICANT_AGE_YEARS = 60
MAXIMUM_INSTALLMENT_TO_INCOME_RATIO = 0.50


def calculate_monthly_installment(principal_inr, annual_interest_rate_percent, tenure_months):
    """Returns the fixed monthly instalment that repays the loan over its tenure on a reducing balance."""
    principal = float(principal_inr)
    rate = float(annual_interest_rate_percent)
    tenure = int(tenure_months)

    monthly_rate = rate / (12.0 * 100.0)
    if monthly_rate == 0:
        return principal / tenure

    factor = (1.0 + monthly_rate) ** tenure
    return (principal * monthly_rate * factor) / (factor - 1.0)


def calculate_debt_to_income_ratio(monthly_installment_inr, monthly_income_inr):
    """Returns the share of monthly income the instalment consumes."""
    return float(monthly_installment_inr) / float(monthly_income_inr)


class LoanApplication:
    """Holds one application as an object, able to price itself and state rejection reasons."""

    def __init__(self, application_record):
        self.loan_type = str(application_record["loan_type"]).strip().lower()
        self.principal_inr = float(application_record["loan_amount_inr"])
        self.tenure_months = int(application_record["tenure_months"])
        self.monthly_income_inr = float(application_record["monthly_income_inr"])
        self.applicant_age_years = int(application_record["age_years"])

    def interest_rate_percent(self):
        return INTEREST_RATE_PERCENT_BY_LOAN_TYPE[self.loan_type]

    def monthly_installment_inr(self):
        return calculate_monthly_installment(
            self.principal_inr,
            self.interest_rate_percent(),
            self.tenure_months,
        )

    def debt_to_income_ratio(self):
        return calculate_debt_to_income_ratio(
            self.monthly_installment_inr(),
            self.monthly_income_inr,
        )

    def rejection_reasons(self):
        if self.loan_type not in MAXIMUM_LOAN_AMOUNTS_INR:
            return [f"Unsupported loan type: {self.loan_type}"]

        reasons = []
        if (
            self.applicant_age_years < MINIMUM_APPLICANT_AGE_YEARS
            or self.applicant_age_years > MAXIMUM_APPLICANT_AGE_YEARS
        ):
            reasons.append(
                f"Age {self.applicant_age_years} is outside {MINIMUM_APPLICANT_AGE_YEARS} to {MAXIMUM_APPLICANT_AGE_YEARS}"
            )

        dti = self.debt_to_income_ratio()
        if dti > MAXIMUM_INSTALLMENT_TO_INCOME_RATIO:
            reasons.append(
                f"Debt-to-income {dti:.2f} exceeds {MAXIMUM_INSTALLMENT_TO_INCOME_RATIO:.2f}"
            )

        max_amount = MAXIMUM_LOAN_AMOUNTS_INR[self.loan_type]
        if self.principal_inr > max_amount:
            reasons.append(
                f"Amount {self.principal_inr:.2f} exceeds the {self.loan_type} cap of {max_amount:.2f}"
            )

        return reasons

    def is_eligible(self):
        return len(self.rejection_reasons()) == 0


if __name__ == "__main__":
    first = LoanApplication(
        {
            "loan_type": "personal",
            "loan_amount_inr": 500000,
            "tenure_months": 36,
            "monthly_income_inr": 60000,
            "age_years": 32,
        }
    )

    second = LoanApplication(
        {
            "loan_type": "home",
            "loan_amount_inr": 20_000_000,
            "tenure_months": 240,
            "monthly_income_inr": 30000,
            "age_years": 65,
        }
    )

    print(
        first.loan_type,
        f"{first.monthly_installment_inr():.2f}",
        first.is_eligible(),
        first.rejection_reasons(),
    )

    print(
        second.loan_type,
        f"{second.monthly_installment_inr():.2f}",
        second.is_eligible(),
        second.rejection_reasons(),
    )