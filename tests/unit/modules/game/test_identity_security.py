from app.modules.identity.security import hash_password, hash_token, new_token, verify_password


def test_passwords_use_salted_argon2_hashes() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert verify_password("correct horse battery staple", first) is True
    assert verify_password("wrong password", first) is False


def test_session_tokens_are_random_and_stored_as_fixed_hashes() -> None:
    first = new_token()
    second = new_token()

    assert first != second
    assert len(hash_token(first)) == 64
    assert first not in hash_token(first)
