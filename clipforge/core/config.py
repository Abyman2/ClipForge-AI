"""Application Configuration Module.

Loads settings from environment variables and .env with strict validation
and secret masking.
"""

from pathlib import Path
from typing import Literal, Optional
import os
from pydantic import Field, SecretStr

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings

    class SettingsConfigDict(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)


def _load_env_file(filepath: Path = Path(".env")) -> None:
    """Simple .env reader when pydantic-settings is not installed."""
    if not filepath.exists():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"")
                    if k not in os.environ:
                        os.environ[k] = v
    except Exception:
        pass


_load_env_file()


class Settings(BaseSettings):
    """Central application configuration."""

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    # Application
    app_name: str = "ClipForge AI"
    app_version: str = "0.1.0"
    env: Literal["development", "production", "test"] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_ENV", "development")
    )
    debug: bool = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_DEBUG", "true").lower() == "true"
    )
    host: str = Field(default_factory=lambda: os.getenv("CLIPFORGE_HOST", "127.0.0.1"))
    port: int = Field(
        default_factory=lambda: int(os.getenv("CLIPFORGE_PORT", "8000"))
    )

    # Storage Paths
    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CLIPFORGE_DATA_DIR", "clipforge-data"))
    )
    db_name: str = "clipforge.db"
    max_upload_size_bytes: int = Field(
        default_factory=lambda: int(
            os.getenv("CLIPFORGE_MAX_UPLOAD_SIZE_BYTES", str(2 * 1024 * 1024 * 1024))
        )
    )

    # Tool Binary Paths (Optional custom overrides)
    custom_ffmpeg_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_FFMPEG_PATH")
    )
    custom_ffprobe_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_FFPROBE_PATH")
    )

    # External LLM Provider Integration
    llm_api_base: str = Field(
        default_factory=lambda: os.getenv(
            "CLIPFORGE_LLM_API_BASE", "https://api.openai.com/v1"
        )
    )
    llm_api_key: Optional[SecretStr] = Field(
        default_factory=lambda: SecretStr(os.environ["CLIPFORGE_LLM_API_KEY"])
        if "CLIPFORGE_LLM_API_KEY" in os.environ and os.environ["CLIPFORGE_LLM_API_KEY"]
        else None,
        alias="CLIPFORGE_LLM_API_KEY",
    )

    def __init__(self, **data):
        key = data.get("CLIPFORGE_LLM_API_KEY") or data.get("llm_api_key")
        if key is not None:
            if isinstance(key, str):
                key = SecretStr(key)
            data["llm_api_key"] = key
            data["CLIPFORGE_LLM_API_KEY"] = key
        super().__init__(**data)
    llm_model: str = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_LLM_MODEL", "gpt-4o-mini")
    )
    llm_protocol: Literal["openai_compatible", "anthropic"] = Field(
        default_factory=lambda: os.getenv(
            "CLIPFORGE_LLM_PROTOCOL", "openai_compatible"
        )
    )
    llm_max_tokens: int = Field(
        default_factory=lambda: int(os.getenv("CLIPFORGE_LLM_MAX_TOKENS", "4000"))
    )
    llm_timeout: float = Field(
        default_factory=lambda: float(os.getenv("CLIPFORGE_LLM_TIMEOUT", "60.0"))
    )

    # Hardware & Inference Defaults
    device: Literal["cpu", "cuda", "auto"] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_DEVICE", "cpu")
    )
    compute_type: Literal["int8", "float16", "int8_float16"] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_COMPUTE_TYPE", "int8")
    )
    model_size: Literal["tiny", "base", "small", "medium"] = Field(
        default_factory=lambda: os.getenv("CLIPFORGE_MODEL_SIZE", "tiny")
    )
    cpu_threads: int = Field(
        default_factory=lambda: int(os.getenv("CLIPFORGE_CPU_THREADS", "4"))
    )
    models_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("CLIPFORGE_MODELS_DIR", "models"))
    )

    @property
    def whisper_model_dir(self) -> Path:
        """Directory for persistent local Whisper model weights cache."""
        return self.models_dir / "whisper"

    @property
    def db_path(self) -> Path:
        """Absolute or relative path to the SQLite database file."""
        return self.data_dir / self.db_name

    @property
    def projects_dir(self) -> Path:
        """Path to projects storage."""
        return self.data_dir / "projects"

    def get_project_dir(self, project_id: str) -> Path:
        """Get the storage directory for a specific project."""
        return self.projects_dir / project_id

    def ensure_directories(self) -> None:
        """Create necessary storage directories if they do not exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.whisper_model_dir.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
