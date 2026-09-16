from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from config.constants import SECURED_LOAN_TYPES
from loanserve.core.validators import (
    validate_email_address,
    validate_mobile_number,
    validate_pan_number,
)


class LoanApplicationRequest(BaseModel):
    """Request body to create or replace a loan application."""

    pan_number: str
    mobile_number: str
    email_address: str
    applicant_name: str
    loan_type: Literal["home", "vehicle", "gold", "personal"]
    loan_amount_inr: float = Field(gt=0)
    tenure_months: int = Field(ge=1, le=300)
    monthly_income_inr: float = Field(gt=0)
    age_years: int = Field(ge=18, le=100)
    credit_score: int = Field(ge=300, le=900)
    collateral_value_inr: float = 0.0

    @field_validator("pan_number", mode="before")
    @classmethod
    def settle_pan_number(cls, v):
        return validate_pan_number(v)

    @field_validator("mobile_number", mode="before")
    @classmethod
    def settle_mobile_number(cls, v):
        return validate_mobile_number(v)

    @field_validator("email_address", mode="before")
    @classmethod
    def settle_email_address(cls, v):
        return validate_email_address(v)

    @model_validator(mode="after")
    def require_collateral_for_secured_loans(self):
        if self.loan_type in SECURED_LOAN_TYPES:
            if self.collateral_value_inr <= 0:
                raise ValueError(
                    f"{self.loan_type} is a secured product and requires a positive collateral value."
                )
        return self


class LoanApplicationResponse(BaseModel):
    """Response promise for a priced loan application."""

    application_id: str
    applicant_name: str
    loan_type: str
    loan_amount_inr: float
    tenure_months: int
    monthly_income_inr: Optional[float] = None
    age_years: Optional[int] = None
    credit_score: Optional[int] = None
    collateral_value_inr: Optional[float] = 0.0
    interest_rate_percent: float
    monthly_installment_inr: float
    is_eligible: bool
    rejection_reasons: List[str]


class RepaymentSchedule(BaseModel):
    """Response shape for the repayment schedule endpoint."""

    application_id: str
    outstanding_after_each_month: List[float]


class ApplicationFilters(BaseModel):
    """Query parameters for listing applications."""

    loan_type: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ApplicationPage(BaseModel):
    """Paginated list of loan applications."""

    applications: List[LoanApplicationResponse]
    total: int
    limit: int
    offset: int


class AccountRequest(BaseModel):
    """Request shape for signup and login."""

    user_name: str = Field(min_length=1)
    password: str = Field(min_length=6)
    role: Literal["loan_officer", "administrator"] = "loan_officer"


class AccountResponse(BaseModel):
    """Response shape after signup."""

    user_name: str
    role: str


class TokenResponse(BaseModel):
    """Response shape with bearer token after login."""

    access_token: str
    token_type: str = "bearer"


class AssistantRequest(BaseModel):
    """Request body for assistant endpoint."""

    question: str = Field(min_length=5)
    thread_id: Optional[str] = None


class AssistantResponse(BaseModel):
    """Response shape from the AI assistant."""

    question: str
    answer: str
    steps: List[str]
    refused: Optional[str] = None
    narration: List[str]
    waiting_for_approval: bool = False
