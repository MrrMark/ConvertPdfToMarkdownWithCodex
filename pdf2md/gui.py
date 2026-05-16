from __future__ import annotations

import argparse
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import webbrowser

from pdf2md.gui_runner import (
    GuiBatchProgress,
    GuiConversionOptions,
    GuiConversionRequest,
    GuiConversionSummary,
    GuiDocumentSummary,
    GuiDiagnosticError,
    GuiDiagnosticReport,
    check_gui_runtime,
    format_gui_summary,
    run_gui_conversion,
    validate_gui_request,
)
from pdf2md.gui_state import (
    GuiRecentState,
    GuiStateStore,
    RecentPathKind,
    ResultOpenTarget,
    first_existing_path,
    gui_batch_progress_snapshot,
    gui_document_open_target,
    remember_gui_path,
)
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


def gui_user_guide_path() -> Path:
    """Return the local GUI user guide path for source checkout/editable installs."""
    return Path(__file__).resolve().parents[1] / "docs" / "GUI_USER_GUIDE.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2md-gui",
        description="Launch the minimal desktop GUI wrapper for pdf2md.",
    )
    return parser


class Pdf2MdGuiApp:
    def __init__(self, root) -> None:  # noqa: ANN001
        import tkinter as tk

        self.root = root
        self.root.title("pdf2md")
        self.root.minsize(760, 560)
        self.queue: Queue[tuple[str, object]] = Queue()
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.last_summary: GuiConversionSummary | None = None
        self.result_documents: dict[str, GuiDocumentSummary] = {}
        self.state_store = GuiStateStore()
        self.recent_state = self.state_store.load()

        self.input_mode = tk.StringVar(value="file")
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.pages = tk.StringVar()
        self.password = tk.StringVar()
        self.image_mode = tk.StringVar(value=ImageMode.REFERENCED.value)
        self.table_mode = tk.StringVar(value=TableMode.AUTO.value)
        self.rag_table_output = tk.StringVar(value=RagTableOutputMode.NONE.value)
        self.domain_adapter = tk.StringVar(value=DomainAdapterMode.NONE.value)
        self.ocr_lang = tk.StringVar(value="eng")
        self.skip_existing = tk.BooleanVar(value=False)
        self.confidential_safe_mode = tk.BooleanVar(value=False)
        self.force_ocr = tk.BooleanVar(value=False)
        self.keep_page_markers = tk.BooleanVar(value=False)
        self.remove_header_footer = tk.BooleanVar(value=False)
        self.dedupe_images = tk.BooleanVar(value=False)
        self.repair_hyphenation = tk.BooleanVar(value=False)
        self.figure_crop_fallback = tk.BooleanVar(value=False)

        self._restore_recent_paths()
        self._build_ui()
        self.root.after(100, self._poll_queue)

    def _build_ui(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        mode_frame = ttk.LabelFrame(frame, text="Input")
        mode_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        mode_frame.columnconfigure(1, weight=1)
        ttk.Radiobutton(mode_frame, text="PDF file", variable=self.input_mode, value="file").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(mode_frame, text="PDF folder", variable=self.input_mode, value="folder").grid(row=0, column=1, sticky="w")
        ttk.Entry(mode_frame, textvariable=self.input_path).grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(mode_frame, text="Browse", command=self._browse_input).grid(row=1, column=2, pady=4)

        ttk.Label(frame, text="Output folder").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=4)
        ttk.Button(frame, text="Browse", command=self._browse_output).grid(row=1, column=2, pady=4)

        options = ttk.LabelFrame(frame, text="Options")
        options.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        for col in range(4):
            options.columnconfigure(col, weight=1)

        self._add_labeled_entry(options, "Pages", self.pages, 0, 0)
        self._add_labeled_entry(options, "Password", self.password, 0, 2, show="*")
        self._add_labeled_entry(options, "OCR lang", self.ocr_lang, 1, 0)
        self._add_labeled_combo(options, "Image", self.image_mode, [mode.value for mode in ImageMode], 1, 2)
        self._add_labeled_combo(options, "Table", self.table_mode, [mode.value for mode in TableMode], 2, 0)
        self._add_labeled_combo(options, "RAG tables", self.rag_table_output, [mode.value for mode in RagTableOutputMode], 2, 2)
        self._add_labeled_combo(options, "Domain", self.domain_adapter, [mode.value for mode in DomainAdapterMode], 3, 0)

        flags = ttk.LabelFrame(frame, text="Flags")
        flags.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in range(3):
            flags.columnconfigure(col, weight=1)
        checkboxes = [
            ("Skip existing", self.skip_existing),
            ("Confidential safe", self.confidential_safe_mode),
            ("Force OCR", self.force_ocr),
            ("Page markers", self.keep_page_markers),
            ("Remove header/footer", self.remove_header_footer),
            ("Dedupe images", self.dedupe_images),
            ("Repair hyphenation", self.repair_hyphenation),
            ("Figure crop fallback", self.figure_crop_fallback),
        ]
        for idx, (label, variable) in enumerate(checkboxes):
            ttk.Checkbutton(flags, text=label, variable=variable).grid(row=idx // 3, column=idx % 3, sticky="w")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.start_button = ttk.Button(button_frame, text="Start conversion", command=self._start_conversion)
        self.start_button.pack(side=tk.LEFT)
        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self._request_cancel, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=(8, 0))
        self.open_output_button = ttk.Button(button_frame, text="Open output folder", command=self._open_output, state=tk.DISABLED)
        self.open_output_button.pack(side=tk.LEFT, padx=(8, 0))
        self.help_button = ttk.Button(button_frame, text="Help", command=self._open_help)
        self.help_button.pack(side=tk.LEFT, padx=(8, 0))
        self.clear_recent_button = ttk.Button(button_frame, text="Clear recent", command=self._clear_recent)
        self.clear_recent_button.pack(side=tk.LEFT, padx=(8, 0))

        progress_frame = ttk.Frame(frame)
        progress_frame.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        progress_frame.columnconfigure(1, weight=1)
        ttk.Label(progress_frame, textvariable=self.status_text).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            maximum=100,
            variable=self.progress_value,
        )
        self.progress_bar.grid(row=0, column=1, sticky="ew")

        results = ttk.LabelFrame(frame, text="Results")
        results.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.result_tree = ttk.Treeview(
            results,
            columns=("document", "status", "warnings", "retry", "markdown", "report"),
            show="headings",
            height=5,
        )
        self.result_tree.heading("document", text="Document")
        self.result_tree.heading("status", text="Status")
        self.result_tree.heading("warnings", text="Warnings")
        self.result_tree.heading("retry", text="Retry")
        self.result_tree.heading("markdown", text="Markdown")
        self.result_tree.heading("report", text="Report")
        self.result_tree.column("document", width=150, anchor="w")
        self.result_tree.column("status", width=110, anchor="w")
        self.result_tree.column("warnings", width=90, anchor="center")
        self.result_tree.column("retry", width=70, anchor="center")
        self.result_tree.column("markdown", width=170, anchor="w")
        self.result_tree.column("report", width=170, anchor="w")
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        self.result_tree.bind("<<TreeviewSelect>>", lambda event: self._update_result_action_buttons())

        result_actions = ttk.Frame(results)
        result_actions.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.open_markdown_button = ttk.Button(
            result_actions,
            text="Open Markdown",
            command=lambda: self._open_selected_result("markdown"),
            state=tk.DISABLED,
        )
        self.open_markdown_button.pack(side=tk.LEFT)
        self.open_report_button = ttk.Button(
            result_actions,
            text="Open Report",
            command=lambda: self._open_selected_result("report"),
            state=tk.DISABLED,
        )
        self.open_report_button.pack(side=tk.LEFT, padx=(8, 0))
        self.open_manifest_button = ttk.Button(
            result_actions,
            text="Open Manifest",
            command=lambda: self._open_selected_result("manifest"),
            state=tk.DISABLED,
        )
        self.open_manifest_button.pack(side=tk.LEFT, padx=(8, 0))
        self.open_assets_button = ttk.Button(
            result_actions,
            text="Open Assets",
            command=lambda: self._open_selected_result("assets"),
            state=tk.DISABLED,
        )
        self.open_assets_button.pack(side=tk.LEFT, padx=(8, 0))

        self.log_text = tk.Text(frame, height=9, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=7, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(6, weight=1)
        frame.rowconfigure(7, weight=1)

    def _add_labeled_entry(self, parent, label: str, variable, row: int, col: int, show: str | None = None) -> None:  # noqa: ANN001
        from tkinter import ttk

        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=3)
        ttk.Entry(parent, textvariable=variable, show=show).grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=3)

    def _add_labeled_combo(self, parent, label: str, variable, values: list[str], row: int, col: int) -> None:  # noqa: ANN001
        from tkinter import ttk

        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 4), pady=3)
        ttk.Combobox(parent, textvariable=variable, values=values, state="readonly").grid(
            row=row,
            column=col + 1,
            sticky="ew",
            padx=(0, 8),
            pady=3,
        )

    def _restore_recent_paths(self) -> None:
        recent_file = first_existing_path(self.recent_state.recent_input_files)
        recent_folder = first_existing_path(self.recent_state.recent_input_folders)
        if recent_file is not None:
            self.input_mode.set("file")
            self.input_path.set(str(recent_file))
        elif recent_folder is not None:
            self.input_mode.set("folder")
            self.input_path.set(str(recent_folder))
        recent_output = first_existing_path(self.recent_state.recent_output_dirs)
        if recent_output is not None:
            self.output_dir.set(str(recent_output))

    def _remember_recent_path(self, kind: RecentPathKind, path: Path) -> None:
        try:
            self.recent_state = remember_gui_path(self.recent_state, kind, path, max_items=self.state_store.max_items)
            self.state_store.save(self.recent_state)
        except Exception as exc:  # noqa: BLE001
            self._append_log(f"Could not save recent GUI path: {exc}")

    def _remember_request_paths(self, request: GuiConversionRequest) -> None:
        if request.input_mode.lower() == "folder":
            self._remember_recent_path("input_folder", request.input_path)
        else:
            self._remember_recent_path("input_file", request.input_path)
        if request.output_dir is not None:
            self._remember_recent_path("output_dir", request.output_dir)

    def _browse_input(self) -> None:
        from tkinter import filedialog

        if self.input_mode.get() == "folder":
            selected = filedialog.askdirectory(title="Select PDF folder")
        else:
            selected = filedialog.askopenfilename(title="Select PDF file", filetypes=[("PDF files", "*.pdf")])
        if selected:
            self.input_path.set(selected)
            if self.input_mode.get() == "folder":
                self._remember_recent_path("input_folder", Path(selected))
            else:
                self._remember_recent_path("input_file", Path(selected))

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select output folder")
        if selected:
            self.output_dir.set(selected)
            self._remember_recent_path("output_dir", Path(selected))

    def _options(self) -> GuiConversionOptions:
        return GuiConversionOptions(
            pages=self.pages.get().strip() or None,
            password=self.password.get() or None,
            image_mode=self.image_mode.get(),
            table_mode=self.table_mode.get(),
            rag_table_output=self.rag_table_output.get(),
            domain_adapter=self.domain_adapter.get(),
            confidential_safe_mode=self.confidential_safe_mode.get(),
            force_ocr=self.force_ocr.get(),
            ocr_lang=self.ocr_lang.get().strip() or "eng",
            keep_page_markers=self.keep_page_markers.get(),
            remove_header_footer=self.remove_header_footer.get(),
            dedupe_images=self.dedupe_images.get(),
            repair_hyphenation=self.repair_hyphenation.get(),
            figure_crop_fallback=self.figure_crop_fallback.get(),
            skip_existing=self.skip_existing.get(),
        )

    def _request(self) -> GuiConversionRequest:
        output_text = self.output_dir.get().strip()
        return GuiConversionRequest(
            input_mode=self.input_mode.get(),
            input_path=Path(self.input_path.get().strip()),
            output_dir=Path(output_text) if output_text else None,
            options=self._options(),
        )

    def _start_conversion(self) -> None:
        from tkinter import messagebox

        if self.worker is not None and self.worker.is_alive():
            return
        if not self.input_path.get().strip():
            messagebox.showerror("Missing input", "Select a PDF file or folder.")
            return
        request = self._request()
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.open_output_button.configure(state="disabled")
        self.cancel_event.clear()
        self.last_summary = None
        self._clear_log()
        self._clear_results()
        self.status_text.set("Validating request")
        self.progress_value.set(0)
        self._append_log("Starting conversion")
        diagnostics = validate_gui_request(request)
        if diagnostics.has_errors:
            self.start_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self._reset_progress("Cannot start conversion")
            self._append_log(diagnostics.user_message())
            messagebox.showerror("Cannot start conversion", diagnostics.user_message())
            return
        if diagnostics.warnings:
            self._append_log(diagnostics.user_message())
        self._remember_request_paths(request)
        self._begin_progress(request)

        def worker() -> None:
            try:
                summary = run_gui_conversion(
                    request,
                    progress=lambda message: self.queue.put(("log", message)),
                    batch_progress=lambda event: self.queue.put(("batch_progress", event)),
                    cancel_requested=self.cancel_event.is_set,
                )
            except GuiDiagnosticError as exc:
                self.queue.put(("diagnostic_error", exc))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("error", exc))
            else:
                self.queue.put(("done", summary))

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def _poll_queue(self) -> None:
        from tkinter import messagebox

        try:
            while True:
                event, payload = self.queue.get_nowait()
                if event == "log":
                    self._append_log(str(payload))
                    self.status_text.set(str(payload))
                elif event == "batch_progress" and isinstance(payload, GuiBatchProgress):
                    self._handle_batch_progress(payload)
                elif event == "diagnostic_error" and isinstance(payload, GuiDiagnosticError):
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self._finish_progress("Cannot start conversion", value=0)
                    self._append_log(payload.report.user_message())
                    messagebox.showerror("Cannot start conversion", payload.report.user_message())
                elif event == "error":
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self._finish_progress("Conversion failed", value=0)
                    self._append_log(f"Failed: {payload}")
                    messagebox.showerror("Conversion failed", str(payload))
                elif event == "done" and isinstance(payload, GuiConversionSummary):
                    self.last_summary = payload
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self.open_output_button.configure(state="normal")
                    self._remember_recent_path("output_dir", payload.output_root)
                    status_text = "Conversion finished" if payload.exit_code == 0 else "Conversion finished with warnings or failures"
                    self._finish_progress(status_text, value=100)
                    self._populate_results(payload)
                    self._append_log(format_gui_summary(payload))
                    messagebox.showinfo("Conversion finished", self._summary_text(payload))
        except Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _summary_text(self, summary: GuiConversionSummary) -> str:
        return format_gui_summary(summary)

    def _populate_results(self, summary: GuiConversionSummary) -> None:
        self._clear_results()
        first_item_id: str | None = None
        for document in summary.documents:
            warning_value = str(document.warning_count)
            if document.warning_codes:
                warning_value = f"{document.warning_count}: {', '.join(document.warning_codes)}"
            item_id = self.result_tree.insert(
                "",
                "end",
                values=(
                    document.input_pdf.name,
                    document.status,
                    warning_value,
                    "yes" if document.retry_candidate else "",
                    str(document.markdown_path or ""),
                    str(document.report_path or ""),
                ),
            )
            self.result_documents[item_id] = document
            if first_item_id is None:
                first_item_id = item_id
        if first_item_id is not None:
            self.result_tree.selection_set(first_item_id)
            self.result_tree.focus(first_item_id)
        self._update_result_action_buttons()

    def _clear_results(self) -> None:
        for item_id in self.result_tree.get_children():
            self.result_tree.delete(item_id)
        self.result_documents.clear()
        self._update_result_action_buttons()

    def _request_cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_button.configure(state="disabled")
        self.status_text.set("Cancel requested")
        self._append_log("Cancel requested; the current document will finish before the batch stops.")

    def _batch_progress_text(self, event: GuiBatchProgress) -> str:
        return f"Batch {event.current}/{event.total} {event.input_pdf.name}: {event.status}"

    def _begin_progress(self, request: GuiConversionRequest) -> None:
        self.progress_bar.stop()
        if request.input_mode.lower() == "folder":
            self.progress_bar.configure(mode="determinate", maximum=100)
            self.progress_value.set(0)
            self.status_text.set("Batch conversion starting")
        else:
            self.progress_bar.configure(mode="indeterminate", maximum=100)
            self.progress_value.set(0)
            self.status_text.set("Conversion starting")
            self.progress_bar.start(10)

    def _handle_batch_progress(self, event: GuiBatchProgress) -> None:
        snapshot = gui_batch_progress_snapshot(
            current=event.current,
            total=event.total,
            input_pdf=event.input_pdf,
            status=event.status,
        )
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_value.set(snapshot.percent)
        self.status_text.set(snapshot.label)
        self._append_log(snapshot.label)

    def _finish_progress(self, message: str, *, value: int) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_value.set(value)
        self.status_text.set(message)

    def _reset_progress(self, message: str = "Ready") -> None:
        self._finish_progress(message, value=0)

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _selected_document(self) -> GuiDocumentSummary | None:
        selection = self.result_tree.selection()
        if not selection:
            return None
        return self.result_documents.get(selection[0])

    def _update_result_action_buttons(self) -> None:
        if not hasattr(self, "open_markdown_button"):
            return
        document = self._selected_document()
        button_targets = (
            (self.open_markdown_button, "markdown"),
            (self.open_report_button, "report"),
            (self.open_manifest_button, "manifest"),
            (self.open_assets_button, "assets"),
        )
        for button, target in button_targets:
            path = gui_document_open_target(document, target) if document is not None else None
            button.configure(state="normal" if path is not None else "disabled")

    def _open_selected_result(self, target: ResultOpenTarget) -> None:
        document = self._selected_document()
        path = gui_document_open_target(document, target) if document is not None else None
        self._open_path(path, f"Open {target} failed")

    def _open_output(self) -> None:
        if self.last_summary is None:
            return
        document = self._selected_document()
        path = gui_document_open_target(document, "output_dir") if document is not None else self.last_summary.output_root
        self._open_path(path, "Open output folder failed")

    def _open_path(self, path: Path | None, failure_title: str) -> None:
        from tkinter import messagebox

        if path is None:
            message = "No result path is available for the selected document."
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        if not path.exists():
            message = f"Result path does not exist: {path}"
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        try:
            opened = webbrowser.open(path.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001
            message = f"Could not open result path: {exc}"
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        if not opened:
            message = f"Could not open result path: {path}"
            self._append_log(message)
            messagebox.showwarning(failure_title, message)

    def _clear_recent(self) -> None:
        from tkinter import messagebox

        try:
            self.recent_state = self.state_store.clear()
        except Exception as exc:  # noqa: BLE001
            self.recent_state = GuiRecentState()
            message = f"Could not clear recent GUI paths: {exc}"
            self._append_log(message)
            messagebox.showwarning("Clear recent failed", message)
            return
        self.input_path.set("")
        self.output_dir.set("")
        self._append_log("Recent GUI paths cleared.")
        self.status_text.set("Recent paths cleared")

    def _open_help(self) -> None:
        from tkinter import messagebox

        guide_path = gui_user_guide_path()
        if not guide_path.exists():
            message = (
                "GUI user guide was not found. "
                "Open docs/GUI_USER_GUIDE.md from the project root, or reinstall from the source checkout."
            )
            self._append_log(message)
            messagebox.showwarning("Help unavailable", message)
            return
        try:
            opened = webbrowser.open(guide_path.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001
            message = f"Could not open GUI user guide: {exc}"
            self._append_log(message)
            messagebox.showwarning("Help unavailable", message)
            return
        if not opened:
            message = f"Could not open GUI user guide: {guide_path}"
            self._append_log(message)
            messagebox.showwarning("Help unavailable", message)


def _write_startup_diagnostics(report: GuiDiagnosticReport) -> None:
    message = report.user_message()
    if message:
        sys.stderr.write(message + "\n")


def launch_gui() -> int:
    runtime_report = check_gui_runtime()
    if runtime_report.has_errors:
        _write_startup_diagnostics(runtime_report)
        return 1

    import tkinter as tk
    root = tk.Tk()
    app = Pdf2MdGuiApp(root)
    if runtime_report.warnings:
        app._append_log(runtime_report.user_message())
    root.mainloop()
    return 0


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
