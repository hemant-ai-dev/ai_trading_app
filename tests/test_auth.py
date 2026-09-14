"""Auth hashing and SQLite TReadUser."""

from auth.captcha import captcha_matches, generate_captcha_text
from auth.passwords import hash_password, validate_signup, verify_password
from auth.users import authenticate, create_user
from db.bootstrap import initialize


def test_password_roundtrip():
    stored = hash_password("secret-pass1")
    assert "secret-pass1" not in stored
    assert stored.startswith("$2")
    assert verify_password("secret-pass1", stored)
    assert not verify_password("wrong-pass1", stored)


def test_signup_rules():
    assert validate_signup("ab", "a@b.com", "secret-pass1")
    assert validate_signup("trader1", "bad", "secret-pass1")
    assert validate_signup("trader1", "t@example.com", "short")
    assert validate_signup("trader1", "t@example.com", "allletters")
    assert validate_signup("trader1", "t@example.com", "secret-pass1") is None


def test_captcha_has_letters_and_digits():
    code = generate_captcha_text()
    assert len(code) == 6
    assert any(c.isalpha() for c in code)
    assert any(c.isdigit() for c in code)
    assert captcha_matches(code.lower(), code)
    assert not captcha_matches("XXXXXX", code)


def test_sqlite_register_login(tmp_path, monkeypatch):
    monkeypatch.setenv("ANGAD_SQLITE_PATH", str(tmp_path / "trading_tool.db"))
    initialize()
    rec, err = create_user("trader1", "t@example.com", "secret-pass1")
    assert err is None and rec is not None
    assert rec.role == "Admin"
    user, login_err = authenticate("t@example.com", "secret-pass1")
    assert login_err is None
    assert user.username == "trader1"
    rec2, err2 = create_user("trader2", "u@example.com", "secret-pass1")
    assert err2 is None
    assert rec2.role == "User"
    bad, bad_err = authenticate("trader1", "wrong-pass1")
    assert bad is None and bad_err
