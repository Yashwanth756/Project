from pathlib import Path
import pandas as pd

from config.constants import (
    APPLICATION_DATABASE_PATH,
    CHAMPION_MODEL_PATH,
    MODELLING_COLUMNS,
    POLICY_STORE_PATH,
)
from loanserve.core.exceptions import LoanServeError
from loanserve.core.loan_calculations import calculate_monthly_installment
from loanserve.data_access.database_loader import ApplicationDatabase
from loanserve.retrieval.filtered_search import filtered_search
from loanserve.retrieval.vector_store import load_embedder, open_policy_store
from loanserve.risk_models.baseline_model import (
    load_model,
    predict_default_probability,
)


class ToolError(LoanServeError):
    """Raised when a tool is called with invalid, missing, or unresolvable arguments."""


def calculate_installment(arguments):
    """Calculates monthly installment on a reducing balance."""
    if not isinstance(arguments, dict):
        raise ToolError("Arguments must be a dictionary.")

    for req in ("principal_inr", "annual_interest_rate_percent", "tenure_months"):
        if req not in arguments:
            raise ToolError(f"Missing required argument: {req}")

    try:
        principal = float(arguments["principal_inr"])
        rate = float(arguments["annual_interest_rate_percent"])
        tenure = int(arguments["tenure_months"])
    except (ValueError, TypeError):
        raise ToolError("Invalid numerical arguments for installment calculation.")

    if principal <= 0 or tenure <= 0 or rate < 0:
        raise ToolError("Principal and tenure must be positive, interest rate non-negative.")

    try:
        installment = calculate_monthly_installment(principal, rate, tenure)
        return {"monthly_installment_inr": round(installment, 2)}
    except Exception as err:
        raise ToolError(f"Calculation failed: {err}")


def lookup_application(arguments, database_path=APPLICATION_DATABASE_PATH):
    """Looks up application record from database by application_id."""
    if not isinstance(arguments, dict) or "application_id" not in arguments:
        raise ToolError("Missing application_id argument.")

    app_id = str(arguments["application_id"]).strip().upper()
    if not app_id:
        raise ToolError("Application ID cannot be blank.")

    database = ApplicationDatabase(database_path)
    record = database.find_application(app_id)
    if not record:
        raise ToolError(f"Application {app_id} not found in database.")

    return record


def predict_default_risk(arguments, model_path=CHAMPION_MODEL_PATH):
    """Scores application against the champion risk model."""
    if not isinstance(arguments, dict) or "application" not in arguments:
        raise ToolError("Missing application record argument.")

    app_dict = arguments["application"]
    if not isinstance(app_dict, dict):
        raise ToolError("Application must be a dictionary.")

    # Check for presence of required modeling fields
    missing_cols = [c for c in MODELLING_COLUMNS if c not in app_dict]
    if missing_cols:
        raise ToolError(f"Application is missing required columns: {missing_cols}")

    try:
        champion = load_model(model_path)
        df = pd.DataFrame([app_dict])
        prob = float(predict_default_probability(champion, df)[0])
        return {"default_probability": round(prob, 6)}
    except Exception as err:
        raise ToolError(f"Risk prediction failed: {err}")


def search_policy_documents(arguments, store_path=POLICY_STORE_PATH):
    """Searches policy vector store for relevant passages."""
    if not isinstance(arguments, dict) or "question" not in arguments:
        raise ToolError("Missing question argument.")

    question = str(arguments["question"]).strip()
    if len(question) < 5:
        raise ToolError("Question too short to perform policy search.")

    how_many = arguments.get("how_many", 3)
    try:
        how_many = int(how_many)
    except (ValueError, TypeError):
        raise ToolError("how_many must be an integer.")

    if how_many < 1 or how_many > 20:
        raise ToolError("how_many must be between 1 and 20.")

    try:
        collection = open_policy_store(store_path)
        embedder = load_embedder()
        passages = filtered_search(collection, question, embedder, how_many=how_many)
        return {"passages": passages}
    except Exception as err:
        raise ToolError(f"Policy search failed: {err}")
