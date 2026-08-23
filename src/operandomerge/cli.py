"""Command-line interface for inspectable, reproducible merges."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import matplotlib.pyplot as plt

from operandomerge import __version__
from operandomerge.config import load_config
from operandomerge.export import export_csv_bundle, export_excel, plot_alignment
from operandomerge.io import inspect_columns
from operandomerge.service import MergeService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="operandomerge", description=__doc__)
    parser.add_argument("--version", action="version", version=f"OperandoMerge {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="List columns in a CSV/XLSX file")
    inspect_parser.add_argument("input", type=Path)
    inspect_parser.add_argument("--sheet", default=0)

    merge_parser = subparsers.add_parser("merge", help="Run a merge from a JSON configuration")
    merge_parser.add_argument("config", type=Path)
    output = merge_parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--excel", type=Path, help="Write a multi-sheet XLSX report")
    output.add_argument("--csv-dir", type=Path, help="Write a CSV report bundle")
    merge_parser.add_argument("--plot", type=Path, help="Write an alignment-preview PNG/SVG/PDF")
    merge_parser.add_argument("--fail-on-qc-error", action="store_true")

    subparsers.add_parser("gui", help="Launch the desktop GUI")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            columns = inspect_columns(args.input, _sheet_value(args.sheet))
            print(json.dumps(columns, indent=2))
            return 0
        if args.command == "gui":
            from operandomerge.gui import main as gui_main

            gui_main()
            return 0
        datasets, merge_config = load_config(args.config)
        result = MergeService().run(datasets, merge_config)
        if args.excel:
            export_excel(result, args.excel)
            destination = args.excel
        else:
            export_csv_bundle(result, args.csv_dir)
            destination = args.csv_dir
        if args.plot:
            figure = plot_alignment(result, args.plot)
            plt.close(figure)
        errors = sum(issue.severity == "error" for issue in result.qc)
        warnings = sum(issue.severity == "warning" for issue in result.qc)
        print(
            f"Merged {len(datasets)} dataset(s), {len(result.merged)} timeline row(s); "
            f"QC: {errors} error(s), {warnings} warning(s); output: {destination}"
        )
        return 2 if args.fail_on_qc_error and errors else 0
    except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
        print(f"operandomerge: error: {error}", file=sys.stderr)
        return 2


def _sheet_value(value: object) -> str | int | None:
    if value is None:
        return None
    text = str(value)
    return int(text) if text.isdigit() else text


if __name__ == "__main__":
    raise SystemExit(main())
