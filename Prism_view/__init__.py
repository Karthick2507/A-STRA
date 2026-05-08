"""
PRISM — public plugin API.

Use this package directly when integrating PRISM into another framework:

    from prism import ShadowCoder, SelfHealer

    coder = ShadowCoder(session_dir="./my_sessions")
    files = coder.record_and_generate("https://yourapp.com")

    healer = SelfHealer()
    new_locator = healer.heal(broken_locator, page)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

# Re-export low-level building blocks for advanced users
from Prism_view.shadow_coding import (
    ShadowRecorder,
    ShadowSession,
    CodeEnhancer,
    ROLES,
    ROLE_NAMES,
    output_path_for,
)
from Prism_view.self_healing import (
    LocatorRegistry,
    LocatorRecord,
    HealerOrchestrator,
    HealResult,
    HealingConfig,
)
from Prism_view.shadow_coding.scanner import (
    ScannedFile,
    RoleAssignment,
    ScanResult,
)

# ─────────────────────────────────────────────────────────────────────────────
# High-level plugin API — what most consumers should use
# ─────────────────────────────────────────────────────────────────────────────

class ShadowCoder:
    """Record a browser session and generate corporate-style POM files.

    Args:
        session_dir: Where raw recordings + generated files are written.
                     Default: from prism_config.json shadow_coding.session_dir.
        network_name: Tag included in generated test data (default "YourNetwork").
    """

    def __init__(
        self,
        session_dir: Optional[str | Path] = None,
        network_name: str = "YourNetwork",
    ) -> None:
        from core.config import CONFIG
        self._session_dir = Path(session_dir or CONFIG.shadow_session_dir)
        self._network_name = network_name

    def record_and_generate(self, url: str, timeout_sec: int = 600) -> Dict[str, Path]:
        """Open a browser at `url`, record user actions, generate POM files when closed.

        Returns a dict of generated file paths keyed by role
        (`ui`, `data`, `base_page`, optionally `locators`, `controller`, `api_test`).
        """
        recorder = ShadowRecorder(output_dir=self._session_dir)
        session = recorder.start(url=url)
        final = recorder.stop(timeout=timeout_sec)
        enhancer = CodeEnhancer(
            session_id=final.session_id,
            network_name=self._network_name,
        )
        return enhancer.enhance_file(final.raw_file)


class SelfHealer:
    """Heal broken locators via 6-strategy pipeline + ML re-rank.

    Args:
        registry_path: SQLite path for locator history.
                       Default: from prism_config.json self_healing.registry_path.
        min_confidence: Minimum score to auto-apply a heal (default 0.75).
    """

    def __init__(
        self,
        registry_path: Optional[str | Path] = None,
        min_confidence: Optional[float] = None,
    ) -> None:
        from core.config import CONFIG
        self._registry = LocatorRegistry(
            str(registry_path or CONFIG.locator_registry_path)
        )
        self._config = HealingConfig(
            min_confidence=min_confidence or CONFIG.healing_min_confidence,
            auto_apply_silent=CONFIG.healing_auto_apply_silent,
        )
        self._orchestrator = HealerOrchestrator(
            registry=self._registry,
            config=self._config,
        )

    def heal(self, broken_locator: str, page) -> HealResult:
        """Attempt to heal `broken_locator` against `page`. Returns a HealResult."""
        return self._orchestrator.heal(broken_locator, page)

    @property
    def registry(self) -> LocatorRegistry:
        return self._registry


class FolderScanner:
    """Scan a corporate framework folder to learn its style (Option C).

    Args:
        root: Directory to scan.
        ignore_dirs: Extra directory names to skip (on top of defaults like node_modules).
        max_depth: Maximum recursion depth (None = unlimited).
    """

    def __init__(
        self,
        root: str | Path,
        ignore_dirs=None,
        max_depth=None,
    ) -> None:
        from Prism_view.shadow_coding.scanner import FolderScanner as _FS
        self._scanner = _FS(root=root, ignore_dirs=ignore_dirs, max_depth=max_depth)

    def scan(self):
        """Walk *root* and classify every supported file by PRISM role.

        Returns a ScanResult with per-role assignments and confidence levels.
        """
        return self._scanner.scan()


__all__ = [
    # High-level
    "ShadowCoder",
    "SelfHealer",
    "FolderScanner",
    # Low-level (advanced)
    "ShadowRecorder",
    "ShadowSession",
    "CodeEnhancer",
    "LocatorRegistry",
    "LocatorRecord",
    "HealerOrchestrator",
    "HealResult",
    "HealingConfig",
    "ROLES",
    "ROLE_NAMES",
    "output_path_for",
    # Scanner
    "ScannedFile",
    "RoleAssignment",
    "ScanResult",
]
