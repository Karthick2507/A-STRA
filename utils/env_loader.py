"""ASTRA environment loader - loads and validates .env configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv, set_key

_ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)

REQUIRED_KEYS = [
    "BASE_URL",
    "LOGIN_URL",
    "TARGET_PAGE_URL",
    "APP_USERNAME",
    "APP_PASSWORD",
]


@dataclass
class EnvConfig:
    BASE_URL: str
    LOGIN_URL: str
    TARGET_PAGE_URL: str
    APP_USERNAME: str
    APP_PASSWORD: str
    BEARER_TOKEN: str
    HEALTH_CHECK: str
    BROWSER: str
    HEADLESS: str


def _load_env() -> EnvConfig:
    missing = [k for k in REQUIRED_KEYS if not os.getenv(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in the values."
        )
    return EnvConfig(
        BASE_URL=os.environ["BASE_URL"],
        LOGIN_URL=os.environ["LOGIN_URL"],
        TARGET_PAGE_URL=os.environ["TARGET_PAGE_URL"],
        APP_USERNAME=os.environ["APP_USERNAME"],
        APP_PASSWORD=os.environ["APP_PASSWORD"],
        BEARER_TOKEN=os.getenv("BEARER_TOKEN", ""),
        HEALTH_CHECK=os.getenv("HEALTH_CHECK", "true"),
        BROWSER=os.getenv("BROWSER", "chromium"),
        HEADLESS=os.getenv("HEADLESS", "false"),
    )


def update_env_file(key: str, value: str) -> None:
    """Persist a key-value pair to the .env file."""
    set_key(str(_ENV_FILE), key, value)
    os.environ[key] = value


ENV: EnvConfig = _load_env()
