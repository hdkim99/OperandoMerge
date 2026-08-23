"""Real Tk widget-to-controller/core/export smoke for a supplied merge config."""

from __future__ import annotations

import argparse
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from operandomerge.gui import OperandoMergeApp


def main(config_path: Path, output_path: Path) -> int:
    root = tk.Tk()
    root.withdraw()
    try:
        app = OperandoMergeApp(root)
        original_open = filedialog.askopenfilename
        filedialog.askopenfilename = lambda **_kwargs: str(config_path)
        try:
            app.load_config()
        finally:
            filedialog.askopenfilename = original_open
        if not app.controller.datasets:
            raise RuntimeError("GUI did not load configured datasets")
        app.merge()
        root.update_idletasks()
        if app.controller.result is None:
            raise RuntimeError("GUI merge did not produce a result")
        original_save = filedialog.asksaveasfilename
        filedialog.asksaveasfilename = lambda **_kwargs: str(output_path)
        try:
            app.export()
        finally:
            filedialog.asksaveasfilename = original_save
        if not output_path.is_file() or output_path.stat().st_size < 1000:
            raise RuntimeError("GUI export was not written")
    finally:
        root.destroy()
    print("OperandoMerge real-widget backend smoke passed")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    raise SystemExit(main(arguments.config.resolve(), arguments.output.resolve()))
