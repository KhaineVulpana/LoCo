from app.core import auth


def test_get_or_create_token_creates_and_reuses(monkeypatch, tmp_path):
    token_path = tmp_path / 'token'
    monkeypatch.setattr(auth, 'TOKEN_FILE', token_path)

    token = auth.get_or_create_token()
    assert token_path.exists()

    token_again = auth.get_or_create_token()
    assert token_again == token


def test_verify_token(monkeypatch, tmp_path):
    token_path = tmp_path / 'token'
    monkeypatch.setattr(auth, 'TOKEN_FILE', token_path)

    token = auth.get_or_create_token()
    assert auth.verify_token(token) is True
    assert auth.verify_token('wrong-token') is False
