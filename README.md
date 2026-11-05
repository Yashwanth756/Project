# LoanServe

LoanServe is a FastAPI loan-application service with authentication, application
pricing, repayment schedules, default-risk scoring, policy retrieval, and an
assistant workflow.

## Application entrypoint

The application is created by `loanserve.api.application_factory.create_application`.
The factory builds an isolated `FastAPI` instance and attaches:

1. CORS middleware.
2. A `LoanServeError` handler that converts domain errors to HTTP 400 responses.
3. Sliding-window rate limiting.
4. Optional request logging.
5. Authentication state, password hashing, and an application repository.
6. The health, authentication, application, and assistant routes.

The factory uses SQLite by default at `database/loanserve.db`, creates the
SQLAlchemy tables there, and uses `SqlApplicationRepository`. You can provide
another `database_url` to use a different database. The in-memory repository is
still available for isolated tests by calling `create_application(use_in_memory=True)`.
The assistant route receives the same repository instance from application state,
so applications created through FastAPI are immediately available to assistant
lookup and risk questions.

Authentication is controlled by `LOANSERVE_OPEN_MODE`. When it is `1`, application
and assistant routes are open. Otherwise, those routes require a valid bearer JWT.
Authentication routes remain available so a caller can sign up and log in.

## Dependency map

```text
application_factory
├── access_control
│   ├── JWT creation and validation
│   └── role checks and audit logging
├── middleware
│   ├── request rate limiting
│   └── optional request logging
├── password_hashing
├── repository
│   ├── InMemoryApplicationRepository
│   └── SqlApplicationRepository
├── routers/user_accounts
├── routers/loan_applications
│   ├── core/entities
│   └── core/loan_calculations
└── routers/assistant
    └── assistant/workflow
        ├── assistant/graph
        ├── assistant/nodes
        ├── assistant/agents
        ├── assistant/tools
        ├── message_intelligence/injection_guard
        ├── message_intelligence/message_classifier
        ├── retrieval/vector_store
        └── risk_models/baseline_model
```

Shared configuration and paths are defined in `config/constants.py`. Request
and response validation is defined in `loanserve/api/schemas.py`.

## Common request lifecycle

Every request enters FastAPI and passes through middleware before reaching a
route handler:

1. The request reaches the FastAPI application created by the factory.
2. CORS middleware adds or checks cross-origin behavior where appropriate.
3. The sliding-window limiter identifies the client by IP address and rejects
   requests above the configured limit with `429`.
4. If enabled, the request logger records the request.
5. FastAPI parses the URL, query parameters, headers, and JSON body.
6. Pydantic validates the parsed values. The route function does not run when
   validation fails.
7. On protected routers, `AccessControl.authorise` reads the `Authorization:
   Bearer <JWT>` header, verifies the signature and expiry, and checks whether
   the role may perform the HTTP method.
8. The route calls the repository and/or domain services.
9. The returned object is validated and serialized by the response schema.
10. Missing resources return `404`; validation/authentication failures return
   FastAPI's validation response or `401`/`403`; domain errors are returned as
   `400`.

### Example: signup request

For:

```http
POST /api/v1/auth/signup
Content-Type: application/json

{"user_name":"priya","password":"secret123","role":"loan_officer"}
```

the execution is:

1. The limiter checks the client.
2. `AccountRequest` verifies that the username is non-empty, the password has
   at least six characters, and the role is one of the allowed roles.
3. The unauthenticated account route looks in `app.state.user_accounts`.
4. `PasswordVault` hashes `secret123`; the plaintext password is discarded.
5. The hash and role are stored in the application instance's account store.
6. FastAPI serializes the result:

```json
{"user_name":"priya","role":"loan_officer"}
```

The password is never returned. A second signup for `priya` stops at step 3
with `409 Conflict`.

### Example: protected request

For:

```http
GET /api/v1/applications/LA000001
Authorization: Bearer eyJ...
```

the execution is:

1. Middleware performs the common checks.
2. The router-level authorization dependency extracts the bearer token.
3. `jwt.decode` verifies the token with the configured secret, algorithm, and
   expiry.
4. The claims are returned to the dependency. For a `GET`, any valid role is
   sufficient; for `DELETE`, the role must be `administrator`.
5. The route asks the configured repository for `LA000001`.
6. The record is priced through the domain model and serialized as the
   response schema.

Without a token, the request stops at step 3 with `401`. A loan officer trying
to delete an application passes token validation but stops at step 4 with
`403`.

## Endpoint flows

### `GET /health`

1. The factory's health handler reads the repository from `app.state`.
2. It counts stored applications through `list_applications`.
3. It returns:

```json
{"status": "ok", "applications": 0}
```

This endpoint does not require authentication.

