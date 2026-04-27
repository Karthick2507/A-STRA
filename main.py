"""ASTRA Framework - Main entry point."""
from __future__ import annotations

import argparse
import sys
from utils.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="ASTRA - Autonomous A* Search Based Test & Reporting Architecture"
    )
    subparsers = parser.add_subparsers(dest="command")

    # preflight command
    preflight_parser = subparsers.add_parser("preflight", help="Run preflight health checks")

    # ui command
    ui_parser = subparsers.add_parser("ui", help="Run UI test pipeline")
    ui_parser.add_argument("--skip-preflight", action="store_true")
    ui_parser.add_argument("--skip-schema-gen", action="store_true")

    # api command
    api_parser = subparsers.add_parser("api", help="Run API test pipeline")
    api_parser.add_argument("--skip-preflight", action="store_true")
    api_parser.add_argument("--skip-schema-gen", action="store_true")

    # e2e command
    e2e_parser = subparsers.add_parser("e2e", help="Run full E2E pipeline")
    e2e_parser.add_argument("--skip-preflight", action="store_true")
    e2e_parser.add_argument("--skip-ui", action="store_true")
    e2e_parser.add_argument("--skip-api", action="store_true")
    e2e_parser.add_argument("--skip-schema-gen", action="store_true")

    args = parser.parse_args()

    if args.command == "preflight":
        from preflight.health_check_orchestrator import run_health_check
        run_health_check()

    elif args.command == "ui":
        from runners.ui.ui_test_runner import UiTestRunner
        runner = UiTestRunner(
            skip_preflight=args.skip_preflight,
            skip_schema_gen=args.skip_schema_gen,
        )
        runner.run()

    elif args.command == "api":
        from runners.api.api_test_runner import ApiTestRunner
        runner = ApiTestRunner(
            skip_preflight=args.skip_preflight,
            skip_schema_gen=args.skip_schema_gen,
        )
        runner.run()

    elif args.command == "e2e":
        from runners.e2e.e2e_test_runner import E2ETestRunner
        runner = E2ETestRunner(
            skip_preflight=args.skip_preflight,
            skip_ui=args.skip_ui,
            skip_api=args.skip_api,
            skip_schema_gen=args.skip_schema_gen,
        )
        runner.run()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
