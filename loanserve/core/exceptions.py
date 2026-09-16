class LoanServeError(Exception):
    """Base class for every error the platform raises deliberately."""


class UnsupportedLoanTypeError(LoanServeError):
    """The loan type is not in the product catalogue. Raised by the entities of Week 1 Day 4."""


class StorageError(LoanServeError):
    """A stored file could not be read or written. Raised by the file storage below."""


class InvalidApplicationError(LoanServeError):
    """An application field failed its format check. Raised by the validators and the argument decorator of Week 1 Day 5."""


class LanguageModelError(LoanServeError):
    """Raised when language model configuration or call fails."""