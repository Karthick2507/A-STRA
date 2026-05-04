"""
PRISM Config Loader.

Merges three sources, in increasing precedence:

    1. config.json     (non-secret defaults, committed to repo)
    2. .env            (secrets, NOT committed)
    3. CLI override    (--env=staging passes through to argparse / pytest)

Selecting an environment:
    Set ENV via .env, CLI flag, or pytest --env=<name>.
    The matching block in config["environments"][env] is merged into the top level
    so callers can simply read `config.base_url` regardless of environment.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

#from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent          # …/PRISM
REPO_ROOT    = PROJECT_ROOT.parent                 # repo root
CONFIG_JSON  = PROJECT_ROOT / "config.json"
ENV_FILE     = PROJECT_ROOT / ".env"

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Read-only typed view over merged config.

    Use `load_config()` to obtain an instance.
    """
    # Selected environment
    env: str = "dev"

    # Active environment URLs (from environments[env])
    base_url: str = ""
    api_url:  str = ""

    # Secrets (from .env)
    app_username:  str = ""
    app_password:  str = ""
    bearer_token:  str = ""
    api_key:       str = ""
    sso_client_id: str = ""
    sso_client_secret: str = ""

    slack_webhook_url:  str = ""
    teams_webhook_url:  str = ""
    smtp_host:          str = ""
    smtp_port:          int = 587
    smtp_user:          str = ""
    smtp_password:      str = ""
    smtp_from:          str = ""
    smtp_to:            List[str] = field(default_factory=list)

    # Browser
    browser:        str  = "chromium"
    headless:       bool = False
    slow_mo_ms:     int  = 0
    viewport:       Dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 720})

    # Timeouts
    action_timeout_ms:     int = 15000
    navigation_timeout_ms: int = 30000
    expect_timeout_ms:     int = 10000

    # Retry
    retry_max_attempts:    int       = 3
    retry_backoff_seconds: List[int] = field(default_factory=lambda: [2, 4, 8])

    # Self-healing
    healing_enabled:           bool   = True
    healing_auto_apply_silent: bool   = True
    healing_min_confidence:    float  = 0.75
    locator_registry_path:     str    = "Data/locators/locator_registry.db"
    onnx_model_path:           str    = "Prism_view/self_healing/ml/models/healer_model.onnx"
    sklearn_model_path:        str    = "Prism_view/self_healing/ml/models/healer_model.pkl"

    # Shadow coding
    shadow_session_dir:        str        = "Prism_view/shadow_coding/sessions"
    shadow_auto_assertions:    bool       = True
    shadow_checkpoints:        List[str]  = field(default_factory=list)
    slate_file:                str        = "Prism_view/shadow_coding/corporate_slate.py"
    slate_language:            str        = "python"
    style_profile_path:        str        = "Prism_view/shadow_coding/style_profile.json"
    train_classifier_on_learn: bool       = True
    slates:                    Dict[str, Dict[str, str]] = field(default_factory=dict)

    # Reporting
    report_tool:               str   = "allure"
    report_results_dir:        str   = "reports/allure-results"
    attach_screenshots:        bool  = True
    attach_traces:             bool  = True
    attach_videos:             bool  = False

    # Notifications
    notify_enabled:            bool       = True
    notify_send_on:            str        = "every_run"
    notify_channels:           List[str]  = field(default_factory=list)

    # Raw blob in case callers want unmapped keys
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _detect_env() -> str:
    """Return the selected environment name.

    Precedence:
        1. CLI flag           --env=<name>          (works for both python main.py and pytest)
        2. Env var            ASTRA_ENV=<name>
        3. config.json        default_env
    """
    # CLI: scan sys.argv for --env=foo or --env foo
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--env="):
            return arg.split("=", 1)[1]
        if arg == "--env" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]

    if os.getenv("ASTRA_ENV"):
        return os.environ["ASTRA_ENV"]

    return ""  # caller will fall back to config["default_env"]


