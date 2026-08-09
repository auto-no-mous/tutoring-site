import pytest

from app.core.config import INSECURE_DEFAULT_JWT_SECRET, settings
from app.main import _validate_production_config


def test_refuses_to_start_with_insecure_secret_outside_debug(monkeypatch) -> None:
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret_key", INSECURE_DEFAULT_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
        _validate_production_config()


def test_allows_insecure_secret_while_debug_is_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "jwt_secret_key", INSECURE_DEFAULT_JWT_SECRET)
    _validate_production_config()  # does not raise


def test_allows_debug_false_with_a_real_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "jwt_secret_key", "a-real-random-secret")
    _validate_production_config()  # does not raise
