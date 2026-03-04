"""CLI interface: argparse with fetch/analyze/visualize/compare/export/stats commands."""

import argparse
import logging
import sys

from config.settings import get_regions
from maps_analyser.pipeline import (
    run_fetch, run_analyze, run_visualize, run_compare,
    run_export, run_estimate, run_stats, run_full_pipeline,
)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="maps_analyser",
        description="Google Maps Store Distribution Analyzer for Chennai neighborhoods",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch places from Google Maps API")
    p_fetch.add_argument("region", nargs="?", help="Region key (e.g. t_nagar)")
    p_fetch.add_argument("--all", action="store_true", help="Fetch all regions")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run analytics on stored data")
    p_analyze.add_argument("region", help="Region key")

    # visualize
    p_vis = sub.add_parser("visualize", help="Generate charts and maps")
    p_vis.add_argument("region", help="Region key")

    # compare
    p_comp = sub.add_parser("compare", help="Compare categories across regions")
    p_comp.add_argument("regions", nargs="+", help="Region keys to compare")

    # export
    p_export = sub.add_parser("export", help="Export region data to CSV")
    p_export.add_argument("region", help="Region key")

    # estimate
    p_est = sub.add_parser("estimate", help="Dry run: show API call estimate")
    p_est.add_argument("region", help="Region key")

    # stats
    sub.add_parser("stats", help="Show database summary")

    # run (full pipeline)
    p_run = sub.add_parser("run", help="Full pipeline: fetch → analyze → visualize")
    p_run.add_argument("--all", action="store_true", help="Run for all regions")
    p_run.add_argument("regions", nargs="*", help="Region keys (or use --all)")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    regions = get_regions()

    try:
        if args.command == "fetch":
            if args.all:
                for key in regions:
                    count = run_fetch(key)
                    print(f"{key}: {count} places stored")
            elif args.region:
                count = run_fetch(args.region)
                print(f"{args.region}: {count} places stored")
            else:
                print("Specify a region or use --all")
                return 1

        elif args.command == "analyze":
            run_analyze(args.region)

        elif args.command == "visualize":
            paths = run_visualize(args.region)
            print(f"Generated {len(paths)} files:")
            for p in paths:
                print(f"  {p}")

        elif args.command == "compare":
            path = run_compare(args.regions)
            if path:
                print(f"Comparison chart: {path}")

        elif args.command == "export":
            run_export(args.region)

        elif args.command == "estimate":
            run_estimate(args.region)

        elif args.command == "stats":
            run_stats()

        elif args.command == "run":
            keys = list(regions.keys()) if args.all else (args.regions or None)
            if not keys:
                print("Specify regions or use --all")
                return 1
            run_full_pipeline(keys)

    except PermissionError as e:
        print(f"ERROR: {e}")
        return 1
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1

    return 0
