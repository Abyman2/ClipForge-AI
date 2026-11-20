"""Secure logging module with secret scrubbing."""

import logging
import re
from typing import Dict, Any

SECRET_PATTERNS = [
    re.compile(r"(Bearer\s+)[a-zA-Z0-9_\-\.]{15,}", re.IGNORECASE),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),
    re.compile(r"(sk-ant-[a-zA-Z0-9]{20,})"),
    re.compile(r"(ghp_[a-zA-Z0-9]{20,})"),
]

SENSITIVE_HEADERS = {"authorization", "x-api-key", "api-key", "token"}


def sanitize_message(msg: str) -> str:
    """Mask secret patterns inside a string."""
    for pattern in SECRET_PATTERNS:
        msg = pattern.sub(r"\1***REDACTED***", msg)
    return msg


def sanitize_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive HTTP headers."""
    sanitized = {}
    for k, v in headers.items():
        if k.lower() in SENSITIVE_HEADERS:
            sanitized[k] = "***REDACTED***"
        else:
            sanitized[k] = v
    return sanitized


class SecretScrubbingFormatter(logging.Formatter):
    """Custom logging formatter that scrubs credentials from output."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return sanitize_message(original)


def setup_logger(name: str = "clipforge", level: int = logging.INFO) -> logging.Logger:
    """Create a configured logger with secret scrubbing."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = SecretScrubbingFormatter(
            fmt="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logger()