def _load_json() -> Dict[str, Any]:
    if not CONFIG_JSON.exists():
        raise FileNotFoundError(
            f"config.json not found at {CONFIG_JSON}. "
            f"Cannot load framework configuration."
        )
    return json.loads(CONFIG_JSON.read_text(encoding="utf-8"))


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> Config:
    """Build a `Config` from config.json + .env + --env override.

    Safe to call repeatedly; returns a fresh instance each call.
    Validation: required secrets emit warnings (not hard errors)
    so unit tests in CI without real creds still run.
    """
    raw = _load_json()

    env_name = _detect_env() or raw.get("default_env", "dev")
    env_block = raw.get("environments", {}).get(env_name, {})
    if not env_block:
        raise ValueError(
            f"Environment '{env_name}' not found in config.json. "
            f"Available: {list(raw.get('environments', {}).keys())}"
        )

    cfg = Config(
        env      = env_name,
        base_url = env_block.get("base_url", ""),
        api_url  = env_block.get("api_url",  ""),
        raw      = raw,

        # Secrets
        app_username       = os.getenv("APP_USERNAME",       ""),
        app_password       = os.getenv("APP_PASSWORD",       ""),
        bearer_token       = os.getenv("BEARER_TOKEN",       ""),
        api_key            = os.getenv("API_KEY",            ""),
        sso_client_id      = os.getenv("SSO_CLIENT_ID",      ""),
        sso_client_secret  = os.getenv("SSO_CLIENT_SECRET",  ""),
        slack_webhook_url  = os.getenv("SLACK_WEBHOOK_URL",  ""),
        teams_webhook_url  = os.getenv("TEAMS_WEBHOOK_URL",  ""),
        smtp_host          = os.getenv("SMTP_HOST",          ""),
        smtp_port          = int(os.getenv("SMTP_PORT",      "587")),
        smtp_user          = os.getenv("SMTP_USER",          ""),
        smtp_password      = os.getenv("SMTP_PASSWORD",      ""),
        smtp_from          = os.getenv("SMTP_FROM",          ""),
        smtp_to            = _split_csv(os.getenv("SMTP_TO", "")),
    )

    # Browser block
    b = raw.get("browser", {})
    cfg.browser    = os.getenv("BROWSER",  b.get("default",   "chromium"))
    cfg.headless   = (os.getenv("HEADLESS", str(b.get("headless", False))).lower() == "true")
    cfg.slow_mo_ms = int(os.getenv("SLOW_MO_MS", b.get("slow_mo_ms", 0)))
    cfg.viewport   = b.get("viewport", {"width": 1280, "height": 720})

    # Timeouts
    t = raw.get("timeouts", {})
    cfg.action_timeout_ms     = int(t.get("action_ms",      15000))
    cfg.navigation_timeout_ms = int(t.get("navigation_ms",  30000))
    cfg.expect_timeout_ms     = int(t.get("expect_ms",      10000))

    # Retry
    r = raw.get("retry", {})
    cfg.retry_max_attempts    = int(r.get("max_attempts", 3))
    cfg.retry_backoff_seconds = list(r.get("backoff_seconds", [2, 4, 8]))

    # Self-healing
    h = raw.get("self_healing", {})
    cfg.healing_enabled           = bool(h.get("enabled", True))
    cfg.healing_auto_apply_silent = bool(h.get("auto_apply_silent", True))
    cfg.healing_min_confidence    = float(h.get("min_confidence", 0.75))
    cfg.locator_registry_path     = h.get("registry_path",       cfg.locator_registry_path)
    cfg.onnx_model_path           = h.get("model_path",          cfg.onnx_model_path)
    cfg.sklearn_model_path        = h.get("sklearn_model_path",  cfg.sklearn_model_path)

    # Shadow coding
    s = raw.get("shadow_coding", {})
    cfg.shadow_session_dir     = s.get("session_dir", cfg.shadow_session_dir)
    cfg.shadow_auto_assertions = bool(s.get("auto_assertions", True))
    cfg.shadow_checkpoints     = list(s.get("assertion_checkpoints", []))
    cfg.slate_file             = s.get("slate_file",             cfg.slate_file)
    cfg.slate_language         = s.get("slate_language",         cfg.slate_language)
    cfg.style_profile_path     = s.get("style_profile_path",     cfg.style_profile_path)
    cfg.train_classifier_on_learn = bool(s.get("train_classifier_on_learn", True))
    cfg.slates                 = dict(s.get("slates", {}))

    # Reporting
    rep = raw.get("reporting", {})
    cfg.report_tool        = rep.get("tool", "allure")
    cfg.report_results_dir = rep.get("results_dir", cfg.report_results_dir)
    cfg.attach_screenshots = bool(rep.get("attach_screenshots_on_failure", True))
    cfg.attach_traces      = bool(rep.get("attach_traces_on_failure",      True))
    cfg.attach_videos      = bool(rep.get("attach_videos_on_failure",     False))

    # Notifications
    n = raw.get("notifications", {})
    cfg.notify_enabled  = bool(n.get("enabled", True))
    cfg.notify_send_on  = n.get("send_on", "every_run")
    cfg.notify_channels = list(n.get("channels", []))

    return cfg


# Convenience module-level singleton
CONFIG: Config = load_config()
