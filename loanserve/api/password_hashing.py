from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class PasswordVault:
    """Argon2 password hasher and verifier."""

    def __init__(self):
        self.password_hasher = PasswordHasher()

    def hash_password(self, plain_password):
        return self.password_hasher.hash(plain_password)

    def matches_stored_hash(self, plain_password, stored_hash):
        try:
            return self.password_hasher.verify(stored_hash, plain_password)
        except (VerifyMismatchError, InvalidHashError, Exception):
            return False


if __name__ == "__main__":
    vault = PasswordVault()
    stored = vault.hash_password("sunlit-harbour-42")
    print(f"stored: {stored[:40]} ...")
    print(vault.matches_stored_hash("sunlit-harbour-42", stored), vault.matches_stored_hash("wrong", stored))
