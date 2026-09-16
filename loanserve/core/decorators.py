from functools import wraps
from time import perf_counter

from loanserve.core.exceptions import InvalidApplicationError


def reject_negative_arguments(wrapped_function):
    """Guards a calculation against negative numerical arguments."""

    @wraps(wrapped_function)
    def checked_call(*positional_arguments, **keyword_arguments):
        for arg in positional_arguments:
            if isinstance(arg, (int, float)) and not isinstance(arg, bool):
                if arg < 0:
                    raise InvalidApplicationError(
                        f"{wrapped_function.__name__} received negative argument: {arg}"
                    )
        return wrapped_function(*positional_arguments, **keyword_arguments)

    return checked_call


def measure_duration(wrapped_function):
    """Records how long a call took on the last_duration_seconds attribute."""

    @wraps(wrapped_function)
    def timed_call(*positional_arguments, **keyword_arguments):
        start = perf_counter()
        try:
            return wrapped_function(*positional_arguments, **keyword_arguments)
        finally:
            timed_call.last_duration_seconds = perf_counter() - start

    timed_call.last_duration_seconds = 0.0
    return timed_call


if __name__ == "__main__":
    @measure_duration
    @reject_negative_arguments
    def add_processing_fee(loan_amount_inr):
        return loan_amount_inr * 1.01

    result = add_processing_fee(500000.0)
    print(result, add_processing_fee.last_duration_seconds)