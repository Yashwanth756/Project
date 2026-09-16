import numpy as np

from loanserve.core.decorators import reject_negative_arguments


@reject_negative_arguments
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


def build_outstanding_balances(principal_inr, annual_interest_rate_percent, tenure_months):
    """Returns the balance still owed after each month of the loan, for the whole tenure at once."""
    principal = float(principal_inr)
    rate = float(annual_interest_rate_percent)
    tenure = int(tenure_months)

    if tenure <= 0:
        return np.array([], dtype=float)

    monthly_installment = calculate_monthly_installment(principal, rate, tenure)
    monthly_rate = rate / (12.0 * 100.0)
    months = np.arange(1, tenure + 1, dtype=float)

    if monthly_rate == 0:
        balances = principal - months * (principal / tenure)
    else:
        compounded = (1.0 + monthly_rate) ** months
        balances = principal * compounded - monthly_installment * ((compounded - 1.0) / monthly_rate)

    balances[np.abs(balances) < 1e-4] = 0.0
    balances[-1] = 0.0
    return balances


if __name__ == "__main__":
    from pathlib import Path
    from loanserve.data_access.file_storage import ApplicationFileStorage

    inst = calculate_monthly_installment(500000.0, 14.0, 36)
    print(f"instalment: {inst:.2f}")

    storage_path = Path("output/day03_storage")
    if (storage_path / "applications.csv").exists():
        storage = ApplicationFileStorage(storage_path)
        apps = storage.load_applications("applications.csv")
        for app in apps:
            balances = build_outstanding_balances(app.principal_inr, app.interest_rate_percent(), app.tenure_months)
            print(f"{app.loan_type} final balance: {balances[-1]:.1f}")