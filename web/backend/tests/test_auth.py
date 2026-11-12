from app.core.security import create_access_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_access_token_roundtrip():
    token = create_access_token("user-1", "a@b.com")
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"
    assert payload["email"] == "a@b.com"
    assert payload["type"] == "access"
