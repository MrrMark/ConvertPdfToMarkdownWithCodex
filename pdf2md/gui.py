from __future__ import annotations

import argparse
import json
from pathlib import Path
from queue import Empty, Queue
import sys
import threading
import webbrowser

from pdf2md.gui_help import gui_user_guide_path
from pdf2md.gui_runner import (
    GuiBatchProgress,
    GuiConversionOptions,
    GuiConversionRequest,
    GuiConversionSummary,
    GuiDocumentSummary,
    GuiDiagnostic,
    GuiDiagnosticError,
    GuiDiagnosticReport,
    GuiPageProgress,
    check_gui_runtime,
    format_gui_diagnostic_report,
    format_gui_summary,
    gui_diagnostic_report_to_dict,
    run_gui_conversion,
    validate_gui_request,
)
from pdf2md.gui_profiles import load_gui_profile, write_gui_profile
from pdf2md.gui_i18n import GuiLanguage, translate
from pdf2md.gui_layout import (
    GUI_CONTROL_WRAP_LENGTH,
    GUI_STATUS_WRAP_LENGTH,
    GUI_WINDOW_MIN_SIZE,
    gui_wrapping_text_keys,
)
from pdf2md.gui_presets import (
    GuiOptionPreset,
    apply_preset_to_options,
    preset_allows_custom_options,
)
from pdf2md.gui_state import (
    GuiRecentState,
    GuiStateStore,
    RecentPathKind,
    ResultOpenTarget,
    first_existing_path,
    gui_batch_progress_snapshot,
    gui_document_open_target,
    remember_gui_preferences,
    remember_gui_path,
)
from pdf2md.models import DomainAdapterMode, ImageMode, RagTableOutputMode, TableMode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2md-gui",
        description="Launch the minimal desktop GUI wrapper for pdf2md.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run the headless-safe GUI runtime doctor and exit without launching the GUI.",
    )
    parser.add_argument(
        "--doctor-format",
        choices=("text", "json"),
        default="text",
        help="Output format for --doctor. Default: text.",
    )
    parser.add_argument(
        "--doctor-check-window",
        action="store_true",
        help="When used with --doctor, also try creating and destroying a Tk window.",
    )
    return parser


