from app.core.config import Settings


def test_settings_defaults():
    settings = Settings()
    assert settings.PORT == 3199
    assert settings.MODEL_PROVIDER


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv('MODEL_PROVIDER', 'vllm')
    settings = Settings()
    assert settings.MODEL_PROVIDER == 'vllm'
