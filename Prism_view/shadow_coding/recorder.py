"""
PRISM Shadow Coding — Recorder.

Wraps `playwright codegen` CLI so a tester can manually browse the app
while the framework captures every action.  After recording, the raw
codegen output (pytest-style) is piped to CodeEnhancer which converts it
into ASTRA POM style with auto-assertions.

Workflow
────────
    recorder = ShadowRecorder(output_dir="Prism_view/shadow_coding/sessions")
    session  = recorder.start(url="https://app.example.com/login")
    # ← user interacts in the browser window opened by codegen
    result   = recorder.stop()          # blocks until codegen exits
    # result.raw_file  → raw codegen .py
    # result.session_id

Usage from CLI (astra shadow)
──────────────────────────────
    python -m Prism_view.shadow_coding.recorder --url https://... --out sessions/

How codegen is invoked
──────────────────────
    playwright codegen --target python-pytest --output <raw_path> <url>

The subprocess is launched with the user's PATH so it picks up the venv's
`playwright` binary.  On Windows, 'playwright' may not be on PATH if the
venv hasn't been activated — the recorder also tries `python -m playwright`.
"""
from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.logging import logger


@dataclass
class ShadowSession:
    session_id: str
    raw_file:   Path
    url:        str
    started_at: float


class ShadowRecorder:
    """Launch playwright codegen and capture the raw output file."""

    def __init__(self, output_dir: str | Path = "Prism_view/shadow_coding/sessions") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._proc: Optional[subprocess.Popen] = None
        self._session: Optional[ShadowSession] = None

    def start(self, url: str) -> ShadowSession:
        """Launch `playwright codegen` in a subprocess and return the session."""
        if self._proc is not None:
            raise RuntimeError("A recording session is already active. Call stop() first.")

        session_id = f"shadow_{int(time.time())}"
        raw_file   = self.output_dir / f"{session_id}_raw.py"

        cmd = self._build_command(url, raw_file)
        logger.shadow("Starting shadow recording session %s → %s", session_id, raw_file)
        logger.shadow("Command: %s", " ".join(cmd))

        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._session = ShadowSession(
            session_id=session_id,
            raw_file=raw_file,
            url=url,
            started_at=time.time(),
        )
        return self._session

    def stop(self, timeout: float = 300.0) -> ShadowSession:
        """Wait for codegen to exit and return the session object."""
        if self._proc is None or self._session is None:
            raise RuntimeError("No active recording session.")

        logger.shadow("Waiting for playwright codegen to exit (timeout=%.0fs)…", timeout)
        try:
            stdout, stderr = self._proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            stdout, stderr = self._proc.communicate()
            logger.warning("playwright codegen timed out — session saved as-is")

        if stderr:
            logger.debug("codegen stderr: %s", stderr.decode(errors="replace"))

        session = self._session
        self._proc    = None
        self._session = None
        logger.shadow("Shadow recording stopped. Raw file: %s", session.raw_file)
        return session

    def is_recording(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_command(self, url: str, output: Path) -> list[str]:
        playwright_bin = self._find_playwright_binary()
        return [
            playwright_bin, "codegen",
            "--target", "python-pytest",
            "--output", str(output),
            url,
        ]

    @staticmethod
    def _find_playwright_binary() -> str:
        """Return the playwright binary path, preferring the active venv."""
        venv_bin = Path(sys.executable).parent / "playwright"
        if venv_bin.exists():
            return str(venv_bin)
        # Windows
        venv_bin_win = Path(sys.executable).parent / "playwright.exe"
        if venv_bin_win.exists():
            return str(venv_bin_win)
        # Fallback: expect it on PATH
        return "playwright"


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ASTRA Shadow Coding — interactive recorder")
    parser.add_argument("--url", required=True, help="Starting URL for codegen")
    parser.add_argument("--out", default="Prism_view/shadow_coding/sessions", help="Output directory")
    args = parser.parse_args()

    rec = ShadowRecorder(output_dir=args.out)
    sess = rec.start(url=args.url)
    print(f"[ASTRA Shadow] Recording started. Interact with the browser, then close it.")
    print(f"[ASTRA Shadow] Session: {sess.session_id}")
    final = rec.stop(timeout=600)
    print(f"[ASTRA Shadow] Done. Raw file saved to: {final.raw_file}")
