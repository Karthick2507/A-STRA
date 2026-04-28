"""ASTRA Framework - Main entry point."""
from __future__ import annotations

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="ASTRA - Autonomous A* Search Based Test & Reporting Architecture",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py preflight\n"
            "  python main.py ui\n"
            "  python main.py ui --skip-preflight\n"
            "  python main.py api --skip-schema-gen\n"
            "  python main.py e2e --skip-preflight --skip-ui\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    # preflight command
    subparsers.add_parser("preflight", help="Run preflight health checks")

    # ui command
    ui_parser = subparsers.add_parser("ui", help="Run UI test pipeline")
    ui_parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight health check")
    ui_parser.add_argument("--skip-schema-gen", action="store_true", help="Skip code generation, run existing tests")

    # api command
    api_parser = subparsers.add_parser("api", help="Run API test pipeline")
    api_parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight health check")
    api_parser.add_argument("--skip-schema-gen", action="store_true", help="Skip code generation, run existing tests")

    # e2e command
    e2e_parser = subparsers.add_parser("e2e", help="Run full E2E pipeline (preflight + UI + API + report)")
    e2e_parser.add_argument("--skip-preflight", action="store_true", help="Skip preflight health check")
    e2e_parser.add_argument("--skip-ui",        action="store_true", help="Skip UI test phase")
    e2e_parser.add_argument("--skip-api",       action="store_true", help="Skip API test phase")
    e2e_parser.add_argument("--skip-schema-gen",action="store_true", help="Skip code generation")

    # No subcommand → print help and exit cleanly (code 0)
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.command == "preflight":
        from preflight.health_check_orchestrator import run_health_check
        run_health_check()

    elif args.command == "ui":
        from runners.ui.ui_test_runner import UiTestRunner
        UiTestRunner(
            skip_preflight=args.skip_preflight,
            skip_schema_gen=args.skip_schema_gen,
        ).run()

    elif args.command == "api":
        from runners.api.api_test_runner import ApiTestRunner
        ApiTestRunner(
            skip_preflight=args.skip_preflight,
            skip_schema_gen=args.skip_schema_gen,
        ).run()

    elif args.command == "e2e":
        from runners.e2e.e2e_test_runner import E2ETestRunner
        E2ETestRunner(
            skip_preflight=args.skip_preflight,
            skip_ui=args.skip_ui,
            skip_api=args.skip_api,
            skip_schema_gen=args.skip_schema_gen,
        ).run()

    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