class Pdf2MdGuiApp:
    def __init__(self, root) -> None:  # noqa: ANN001
        import tkinter as tk

        self.root = root
        self.root.title("pdf2md")
        self.root.minsize(*GUI_WINDOW_MIN_SIZE)
        self.queue: Queue[tuple[str, object]] = Queue()
        self.worker: threading.Thread | None = None
        self.cancel_event = threading.Event()
        self.last_summary: GuiConversionSummary | None = None
        self.result_documents: dict[str, GuiDocumentSummary] = {}
        self.state_store = GuiStateStore()
        self.recent_state = self.state_store.load()
        self.localized_widgets: dict[str, list[object]] = {}
        self.localized_headings: dict[str, str] = {}
        self.advanced_option_widgets: list[object] = []
        self.wrapping_text_keys = set(gui_wrapping_text_keys())
        self.scroll_canvas = None
        self.scroll_window_id: int | None = None

        self.language = tk.StringVar(value=self.recent_state.language)
        self.option_preset = tk.StringVar(value=self.recent_state.option_preset)
        self.status_key: str | None = "ready"
        self.status_values: dict[str, object] = {}
        self.input_mode = tk.StringVar(value="file")
        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.status_text = tk.StringVar(value=self._t("ready"))
        self.progress_value = tk.DoubleVar(value=0.0)
        self.pages = tk.StringVar()
        self.password = tk.StringVar()
        self.image_mode = tk.StringVar(value=ImageMode.REFERENCED.value)
        self.table_mode = tk.StringVar(value=TableMode.AUTO.value)
        self.rag_table_output = tk.StringVar(value=RagTableOutputMode.NONE.value)
        self.domain_adapter = tk.StringVar(value=DomainAdapterMode.NONE.value)
        self.ocr_lang = tk.StringVar(value="eng")
        self.previous_corpus_manifest = tk.StringVar()
        self.skip_existing = tk.BooleanVar(value=False)
        self.reuse_unchanged = tk.BooleanVar(value=False)
        self.confidential_safe_mode = tk.BooleanVar(value=False)
        self.force_ocr = tk.BooleanVar(value=False)
        self.keep_page_markers = tk.BooleanVar(value=False)
        self.remove_header_footer = tk.BooleanVar(value=False)
        self.dedupe_images = tk.BooleanVar(value=False)
        self.repair_hyphenation = tk.BooleanVar(value=False)
        self.figure_crop_fallback = tk.BooleanVar(value=False)
        self.page_workers = tk.StringVar(value="1")
        self.debug = tk.BooleanVar(value=False)
        self.verbose = tk.BooleanVar(value=False)

        self._restore_recent_paths()
        self._build_ui()
        self._apply_selected_preset(save=False)
        self._refresh_texts()
        self.root.after(100, self._poll_queue)

    def _t(self, key: str, **values: object) -> str:
        return translate(self.language.get(), key, **values)

    def _track_text(self, key: str, widget: object) -> object:
        self.localized_widgets.setdefault(key, []).append(widget)
        if key in self.wrapping_text_keys:
            self._configure_wrap(widget, GUI_CONTROL_WRAP_LENGTH)
        return widget

    def _configure_text(self, widget: object, text: str) -> None:
        if hasattr(widget, "configure"):
            widget.configure(text=text)

    def _configure_wrap(self, widget: object, wraplength: int) -> None:
        if not hasattr(widget, "configure"):
            return
        try:
            widget.configure(wraplength=wraplength)
        except Exception:  # noqa: BLE001
            return

    def _refresh_texts(self) -> None:
        self.root.title(self._t("app_title"))
        for key, widgets in self.localized_widgets.items():
            for widget in widgets:
                self._configure_text(widget, self._t(key))
        for column, key in self.localized_headings.items():
            self.result_tree.heading(column, text=self._t(key))
        if self.status_key is not None:
            self.status_text.set(self._t(self.status_key, **self.status_values))
        self._update_result_action_buttons()

    def _build_ui(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        outer = ttk.Frame(self.root)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        frame = ttk.Frame(canvas, padding=12)
        self.scroll_canvas = canvas
        self.scroll_window_id = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", self._resize_scroll_window)
        self._bind_mousewheel(canvas)

        frame.columnconfigure(1, weight=1)

        settings_frame = ttk.LabelFrame(frame, text=self._t("language"))
        self._track_text("language", settings_frame)
        settings_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        settings_frame.columnconfigure(1, weight=1)
        self._track_text(
            "language_ko",
            ttk.Radiobutton(settings_frame, text=self._t("language_ko"), variable=self.language, value="ko", command=self._change_language),
        ).grid(row=0, column=0, sticky="w", padx=(0, 12))
        self._track_text(
            "language_en",
            ttk.Radiobutton(settings_frame, text=self._t("language_en"), variable=self.language, value="en", command=self._change_language),
        ).grid(row=0, column=1, sticky="w")

        preset_frame = ttk.LabelFrame(frame, text=self._t("preset"))
        self._track_text("preset", preset_frame)
        preset_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        preset_frame.columnconfigure(0, weight=1)
        self._track_text(
            "preset_preserve",
            ttk.Radiobutton(
                preset_frame,
                text=self._t("preset_preserve"),
                variable=self.option_preset,
                value="preserve",
                command=self._change_preset,
            ),
        ).grid(row=0, column=0, sticky="w", pady=1)
        self._track_text(
            "preset_rag_optimized",
            ttk.Radiobutton(
                preset_frame,
                text=self._t("preset_rag_optimized"),
                variable=self.option_preset,
                value="rag_optimized",
                command=self._change_preset,
            ),
        ).grid(row=1, column=0, sticky="w", pady=1)
        self._track_text(
            "preset_custom",
            ttk.Radiobutton(
                preset_frame,
                text=self._t("preset_custom"),
                variable=self.option_preset,
                value="custom",
                command=self._change_preset,
            ),
        ).grid(row=2, column=0, sticky="w", pady=1)

        mode_frame = ttk.LabelFrame(frame, text=self._t("input"))
        self._track_text("input", mode_frame)
        mode_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        mode_frame.columnconfigure(1, weight=1)
        self._track_text("pdf_file", ttk.Radiobutton(mode_frame, text=self._t("pdf_file"), variable=self.input_mode, value="file")).grid(row=0, column=0, sticky="w")
        self._track_text("pdf_folder", ttk.Radiobutton(mode_frame, text=self._t("pdf_folder"), variable=self.input_mode, value="folder")).grid(row=0, column=1, sticky="w")
        ttk.Entry(mode_frame, textvariable=self.input_path).grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 8), pady=4)
        self._track_text("browse", ttk.Button(mode_frame, text=self._t("browse"), command=self._browse_input)).grid(row=1, column=2, pady=4)

        self._track_text("output_folder", ttk.Label(frame, text=self._t("output_folder"))).grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.output_dir).grid(row=3, column=1, sticky="ew", padx=(0, 8), pady=4)
        self._track_text("browse", ttk.Button(frame, text=self._t("browse"), command=self._browse_output)).grid(row=3, column=2, pady=4)

        options = ttk.LabelFrame(frame, text=self._t("options"))
        self._track_text("options", options)
        options.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(4, 8))
        options.columnconfigure(1, weight=1)
        self._add_labeled_entry(options, "pages", self.pages, 0, 0)
        self._add_labeled_entry(options, "password", self.password, 1, 0, show="*")
        self._add_labeled_entry(options, "ocr_lang", self.ocr_lang, 2, 0)
        self._add_labeled_combo(options, "image", self.image_mode, [mode.value for mode in ImageMode], 3, 0)
        self._add_labeled_combo(options, "table", self.table_mode, [mode.value for mode in TableMode], 4, 0)
        self._add_labeled_combo(options, "rag_tables", self.rag_table_output, [mode.value for mode in RagTableOutputMode], 5, 0)
        self._add_labeled_combo(options, "domain", self.domain_adapter, [mode.value for mode in DomainAdapterMode], 6, 0)
        self._track_text("previous_corpus_manifest", ttk.Label(options, text=self._t("previous_corpus_manifest"))).grid(
            row=7,
            column=0,
            sticky="w",
            padx=(0, 4),
            pady=3,
        )
        ttk.Entry(options, textvariable=self.previous_corpus_manifest).grid(
            row=7,
            column=1,
            sticky="ew",
            padx=(0, 8),
            pady=3,
        )
        self._track_text(
            "browse",
            ttk.Button(options, text=self._t("browse"), command=self._browse_previous_corpus_manifest),
        ).grid(row=7, column=2, sticky="ew", pady=3)
        self._track_text(
            "reuse_unchanged",
            ttk.Checkbutton(options, text=self._t("reuse_unchanged"), variable=self.reuse_unchanged),
        ).grid(row=8, column=0, columnspan=2, sticky="w", pady=1)

        flags = ttk.LabelFrame(frame, text=self._t("flags"))
        self._track_text("flags", flags)
        flags.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in range(2):
            flags.columnconfigure(col, weight=1)
        checkboxes = [
            ("skip_existing", self.skip_existing),
            ("confidential_safe", self.confidential_safe_mode),
            ("force_ocr", self.force_ocr),
            ("page_markers", self.keep_page_markers),
            ("remove_header_footer", self.remove_header_footer),
            ("dedupe_images", self.dedupe_images),
            ("repair_hyphenation", self.repair_hyphenation),
            ("figure_crop_fallback", self.figure_crop_fallback),
        ]
        for idx, (label_key, variable) in enumerate(checkboxes):
            checkbox = self._track_text(
                label_key,
                ttk.Checkbutton(flags, text=self._t(label_key), variable=variable),
            )
            checkbox.grid(row=idx // 2, column=idx % 2, sticky="w", pady=1)
            self.advanced_option_widgets.append(checkbox)

        expert = ttk.LabelFrame(frame, text=self._t("expert_options"))
        self._track_text("expert_options", expert)
        expert.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in range(2):
            expert.columnconfigure(col, weight=1)
        page_workers_entry = self._add_labeled_entry(expert, "page_workers", self.page_workers, 0, 0)
        self.advanced_option_widgets.append(page_workers_entry)
        debug_checkbox = self._track_text("debug", ttk.Checkbutton(expert, text=self._t("debug"), variable=self.debug))
        debug_checkbox.grid(row=1, column=0, sticky="w", pady=1)
        self.advanced_option_widgets.append(debug_checkbox)
        verbose_checkbox = self._track_text("verbose", ttk.Checkbutton(expert, text=self._t("verbose"), variable=self.verbose))
        verbose_checkbox.grid(row=1, column=1, sticky="w", pady=1)
        self.advanced_option_widgets.append(verbose_checkbox)
        self.import_profile_button = self._track_text(
            "import_profile",
            ttk.Button(expert, text=self._t("import_profile"), command=self._import_profile),
        )
        self.import_profile_button.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=(4, 2))
        self.export_profile_button = self._track_text(
            "export_profile",
            ttk.Button(expert, text=self._t("export_profile"), command=self._export_profile),
        )
        self.export_profile_button.grid(row=2, column=1, sticky="ew", pady=(4, 2))

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        for col in range(3):
            button_frame.columnconfigure(col, weight=1)
        self.start_button = self._track_text(
            "start_conversion",
            ttk.Button(button_frame, text=self._t("start_conversion"), command=self._start_conversion),
        )
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.cancel_button = self._track_text(
            "cancel",
            ttk.Button(button_frame, text=self._t("cancel"), command=self._request_cancel, state=tk.DISABLED),
        )
        self.cancel_button.grid(row=0, column=1, sticky="ew", padx=(0, 6), pady=2)
        self.open_output_button = self._track_text(
            "open_output_folder",
            ttk.Button(
                button_frame,
                text=self._t("open_output_folder"),
                command=self._open_output,
                state=tk.DISABLED,
            ),
        )
        self.open_output_button.grid(row=0, column=2, sticky="ew", pady=2)
        self.help_button = self._track_text("help", ttk.Button(button_frame, text=self._t("help"), command=self._open_help))
        self.help_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.clear_recent_button = self._track_text(
            "clear_recent",
            ttk.Button(button_frame, text=self._t("clear_recent"), command=self._clear_recent),
        )
        self.clear_recent_button.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)

        progress_frame = ttk.Frame(frame)
        progress_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        progress_frame.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_text)
        self._configure_wrap(self.status_label, GUI_STATUS_WRAP_LENGTH)
        self.status_label.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode="determinate",
            maximum=100,
            variable=self.progress_value,
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew")

        results = ttk.LabelFrame(frame, text=self._t("results"))
        self._track_text("results", results)
        results.grid(row=9, column=0, columnspan=3, sticky="nsew", pady=(0, 8))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)
        self.result_tree = ttk.Treeview(
            results,
            columns=("document", "status", "warnings", "retry", "markdown", "report"),
            show="headings",
            height=5,
        )
        self.localized_headings = {
            "document": "document",
            "status": "status",
            "warnings": "warnings",
            "retry": "retry",
            "markdown": "markdown",
            "report": "report",
        }
        for column, label_key in self.localized_headings.items():
            self.result_tree.heading(column, text=self._t(label_key))
        self.result_tree.column("document", width=150, anchor="w")
        self.result_tree.column("status", width=110, anchor="w")
        self.result_tree.column("warnings", width=90, anchor="center")
        self.result_tree.column("retry", width=70, anchor="center")
        self.result_tree.column("markdown", width=170, anchor="w")
        self.result_tree.column("report", width=170, anchor="w")
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        result_x_scroll = ttk.Scrollbar(results, orient=tk.HORIZONTAL, command=self.result_tree.xview)
        self.result_tree.configure(xscrollcommand=result_x_scroll.set)
        result_x_scroll.grid(row=1, column=0, sticky="ew")
        self.result_tree.bind("<<TreeviewSelect>>", lambda event: self._update_result_action_buttons())

        result_actions = ttk.Frame(results)
        result_actions.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        for col in range(2):
            result_actions.columnconfigure(col, weight=1)
        self.open_markdown_button = ttk.Button(
            result_actions,
            text=self._t("open_markdown"),
            command=lambda: self._open_selected_result("markdown"),
            state=tk.DISABLED,
        )
        self._track_text("open_markdown", self.open_markdown_button)
        self.open_markdown_button.grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.open_report_button = ttk.Button(
            result_actions,
            text=self._t("open_report"),
            command=lambda: self._open_selected_result("report"),
            state=tk.DISABLED,
        )
        self._track_text("open_report", self.open_report_button)
        self.open_report_button.grid(row=0, column=1, sticky="ew", pady=2)
        self.open_manifest_button = ttk.Button(
            result_actions,
            text=self._t("open_manifest"),
            command=lambda: self._open_selected_result("manifest"),
            state=tk.DISABLED,
        )
        self._track_text("open_manifest", self.open_manifest_button)
        self.open_manifest_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.open_assets_button = ttk.Button(
            result_actions,
            text=self._t("open_assets"),
            command=lambda: self._open_selected_result("assets"),
            state=tk.DISABLED,
        )
        self._track_text("open_assets", self.open_assets_button)
        self.open_assets_button.grid(row=1, column=1, sticky="ew", pady=2)
        self.open_corpus_manifest_button = ttk.Button(
            result_actions,
            text=self._t("open_corpus_manifest"),
            command=lambda: self._open_summary_artifact("corpus_manifest"),
            state=tk.DISABLED,
        )
        self._track_text("open_corpus_manifest", self.open_corpus_manifest_button)
        self.open_corpus_manifest_button.grid(row=2, column=0, sticky="ew", padx=(0, 6), pady=2)
        self.open_corpus_diff_button = ttk.Button(
            result_actions,
            text=self._t("open_corpus_diff"),
            command=lambda: self._open_summary_artifact("corpus_diff"),
            state=tk.DISABLED,
        )
        self._track_text("open_corpus_diff", self.open_corpus_diff_button)
        self.open_corpus_diff_button.grid(row=2, column=1, sticky="ew", pady=2)
        self.open_requirement_impact_button = ttk.Button(
            result_actions,
            text=self._t("open_requirement_impact"),
            command=lambda: self._open_summary_artifact("requirement_impact"),
            state=tk.DISABLED,
        )
        self._track_text("open_requirement_impact", self.open_requirement_impact_button)
        self.open_requirement_impact_button.grid(row=3, column=0, columnspan=2, sticky="ew", pady=2)

        self.log_text = tk.Text(frame, height=9, wrap="word", state=tk.DISABLED)
        self.log_text.grid(row=10, column=0, columnspan=3, sticky="nsew")
        frame.rowconfigure(9, weight=1)
        frame.rowconfigure(10, weight=1)

    def _resize_scroll_window(self, event) -> None:  # noqa: ANN001
        if self.scroll_canvas is None or self.scroll_window_id is None:
            return
        self.scroll_canvas.itemconfigure(self.scroll_window_id, width=event.width)

    def _bind_mousewheel(self, widget: object) -> None:
        if not hasattr(widget, "bind"):
            return

        def _on_mousewheel(event) -> None:  # noqa: ANN001
            if self.scroll_canvas is None:
                return
            delta = getattr(event, "delta", 0)
            if delta:
                self.scroll_canvas.yview_scroll(int(-1 * (delta / 120)), "units")
                return
            if getattr(event, "num", None) == 4:
                self.scroll_canvas.yview_scroll(-1, "units")
            elif getattr(event, "num", None) == 5:
                self.scroll_canvas.yview_scroll(1, "units")

        widget.bind("<MouseWheel>", _on_mousewheel)
        widget.bind("<Button-4>", _on_mousewheel)
        widget.bind("<Button-5>", _on_mousewheel)

    def _add_labeled_entry(self, parent, label_key: str, variable, row: int, col: int, show: str | None = None):  # noqa: ANN001
        from tkinter import ttk

        self._track_text(label_key, ttk.Label(parent, text=self._t(label_key))).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(0, 4),
            pady=3,
        )
        entry = ttk.Entry(parent, textvariable=variable, show=show)
        entry.grid(row=row, column=col + 1, sticky="ew", padx=(0, 8), pady=3)
        return entry

    def _add_labeled_combo(self, parent, label_key: str, variable, values: list[str], row: int, col: int) -> None:  # noqa: ANN001
        from tkinter import ttk

        self._track_text(label_key, ttk.Label(parent, text=self._t(label_key))).grid(
            row=row,
            column=col,
            sticky="w",
            padx=(0, 4),
            pady=3,
        )
        combo = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
        combo.grid(
            row=row,
            column=col + 1,
            sticky="ew",
            padx=(0, 8),
            pady=3,
        )
        self.advanced_option_widgets.append(combo)

    def _set_status(self, key: str, **values: object) -> None:
        self.status_key = key
        self.status_values = dict(values)
        self.status_text.set(self._t(key, **values))

    def _set_status_text(self, message: str) -> None:
        self.status_key = None
        self.status_values = {}
        self.status_text.set(message)

    def _change_language(self) -> None:
        self._refresh_texts()
        self._save_gui_preferences(language=self.language.get())

    def _change_preset(self) -> None:
        self._apply_selected_preset(save=True)

    def _save_gui_preferences(
        self,
        *,
        language: GuiLanguage | str | None = None,
        option_preset: GuiOptionPreset | str | None = None,
    ) -> None:
        try:
            self.recent_state = remember_gui_preferences(
                self.recent_state,
                language=language,
                option_preset=option_preset,
            )
            self.state_store.save(self.recent_state)
        except Exception as exc:  # noqa: BLE001
            self._append_log(self._t("save_recent_failed", error=exc))

    def _apply_selected_preset(self, *, save: bool) -> None:
        options = apply_preset_to_options(self.option_preset.get(), self._options(strict_page_workers=False))
        self._set_option_vars(options)
        self._set_advanced_options_state()
        if save:
            self._save_gui_preferences(option_preset=self.option_preset.get())

    def _set_option_vars(self, options: GuiConversionOptions) -> None:
        self.pages.set(options.pages or "")
        self.password.set(options.password or "")
        self.image_mode.set(options.image_mode)
        self.table_mode.set(options.table_mode)
        self.rag_table_output.set(options.rag_table_output)
        self.domain_adapter.set(options.domain_adapter)
        self.ocr_lang.set(options.ocr_lang or "eng")
        self.skip_existing.set(options.skip_existing)
        self.confidential_safe_mode.set(options.confidential_safe_mode)
        self.force_ocr.set(options.force_ocr)
        self.keep_page_markers.set(options.keep_page_markers)
        self.remove_header_footer.set(options.remove_header_footer)
        self.dedupe_images.set(options.dedupe_images)
        self.repair_hyphenation.set(options.repair_hyphenation)
        self.figure_crop_fallback.set(options.figure_crop_fallback)
        self.page_workers.set(str(options.page_workers))
        self.debug.set(options.debug)
        self.verbose.set(options.verbose)

    def _set_advanced_options_state(self) -> None:
        editable = preset_allows_custom_options(self.option_preset.get())
        for widget in self.advanced_option_widgets:
            normal_state = "readonly" if getattr(widget, "winfo_class", lambda: "")() == "TCombobox" else "normal"
            widget.configure(state=normal_state if editable else "disabled")

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
            self._append_log(self._t("save_recent_failed", error=exc))

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
            selected = filedialog.askdirectory(title=self._t("select_pdf_folder"))
        else:
            selected = filedialog.askopenfilename(
                title=self._t("select_pdf_file"),
                filetypes=[(self._t("pdf_files"), "*.pdf")],
            )
        if selected:
            self.input_path.set(selected)
            if self.input_mode.get() == "folder":
                self._remember_recent_path("input_folder", Path(selected))
            else:
                self._remember_recent_path("input_file", Path(selected))

    def _browse_output(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askdirectory(title=self._t("select_output_folder"))
        if selected:
            self.output_dir.set(selected)
            self._remember_recent_path("output_dir", Path(selected))

    def _browse_previous_corpus_manifest(self) -> None:
        from tkinter import filedialog

        selected = filedialog.askopenfilename(
            title=self._t("select_previous_corpus_manifest"),
            filetypes=[(self._t("corpus_manifest_files"), "*.json"), ("JSON", "*.json"), ("All files", "*.*")],
        )
        if selected:
            self.previous_corpus_manifest.set(selected)

    def _page_workers_value(self, *, strict: bool) -> int:
        raw_value = self.page_workers.get().strip()
        try:
            value = int(raw_value)
        except ValueError:
            if not strict:
                return 1
            raise self._page_workers_error() from None
        if value < 1:
            if not strict:
                return 1
            raise self._page_workers_error()
        return value

    def _page_workers_error(self) -> GuiDiagnosticError:
        return GuiDiagnosticError(
            GuiDiagnosticReport(
                [
                    GuiDiagnostic(
                        code="page_workers_invalid",
                        severity="error",
                        message=self._t("page_workers_invalid"),
                        action="Use an integer greater than or equal to 1.",
                    )
                ]
            )
        )

    def _options(self, *, strict_page_workers: bool = True) -> GuiConversionOptions:
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
            page_workers=self._page_workers_value(strict=strict_page_workers),
            debug=self.debug.get(),
            verbose=self.verbose.get(),
            skip_existing=self.skip_existing.get(),
        )

    def _request(self) -> GuiConversionRequest:
        output_text = self.output_dir.get().strip()
        previous_manifest_text = self.previous_corpus_manifest.get().strip()
        return GuiConversionRequest(
            input_mode=self.input_mode.get(),
            input_path=Path(self.input_path.get().strip()),
            output_dir=Path(output_text) if output_text else None,
            previous_corpus_manifest=Path(previous_manifest_text) if previous_manifest_text else None,
            reuse_unchanged=self.reuse_unchanged.get(),
            options=self._options(),
        )

    def _profile_filetypes(self) -> list[tuple[str, str]]:
        return [(self._t("profile_files"), "*.json"), ("JSON", "*.json"), ("All files", "*.*")]

    def _import_profile(self) -> None:
        from tkinter import filedialog, messagebox

        selected = filedialog.askopenfilename(title=self._t("select_profile_file"), filetypes=self._profile_filetypes())
        if not selected:
            return
        try:
            options = load_gui_profile(Path(selected), base_options=self._options(strict_page_workers=False))
        except GuiDiagnosticError as exc:
            message = exc.report.user_message()
            self._append_log(message)
            messagebox.showerror(self._t("profile_error"), message)
            return
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._append_log(message)
            messagebox.showerror(self._t("profile_error"), message)
            return
        self.option_preset.set("custom")
        self._set_option_vars(options)
        self._set_advanced_options_state()
        self._save_gui_preferences(option_preset="custom")
        self._append_log(self._t("profile_imported"))
        self._set_status("profile_imported")

    def _export_profile(self) -> None:
        from tkinter import filedialog, messagebox

        selected = filedialog.asksaveasfilename(
            title=self._t("save_profile_file"),
            defaultextension=".json",
            initialfile="pdf2md-gui-profile.json",
            filetypes=self._profile_filetypes(),
        )
        if not selected:
            return
        try:
            path = write_gui_profile(Path(selected), self._options())
        except GuiDiagnosticError as exc:
            message = exc.report.user_message()
            self._append_log(message)
            messagebox.showerror(self._t("profile_error"), message)
            return
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            self._append_log(message)
            messagebox.showerror(self._t("profile_error"), message)
            return
        self._append_log(self._t("profile_exported", path=path))
        self._set_status("profile_exported", path=path)

    def _start_conversion(self) -> None:
        from tkinter import messagebox

        if self.worker is not None and self.worker.is_alive():
            return
        if not self.input_path.get().strip():
            messagebox.showerror(self._t("missing_input_title"), self._t("missing_input_message"))
            return
        try:
            request = self._request()
        except GuiDiagnosticError as exc:
            message = exc.report.user_message()
            self._append_log(message)
            messagebox.showerror(self._t("cannot_start_conversion"), message)
            return
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.open_output_button.configure(state="disabled")
        self.cancel_event.clear()
        self.last_summary = None
        self._clear_log()
        self._clear_results()
        self._set_status("validating_request")
        self.progress_value.set(0)
        self._append_log(self._t("starting_conversion"))
        diagnostics = validate_gui_request(request)
        if diagnostics.has_errors:
            self.start_button.configure(state="normal")
            self.cancel_button.configure(state="disabled")
            self._reset_progress("cannot_start_conversion")
            self._append_log(diagnostics.user_message())
            messagebox.showerror(self._t("cannot_start_conversion"), diagnostics.user_message())
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
                    page_progress=lambda event: self.queue.put(("page_progress", event)),
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
                    self._set_status_text(str(payload))
                elif event == "batch_progress" and isinstance(payload, GuiBatchProgress):
                    self._handle_batch_progress(payload)
                elif event == "page_progress" and isinstance(payload, GuiPageProgress):
                    self._handle_page_progress(payload)
                elif event == "diagnostic_error" and isinstance(payload, GuiDiagnosticError):
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self._finish_progress_key("cannot_start_conversion", value=0)
                    self._append_log(payload.report.user_message())
                    messagebox.showerror(self._t("cannot_start_conversion"), payload.report.user_message())
                elif event == "error":
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self._finish_progress_key("conversion_failed", value=0)
                    self._append_log(self._t("failed_prefix", error=payload))
                    messagebox.showerror(self._t("conversion_failed"), str(payload))
                elif event == "done" and isinstance(payload, GuiConversionSummary):
                    self.last_summary = payload
                    self.start_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self.open_output_button.configure(state="normal")
                    self._remember_recent_path("output_dir", payload.output_root)
                    status_key = (
                        "conversion_finished_percent"
                        if payload.exit_code == 0
                        else "conversion_finished_with_warnings_percent"
                    )
                    self._finish_progress_key(status_key, value=100, percent=self._t("single_complete_percent"))
                    self._populate_results(payload)
                    self._append_log(format_gui_summary(payload))
                    messagebox.showinfo(self._t("conversion_finished"), self._summary_text(payload))
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
                    self._t("yes") if document.retry_candidate else "",
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
        self._set_status("cancel_requested")
        self._append_log(self._t("cancel_requested_detail"))

    def _batch_progress_text(self, event: GuiBatchProgress) -> str:
        snapshot = gui_batch_progress_snapshot(
            current=event.current,
            total=event.total,
            input_pdf=event.input_pdf,
            status=event.status,
        )
        return self._t(
            "batch_progress",
            current=snapshot.current,
            total=snapshot.total,
            percent=snapshot.percent,
            document=event.input_pdf.name,
            status=event.status,
        )

    def _begin_progress(self, request: GuiConversionRequest) -> None:
        self.progress_bar.stop()
        if request.input_mode.lower() == "folder":
            self.progress_bar.configure(mode="determinate", maximum=100)
            self.progress_value.set(0)
            self._set_status("batch_conversion_starting")
        else:
            self.progress_bar.configure(mode="indeterminate", maximum=100)
            self.progress_value.set(0)
            self._set_status("conversion_starting")
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
        label = self._t(
            "batch_progress",
            current=snapshot.current,
            total=snapshot.total,
            percent=snapshot.percent,
            document=event.input_pdf.name,
            status=event.status,
        )
        self._set_status_text(label)
        self._append_log(label)

    def _handle_page_progress(self, event: GuiPageProgress) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_value.set(event.percent)
        label = self._t(
            "page_progress",
            current=event.current,
            total=event.total,
            percent=event.percent,
            page=event.page,
        )
        self._set_status_text(label)
        self._append_log(label)

    def _finish_progress(self, message: str, *, value: int) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_value.set(value)
        self._set_status_text(message)

    def _finish_progress_key(self, key: str, *, value: int, **values: object) -> None:
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate", maximum=100)
        self.progress_value.set(value)
        self._set_status(key, **values)

    def _reset_progress(self, key: str = "ready") -> None:
        self._finish_progress_key(key, value=0)

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
        summary_targets = (
            (self.open_corpus_manifest_button, "corpus_manifest"),
            (self.open_corpus_diff_button, "corpus_diff"),
            (self.open_requirement_impact_button, "requirement_impact"),
        )
        for button, target in summary_targets:
            path = self._summary_artifact_path(target)
            button.configure(state="normal" if path is not None else "disabled")

    def _open_selected_result(self, target: ResultOpenTarget) -> None:
        document = self._selected_document()
        path = gui_document_open_target(document, target) if document is not None else None
        self._open_path(path, self._t("open_target_failed", target=target))

    def _summary_artifact_path(self, target: str) -> Path | None:
        if self.last_summary is None:
            return None
        if target == "corpus_manifest":
            return self.last_summary.corpus_manifest_path
        if target == "corpus_diff":
            return self.last_summary.corpus_diff_report_path
        if target == "requirement_impact":
            return self.last_summary.requirement_change_impact_report_path
        return None

    def _open_summary_artifact(self, target: str) -> None:
        self._open_path(self._summary_artifact_path(target), self._t("open_target_failed", target=target))

    def _open_output(self) -> None:
        if self.last_summary is None:
            return
        document = self._selected_document()
        path = gui_document_open_target(document, "output_dir") if document is not None else self.last_summary.output_root
        self._open_path(path, self._t("open_output_failed"))

    def _open_path(self, path: Path | None, failure_title: str) -> None:
        from tkinter import messagebox

        if path is None:
            message = self._t("no_result_path")
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        if not path.exists():
            message = self._t("result_path_missing", path=path)
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        try:
            opened = webbrowser.open(path.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001
            message = self._t("result_path_open_error", error=exc)
            self._append_log(message)
            messagebox.showwarning(failure_title, message)
            return
        if not opened:
            message = self._t("result_path_open_false", path=path)
            self._append_log(message)
            messagebox.showwarning(failure_title, message)

    def _clear_recent(self) -> None:
        from tkinter import messagebox

        try:
            cleared_state = self.state_store.clear()
            self.recent_state = remember_gui_preferences(
                cleared_state,
                language=self.language.get(),
                option_preset=self.option_preset.get(),
            )
            self.state_store.save(self.recent_state)
        except Exception as exc:  # noqa: BLE001
            self.recent_state = remember_gui_preferences(
                GuiRecentState(),
                language=self.language.get(),
                option_preset=self.option_preset.get(),
            )
            message = self._t("save_recent_failed", error=exc)
            self._append_log(message)
            messagebox.showwarning(self._t("clear_recent_failed"), message)
            return
        self.input_path.set("")
        self.output_dir.set("")
        self.previous_corpus_manifest.set("")
        self.reuse_unchanged.set(False)
        self._append_log(self._t("recent_paths_cleared"))
        self._set_status("recent_paths_cleared_status")

    def _open_help(self) -> None:
        from tkinter import messagebox

        guide_path = gui_user_guide_path()
        if not guide_path.exists():
            message = self._t("help_missing")
            self._append_log(message)
            messagebox.showwarning(self._t("help_unavailable"), message)
            return
        try:
            opened = webbrowser.open(guide_path.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001
            message = self._t("help_open_error", error=exc)
            self._append_log(message)
            messagebox.showwarning(self._t("help_unavailable"), message)
            return
        if not opened:
            message = self._t("help_open_false", path=guide_path)
            self._append_log(message)
            messagebox.showwarning(self._t("help_unavailable"), message)


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
    args = build_parser().parse_args(argv)
    if args.doctor:
        report = check_gui_runtime(check_window=args.doctor_check_window)
        if args.doctor_format == "json":
            print(json.dumps(gui_diagnostic_report_to_dict(report), indent=2, sort_keys=True))
        else:
            print(format_gui_diagnostic_report(report))
        return 0 if not report.has_errors else 1
    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
