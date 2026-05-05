"""
PRISM CLI entry point.

Subcommands
───────────
    preflight      Validate config, check imports, ping target URLs
    ui             Run UI tests (delegates to pytest UI/tests)
    api            Run API tests (delegates to pytest API/tests)
    e2e            Run UI + API together
    shadow         Launch shadow coding (playwright codegen) and enhance output
    train          Train the self-healing ML model from collected JSONL data
    registry       Inspect locator registry stats / export

Examples
────────
    python main.py preflight
    python main.py ui --env=stg --browser=chromium -m smoke
    python main.py shadow --url https://mrm.stg.freewheel.tv/
    python main.py train
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
    print(f"  api_url:  {Config.api_url or '(not set)'}")
    print(f"  browser:  {Config.browser} (headless={Config.headless})")
    print(f"  healing:  enabled={Config.healing_enabled} "
          f"min_conf={Config.healing_min_confidence}")

    # Check critical imports
    print("Checking imports…")
    issues = []
    for pkg in ("playwright", "pytest", "httpx", "numpy", "sklearn", "joblib"):
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


def cmd_ui(args: argparse.Namespace) -> int:
    import pytest
    pytest_args = ["UI/tests", "-q", f"--browser={args.browser or Config.browser}"]
    if args.marker:
        pytest_args += ["-m", args.marker]
    if args.parallel:
        pytest_args += ["-n", str(args.parallel)]
    return pytest.main(pytest_args)


def cmd_api(args: argparse.Namespace) -> int:
    import pytest
    pytest_args = ["API/tests", "-q"]
    if args.marker:
        pytest_args += ["-m", args.marker]
    if args.parallel:
        pytest_args += ["-n", str(args.parallel)]
    return pytest.main(pytest_args)


def cmd_e2e(args: argparse.Namespace) -> int:
    import pytest
    pytest_args = ["UI/tests", "API/tests", "-q",
                   f"--browser={args.browser or Config.browser}"]
    if args.marker:
        pytest_args += ["-m", args.marker]
    return pytest.main(pytest_args)


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
    from Prism_view.shadow_coding.slate_learner import SlateLearner
    learner = SlateLearner(
        profile_path   = Config.style_profile_path,
        classifier_dir = "Prism_view/shadow_coding/ml",
    )

    # Multi-slate mode: learn all roles defined in config
    if not args.slate and Config.slates:
        try:
            results = learner.learn_all(
                Config.slates,
                train_classifier=Config.train_classifier_on_learn,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"Learn failed: {exc}")
            return 1
        if not results:
            print("No slate files found. Add slate files under the paths defined in config.json slates block.")
            return 1
        print(f"Style learned from {len(results)} role(s):")
        for role, profile in results.items():
            print(f"  [{role}] {profile.source_language} | base={profile.base_class} | method={profile.method_style}")
        print(f"  profile saved → {Config.style_profile_path}")
        return 0

    # Single-slate mode (legacy): --slate <path> or config.slate_file
    slate = args.slate or Config.slate_file
    try:
        profile = learner.learn(slate, train_classifier=Config.train_classifier_on_learn)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Learn failed: {exc}")
        return 1
    print(f"Style learned from: {slate}")
    print(f"  language : {profile.source_language}")
    print(f"  base class: {profile.base_class}")
    print(f"  method style: {profile.method_style}")
    print(f"  logging: {profile.logging_call} ({profile.logging_format})")
    print(f"  type hints: {profile.has_type_hints}")
    print(f"  try-except: {profile.has_try_except}")
    print(f"  profile saved → {Config.style_profile_path}")
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
    # Shared parent so --env is accepted both BEFORE and AFTER the subcommand:
    #   python main.py --env=staging ui ...   ← before subcommand
    #   python main.py ui --env=staging ...   ← after subcommand (most natural)
    _common = argparse.ArgumentParser(add_help=False)
    _common.add_argument(
        "--env",
        help="Environment override (dev|staging|prod). "
             "Also accepted via ASTRA_ENV env var or config.json default_env.",
    )

    p = argparse.ArgumentParser(
        prog="astra-v2",
        description="PRISM automation framework",
        parents=[_common],
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("preflight", parents=[_common], help="Validate config + imports")

    ui = sub.add_parser("ui", parents=[_common], help="Run UI tests")
    ui.add_argument("--browser", choices=["chromium", "firefox", "webkit"])
    ui.add_argument("-m", "--marker", help="pytest marker filter")
    ui.add_argument("-n", "--parallel", help="parallel workers (e.g. auto, 4)")

    api = sub.add_parser("api", parents=[_common], help="Run API tests")
    api.add_argument("-m", "--marker", help="pytest marker filter")
    api.add_argument("-n", "--parallel", help="parallel workers")

    e2e = sub.add_parser("e2e", parents=[_common], help="Run UI + API tests")
    e2e.add_argument("--browser", choices=["chromium", "firefox", "webkit"])
    e2e.add_argument("-m", "--marker", help="pytest marker filter")

    sh = sub.add_parser("shadow", parents=[_common], help="Launch playwright codegen + enhance to POM")
    sh.add_argument("--url", required=True, help="Start URL")

    tr = sub.add_parser("train", parents=[_common], help="Train self-healing ML model")
    tr.add_argument("--min-samples", type=int, default=30)

    rg = sub.add_parser("registry", parents=[_common], help="Inspect locator registry")
    rg.add_argument("--export", help="Export registry to JSON file at this path")

    lrn = sub.add_parser("learn", parents=[_common],
                         help="Learn corporate style from slate file → update style_profile.json")
    lrn.add_argument("--slate", default=None,
                     help="Path to corporate slate file (.py/.ts/.js/.java). "
                          "Defaults to config slate_file.")

    return p


def main() -> int:
    if len(sys.argv) == 1:
        build_parser().print_help()
        return 0

    parser = build_parser()
    args   = parser.parse_args()

    dispatch = {
        "preflight": cmd_preflight,
        "ui":        cmd_ui,
        "api":       cmd_api,
        "e2e":       cmd_e2e,
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