### `POST /api/v1/auth/signup`

1. `AccountRequest` validates username, password length, and role.
2. The handler checks the in-memory account store for duplicates.
3. `PasswordVault` hashes the password; the plain password is not stored.
4. The account record is saved in `app.state.user_accounts`.
5. `AccountResponse` returns the username and role.

Duplicate usernames return `409`.

### `POST /api/v1/auth/login`

1. The request is validated as an `AccountRequest`.
2. The account is loaded from the factory's account store.
3. `PasswordVault` verifies the submitted password against the stored hash.
4. `AccessControl.issue_token` creates a signed JWT containing the subject,
   role, and expiry.
5. An audit entry is queued as a background task.
6. `TokenResponse` returns the bearer token.

Unknown users or incorrect passwords return `401`.

### `POST /api/v1/applications`

This endpoint has two validation layers: input validation before persistence
and lending-rule evaluation while building the response.

#### 1. Request validation

`LoanApplicationRequest` first validates:

- `loan_type` is `home`, `vehicle`, `gold`, or `personal`.
- Amount and monthly income are positive.
- Tenure is between 1 and 300 months.
- Age is between 18 and 100 and credit score is between 300 and 900.
- PAN, mobile number, and email are normalized and validated.
- `home`, `vehicle`, and `gold` are secured products and must provide a
  positive `collateral_value_inr`.
- `personal` is unsecured and does not require collateral.

Invalid input returns `422`; the repository is not called.

#### 2. Persistence

After validation, the selected repository stores the normalized record and
assigns an ID such as `LA000001`. The default factory uses SQLite at
`database/loanserve.db`; isolated tests can opt into memory with
`create_application(use_in_memory=True)`.

#### 3. Product model and rules

`create_loan_application` selects the domain class:

| Product type | Domain class | Security rule |
|---|---|---|
| `home`, `vehicle`, `gold` | `SecuredLoanApplication` | Collateral required; loan-to-value (LTV) must be at most `0.80` |
| `personal` | `UnsecuredLoanApplication` | No collateral; credit score must be at least `700` |

Both classes apply the common rules:

- Applicant age must be from `21` through `60`.
- Monthly installment divided by monthly income must be at most `0.50`.
- The requested amount must not exceed the product cap:
  home `INR 15,000,000`, vehicle `INR 2,500,000`, gold `INR 1,000,000`,
  personal `INR 1,500,000`.

#### Accepted application example

```json
{
  "pan_number": "ABCDE1234F",
  "mobile_number": "9876543210",
  "email_address": "priya.patel@example.com",
  "applicant_name": "Priya Patel",
  "loan_type": "home",
  "loan_amount_inr": 2500000,
  "tenure_months": 240,
  "monthly_income_inr": 150000,
  "age_years": 32,
  "credit_score": 760,
  "collateral_value_inr": 4000000
}
```

This is expected to return `is_eligible: true` with an empty
`rejection_reasons` list.

#### Rejected application examples

The API stores and prices valid requests even when lending rules reject them;
the response contains `is_eligible: false` and explains each reason.

Low credit score for an unsecured personal loan:

```json
{
  "pan_number": "FGHIJ5678K",
  "mobile_number": "9123456789",
  "email_address": "rahul.sharma@example.com",
  "applicant_name": "Rahul Sharma",
  "loan_type": "personal",
  "loan_amount_inr": 500000,
  "tenure_months": 36,
  "monthly_income_inr": 80000,
  "age_years": 35,
  "credit_score": 620,
  "collateral_value_inr": 0
}
```

Expected reason: `Credit score 620 is below 700`.

Excessive personal-loan amount:

```json
{
  "pan_number": "LMNOP1234Q",
  "mobile_number": "9988776655",
  "email_address": "amit.kumar@example.com",
  "applicant_name": "Amit Kumar",
  "loan_type": "personal",
  "loan_amount_inr": 2000000,
  "tenure_months": 60,
  "monthly_income_inr": 120000,
  "age_years": 40,
  "credit_score": 780,
  "collateral_value_inr": 0
}
```

Expected reason: the amount exceeds the personal-loan cap of
`INR 1,500,000`.

Insufficient collateral for a secured home loan:

```json
{
  "pan_number": "RSTUV1234W",
  "mobile_number": "9876543211",
  "email_address": "neha.verma@example.com",
  "applicant_name": "Neha Verma",
  "loan_type": "home",
  "loan_amount_inr": 4000000,
  "tenure_months": 240,
  "monthly_income_inr": 180000,
  "age_years": 38,
  "credit_score": 750,
  "collateral_value_inr": 3000000
}
```

This has an LTV of `1.33`, above the allowed `0.80`.

For secured products, LTV is:

