from __future__ import annotations

import argparse
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import webbrowser

from pdf2md.gui_runner import (
    GuiConversionOptions,
    GuiConversionRequest,
    GuiConversionSummary,
    GuiDiagnosticError,
    GuiDiagnosticReport,
    check_gui_runtime,
    run_gui_conversion,
    validate_gui_request,
)
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


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
        self.last_summary: GuiConversionSummary | None = None

        self.input_mode = tk.StringVar(value="file")
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
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
        self.open_output_button = ttk.Button(button_frame, text="Open output folder", command=self._open_output, state=tk.DISABLED)
        self.open_output_button.pack(side=tk.LEFT, padx=(8, 0))

        self.log_text = tk.Text(frame, height=14, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=5, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(5, weight=1)

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

    def _browse_input(self) -> None:
        from tkinter import filedialog

        if self.input_mode.get() == "folder":
            selected = filedialog.askdirectory(title="Select PDF folder")
        else:
            selected = filedialog.askopenfilename(title="Select PDF file", filetypes=[("PDF files", "*.pdf")])
        if selected:
            self.input_path.set(selected)

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title="Select output folder")
        if selected:
            self.output_dir.set(selected)

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
        self.open_output_button.configure(state="disabled")
        self.last_summary = None
        self._clear_log()
        self._append_log("Starting conversion")
        diagnostics = validate_gui_request(request)
        if diagnostics.has_errors:
            self.start_button.configure(state="normal")
            self._append_log(diagnostics.user_message())
            messagebox.showerror("Cannot start conversion", diagnostics.user_message())
            return
        if diagnostics.warnings:
            self._append_log(diagnostics.user_message())

        def worker() -> None:
            try:
                summary = run_gui_conversion(request, progress=lambda message: self.queue.put(("log", message)))
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
                elif event == "diagnostic_error" and isinstance(payload, GuiDiagnosticError):
                    self.start_button.configure(state="normal")
                    self._append_log(payload.report.user_message())
                    messagebox.showerror("Cannot start conversion", payload.report.user_message())
                elif event == "error":
                    self.start_button.configure(state="normal")
                    self._append_log(f"Failed: {payload}")
                    messagebox.showerror("Conversion failed", str(payload))
                elif event == "done" and isinstance(payload, GuiConversionSummary):
                    self.last_summary = payload
                    self.start_button.configure(state="normal")
                    self.open_output_button.configure(state="normal")
                    self._append_log(self._summary_text(payload))
                    messagebox.showinfo("Conversion finished", self._summary_text(payload))
        except Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _summary_text(self, summary: GuiConversionSummary) -> str:
        return (
            "Finished: "
            f"success={summary.success_count}, "
            f"partial={summary.partial_success_count}, "
            f"failed={summary.failed_count}, "
            f"skipped={summary.skipped_count}, "
            f"output={summary.output_root}"
        )

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _open_output(self) -> None:
        if self.last_summary is None:
            return
        webbrowser.open(self.last_summary.output_root.resolve().as_uri())


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
