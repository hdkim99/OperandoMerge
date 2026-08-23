"""Tk desktop workflow wired to :class:`operandomerge.service.MergeService`."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib.pyplot as plt
import pandas as pd

from operandomerge import __version__
from operandomerge.controller import GuiController, merge_config_from_fields
from operandomerge.export import plot_alignment
from operandomerge.io import inspect_columns
from operandomerge.models import (
    AlignmentConfig,
    AlignmentMethod,
    ChannelConfig,
    DatasetConfig,
    DataType,
    DelayConfig,
    QCIssue,
    TimeRepresentation,
)


class DatasetDialog(tk.Toplevel):
    """Column/time/type/alignment mapper for one input file."""

    def __init__(
        self,
        parent: tk.Misc,
        path: Path,
        callback: Callable[[DatasetConfig], None],
        existing: DatasetConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Map dataset — {path.name}")
        self.resizable(True, True)
        self.path = path
        self.callback = callback
        columns = inspect_columns(path)
        self.column_names = columns
        self.name_var = tk.StringVar(value=existing.dataset_name if existing else path.stem)
        self.time_var = tk.StringVar(
            value=existing.time_column if existing else _guess_time(columns)
        )
        self.representation_var = tk.StringVar(
            value=existing.time_representation.value if existing else _guess_representation(columns)
        )
        self.alignment_var = tk.StringVar(
            value=existing.alignment.method.value if existing else AlignmentMethod.ELAPSED.value
        )
        self.offset_var = tk.StringVar(
            value=str(existing.alignment.manual_offset_s if existing else 0.0)
        )
        self.source_event_var = tk.StringVar(
            value=""
            if existing is None or existing.alignment.source_event_time_s is None
            else str(existing.alignment.source_event_time_s)
        )
        self.target_event_var = tk.StringVar(
            value=""
            if existing is None or existing.alignment.target_event_time_s is None
            else str(existing.alignment.target_event_time_s)
        )
        delay = existing.delay if existing else DelayConfig()
        self.delay_vars = {
            "manual_s": tk.StringVar(value=str(delay.manual_s)),
            "sampling_s": tk.StringVar(value=str(delay.sampling_s)),
            "transport_s": tk.StringVar(value=str(delay.transport_s)),
            "dead_volume_s": tk.StringVar(value=str(delay.dead_volume_s)),
            "analysis_s": tk.StringVar(value=str(delay.analysis_s)),
        }
        self._build(existing)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

    def _build(self, existing: DatasetConfig | None) -> None:
        form = ttk.Frame(self, padding=12)
        form.grid(sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)
        fields = [
            ("Dataset name", ttk.Entry(form, textvariable=self.name_var)),
            (
                "Time column",
                ttk.Combobox(
                    form, textvariable=self.time_var, values=self.column_names, state="readonly"
                ),
            ),
            (
                "Time representation",
                ttk.Combobox(
                    form,
                    textvariable=self.representation_var,
                    values=[item.value for item in TimeRepresentation],
                    state="readonly",
                ),
            ),
            (
                "Alignment",
                ttk.Combobox(
                    form,
                    textvariable=self.alignment_var,
                    values=[item.value for item in AlignmentMethod],
                    state="readonly",
                ),
            ),
            ("Manual offset / s", ttk.Entry(form, textvariable=self.offset_var)),
            ("Source event time / s", ttk.Entry(form, textvariable=self.source_event_var)),
            ("Target event time / s", ttk.Entry(form, textvariable=self.target_event_var)),
        ]
        row = 0
        for label, widget in fields:
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            widget.grid(row=row, column=1, sticky="ew", pady=3)
            row += 1
        ttk.Label(form, text="Positive delays are subtracted from reported time.").grid(
            row=row, columnspan=2, sticky="w", pady=(8, 2)
        )
        row += 1
        for name, variable in self.delay_vars.items():
            ttk.Label(form, text=name.replace("_s", " delay / s").replace("_", " ").title()).grid(
                row=row, column=0, sticky="w", pady=3
            )
            ttk.Entry(form, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=3)
            row += 1
        ttk.Label(
            form, text="Channels — one per line: source_column, data_type, optional_output_name"
        ).grid(row=row, columnspan=2, sticky="w", pady=(10, 3))
        row += 1
        self.channels_text = tk.Text(form, width=60, height=10)
        self.channels_text.grid(row=row, columnspan=2, sticky="nsew")
        form.rowconfigure(row, weight=1)
        channels = (
            existing.channels
            if existing
            else tuple(
                ChannelConfig(column)
                for column in self.column_names
                if column != self.time_var.get()
            )
        )
        channel_lines = [
            f"{channel.source_column}, {channel.data_type.value}"
            + (f", {channel.output_name}" if channel.output_name else "")
            for channel in channels
        ]
        self.channels_text.insert("1.0", "\n".join(channel_lines))
        row += 1
        buttons = ttk.Frame(form)
        buttons.grid(row=row, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Apply mapping", command=self._apply).pack(side="right")

    def _apply(self) -> None:
        try:
            channels: list[ChannelConfig] = []
            for line in self.channels_text.get("1.0", "end").splitlines():
                if not line.strip():
                    continue
                parts = [part.strip() for part in line.split(",")]
                if len(parts) not in {2, 3}:
                    raise ValueError(f"Invalid channel mapping line: {line!r}")
                if parts[0] not in self.column_names:
                    raise ValueError(f"Unknown source column {parts[0]!r}")
                output_name = parts[2] or None if len(parts) == 3 else None
                channels.append(ChannelConfig(parts[0], DataType(parts[1]), output_name))
            config = DatasetConfig(
                path=self.path,
                name=self.name_var.get().strip() or self.path.stem,
                time_column=self.time_var.get(),
                time_representation=TimeRepresentation(self.representation_var.get()),
                channels=tuple(channels),
                alignment=AlignmentConfig(
                    method=AlignmentMethod(self.alignment_var.get()),
                    manual_offset_s=float(self.offset_var.get()),
                    source_event_time_s=_optional_gui_float(self.source_event_var.get()),
                    target_event_time_s=_optional_gui_float(self.target_event_var.get()),
                ),
                delay=DelayConfig(
                    **{name: float(variable.get()) for name, variable in self.delay_vars.items()}
                ),
            )
            config.validate()
        except (TypeError, ValueError) as error:
            messagebox.showerror("Invalid mapping", str(error), parent=self)
            return
        self.callback(config)
        self.destroy()


class OperandoMergeApp(ttk.Frame):
    def __init__(self, master: tk.Tk, controller: GuiController | None = None) -> None:
        super().__init__(master, padding=12)
        self.master = master
        self.controller = controller or GuiController()
        self.status = tk.StringVar(value="Add CSV/XLSX datasets to begin.")
        self.timeline_var = tk.StringVar(value="union")
        self.reference_var = tk.StringVar()
        self.origin_var = tk.StringVar()
        self.continuous_var = tk.StringVar(value="linear")
        self.stepwise_var = tk.StringVar(value="previous")
        self.tolerance_var = tk.StringVar(value="1e-9")
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.grid(sticky="nsew")
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        toolbar = ttk.Frame(self)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for text, command in [
            ("Add files", self.add_files),
            ("Edit mapping", self.edit_selected),
            ("Remove", self.remove_selected),
            ("Load config", self.load_config),
            ("Save config", self.save_config),
        ]:
            ttk.Button(toolbar, text=text, command=command).pack(side="left", padx=(0, 5))
        self.tree = ttk.Treeview(
            self,
            columns=("file", "time", "representation", "channels", "offset", "delay"),
            show="headings",
            height=10,
        )
        for column, label in [
            ("file", "Dataset / file"),
            ("time", "Time column"),
            ("representation", "Representation"),
            ("channels", "Channels"),
            ("offset", "Offset / s"),
            ("delay", "Delay / s"),
        ]:
            self.tree.heading(column, text=label)
            self.tree.column(column, width=130, stretch=True)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _event: self.edit_selected())
        settings = ttk.LabelFrame(self, text="Merge policy", padding=8)
        settings.grid(row=2, column=0, sticky="ew", pady=8)
        ttk.Label(settings, text="Timeline").pack(side="left")
        ttk.Combobox(
            settings,
            textvariable=self.timeline_var,
            values=["union", "reference"],
            width=10,
            state="readonly",
        ).pack(side="left", padx=5)
        ttk.Label(settings, text="Reference dataset").pack(side="left", padx=(8, 0))
        self.reference_combo = ttk.Combobox(
            settings, textvariable=self.reference_var, width=16, state="readonly"
        )
        self.reference_combo.pack(side="left", padx=5)
        ttk.Label(settings, text="Absolute origin").pack(side="left", padx=(8, 0))
        ttk.Entry(settings, textvariable=self.origin_var, width=22).pack(side="left", padx=5)
        ttk.Label(settings, text="Continuous").pack(side="left", padx=(8, 0))
        ttk.Combobox(
            settings,
            textvariable=self.continuous_var,
            values=["linear", "nearest", "none"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=5)
        ttk.Label(settings, text="Stepwise").pack(side="left", padx=(8, 0))
        ttk.Combobox(
            settings,
            textvariable=self.stepwise_var,
            values=["previous", "none"],
            width=9,
            state="readonly",
        ).pack(side="left", padx=5)
        ttk.Label(settings, text="Exact tolerance / s").pack(side="left", padx=(8, 0))
        ttk.Entry(settings, textvariable=self.tolerance_var, width=8).pack(side="left", padx=5)
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew")
        ttk.Button(actions, text="Merge", command=self.merge).pack(side="left")
        ttk.Button(actions, text="Preview alignment", command=self.preview).pack(
            side="left", padx=5
        )
        ttk.Button(actions, text="Export Excel", command=self.export).pack(side="left")
        ttk.Button(actions, text="Inspect result", command=self.inspect_result).pack(
            side="left", padx=5
        )
        ttk.Label(actions, textvariable=self.status).pack(side="right")

    def refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        names = [config.dataset_name for config in self.controller.datasets]
        for index, config in enumerate(self.controller.datasets):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    f"{config.dataset_name} / {config.path.name}",
                    config.time_column,
                    config.time_representation.value,
                    len(config.channels),
                    config.alignment.effective_offset_s(),
                    config.delay.total_s,
                ),
            )
        self.reference_combo.configure(values=names)
        if names and self.reference_var.get() not in names:
            self.reference_var.set(names[0])

    def add_files(self) -> None:
        names = filedialog.askopenfilenames(filetypes=[("Tabular data", "*.csv *.xlsx *.xlsm")])
        for name in names:
            dialog = DatasetDialog(self, Path(name), self._append_dataset)
            self.wait_window(dialog)

    def _append_dataset(self, config: DatasetConfig) -> None:
        if config.dataset_name in {item.dataset_name for item in self.controller.datasets}:
            messagebox.showerror("Duplicate name", "Dataset names must be unique.", parent=self)
            return
        self.controller.datasets.append(config)
        self.controller.result = None
        self.refresh()

    def edit_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Edit mapping", "Select a dataset first.", parent=self)
            return
        index = int(selection[0])
        existing = self.controller.datasets[index]
        DatasetDialog(
            self, existing.path, lambda config: self._replace_dataset(index, config), existing
        )

    def _replace_dataset(self, index: int, config: DatasetConfig) -> None:
        self.controller.datasets[index] = config
        self.controller.result = None
        self.refresh()

    def remove_selected(self) -> None:
        selection = self.tree.selection()
        if selection:
            self.controller.datasets.pop(int(selection[0]))
            self.controller.result = None
            self.refresh()

    def _sync_merge_config(self) -> None:
        self.controller.merge_config = merge_config_from_fields(
            self.timeline_var.get(),
            self.reference_var.get(),
            self.origin_var.get(),
            self.continuous_var.get(),
            self.stepwise_var.get(),
            self.tolerance_var.get(),
        )

    def merge(self) -> None:
        try:
            self._sync_merge_config()
            result = self.controller.run_merge()
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            messagebox.showerror("Merge failed", str(error), parent=self)
            return
        errors = sum(issue.severity == "error" for issue in result.qc)
        warnings = sum(issue.severity == "warning" for issue in result.qc)
        self.status.set(f"{len(result.merged)} rows · QC {errors} errors / {warnings} warnings")

    def preview(self) -> None:
        if self.controller.result is None:
            self.merge()
        if self.controller.result is not None:
            plot_alignment(self.controller.result)
            plt.show(block=False)

    def export(self) -> None:
        if self.controller.result is None:
            self.merge()
        if self.controller.result is None:
            return
        destination = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")]
        )
        if destination:
            self.controller.export(Path(destination))
            self.status.set(f"Exported {destination}")

    def inspect_result(self) -> None:
        if self.controller.result is None:
            self.merge()
        if self.controller.result is not None:
            ResultDialog(
                self,
                self.controller.result.merged,
                self.controller.result.provenance,
                self.controller.result.qc,
            )

    def load_config(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON config", "*.json")])
        if not path:
            return
        try:
            self.controller.load(Path(path))
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            messagebox.showerror("Load failed", str(error), parent=self)
            return
        self.timeline_var.set(self.controller.merge_config.timeline)
        self.reference_var.set(self.controller.merge_config.reference_dataset or "")
        self.origin_var.set(self.controller.merge_config.experiment_origin or "")
        self.continuous_var.set(self.controller.merge_config.continuous_method)
        self.stepwise_var.set(self.controller.merge_config.stepwise_method)
        self.tolerance_var.set(str(self.controller.merge_config.exact_tolerance_s))
        self.refresh()

    def save_config(self) -> None:
        try:
            self._sync_merge_config()
        except ValueError as error:
            messagebox.showerror("Invalid merge policy", str(error), parent=self)
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON config", "*.json")]
        )
        if path:
            self.controller.save(Path(path))
            self.status.set(f"Saved configuration {path}")


def _guess_time(columns: list[str]) -> str:
    for column in columns:
        if column.lower() in {"time", "timestamp", "datetime", "elapsed_s", "elapsed_time"}:
            return column
    return columns[0] if columns else ""


def _guess_representation(columns: list[str]) -> str:
    guessed = _guess_time(columns).lower()
    if "min" in guessed:
        return TimeRepresentation.ELAPSED_MINUTES.value
    if "stamp" in guessed or "date" in guessed:
        return TimeRepresentation.ABSOLUTE.value
    return TimeRepresentation.ELAPSED_SECONDS.value


def _optional_gui_float(text: str) -> float | None:
    return None if not text.strip() else float(text)


class ResultDialog(tk.Toplevel):
    """Inspect merged values, provenance, and QC without recomputation."""

    def __init__(
        self,
        parent: tk.Misc,
        merged: pd.DataFrame,
        provenance: pd.DataFrame,
        qc: list[QCIssue],
    ) -> None:
        super().__init__(parent)
        self.title("OperandoMerge result")
        self.geometry("1000x560")
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self._add_frame(notebook, "Merged", merged)
        self._add_frame(notebook, "Provenance", provenance)
        qc_frame = pd.DataFrame([issue.as_dict() for issue in qc])
        self._add_frame(notebook, "QC", qc_frame)

    @staticmethod
    def _add_frame(notebook: ttk.Notebook, title: str, frame: pd.DataFrame) -> None:
        container = ttk.Frame(notebook)
        notebook.add(container, text=title)
        tree = ttk.Treeview(container, columns=list(frame.columns), show="headings")
        for column in frame.columns:
            tree.heading(str(column), text=str(column))
            tree.column(str(column), width=130, stretch=True)
        for row in frame.head(500).itertuples(index=False, name=None):
            tree.insert("", "end", values=["" if pd.isna(value) else value for value in row])
        vertical = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        horizontal = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)


def create_app() -> tuple[tk.Tk, OperandoMergeApp]:
    root = tk.Tk()
    root.title(f"OperandoMerge {__version__}")
    root.geometry("1320x560")
    return root, OperandoMergeApp(root)


def main() -> None:
    root, _app = create_app()
    root.mainloop()


if __name__ == "__main__":
    main()
