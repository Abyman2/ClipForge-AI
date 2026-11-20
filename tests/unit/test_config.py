"""Unit tests for configuration loading and secret handling."""

from clipforge.core.config import Settings
from pydantic import SecretStr


def test_default_config():
    """Verify default configuration values."""
    cfg = Settings()
    assert cfg.app_name == "ClipForge AI"
    assert cfg.port == 8000
    assert cfg.device == "cpu"
    assert cfg.compute_type == "int8"
    assert cfg.model_size == "tiny"


def test_secret_str_masking():
    """Verify that SecretStr does not expose raw values in string representations."""
    test_key_val = "sample-redacted-key-val"
    cfg = Settings(CLIPFORGE_LLM_API_KEY=test_key_val)
    assert isinstance(cfg.llm_api_key, SecretStr)
    assert test_key_val not in str(cfg.llm_api_key)
    assert cfg.llm_api_key.get_secret_value() == test_key_val

