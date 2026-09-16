from pathlib import Path
from time import perf_counter
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.constants import (
    ALLOWED_ORIGINS,
    MAXIMUM_REQUESTS_PER_MINUTE,
)
from loanserve.api.access_control import AccessControl
from loanserve.api.middleware import RequestLogger, SlidingWindowRateLimiter
from loanserve.api.orm_models import create_session_factory
from loanserve.api.password_hashing import PasswordVault
from loanserve.api.repository import (
    InMemoryApplicationRepository,
    SqlApplicationRepository,
)
from loanserve.api.routers import loan_applications, user_accounts
from loanserve.core.exceptions import LoanServeError


def create_application(
    database_url=None,
    maximum_requests_per_minute=None,
    request_log_path=None,
):
    """Factory creating an isolated LoanServe FastAPI application instance."""
    app = FastAPI(title="LoanServe", version="1.0")

    # Domain error handler
    @app.exception_handler(LoanServeError)
    def report_domain_error(_request: Request, raised_error: LoanServeError):
        return JSONResponse(status_code=400, content={"detail": str(raised_error)})

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(ALLOWED_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # State initialization
    access_control = AccessControl()
    password_vault = PasswordVault()
    user_accounts_store = {}

    if database_url is not None:
        session_factory = create_session_factory(database_url)
        app_repo = SqlApplicationRepository(session_factory)
    else:
        app_repo = InMemoryApplicationRepository()

    app.state.application_repository = app_repo
    app.state.access_control = access_control
    app.state.password_vault = password_vault
    app.state.user_accounts = user_accounts_store

    # Rate limiting middleware
    max_req = (
        maximum_requests_per_minute
        if maximum_requests_per_minute is not None
        else MAXIMUM_REQUESTS_PER_MINUTE
    )
    limiter = SlidingWindowRateLimiter(max_req, 60)

    @app.middleware("http")
    async def refuse_when_over_the_limit(request: Request, call_next):
        client_key = request.client.host if request.client else "unknown"
        current_time = perf_counter()
        if not limiter.is_allowed(client_key, current_time):
            return JSONResponse(status_code=429, content={"detail": "Too many requests"})
        return await call_next(request)

    # Request logger middleware if requested
    if request_log_path is not None:
        app.middleware("http")(RequestLogger(request_log_path))

    # Health endpoint
    @app.get("/health", tags=["service"])
    def read_health():
        repo = app.state.application_repository
        _page, total = repo.list_applications(None, 1000000, 0)
        return {"status": "ok", "applications": total}

    # Mount auth router (unguarded)
    app.include_router(user_accounts.router, prefix="/api/v1")

    # Mount applications router
    if access_control.open_mode:
        app.include_router(loan_applications.router, prefix="/api/v1")
    else:
        app.include_router(
            loan_applications.router,
            prefix="/api/v1",
            dependencies=[Depends(access_control.authorise)],
        )

    # Optional assistant router
    try:
        from loanserve.api.routers import assistant
        if access_control.open_mode:
            app.include_router(assistant.router, prefix="/api/v1")
        else:
            app.include_router(
                assistant.router,
                prefix="/api/v1",
                dependencies=[Depends(access_control.authorise)],
            )
    except (ImportError, AttributeError):
        pass

    return app


if __name__ == "__main__":
    from fastapi.testclient import TestClient

    app = create_application(request_log_path="output/logs/request.log")
    client = TestClient(app)
    response = client.get("/health")
    print(response.json())
