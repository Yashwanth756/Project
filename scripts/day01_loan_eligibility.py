loan_type = input().strip().lower()
principal_inr = float(input())
annual_interest_rate_percent = float(input())
tenure_months = int(input())
monthly_income_inr = float(input())
applicant_age_years = int(input())

product_limits = {
    "home": 15000_000.0,
    "vehicle": 2_500_000.0,
    "gold": 1_000_000.0,
    "personal": 1_500_000.0,
}
   

max_loan_amount = product_limits.get(loan_type, 0)

monthly_rate = annual_interest_rate_percent / (12 * 100)

if tenure_months > 0:
    if monthly_rate == 0:
        monthly_installment_inr = principal_inr / tenure_months
    else:
        factor = (1 + monthly_rate) ** tenure_months
        monthly_installment_inr = (
            principal_inr * monthly_rate * factor
        ) / (factor - 1)
else:
    monthly_installment_inr = 0

total_interest_inr = (
    monthly_installment_inr * tenure_months
) - principal_inr

if monthly_income_inr > 0:
    debt_to_income_ratio = (
        monthly_installment_inr / monthly_income_inr
    )
else:
    debt_to_income_ratio = 0

print("LoanServe Eligibility Check")
print(f"Loan Type: {loan_type}")
print(f"Principal (INR): {principal_inr:.2f}")
print(f"Annual Interest Rate (%): {annual_interest_rate_percent:.2f}")
print(f"Tenure (months): {tenure_months}")
print(f"Monthly Income (INR): {monthly_income_inr:.2f}")
print(f"Applicant Age (years): {applicant_age_years}")
print(f"Monthly Installment (INR): {monthly_installment_inr:.2f}")
print(f"Total Interest (INR): {total_interest_inr:.2f}")
print(f"Debt-to-Income Ratio: {debt_to_income_ratio:.2f}")

print("Repayment Schedule (first 3 months):")

outstanding = principal_inr

for month in range(1, 4):
    interest = outstanding * monthly_rate
    principal_component = monthly_installment_inr - interest
    outstanding -= principal_component

    if abs(outstanding) < 0.005:
        outstanding = 0

    print(
        f"Month {month} | "
        f"Interest: {interest:.2f} | "
        f"Principal: {principal_component:.2f} | "
        f"Outstanding: {outstanding:.2f}"
    )

reasons = []

if applicant_age_years < 21 or applicant_age_years > 60:
    reasons.append(
        f"Reason: age {applicant_age_years} outside allowed range 21-60"
    )

if debt_to_income_ratio > 0.50:
    reasons.append(
        f"Reason: installment {monthly_installment_inr:.2f} exceeds 50% of income {monthly_income_inr:.2f}"
    )

if principal_inr > max_loan_amount:
    reasons.append(
        f"Reason: loan amount {principal_inr:.2f} exceeds limit {max_loan_amount:.2f}"
    )

if reasons:
    print("Decision: REJECTED")
    for reason in reasons:
        print(reason)
else:
    print("Decision: APPROVED")