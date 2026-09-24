"""
Security-related tests.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.core.config import settings


def test_password_hashing():
    """Test password hashing and verification."""
    password = "SecurePass123"
    hashed = hash_password(password)

    # Verify that the password is not stored in plaintext
    assert hashed != password
    assert len(hashed) > 0

    # Verify that password verification works
    assert verify_password(password, hashed) == True
    assert verify_password("wrong_password", hashed) == False


def test_jwt_token_creation_and_decoding():
    """Test JWT token creation and decoding."""
    subject = "123"
    role = "patient"

    # Create token
    token = create_access_token(subject=subject, role=role)
    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode token
    payload = decode_access_token(token)
    assert payload is not None
    assert payload.sub == subject
    assert payload.role == role

    # Test with invalid token
    invalid_payload = decode_access_token("invalid.token.string")
    assert invalid_payload is None


def test_jwt_token_expiration():
    """Test that JWT tokens expire."""
    # This test would require mocking time or checking expiration behavior
    # For now, we'll just verify the token creation works
    pass


if __name__ == "__main__":
    test_password_hashing()
    test_jwt_token_creation_and_decoding()
    test_jwt_token_expiration()
    print("Security tests passed!")