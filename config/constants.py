"""Fixed values shared across the platform.

Every value here is a contract: a published lending rule, a platform setting, or a wording
the service is required to produce. Import them rather than retyping the figures, so that
one change reaches every module that depends on it.

This file is supplied complete. Nothing in it is added to or edited.
"""

# Lending rules. Applied when an application is priced and again when it is judged.
MINIMUM_APPLICANT_AGE_YEARS = 21
MAXIMUM_APPLICANT_AGE_YEARS = 60
MAXIMUM_INSTALLMENT_TO_INCOME_RATIO = 0.50

# Annual interest rate charged for each product, as a percentage.
INTEREST_RATE_PERCENT_BY_LOAN_TYPE = {
    "home": 8.50,
    "vehicle": 9.75,
    "gold": 11.00,
    "personal": 14.50,
}

# Largest amount advanced for each product, in rupees. The keys are the product catalogue:
# a loan type absent from here is one the lender does not offer.
MAXIMUM_LOAN_AMOUNTS_INR = {
    "home": 15_000_000.0,
    "vehicle": 2_500_000.0,
    "gold": 1_000_000.0,
    "personal": 1_500_000.0,
}

# Products backed by an asset, and the two rules that apply only to secured and only to
# unsecured lending.
SECURED_LOAN_TYPES = ("home", "vehicle", "gold")
MAXIMUM_LOAN_TO_VALUE_RATIO = 0.80
MINIMUM_CREDIT_SCORE_FOR_UNSECURED = 700

# The range a bureau score can be issued in.
MINIMUM_CREDIT_SCORE = 300
MAXIMUM_CREDIT_SCORE = 900

# Modelling settings. The seed fixes every random choice, so two runs of the same model
# report the same figure and two models can be compared.
RANDOM_SEED = 42
HOLDOUT_SHARE = 0.20
CROSS_VALIDATION_FOLDS = 5

# What each kind of lending mistake costs, in rupees. The two differ, which is why an
# operating threshold is chosen by pricing it rather than by habit.
COST_OF_A_MISSED_DEFAULT_INR = 400000
COST_OF_A_REFUSED_GOOD_APPLICANT_INR = 40000

# Credit score bands, and the columns derived from the application book.
CREDIT_SCORE_BAND_EDGES = (0, 580, 670, 740, 900)
CREDIT_BAND_NAMES = ("poor", "fair", "good", "excellent")
ENGINEERED_NUMERIC_COLUMNS = ("monthly_installment_inr", "installment_to_income")
ENGINEERED_CATEGORICAL_COLUMNS = ("credit_band",)

# The columns a risk model is allowed to see. Every model is prepared and trained on these
# and on nothing else, so a difference between two models is a difference between the models.
MODELLING_COLUMNS = (
    "age_years", "monthly_income_inr", "employment_type", "credit_score",
    "debt_to_income_ratio", "existing_loan_count", "late_payments_last_12_months",
    "loan_type", "loan_amount_inr", "tenure_months",
)

NUMERIC_MODELLING_COLUMNS = (
    "age_years", "monthly_income_inr", "credit_score", "debt_to_income_ratio",
    "existing_loan_count", "late_payments_last_12_months", "loan_amount_inr", "tenure_months",
)
CATEGORICAL_MODELLING_COLUMNS = ("employment_type", "loan_type")
TARGET_COLUMN = "defaulted"

# Web service settings.
MAXIMUM_REQUESTS_PER_MINUTE = 60
ALLOWED_ORIGINS = ("http://localhost:8080",)

# Formats an identifier must match before it is stored.
PAN_NUMBER_PATTERN = r"^[A-Z]{5}[0-9]{4}[A-Z]$"
MOBILE_NUMBER_PATTERN = r"^[6-9][0-9]{9}$"
EMAIL_ADDRESS_PATTERN = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"

# Access control. The signing key is a development default and is overridden by the
# LOANSERVE_JWT_SECRET environment variable wherever the service is deployed.
JWT_SECRET_KEY = "development-only-secret-replace-before-any-deployment"
JWT_ALGORITHM = "HS256"
TOKEN_LIFETIME_MINUTES = 30
ADMIN_ONLY_METHODS = ("DELETE",)
AUDIT_LOG_PATH = "output/logs/audit.log"

# What a link, a ticket reference and an application reference are replaced with when a
# customer message is cleaned. Later work reads around these exact strings.
URL_PLACEHOLDER = "<url>"
TICKET_PLACEHOLDER = "<ticket>"
APPLICATION_REFERENCE_PLACEHOLDER = "<application_ref>"

# The keys a reply from the language model must carry, and where replies are cached so that
# the same prompt is paid for once.
LLM_REQUIRED_KEYS = ("summary", "sentiment", "action")
LLM_CACHE_PATH = "artifacts/llm_cache.json"

# Where the assistant finds the four things earlier days built, and where a paused run is kept
# until a person answers it.
MESSAGE_CLASSIFIER_PATH = "artifacts/message_classifier.pkl"
CHAMPION_MODEL_PATH = "artifacts/champion.pkl"
APPLICATION_DATABASE_PATH = "database/loanserve.db"
POLICY_STORE_PATH = "database/policy_store"
CHECKPOINT_DATABASE_PATH = "database/assistant_threads.sqlite"

# A message longer than this is refused rather than processed.
MAXIMUM_MESSAGE_CHARACTERS = 4000

# Escalation. Two signals raise a case for a person; exposure on its own has to be very
# large before it counts.
UNHAPPY_SENTIMENTS = ("angry", "worried")
LARGE_EXPOSURE_INR = 1_500_000
VERY_LARGE_EXPOSURE_INR = 5_000_000

# The longest a policy chunk may run before it is cut.
POLICY_CHUNK_CHARACTERS = 700

# What a customer is shown when the assistant has no answer it stands behind. The internal
# reason names what tripped and is never sent to the person who asked.
LOW_CONFIDENCE_REFUSAL = ("I could not answer that reliably. A colleague has been asked to "
                          "look at your question and will come back to you.")
MINIMUM_ANSWER_CONFIDENCE = 0.6

# A free tier answers a fixed number of requests a minute and refuses the rest with a 429,
# so a refusal clears when the minute does. This is how long to wait before asking again.
FREE_TIER_WAIT_SECONDS = 60