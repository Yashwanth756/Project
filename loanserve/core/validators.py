import re

from config.constants import (
    EMAIL_ADDRESS_PATTERN,
    MOBILE_NUMBER_PATTERN,
    PAN_NUMBER_PATTERN,
)
from loanserve.core.exceptions import InvalidApplicationError


def validate_pan_number(pan_number):
    """Settles a PAN into its canonical form and refuses one that is not a PAN."""
    if not isinstance(pan_number, str):
        raise InvalidApplicationError(f"PAN number {pan_number} is not in the format AAAAA9999A")

    settled = pan_number.strip().upper()
    if not re.match(PAN_NUMBER_PATTERN, settled):
        raise InvalidApplicationError(
            f"PAN number {pan_number} is not in the format AAAAA9999A"
        )
    return settled


def validate_mobile_number(mobile_number):
    """Settles a mobile number into its canonical form and refuses one that is not usable."""
    if not isinstance(mobile_number, str):
        raise InvalidApplicationError(
            f"Mobile number {mobile_number} is invalid: ten digits led by 6 to 9 are expected"
        )

    settled = re.sub(r"\s+", "", mobile_number.strip())
    if not re.match(MOBILE_NUMBER_PATTERN, settled):
        raise InvalidApplicationError(
            f"Mobile number {mobile_number} is invalid: ten digits led by 6 to 9 are expected"
        )
    return settled


def validate_email_address(email_address):
    """Settles an email address into its canonical form and refuses one that is not an address."""
    if not isinstance(email_address, str):
        raise InvalidApplicationError(f"Email address {email_address} is not valid")

    settled = email_address.strip().lower()
    if not re.match(EMAIL_ADDRESS_PATTERN, settled):
        raise InvalidApplicationError(f"Email address {email_address} is not valid")
    return settled


if __name__ == "__main__":
    pan = validate_pan_number(" abcde1234f ")
    mob = validate_mobile_number("98765 43210")
    print(f"{pan} {mob}")
    try:
        validate_pan_number("ABCD1234F")
    except InvalidApplicationError as e:
        print(f"refused: {e}")