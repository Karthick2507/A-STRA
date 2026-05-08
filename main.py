"""
PRISM CLI entry point.

Subcommands
───────────
    preflight   Validate config + check imports
    shadow      Launch shadow coding (playwright codegen) and enhance output
    learn       Learn corporate style — placeholder until folder scanner lands (Batch 4)
    train       Train the self-healing ML model from collected JSONL data
    registry    Inspect locator registry stats / export

Examples
────────
    python main.py preflight
    python main.py shadow --url https://yourapp.stg.com
    python main.py train
    python main.py registry --export Data/locators/dump.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make PRISM root importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config.config_loader import CONFIG as Config


def cmd_preflight(args: argparse.Namespace) -> int:
    print(f"PRISM preflight — env={Config.env}")
    print(f"  base_url: {Config.base_url or '(not set)'}")
    print(f"  browser:  {Config.browser} (headless={Config.headless})")
    print(f"  healing:  enabled={Config.healing_enabled} "
          f"min_conf={Config.healing_min_confidence}")

    print("Checking imports…")
    issues = []
    for pkg in ("playwright", "pytest", "numpy", "sklearn", "joblib"):
        try:
            __import__(pkg)
            print(f"  ✓ {pkg}")
        except ImportError:
            print(f"  ✗ {pkg}  ← MISSING")
            issues.append(pkg)

    if issues:
        print(f"\nMissing packages: {', '.join(issues)}")
        print("Run: pip install -r requirements.txt")
        return 1

    print("\nPreflight OK.")
    return 0


def cmd_shadow(args: argparse.Namespace) -> int:
    from Prism_view.shadow_coding import ShadowRecorder, CodeEnhancer

    rec = ShadowRecorder(output_dir=Config.shadow_session_dir)
    sess = rec.start(url=args.url)
    print(f"Shadow recording started: {sess.session_id}")
    print("Interact with the browser. Close it when finished.")
    final = rec.stop(timeout=600)
    print(f"Raw codegen output: {final.raw_file}")

    enhancer = CodeEnhancer(session_id=final.session_id)
    files = enhancer.enhance_file(final.raw_file)
    print(f"Generated UI page object : {files['ui']}")
    print(f"Generated test data      : {files['data']}")
    print(f"Generated base page      : {files['base_page']}")
    for key in ("locators", "controller", "api_test"):
        if key in files:
            print(f"Generated {key:<15}: {files[key]}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from Prism_view.self_healing.ml import HealerTrainer
    trainer = HealerTrainer()
    try:
        result = trainer.train(min_samples=args.min_samples)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"Training skipped: {exc}")
        return 1
    print(f"Training complete:")
    print(f"  accuracy={result.accuracy:.3f}  auc={result.roc_auc:.3f}")
    print(f"  pkl:  {result.pkl_path}")
    print(f"  onnx: {result.onnx_path}")
    return 0


def cmd_learn(args: argparse.Namespace) -> int:
    """Learn corporate style by scanning a folder (or a single file)."""
    from Prism_view.shadow_coding.scanner import FolderScanner
    from Prism_view.shadow_coding.scanner.interactive_cli import review_scan
    from Prism_view.shadow_coding.scanner.file_classifier import classify_file
    from Prism_view.shadow_coding.scanner.scan_result import RoleAssignment, ScanResult
    from Prism_view.shadow_coding.slate_learner import SlateLearner
    from pathlib import Path as _P

    if not args.scan and not args.slate:
        print("Usage:")
        print("  prism learn --scan /path/to/your/framework")
        print("  prism learn --slate /path/to/single/file.py")
        return 1

    if args.scan:
        target = _P(args.scan)
        if not target.is_dir():
            print(f"--scan target is not a directory: {target}")
            return 1
        result = FolderScanner(target).scan()
    else:
        target = _P(args.slate)
        if not target.is_file():
            print(f"--slate target is not a file: {target}")
            return 1
        scanned = classify_file(target)
        if scanned is None:
            print(f"Unsupported file type: {target.suffix}")
            return 1
        result = ScanResult(root=target.parent, total_files_scanned=1)
        result.assignments[scanned.role] = RoleAssignment(role=scanned.role, files=[scanned])
        result.languages_found = [scanned.language] if scanned.language != "data" else []

    result = review_scan(result, non_interactive=args.yes)

    if not result.assignments:
        print("No roles to learn — aborting.")
        return 1

    learner = SlateLearner()
    role_profiles = learner.learn_from_scan(
        result, train_classifier=Config.train_classifier_on_learn
    )
    print(f"\n✓ style_profile.json updated — roles: {sorted(role_profiles)}")
    return 0


def cmd_registry(args: argparse.Namespace) -> int:
    from Prism_view.self_healing import LocatorRegistry
    reg = LocatorRegistry(Config.locator_registry_path)
    stats = reg.stats()
    print(f"Locator registry @ {Config.locator_registry_path}")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if args.export:
        path = reg.export_json(args.export)
        print(f"Exported → {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument(
        "--env",
        help="Environment override (dev|staging|prod). Also accepted via "
             "ASTRA_ENV env var or default_env in prism_config.json.",
    )

    p = argparse.ArgumentParser(
        prog="prism",
        description="PRISM — Playwright Record, Intelligent Self-healing & Multi-language ML automation framework",
        parents=[_common],
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("preflight", parents=[_common], help="Validate config + imports")

    sh = sub.add_parser("shadow", parents=[_common], help="Launch playwright codegen + enhance to POM")
    sh.add_argument("--url", required=True, help="Start URL")

    tr = sub.add_parser("train", parents=[_common], help="Train self-healing ML model")
    tr.add_argument("--min-samples", type=int, default=30)

    rg = sub.add_parser("registry", parents=[_common], help="Inspect locator registry")
    rg.add_argument("--export", help="Export registry to JSON file at this path")

    lrn = sub.add_parser("learn", parents=[_common], help="Learn corporate style from a folder or single file")
    lrn.add_argument("--scan",  default=None, help="Path to your framework folder (recursive scan).")
    lrn.add_argument("--slate", default=None, help="Path to a single file (treated as a 1-file scan).")
    lrn.add_argument("--yes", "-y", action="store_true",
                     help="Non-interactive: auto-accept all role assignments.")

    return p


def main() -> int:
    if len(sys.argv) == 1:
        build_parser().print_help()
        return 0

    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "preflight": cmd_preflight,
        "shadow":    cmd_shadow,
        "train":     cmd_train,
        "registry":  cmd_registry,
        "learn":     cmd_learn,
    }
    fn = dispatch.get(args.cmd)
    if fn is None:
        parser.print_help()
        return 0
    return fn(args)


if __name__ == "__main__":
    sys.exit(main())
