from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from loanserve.api import schemas
from loanserve.core.entities import create_loan_application
from loanserve.core.loan_calculations import build_outstanding_balances

router = APIRouter(prefix="/applications", tags=["applications"])


def price_application(stored_application):
    """Turns one stored application into a priced response promise."""
    app_obj = create_loan_application(stored_application)
    return schemas.LoanApplicationResponse(
        application_id=stored_application["application_id"],
        applicant_name=stored_application["applicant_name"],
        loan_type=stored_application["loan_type"],
        loan_amount_inr=float(stored_application["loan_amount_inr"]),
        tenure_months=int(stored_application["tenure_months"]),
        monthly_income_inr=float(stored_application.get("monthly_income_inr", 0.0)),
        age_years=int(stored_application.get("age_years", 0)),
        credit_score=int(stored_application.get("credit_score", 0)),
        collateral_value_inr=float(stored_application.get("collateral_value_inr", 0.0)),
        interest_rate_percent=app_obj.interest_rate_percent(),
        monthly_installment_inr=round(app_obj.monthly_installment_inr(), 2),
        is_eligible=app_obj.is_eligible(),
        rejection_reasons=app_obj.rejection_reasons(),
    )


@router.post("", status_code=201, response_model=schemas.LoanApplicationResponse)
def create_application(submitted: schemas.LoanApplicationRequest, request: Request):
    repo = request.app.state.application_repository
    stored = repo.save_application(submitted.model_dump())
    return price_application(stored)


@router.get("", response_model=schemas.ApplicationPage)
def list_applications(
    filters: Annotated[schemas.ApplicationFilters, Query()],
    request: Request,
):
    repo = request.app.state.application_repository
    page, total = repo.list_applications(filters.loan_type, filters.limit, filters.offset)
    return schemas.ApplicationPage(
        applications=[price_application(app) for app in page],
        total=total,
        limit=filters.limit,
        offset=filters.offset,
    )


@router.get("/{application_id}/schedule", response_model=schemas.RepaymentSchedule)
def read_schedule(application_id: str, request: Request):
    repo = request.app.state.application_repository
    stored = repo.find_application(application_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")

    app_obj = create_loan_application(stored)
    balances = build_outstanding_balances(
        app_obj.principal_inr,
        app_obj.interest_rate_percent(),
        app_obj.tenure_months,
    )
    return schemas.RepaymentSchedule(
        application_id=application_id,
        outstanding_after_each_month=[round(float(b), 2) for b in balances],
    )


@router.get("/{application_id}", response_model=schemas.LoanApplicationResponse)
def read_application(application_id: str, request: Request):
    repo = request.app.state.application_repository
    stored = repo.find_application(application_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return price_application(stored)


@router.put("/{application_id}", response_model=schemas.LoanApplicationResponse)
def replace_application(
    application_id: str,
    submitted: schemas.LoanApplicationRequest,
    request: Request,
):
    repo = request.app.state.application_repository
    replaced = repo.replace_application(application_id, submitted.model_dump())
    if replaced is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return price_application(replaced)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: str, request: Request):
    repo = request.app.state.application_repository
    deleted = repo.delete_application(application_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return Response(status_code=204)
