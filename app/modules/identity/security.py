import hashlib
import secrets

from pwdlib import PasswordHash

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    """Hash a user password with the currently recommended Argon2 configuration."""
    return password_hash.hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password and treat malformed stored hashes as authentication failure."""
    try:
        return password_hash.verify(password, encoded_hash)
    except Exception:  # noqa: BLE001 - corrupted credentials must not expose parser details
        return False


def new_token() -> str:
    """Return a URL-safe session or CSRF token with 256 bits of CSPRNG entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Create the non-reversible database representation of a random token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
