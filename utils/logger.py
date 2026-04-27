"""ASTRA logger - color-coded console + rotating file output."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

try:
    import colorlog
    HAS_COLORLOG = True
except ImportError:
    HAS_COLORLOG = False

# Custom log levels
PREFLIGHT_LEVEL = 25
ASTAR_LEVEL = 26
CODEGEN_LEVEL = 27

logging.addLevelName(PREFLIGHT_LEVEL, "PREFLIGHT")
logging.addLevelName(ASTAR_LEVEL, "ASTAR")
logging.addLevelName(CODEGEN_LEVEL, "CODEGEN")

_LOG_DIR = Path(__file__).parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

COLOR_MAP = {
    "DEBUG": "cyan",
    "INFO": "green",
    "PREFLIGHT": "blue",
    "ASTAR": "yellow",
    "CODEGEN": "magenta",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold_red",
}


class AstraLogger(logging.Logger):
    """Extended logger with ASTRA-specific convenience methods."""

    def preflight(self, msg: str, *args, **kwargs) -> None:
        if self.isEnabledFor(PREFLIGHT_LEVEL):
            self._log(PREFLIGHT_LEVEL, msg, args, **kwargs)

    def astar(self, msg: str, *args, **kwargs) -> None:
        if self.isEnabledFor(ASTAR_LEVEL):
            self._log(ASTAR_LEVEL, msg, args, **kwargs)

    def codegen(self, msg: str, *args, **kwargs) -> None:
        if self.isEnabledFor(CODEGEN_LEVEL):
            self._log(CODEGEN_LEVEL, msg, args, **kwargs)

    def astar_step(self, step: int, field: str, score: float) -> None:
        self.astar(f"  Step {step:>3}: [{field}] f={score:.3f}")

    def goal_reached(self, iterations: int, fields_filled: int) -> None:
        self.astar(
            f"  GOAL REACHED after {iterations} iterations, {fields_filled} fields filled"
        )

    def divider(self, char: str = "─", width: int = 60) -> None:
        self.info(char * width)

    def preflight_result(self, analyser: str, status: str, detail: str = "") -> None:
        symbol = "✓" if status == "OK" else "✗" if status == "FAIL" else "⚠"
        self.preflight(f"  {symbol} {analyser:<30} {status}  {detail}")


def _build_logger() -> AstraLogger:
    logging.setLoggerClass(AstraLogger)
    log = logging.getLogger("astra")  # type: ignore[assignment]
    log.__class__ = AstraLogger
    log.setLevel(logging.DEBUG)

    if not log.handlers:
        # Console handler
        if HAS_COLORLOG:
            fmt = colorlog.ColoredFormatter(
                "%(log_color)s%(asctime)s [%(levelname)-9s]%(reset)s %(message)s",
                datefmt="%H:%M:%S",
                log_colors=COLOR_MAP,
            )
        else:
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)-9s] %(message)s", datefmt="%H:%M:%S"
            )
        ch = logging.StreamHandler()
        ch.setFormatter(fmt)
        log.addHandler(ch)

        # Rotating file handler (5 MB, 3 backups)
        fh = RotatingFileHandler(
            _LOG_DIR / "astra.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)-9s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        log.addHandler(fh)

    return log  # type: ignore[return-value]


logger: AstraLogger = _build_logger()
