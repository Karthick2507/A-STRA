"""
PRISM Config Loader.

Config discovery order:
    1. PRISM_CONFIG env var (explicit path)               — highest priority
    2. Prism_view/shadow_coding/prism_config.json         — plugin / standard
    3. config.json at project root                        — legacy fallback

Selecting an environment:
    Set ENV via .env, CLI flag (--env=staging), or pytest --env=<name>.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent.parent          # …/PRISM

# Plugin-mode config home (primary). Standalone root config.json is a fallback
# for legacy installs.
PLUGIN_CONFIG = PROJECT_ROOT / "Prism_view" / "shadow_coding" / "prism_config.json"
ROOT_CONFIG   = PROJECT_ROOT / "config.json"
ENV_FILE      = PROJECT_ROOT / ".env"


def _resolve_config_path() -> Path:
    """Return path to the active config file. Plugin location wins; root is fallback.

    Override by setting PRISM_CONFIG env var to an explicit path.
    """
    override = os.getenv("PRISM_CONFIG")
    if override:
        return Path(override)
    if PLUGIN_CONFIG.exists():
        return PLUGIN_CONFIG
    return ROOT_CONFIG

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Read-only typed view over merged config. Use `load_config()` to obtain an instance."""
    env: str = "dev"
    base_url: str = ""

    # Optional credentials (used by shadow recording / self-healing scenarios)
    app_username:  str = ""
    app_password:  str = ""

    # Browser
    browser:        str  = "chromium"
    headless:       bool = False
    slow_mo_ms:     int  = 0
    viewport:       Dict[str, int] = field(default_factory=lambda: {"width": 1280, "height": 720})

    # Timeouts
    action_timeout_ms:     int = 15000
    navigation_timeout_ms: int = 30000
    expect_timeout_ms:     int = 10000

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
    style_profile_path:        str        = "Prism_view/shadow_coding/style_profile.json"
    train_classifier_on_learn: bool       = True

    # Raw blob for unmapped keys
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _detect_env() -> str:
    """Return the selected environment name from CLI / env var / config default."""
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--env="):
            return arg.split("=", 1)[1]
        if arg == "--env" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]

    if os.getenv("ASTRA_ENV"):
        return os.environ["ASTRA_ENV"]

    return ""


def _load_json() -> Dict[str, Any]:
    path = _resolve_config_path()
    if not path.exists():
        raise FileNotFoundError(
            f"PRISM config not found. Looked at:\n"
            f"  {PLUGIN_CONFIG}  (plugin location)\n"
            f"  {ROOT_CONFIG}    (standalone fallback)\n"
            f"Set PRISM_CONFIG env var to override."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_config() -> Config:
    """Build a `Config` from config.json + .env + --env override."""
    raw = _load_json()

    env_name = _detect_env() or raw.get("default_env", "dev")
    env_block = raw.get("environments", {}).get(env_name, {})

    cfg = Config(
        env      = env_name,
        base_url = env_block.get("base_url", ""),
        raw      = raw,

        app_username = os.getenv("APP_USERNAME", ""),
        app_password = os.getenv("APP_PASSWORD", ""),
    )

    # Browser
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

    # Self-healing
    h = raw.get("self_healing", {})
    cfg.healing_enabled           = bool(h.get("enabled", True))
    cfg.healing_auto_apply_silent = bool(h.get("auto_apply_silent", True))
    cfg.healing_min_confidence    = float(h.get("min_confidence", 0.75))
    cfg.locator_registry_path     = h.get("registry_path",      cfg.locator_registry_path)
    cfg.onnx_model_path           = h.get("model_path",         cfg.onnx_model_path)
    cfg.sklearn_model_path        = h.get("sklearn_path",       cfg.sklearn_model_path)

    # Shadow coding
    s = raw.get("shadow_coding", {})
    cfg.shadow_session_dir        = s.get("session_dir", cfg.shadow_session_dir)
    cfg.shadow_auto_assertions    = bool(s.get("auto_assertions", True))
    cfg.shadow_checkpoints        = list(s.get("assertion_checkpoints", []))
    cfg.style_profile_path        = s.get("style_profile_path",     cfg.style_profile_path)
    cfg.train_classifier_on_learn = bool(s.get("train_classifier_on_learn", True))

    return cfg


# Module-level singleton
CONFIG: Config = load_config()
