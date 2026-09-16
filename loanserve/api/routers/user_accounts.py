from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

from loanserve.api import schemas

router = APIRouter(prefix="/auth", tags=["accounts"])


@router.post("/signup", status_code=201, response_model=schemas.AccountResponse)
def sign_up(submitted: schemas.AccountRequest, request: Request):
    user_accounts = request.app.state.user_accounts
    password_vault = request.app.state.password_vault

    if submitted.user_name in user_accounts:
        raise HTTPException(
            status_code=409,
            detail=f"Username '{submitted.user_name}' already registered",
        )

    password_hash = password_vault.hash_password(submitted.password)
    user_accounts[submitted.user_name] = {
        "user_name": submitted.user_name,
        "password_hash": password_hash,
        "role": submitted.role,
    }

    return schemas.AccountResponse(user_name=submitted.user_name, role=submitted.role)


@router.post("/login", response_model=schemas.TokenResponse)
def log_in(
    submitted: schemas.AccountRequest,
    request: Request,
    background_tasks: BackgroundTasks,
):
    user_accounts = request.app.state.user_accounts
    password_vault = request.app.state.password_vault
    access_control = request.app.state.access_control

    account = user_accounts.get(submitted.user_name)
    if account is None or not password_vault.matches_stored_hash(
        submitted.password, account["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = access_control.issue_token(account["user_name"], account["role"])
    background_tasks.add_task(access_control.record_audit_entry, account["user_name"], "login")

    return schemas.TokenResponse(access_token=token, token_type="bearer")