```text
loan_amount_inr / collateral_value_inr
```

For example, a `INR 800,000` vehicle loan backed by `INR 1,000,000`
collateral has LTV `0.80` and passes this rule. The same loan with
`INR 900,000` collateral has LTV `0.89` and receives an LTV rejection reason.

For an unsecured personal loan, a credit score of `680` adds a credit-score
rejection reason even if the age, installment-to-income ratio, and amount rules
pass.

#### 4. Pricing and response

The domain object selects the product rate, calculates the reducing-balance
monthly installment, calculates the installment-to-income ratio, and collects
every failed rule. The response is returned even when `is_eligible` is false,
so a caller can see the price and all rejection reasons together:

```json
{
  "application_id": "LA000001",
  "applicant_name": "Aarav Nair",
  "loan_type": "personal",
  "loan_amount_inr": 500000.0,
  "tenure_months": 36,
  "monthly_income_inr": 60000.0,
  "age_years": 32,
  "credit_score": 760,
  "collateral_value_inr": 0.0,
  "interest_rate_percent": 14.5,
  "monthly_installment_inr": 17210.49,
  "is_eligible": true,
  "rejection_reasons": []
}
```

The endpoint does not silently alter an ineligible request into an eligible
one. It persists the application and reports the calculated decision.

### `GET /api/v1/applications`

1. `ApplicationFilters` validates `loan_type`, `limit`, and `offset`.
2. The repository applies filtering and pagination.
3. Every stored record is passed through the same pricing function used by
   creation and single-record reads.
4. `ApplicationPage` returns priced applications, total count, and pagination
   values.

### `GET /api/v1/applications/{application_id}`

1. The repository searches for the application ID.
2. A missing record returns `404`.
3. A found record is converted into the domain entity.
4. Current pricing and eligibility are calculated.
5. The response is serialized as `LoanApplicationResponse`.

### `PUT /api/v1/applications/{application_id}`

1. The replacement body passes the same validation as creation.
2. The repository updates the matching record while preserving its ID.
3. The updated record is repriced through the domain entity.
4. The route returns the new `LoanApplicationResponse`.

If the ID does not exist, the route returns `404`.

### `GET /api/v1/applications/{application_id}/schedule`

1. The repository loads the application.
2. A missing record returns `404`.
3. The domain entity supplies the principal, interest rate, and tenure.
4. `build_outstanding_balances` calculates the remaining balance after each
   month.
5. The route returns `RepaymentSchedule` with rounded balances.

### `DELETE /api/v1/applications/{application_id}`

1. The authorization dependency runs first unless open mode is enabled.
2. The repository deletes the record.
3. A missing ID returns `404`; a successful deletion returns `204`.
4. Because `DELETE` is in `ADMIN_ONLY_METHODS`, protected deployments require
   an administrator JWT.

### `POST /api/v1/assistant/ask`

1. `AssistantRequest` validates the question and optional thread ID.
2. The route creates a thread ID when one is not supplied.
3. `run_assistant` opens the SQLite checkpoint store and builds the graph. The
   factory passes its shared application repository into the request context, so
   `lookup_application` reads the same records created by the API.
4. The graph executes these nodes in order:

```text
triage → plan → tools → draft → approval → critic → respond
```

5. `triage` rejects short messages and prompt-injection markers. Otherwise it
   classifies category and urgency with the persisted message classifier.
6. `plan` selects one of the closed tool set:
   `calculate_installment`, `lookup_application`,
   `predict_default_risk`, or `search_policy_documents`.
7. `tools` validates tool arguments and records tool errors without crashing
   the workflow.
8. `draft` creates a customer-facing draft from calculated or retrieved data.
   Policy answers include retrieved passage citations.
9. `approval` pauses with a LangGraph interrupt for waivers, overrides, and
   exceptions.
10. `critic` rejects an empty draft and assigns confidence.
11. `respond` returns the final answer while preserving calculated figures.
12. The route converts graph messages into `narration` and returns
    `AssistantResponse`.

The graph state is checkpointed by thread ID, so interrupted workflows can be
resumed. Refused requests stop at the guard node and return the configured
low-confidence refusal.

#### Assistant question examples

Replace `LA000001` with an application ID returned by the application endpoint.

Installment calculations:

```text
What is the monthly installment for a 15 lakh personal loan at 14.5 percent for 60 months?
Calculate the EMI for a 25 lakh home loan at 8.5 percent for 240 months.
```

Application lookup and risk:

```text
What is the status of application LA000001?
Show me the details for application LA000001.
What is the default risk probability for application LA000001?
Calculate the probability of default for application LA000001.
Is application LA000001 high risk?
```

Policy search:

