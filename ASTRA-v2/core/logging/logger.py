"""
ASTRA-v2 Structured Logger.

Layers:
    1. Console handler with colour-coded levels (colorlog).
    2. Rotating file handler (5 MB × 3 backups).
    3. Custom levels:
         ASTAR     — A* search progress
         HEAL      — self-healing events
         SHADOW    — shadow-coding recorder events
         AUTOPILOT — autopilot runner events
         API       — API client events

Usage:
    from ASTRA_v2.core.logging import logger
    logger.info("hello")
    logger.astar("step 3 — fScore=0.42")
    logger.heal("locator '#email' healed → '[name=email]' (conf=0.92)")
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

try:
    import colorlog
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False

# ─── Custom level numbers (between INFO=20 and WARNING=30) ─────────────────
ASTAR     = 22
HEAL      = 23
SHADOW    = 24
AUTOPILOT = 25
API       = 26

logging.addLevelName(ASTAR,     "ASTAR")
logging.addLevelName(HEAL,      "HEAL")
logging.addLevelName(SHADOW,    "SHADOW")
logging.addLevelName(AUTOPILOT, "AUTOPILOT")
logging.addLevelName(API,       "API")

_LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_COLOR_MAP = {
    "DEBUG":     "cyan",
    "INFO":      "green",
    "ASTAR":     "yellow",
    "HEAL":      "magenta",
    "SHADOW":    "blue",
    "AUTOPILOT": "purple",
    "API":       "light_cyan",
    "WARNING":   "yellow",
    "ERROR":     "red",
    "CRITICAL":  "bold_red",
}


class AstraLogger(logging.Logger):
    """Logger with helpers for the custom levels."""

    def astar(self, msg, *args, **kwargs):
        if self.isEnabledFor(ASTAR):
            self._log(ASTAR, msg, args, **kwargs)

    def heal(self, msg, *args, **kwargs):
        if self.isEnabledFor(HEAL):
            self._log(HEAL, msg, args, **kwargs)

    def shadow(self, msg, *args, **kwargs):
        if self.isEnabledFor(SHADOW):
            self._log(SHADOW, msg, args, **kwargs)

    def autopilot(self, msg, *args, **kwargs):
        if self.isEnabledFor(AUTOPILOT):
            self._log(AUTOPILOT, msg, args, **kwargs)

    def api(self, msg, *args, **kwargs):
        if self.isEnabledFor(API):
            self._log(API, msg, args, **kwargs)

    # Convenience helpers
    def divider(self, char: str = "─", width: int = 70) -> None:
        self.info(char * width)

    def banner(self, text: str) -> None:
        self.divider("═")
        self.info(text)
        self.divider("═")


def _build_logger(name: str = "astra") -> AstraLogger:
    logging.setLoggerClass(AstraLogger)
    log = logging.getLogger(name)
    if log.handlers:
        return log  # type: ignore[return-value]

    log.setLevel(logging.DEBUG)
    log.propagate = False  # avoid double prints if root logger configured

    # ── Console
    if _HAS_COLOR:
        console_fmt = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)-9s]%(reset)s %(message)s",
            datefmt="%H:%M:%S",
            log_colors=_COLOR_MAP,
        )
    else:
        console_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)-9s] %(message)s", datefmt="%H:%M:%S"
        )
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(console_fmt)
    log.addHandler(ch)

    # ── File (rotating)
    fh = RotatingFileHandler(
        _LOG_DIR / "astra.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-9s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    log.addHandler(fh)

    return log  # type: ignore[return-value]


def get_logger(name: Optional[str] = None) -> AstraLogger:
    """Return an Astra logger. Same root settings, optional child name."""
    if not name or name == "astra":
        return _build_logger("astra")
    parent = _build_logger("astra")
    child = parent.getChild(name)
    return child  # type: ignore[return-value]


# Module-level convenience
logger: AstraLogger = _build_logger("astra")
