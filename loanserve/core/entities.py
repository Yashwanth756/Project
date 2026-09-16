from config.constants import (
    INTEREST_RATE_PERCENT_BY_LOAN_TYPE,
    MAXIMUM_INSTALLMENT_TO_INCOME_RATIO,
    MAXIMUM_LOAN_AMOUNTS_INR,
    MAXIMUM_LOAN_TO_VALUE_RATIO,
    MAXIMUM_APPLICANT_AGE_YEARS,
    MINIMUM_APPLICANT_AGE_YEARS,
    MINIMUM_CREDIT_SCORE_FOR_UNSECURED,
    SECURED_LOAN_TYPES,
)
from loanserve.core.exceptions import UnsupportedLoanTypeError
from loanserve.core.loan_calculations import (
    calculate_debt_to_income_ratio,
    calculate_monthly_installment,
)


class LoanApplication:
    """Base class holding shared fields and rules for a loan application."""

    def __init__(self, application_record):
        self.loan_type = str(application_record["loan_type"]).strip().lower()
        if self.loan_type not in MAXIMUM_LOAN_AMOUNTS_INR:
            raise UnsupportedLoanTypeError(f"Unsupported loan type: {self.loan_type}")

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


class SecuredLoanApplication(LoanApplication):
    """An application backed by an asset."""

    def __init__(self, application_record):
        super().__init__(application_record)
        self.collateral_value_inr = float(application_record.get("collateral_value_inr", 0))

    def loan_to_value_ratio(self):
        if self.collateral_value_inr <= 0:
            return float("inf")
        return self.principal_inr / self.collateral_value_inr

    def rejection_reasons(self):
        reasons = super().rejection_reasons()
        ltv = self.loan_to_value_ratio()
        if ltv > MAXIMUM_LOAN_TO_VALUE_RATIO:
            reasons.append(
                f"Loan-to-value {ltv:.2f} exceeds {MAXIMUM_LOAN_TO_VALUE_RATIO:.2f}"
            )
        return reasons


class UnsecuredLoanApplication(LoanApplication):
    """An application with no security behind it."""

    def __init__(self, application_record):
        super().__init__(application_record)
        self.credit_score = int(application_record.get("credit_score", 0))

    def rejection_reasons(self):
        reasons = super().rejection_reasons()
        if self.credit_score < MINIMUM_CREDIT_SCORE_FOR_UNSECURED:
            reasons.append(
                f"Credit score {self.credit_score} is below {MINIMUM_CREDIT_SCORE_FOR_UNSECURED}"
            )
        return reasons


def create_loan_application(application_record):
    """Factory creating appropriate LoanApplication subclass based on product type."""
    loan_type = str(application_record["loan_type"]).strip().lower()
    if loan_type in SECURED_LOAN_TYPES:
        return SecuredLoanApplication(application_record)
    return UnsecuredLoanApplication(application_record)


if __name__ == "__main__":
    record = {
        "loan_type": "personal",
        "loan_amount_inr": 500000,
        "tenure_months": 36,
        "monthly_income_inr": 60000,
        "age_years": 32,
        "credit_score": 610,
    }
    app = create_loan_application(record)
    print(type(app).__name__, app.is_eligible(), app.rejection_reasons())