```text
What documents are required for a home loan?
What documents are needed for a self-employed applicant?
What are the requirements for a secured loan?
What is the minimum credit score for an unsecured personal loan?
```

Missing application handling:

```text
What is the risk for application LA999999?
```

The assistant reports that the application was not found; it does not invent an
under-review status.

### Triage classification in detail

Triage is a local, persisted machine-learning step, not a free-form LLM
decision:

1. `injection_guard.find_injection_markers` checks the raw question against
   patterns for instruction overrides, role reassignment, guardrail
   suppression, prompt extraction, delimiter smuggling, and data
   exfiltration. A match stops the graph before model or tool execution.
2. Very short questions are rejected because there is not enough information
   to route them safely.
3. `artifacts/message_classifier.pkl` contains two scikit-learn pipelines:
   one predicts `category` and one predicts `urgency`.
4. Each pipeline cleans the message, converts it to TF-IDF features using
   unigrams and bigrams, and applies balanced logistic regression.
5. The predicted labels are placed into graph state and passed to the planner.

The classifier was trained with a stratified holdout and fixed random seed.
If the classifier artifact cannot be loaded, the current node uses the safe
default category `loan_query` and urgency `low`; injection and short-message
checks still run first.

### Planning in detail

The planner receives the original question plus triage's category and urgency.
It is given a closed tool list and must produce tool arguments:

- `calculate_installment`: principal, annual rate, and tenure.
- `lookup_application`: application ID.
- `predict_default_risk`: a complete application dictionary.
- `search_policy_documents`: question and result count.

The planner uses the configured Gemini/LLM JSON adapter when available. The
response is validated against the required JSON shape and allowed tool names.
For a calculation, the fallback parser extracts the principal, unit
(`lakh`, `crore`, or `million`), interest rate, and month count rather than
using fixed example values. For an application reference, it extracts IDs such
as `LA000001`. Questions without a recognized application or calculation are
sent to policy search.

The node then wraps the selected plan in graph state. The tools node dispatches
only the explicit allowlisted names; an unknown name becomes a tool error
instead of an arbitrary function call.

### Default-risk prediction in detail

When the planner selects `predict_default_risk`, the tool:

1. Requires an `application` dictionary.
2. Verifies that every column in `MODELLING_COLUMNS` exists, including age,
   income, employment type, credit score, debt-to-income ratio, existing loan
   count, late payments, product, amount, and tenure.
3. Loads `artifacts/champion.pkl` through the model loader.
4. Reconstructs the feature columns expected by the persisted pipeline.
5. Calls `predict_proba` and returns the probability for class `1`, rounded to
   six decimal places.

The value is a model probability, not an approval decision by itself. A
missing feature, missing model artifact, or model failure becomes an explicit
`ToolError`. The champion can be retrained with
`risk_models/champion_model.py`, which compares the logistic baseline and
random-forest candidate and saves the selected pipeline.

### Policy-document search in detail

For a policy question, the tool:

1. Validates that the question is at least five characters and that
   `how_many` is between 1 and 20.
2. Opens the persistent Chroma collection at `database/policy_store`.
3. Loads the `all-MiniLM-L6-v2` sentence-transformer embedder.
4. Encodes the question as a normalized embedding.
5. Detects a product keyword such as home, vehicle, gold, or personal.
6. Applies a metadata filter that includes the requested product and universal
   (`all`) policy documents. Generic questions search without a product
   restriction.
7. Runs cosine similarity search and returns each chunk's text, chunk ID,
   heading, document ID, and distance.

The draft agent uses the retrieved chunks as its source. Generated policy
answers must cite IDs from the returned chunks; an invented or missing
citation is rejected and the safe grounded fallback is used.

## Risk and policy dependencies

The assistant's risk tool loads `artifacts/champion.pkl` through
`risk_models/baseline_model.py`. The champion training workflow is retained in
`risk_models/champion_model.py` and uses `risk_models/tree_models.py` plus the
feature pipeline to compare candidate models and choose a threshold.

The policy tool opens the persistent Chroma store in
`database/policy_store`, creates embeddings with the configured sentence
transformer, applies product metadata filtering, and returns labeled passages.
Those passage IDs are used to ground policy responses.

## Running the service

Install dependencies from `requirements.txt`, then create an application from
the factory in your ASGI entrypoint:

```python
from loanserve.api.application_factory import create_application

app = create_application()
```

For local development with protected routes disabled:

```bash
python -m uvicorn loanserve.api.application_factory:create_application
```

For persistent application storage, pass a SQLAlchemy database URL to
`create_application`, for example `sqlite:///database/loanserve_api.db`.


To run it directly with default application_factory setting use this command

```bash
python -m uvicorn loanserve.api.application_factory:create_application
```