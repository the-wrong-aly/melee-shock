import logging
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog
from typing import Any, Callable

import customtkinter as ctk
from pydantic import ValidationError

import melee_shock.modes.action  # noqa – triggers @register_mode
import melee_shock.modes.damage  # noqa
import melee_shock.modes.interval  # noqa
import melee_shock.config as config_module
from melee_shock.apis.pishock import PiShockSerialAPI
from melee_shock.engine import Engine
from melee_shock.models import OutputMode, Player
from melee_shock.modes.registry import get as get_mode
from melee_shock.sources.dolphin import DolphinSource
from melee_shock.sources.wii import WiiSource

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

OUTPUT_MODES = ["shock", "vibrate", "disabled"]
MODE_NAMES = ["damage", "interval", "action"]

# (key, label, type, default)  types: "intensity" | "int" | "float" | "str" | "bool"
# "intensity" renders as a 0-100 slider; behaves as int for save/load
# default is the placeholder shown when field is empty (None = no placeholder)
MODE_FIELDS: dict[str, list[tuple[str, str, str, str | None]]] = {
    "damage": [
        ("max_intensity", "Max intensity", "intensity", None),
        ("min_duration", "Min duration (s)", "float", "0"),
    ],
    "interval": [
        ("interval", "Interval (s)", "interval_range", None),
        ("intensity", "Intensity", "intensity_range", None),
        ("duration", "Duration (s)", "float", "0.1"),
    ],
    "action": [
        ("action", "Action(s)", "str", None),
        ("intensity", "Intensity", "intensity", None),
        ("do_while", "Repeat while held", "bool", None),
    ],
}

logger = logging.getLogger(__name__)


@dataclass
class ModeEntry:
    name_var: tk.StringVar
    params_vars: dict
    frame: ctk.CTkFrame
    params_frame: ctk.CTkFrame
    lockable: list
    indent: int
    on_change: Callable | None = None


class _QueueHandler(logging.Handler):
    def __init__(self, q: queue.Queue) -> None:
        super().__init__()
        self._q = q

    def emit(self, record: logging.LogRecord) -> None:
        self._q.put(self.format(record))


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("melee-shock")
        self.geometry("600x700")
        self.resizable(True, True)

        self._engine: Engine | None = None
        self._source: DolphinSource | WiiSource | None = None
        self._log_q: queue.Queue = queue.Queue()
        self._worker: threading.Thread | None = None
        self._lockable: list = []
        self._global_mode_entries: list[ModeEntry] = []
        self._global_modes_container: ctk.CTkFrame | None = None
        self._player_mode_entries: dict[int, list[ModeEntry]] = {
            p: [] for p in range(1, 5)
        }
        self._player_modes_container: dict[int, ctk.CTkFrame] = {}
        self._player_global_mode_labels: dict[int, ctk.CTkLabel] = {}

        self._setup_logging()
        self._build_ui()
        self._poll_logs()

    # ── logging ──────────────────────────────────────────────────────────────

    def _setup_logging(self) -> None:
        handler = _QueueHandler(self._log_q)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%H:%M:%S"
            )
        )
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.INFO)

    def _lw(self, widget):
        self._lockable.append(widget)
        return widget

    # ── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self)
        bar.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="Config").grid(
            row=0, column=0, padx=(12, 6), pady=8, sticky="w"
        )
        self._config_var = tk.StringVar(value="config.toml")
        self._lw(ctk.CTkEntry(bar, textvariable=self._config_var)).grid(
            row=0, column=1, sticky="ew", padx=4, pady=8
        )
        self._lw(
            ctk.CTkButton(bar, text="Browse…", width=80, command=self._browse)
        ).grid(row=0, column=2, padx=4, pady=8)
        self._lw(
            ctk.CTkButton(bar, text="Load", width=60, command=self._load_config)
        ).grid(row=0, column=3, padx=4, pady=8)
        self._lw(
            ctk.CTkButton(bar, text="Save", width=60, command=self._save_config)
        ).grid(row=0, column=4, padx=(4, 12), pady=8)

        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, sticky="nsew", padx=12, pady=4)
        tabs.add("Settings")
        tabs.add("Log")
        self._build_settings_tab(tabs.tab("Settings"))
        self._build_log_tab(tabs.tab("Log"))

        ctrl = ctk.CTkFrame(self)
        ctrl.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 12))
        self._status_var = tk.StringVar(value="Stopped")
        ctk.CTkLabel(ctrl, textvariable=self._status_var, anchor="w").pack(
            fill="x", padx=12, pady=(8, 4)
        )
        btns = ctk.CTkFrame(ctrl, fg_color="transparent")
        btns.pack(fill="x", padx=12, pady=(0, 8))
        self._connect_btn = ctk.CTkButton(
            btns, text="Connect & Start", width=160, command=self._on_connect
        )
        self._connect_btn.pack(side="left", padx=(0, 8))
        self._stop_btn = ctk.CTkButton(
            btns,
            text="Stop",
            width=80,
            command=self._on_stop,
            state="disabled",
            fg_color="#555",
            hover_color="#666",
        )
        self._stop_btn.pack(side="left")

    def _build_settings_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.grid(row=0, column=0, sticky="nsew")
        scroll.grid_columnconfigure(1, weight=1)
        r = 0
        r = self._build_source_section(scroll, r)
        r = self._build_global_section(scroll, r)
        r = self._build_players_section(scroll, r)
        self._build_shockers_section(scroll, r)

    def _build_source_section(self, scroll: ctk.CTkScrollableFrame, r: int) -> int:
        ctk.CTkLabel(scroll, text="Source", font=ctk.CTkFont(weight="bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 2)
        )
        r += 1

        ctk.CTkLabel(scroll, text="Type").grid(
            row=r, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._source_var = tk.StringVar(value="dolphin")
        self._lw(
            ctk.CTkOptionMenu(
                scroll,
                variable=self._source_var,
                values=["dolphin", "wii"],
                width=120,
                command=self._on_source_changed,
            )
        ).grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        self._dolphin_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._dolphin_frame.grid(row=r, column=0, columnspan=3, sticky="ew")
        self._dolphin_frame.grid_columnconfigure(1, weight=1)
        r += 1

        ctk.CTkLabel(self._dolphin_frame, text="Path").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._dolphin_path_var = tk.StringVar()
        self._lw(
            ctk.CTkEntry(self._dolphin_frame, textvariable=self._dolphin_path_var)
        ).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
        self._lw(
            ctk.CTkButton(
                self._dolphin_frame,
                text="…",
                width=32,
                command=lambda: self._pick_dir(self._dolphin_path_var),
            )
        ).grid(row=0, column=2, padx=(4, 8), pady=3)

        ctk.CTkLabel(self._dolphin_frame, text="ISO").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._iso_path_var = tk.StringVar()
        self._lw(
            ctk.CTkEntry(self._dolphin_frame, textvariable=self._iso_path_var)
        ).grid(row=1, column=1, sticky="ew", padx=4, pady=3)
        self._lw(
            ctk.CTkButton(
                self._dolphin_frame,
                text="…",
                width=32,
                command=lambda: self._pick_file(self._iso_path_var),
            )
        ).grid(row=1, column=2, padx=(4, 8), pady=3)

        self._wii_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._wii_frame.grid(row=r, column=0, columnspan=3, sticky="ew")
        self._wii_frame.grid_columnconfigure(1, weight=1)
        self._wii_frame.grid_remove()
        r += 1

        ctk.CTkLabel(self._wii_frame, text="IP").grid(
            row=0, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._wii_ip_var = tk.StringVar()
        self._lw(ctk.CTkEntry(self._wii_frame, textvariable=self._wii_ip_var)).grid(
            row=0, column=1, sticky="ew", padx=4, pady=3
        )

        ctk.CTkLabel(self._wii_frame, text="Port").grid(
            row=1, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._wii_port_var = tk.StringVar(value="51441")
        self._lw(
            ctk.CTkEntry(self._wii_frame, textvariable=self._wii_port_var, width=100)
        ).grid(row=1, column=1, sticky="w", padx=4, pady=3)

        ctk.CTkLabel(scroll, text="Debug").grid(
            row=r, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._debug_var = tk.BooleanVar(value=False)
        self._lw(
            ctk.CTkCheckBox(
                scroll, text="", variable=self._debug_var, onvalue=True, offvalue=False
            )
        ).grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        return r

    def _build_global_section(self, scroll: ctk.CTkScrollableFrame, r: int) -> int:
        ctk.CTkLabel(scroll, text="Global", font=ctk.CTkFont(weight="bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 2)
        )
        r += 1

        ctk.CTkLabel(scroll, text="Max intensity").grid(
            row=r, column=0, sticky="w", padx=(20, 8), pady=3
        )
        self._intensity_var = tk.IntVar(value=0)
        self._intensity_label = ctk.CTkLabel(scroll, text="0", width=52, anchor="w")
        self._intensity_label.grid(row=r, column=2, padx=(4, 8), pady=3)
        self._intensity_var.trace_add("write", self._on_intensity_changed)
        self._lw(
            ctk.CTkSlider(
                scroll,
                from_=0,
                to=100,
                number_of_steps=100,
                variable=self._intensity_var,
            )
        ).grid(row=r, column=1, sticky="ew", padx=4, pady=3)
        r += 1

        ctk.CTkLabel(scroll, text="Default modes").grid(
            row=r, column=0, sticky="w", padx=(20, 8), pady=(6, 2)
        )
        r += 1

        global_modes_container = ctk.CTkFrame(scroll, fg_color="transparent")
        global_modes_container.grid(row=r, column=0, columnspan=3, sticky="ew")
        global_modes_container.grid_columnconfigure(0, weight=1)
        self._global_modes_container = global_modes_container
        r += 1

        self._lw(
            ctk.CTkButton(
                scroll,
                text="+ Add mode",
                width=110,
                height=26,
                command=lambda: self._add_global_mode(),
            )
        ).grid(row=r, column=0, sticky="w", padx=(20, 8), pady=(2, 4))
        r += 1

        return r

    def _build_players_section(self, scroll: ctk.CTkScrollableFrame, r: int) -> int:
        ctk.CTkLabel(scroll, text="Players", font=ctk.CTkFont(weight="bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 2)
        )
        r += 1

        self._player_vars: dict[int, tk.StringVar] = {}
        self._player_settings_frames: dict[int, ctk.CTkFrame] = {}

        for port in range(1, 5):
            pf = ctk.CTkFrame(scroll, fg_color="transparent")
            pf.grid(row=r, column=0, columnspan=3, sticky="ew")
            pf.grid_columnconfigure(1, weight=1)
            r += 1

            ctk.CTkLabel(pf, text=f"P{port}").grid(
                row=0, column=0, sticky="w", padx=(20, 8), pady=3
            )
            out_var = tk.StringVar(value="disabled")
            self._player_vars[port] = out_var
            self._lw(
                ctk.CTkOptionMenu(pf, variable=out_var, values=OUTPUT_MODES, width=120)
            ).grid(row=0, column=1, sticky="w", padx=4, pady=3)
            self._lw(
                ctk.CTkButton(
                    pf,
                    text="−",
                    width=28,
                    command=lambda p=port: self._player_vars[p].set("disabled"),
                )
            ).grid(row=0, column=2, padx=(4, 8), pady=3)

            sf = ctk.CTkFrame(pf, fg_color="transparent")
            sf.grid(row=1, column=0, columnspan=3, sticky="ew")
            sf.grid_columnconfigure(0, weight=1)
            self._player_settings_frames[port] = sf

            modes_container = ctk.CTkFrame(sf, fg_color="transparent")
            modes_container.grid(row=0, column=0, columnspan=3, sticky="ew")
            modes_container.grid_columnconfigure(0, weight=1)
            self._player_modes_container[port] = modes_container

            global_lbl = ctk.CTkLabel(
                modes_container,
                text="(using global modes)",
                text_color="gray",
                anchor="w",
            )
            global_lbl.grid(row=0, column=0, sticky="w", padx=(52, 8), pady=(2, 0))
            self._player_global_mode_labels[port] = global_lbl

            self._lw(
                ctk.CTkButton(
                    sf,
                    text="+ Add mode",
                    width=110,
                    height=26,
                    command=lambda p=port: self._add_player_mode(p),
                )
            ).grid(row=1, column=0, sticky="w", padx=(36, 8), pady=(2, 4))

            out_var.trace_add(
                "write", lambda *_, p=port: self._on_player_output_changed(p)
            )
            sf.grid_remove()

        return r

    def _build_shockers_section(self, scroll: ctk.CTkScrollableFrame, r: int) -> None:
        ctk.CTkLabel(scroll, text="Shockers", font=ctk.CTkFont(weight="bold")).grid(
            row=r, column=0, columnspan=3, sticky="w", padx=8, pady=(12, 2)
        )
        r += 1

        self._shockers_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        self._shockers_frame.grid(row=r, column=0, columnspan=3, sticky="ew")
        self._shockers_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            self._shockers_frame, text="Not connected", text_color="gray"
        ).grid(row=0, column=0, sticky="w", padx=(20, 8), pady=4)

    def _on_source_changed(self, source_type: str) -> None:
        if source_type == "dolphin":
            self._dolphin_frame.grid()
            self._wii_frame.grid_remove()
        else:
            self._dolphin_frame.grid_remove()
            self._wii_frame.grid()

    def _build_log_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        wrap = tk.Frame(parent, bg="#1c1c1e")
        wrap.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self._log_text = tk.Text(
            wrap,
            state="disabled",
            wrap="word",
            bg="#1c1c1e",
            fg="#e0e0e0",
            font=("Consolas", 9),
            relief="flat",
            borderwidth=0,
            selectbackground="#3a3a3c",
        )
        sb = tk.Scrollbar(wrap, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        self._log_text.grid(row=0, column=0, sticky="nsew")

    # ── shared mode entry helpers ─────────────────────────────────────────────

    def _add_mode_entry(
        self,
        container: ctk.CTkFrame,
        entries: list[ModeEntry],
        mode_name: str = "damage",
        indent: int = 20,
        on_change: Callable | None = None,
    ) -> ModeEntry:
        row = len(entries)

        entry_frame = ctk.CTkFrame(container, fg_color="transparent")
        entry_frame.grid(row=row, column=0, sticky="ew", pady=(2, 0))
        entry_frame.grid_columnconfigure(1, weight=1)

        name_var = tk.StringVar(value=mode_name)
        lockable: list = []

        dropdown = ctk.CTkOptionMenu(
            entry_frame, variable=name_var, values=MODE_NAMES, width=120
        )
        dropdown.grid(row=0, column=0, sticky="w", padx=(indent, 4), pady=2)
        lockable.append(dropdown)

        remove_btn = ctk.CTkButton(
            entry_frame, text="×", width=28, fg_color="#555", hover_color="#c0392b"
        )
        remove_btn.grid(row=0, column=2, padx=(4, 8), pady=2)
        lockable.append(remove_btn)

        params_frame = ctk.CTkFrame(entry_frame, fg_color="transparent")
        params_frame.grid(row=1, column=0, columnspan=3, sticky="ew")
        params_frame.grid_columnconfigure(1, weight=1)

        entry = ModeEntry(
            name_var=name_var,
            params_vars={},
            frame=entry_frame,
            params_frame=params_frame,
            lockable=lockable,
            indent=indent,
            on_change=on_change,
        )
        entries.append(entry)

        remove_btn.configure(
            command=lambda e=entry: self._remove_mode_entry(entries, e)
        )
        if on_change:
            on_change()
        name_var.trace_add(
            "write",
            lambda *_, e=entry: self._rebuild_mode_params_for_entry(
                e, e.name_var.get()
            ),
        )
        self._rebuild_mode_params_for_entry(entry, mode_name)
        return entry

    def _remove_mode_entry(self, entries: list[ModeEntry], entry: ModeEntry) -> None:
        if entry in entries:
            entries.remove(entry)
        entry.frame.destroy()
        for i, e in enumerate(entries):
            e.frame.grid(row=i, column=0, sticky="ew", pady=(2, 0))
        if entry.on_change:
            entry.on_change()

    def _rebuild_mode_params_for_entry(self, entry: ModeEntry, mode_name: str) -> None:
        frame = entry.params_frame
        for w in frame.winfo_children():
            w.destroy()
        entry.lockable = entry.lockable[:2]
        entry.params_vars.clear()
        indent = entry.indent + 16
        for i, (key, label, typ, default) in enumerate(MODE_FIELDS[mode_name]):
            ctk.CTkLabel(frame, text=label).grid(
                row=i, column=0, sticky="w", padx=(indent, 8), pady=2
            )
            if typ in ("intensity_range", "interval_range"):
                self._build_range_block(
                    frame,
                    i,
                    entry.params_vars,
                    entry.lockable,
                    key_prefix=typ.replace("_range", ""),
                )
                continue
            if typ == "bool":
                var: tk.Variable = tk.BooleanVar(value=False)
                widget = ctk.CTkCheckBox(
                    frame, text="", variable=var, onvalue=True, offvalue=False
                )
            elif typ == "intensity":
                var = tk.IntVar(value=0)
                val_lbl = ctk.CTkLabel(frame, text="0", width=52, anchor="w")
                val_lbl.grid(row=i, column=2, padx=(4, 8), pady=2)
                var.trace_add(
                    "write",
                    lambda *_, v=var, lbl=val_lbl: lbl.configure(text=str(v.get())),
                )
                widget = ctk.CTkSlider(
                    frame, from_=0, to=100, number_of_steps=100, variable=var
                )
            else:
                var = tk.StringVar(value=default if default is not None else "")
                widget = ctk.CTkEntry(frame, textvariable=var, width=160)
            widget.grid(row=i, column=1, sticky="ew", padx=4, pady=2)
            entry.lockable.append(widget)
            entry.params_vars[key] = var

    def _build_range_block(
        self,
        frame: ctk.CTkFrame,
        row: int,
        vars_dict: dict,
        lockable: list,
        key_prefix: str,
    ) -> None:
        """Builds an intensity (slider) or interval (entry) fixed/range toggle block."""
        is_intensity = key_prefix == "intensity"

        sub = ctk.CTkFrame(frame, fg_color="transparent")
        sub.grid(row=row, column=1, columnspan=2, sticky="ew", padx=4, pady=2)
        sub.grid_columnconfigure(1, weight=1)

        use_range_var = tk.BooleanVar(value=False)

        def make_slider(var: tk.IntVar):
            lbl = ctk.CTkLabel(sub, text="0", width=52, anchor="w")
            var.trace_add(
                "write", lambda *_, v=var, l=lbl: l.configure(text=str(v.get()))
            )
            return ctk.CTkSlider(
                sub, from_=0, to=100, number_of_steps=100, variable=var
            ), lbl

        if is_intensity:
            fixed_var: tk.Variable = tk.IntVar(value=0)
            fixed_widget, fixed_extra = make_slider(fixed_var)
            min_var: tk.Variable = tk.IntVar(value=0)
            min_widget, min_extra = make_slider(min_var)
            max_var: tk.Variable = tk.IntVar(value=0)
            max_widget, max_extra = make_slider(max_var)
        else:
            fixed_var = tk.StringVar(value="")
            fixed_widget = ctk.CTkEntry(sub, textvariable=fixed_var, width=160)
            fixed_extra = None
            min_var = tk.StringVar(value="")
            min_widget = ctk.CTkEntry(sub, textvariable=min_var, width=120)
            min_extra = None
            max_var = tk.StringVar(value="")
            max_widget = ctk.CTkEntry(sub, textvariable=max_var, width=120)
            max_extra = None

        toggle = ctk.CTkCheckBox(
            sub,
            text="Random range",
            variable=use_range_var,
            onvalue=True,
            offvalue=False,
        )
        toggle.grid(
            row=1,
            column=0,
            columnspan=3 if is_intensity else 2,
            sticky="w",
            pady=(2, 0),
        )

        min_label = ctk.CTkLabel(sub, text="Min", anchor="w")
        max_label = ctk.CTkLabel(sub, text="Max", anchor="w")

        def _show_fixed(*_):
            fixed_widget.grid(row=0, column=0, columnspan=2, sticky="ew")
            if fixed_extra:
                fixed_extra.grid(row=0, column=2, padx=(4, 0))
            min_label.grid_remove()
            min_widget.grid_remove()
            if min_extra:
                min_extra.grid_remove()
            max_label.grid_remove()
            max_widget.grid_remove()
            if max_extra:
                max_extra.grid_remove()

        def _show_range(*_):
            fixed_widget.grid_remove()
            if fixed_extra:
                fixed_extra.grid_remove()
            min_label.grid(row=2, column=0, sticky="w", padx=(0, 4))
            min_widget.grid(row=2, column=1, sticky="ew")
            if min_extra:
                min_extra.grid(row=2, column=2, padx=(4, 0))
            max_label.grid(row=3, column=0, sticky="w", padx=(0, 4))
            max_widget.grid(row=3, column=1, sticky="ew")
            if max_extra:
                max_extra.grid(row=3, column=2, padx=(4, 0))

        use_range_var.trace_add(
            "write", lambda *_: _show_range() if use_range_var.get() else _show_fixed()
        )

        # Place all, then hide the range half
        fixed_widget.grid(row=0, column=0, columnspan=2, sticky="ew")
        if fixed_extra:
            fixed_extra.grid(row=0, column=2, padx=(4, 0))
        min_label.grid(row=2, column=0, sticky="w", padx=(0, 4))
        min_widget.grid(row=2, column=1, sticky="ew")
        if min_extra:
            min_extra.grid(row=2, column=2, padx=(4, 0))
        max_label.grid(row=3, column=0, sticky="w", padx=(0, 4))
        max_widget.grid(row=3, column=1, sticky="ew")
        if max_extra:
            max_extra.grid(row=3, column=2, padx=(4, 0))
        _show_fixed()

        vars_dict[key_prefix] = fixed_var
        vars_dict[f"{key_prefix}_min"] = min_var
        vars_dict[f"{key_prefix}_max"] = max_var
        vars_dict[f"_{key_prefix}_use_range"] = use_range_var
        lockable.extend([fixed_widget, toggle, min_widget, max_widget])

    # ── global / per-player mode management ──────────────────────────────────

    def _add_global_mode(self, mode_name: str = "damage") -> ModeEntry:
        return self._add_mode_entry(
            self._global_modes_container,
            self._global_mode_entries,
            mode_name,
            indent=20,
        )

    def _add_player_mode(self, port: int, mode_name: str = "damage") -> ModeEntry:
        return self._add_mode_entry(
            self._player_modes_container[port],
            self._player_mode_entries[port],
            mode_name,
            indent=36,
            on_change=lambda: self._update_player_global_label(port),
        )

    def _update_player_global_label(self, port: int) -> None:
        lbl = self._player_global_mode_labels.get(port)
        if lbl is None:
            return
        if (
            self._player_vars[port].get() != "disabled"
            and not self._player_mode_entries[port]
        ):
            lbl.grid()
        else:
            lbl.grid_remove()

    def _on_player_output_changed(self, port: int) -> None:
        sf = self._player_settings_frames[port]
        if self._player_vars[port].get() == "disabled":
            sf.grid_remove()
        else:
            sf.grid()
        self._update_player_global_label(port)

    def _on_intensity_changed(self, *_) -> None:
        self._intensity_label.configure(text=str(self._intensity_var.get()))

    # ── field-level type dispatch ─────────────────────────────────────────────

    @staticmethod
    def _field_to_params(typ: str, key: str, pvars: dict) -> dict[str, Any]:
        """Read one field's vars into a params dict fragment for the mode constructor."""
        if typ == "intensity_range":
            use_range = pvars.get("_intensity_use_range")
            if use_range and use_range.get():
                result = {}
                for rk in ("intensity_min", "intensity_max"):
                    rv = pvars.get(rk)
                    if rv is not None:
                        result[rk] = int(rv.get())
                return result
            var = pvars.get(key)
            s = str(var.get()).strip() if var is not None else ""
            return {key: int(s)} if s else {}
        if typ == "interval_range":
            use_range = pvars.get("_interval_use_range")
            if use_range and use_range.get():
                result = {}
                for rk in ("interval_min", "interval_max"):
                    rv = pvars.get(rk)
                    if rv is not None:
                        s = str(rv.get()).strip()
                        if s:
                            result[rk] = float(s)
                return result
            var = pvars.get(key)
            s = str(var.get()).strip() if var is not None else ""
            return {key: float(s)} if s else {}
        var = pvars.get(key)
        if var is None:
            return {}
        raw = var.get()
        if typ == "bool":
            return {key: bool(raw)}
        if typ in ("int", "intensity"):
            s = str(raw).strip()
            return {key: int(s)} if s else {}
        if typ == "float":
            s = str(raw).strip()
            return {key: float(s)} if s else {}
        # str
        s = str(raw).strip()
        if not s:
            return {}
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return {key: parts[0] if len(parts) == 1 else parts}

    @staticmethod
    def _field_to_toml(typ: str, key: str, pvars: dict) -> list[str]:
        """Serialize one field's vars to TOML lines."""
        if typ == "intensity_range":
            use_range = pvars.get("_intensity_use_range")
            if use_range and use_range.get():
                lines = []
                for rk in ("intensity_min", "intensity_max"):
                    rv = pvars.get(rk)
                    if rv is not None:
                        lines.append(f"{rk} = {int(rv.get())}")
                return lines
            var = pvars.get(key)
            s = str(var.get()).strip() if var is not None else ""
            return [f"{key} = {int(s)}"] if s else []
        if typ == "interval_range":
            use_range = pvars.get("_interval_use_range")
            if use_range and use_range.get():
                lines = []
                for rk in ("interval_min", "interval_max"):
                    rv = pvars.get(rk)
                    if rv is not None:
                        s = str(rv.get()).strip()
                        if s:
                            lines.append(f"{rk} = {float(s)}")
                return lines
            var = pvars.get(key)
            s = str(var.get()).strip() if var is not None else ""
            return [f"{key} = {float(s)}"] if s else []
        var = pvars.get(key)
        if var is None:
            return []
        raw = var.get()
        if typ == "bool":
            return [f"{key} = {'true' if raw else 'false'}"]
        if typ in ("int", "intensity"):
            s = str(raw).strip()
            return [f"{key} = {int(s)}"] if s else []
        if typ == "float":
            s = str(raw).strip()
            return [f"{key} = {float(s)}"] if s else []
        # str
        s = str(raw).strip()
        if not s:
            return []
        parts = [p.strip() for p in s.split(",") if p.strip()]
        if len(parts) == 1:
            return [f'{key} = "{parts[0]}"']
        items = ", ".join(f'"{p}"' for p in parts)
        return [f"{key} = [{items}]"]

    @staticmethod
    def _load_field_from_raw(
        typ: str, key: str, mode_raw: dict, vars_dict: dict
    ) -> None:
        """Load one field from a raw TOML dict into the vars dict."""
        if typ == "intensity_range":
            use_range_var = vars_dict.get("_intensity_use_range")
            if "intensity_min" in mode_raw or "intensity_max" in mode_raw:
                if use_range_var:
                    use_range_var.set(True)
                for rk in ("intensity_min", "intensity_max"):
                    if rk in mode_raw:
                        rv = vars_dict.get(rk)
                        if rv:
                            rv.set(int(mode_raw[rk]))
            else:
                val = mode_raw.get(key)
                var = vars_dict.get(key)
                if val is not None and var is not None:
                    var.set(int(val))
            return
        if typ == "interval_range":
            use_range_var = vars_dict.get("_interval_use_range")
            if "interval_min" in mode_raw or "interval_max" in mode_raw:
                if use_range_var:
                    use_range_var.set(True)
                for rk in ("interval_min", "interval_max"):
                    if rk in mode_raw:
                        rv = vars_dict.get(rk)
                        if rv:
                            rv.set(str(mode_raw[rk]))
            else:
                val = mode_raw.get(key)
                var = vars_dict.get(key)
                if val is not None and var is not None:
                    var.set(str(val))
            return
        val = mode_raw.get(key)
        var = vars_dict.get(key)
        if val is None or var is None:
            return
        if typ == "bool":
            var.set(bool(val))
        elif typ == "intensity":
            var.set(int(val))
        elif typ == "str":
            var.set(", ".join(val) if isinstance(val, list) else str(val))
        else:
            var.set(str(val))

    # ── mode object builders ──────────────────────────────────────────────────

    def _make_mode_from_entry(self, entry: ModeEntry) -> object:
        mode_name = entry.name_var.get()
        mode_cls, config_cls = get_mode(mode_name)
        params: dict = {"name": mode_name}
        for key, _, typ, _ in MODE_FIELDS[mode_name]:
            params.update(self._field_to_params(typ, key, entry.params_vars))
        return mode_cls(config_cls.model_validate(params))

    def _make_global_modes(self) -> list:
        return [self._make_mode_from_entry(e) for e in self._global_mode_entries]

    def _make_player_modes(self, port: int) -> list:
        entries = self._player_mode_entries[port]
        if not entries:
            return self._make_global_modes()
        return [self._make_mode_from_entry(e) for e in entries]

    # ── log ──────────────────────────────────────────────────────────────────

    def _append_log(self, msg: str) -> None:
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    def _poll_logs(self) -> None:
        try:
            while True:
                self._append_log(self._log_q.get_nowait())
        except queue.Empty:
            pass
        self.after(100, self._poll_logs)

    # ── config file ops ───────────────────────────────────────────────────────

    def _browse(self) -> None:
        p = filedialog.askopenfilename(
            title="Select config file",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")],
        )
        if p:
            self._config_var.set(p)
            self._load_config()

    def _pick_dir(self, var: tk.StringVar) -> None:
        p = filedialog.askdirectory(title="Select folder")
        if p:
            var.set(p)

    def _pick_file(self, var: tk.StringVar) -> None:
        p = filedialog.askopenfilename(title="Select file")
        if p:
            var.set(p)

    def _load_config(self) -> None:
        import tomllib

        path = Path(self._config_var.get())
        try:
            cfg = config_module.load(path)
            with open(path, "rb") as f:
                raw = tomllib.load(f)
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Config: {e}")
            return

        logging.getLogger().setLevel(logging.DEBUG if cfg.debug else logging.INFO)

        self._source_var.set(cfg.source)
        self._on_source_changed(cfg.source)

        self._dolphin_path_var.set(str(cfg.dolphin_path) if cfg.dolphin_path else "")
        self._iso_path_var.set(str(cfg.iso_path) if cfg.iso_path else "")
        self._wii_ip_var.set(cfg.wii_ip or "")
        self._wii_port_var.set(str(cfg.wii_port))
        self._debug_var.set(cfg.debug)
        self._intensity_var.set(
            cfg.global_max_intensity if cfg.global_max_intensity is not None else 0
        )

        for entry in self._global_mode_entries:
            entry.frame.destroy()
        self._global_mode_entries.clear()
        for mode_raw in raw.get("modes", []):
            mode_name = mode_raw.get("name", "damage")
            entry = self._add_global_mode(mode_name)
            self._load_mode_fields(mode_raw, mode_name, entry.params_vars)

        raw_players = raw.get("players", {})
        for port in range(1, 5):
            for entry in self._player_mode_entries[port]:
                entry.frame.destroy()
            self._player_mode_entries[port].clear()

            if port in cfg.players:
                player_cfg = cfg.players[port]
                self._player_vars[port].set(player_cfg.output_mode)
                if player_cfg.output_mode != "disabled":
                    player_raw = raw_players.get(str(port), {})
                    for mode_raw in player_raw.get("modes", []):
                        mode_name = mode_raw.get("name", "damage")
                        entry = self._add_player_mode(port, mode_name)
                        self._load_mode_fields(mode_raw, mode_name, entry.params_vars)
            else:
                self._player_vars[port].set("disabled")
            self._update_player_global_label(port)

        logger.info(f"Loaded {path.name}")

    def _load_mode_fields(
        self, mode_raw: dict, mode_name: str, vars_dict: dict[str, tk.Variable]
    ) -> None:
        for key, _, typ, _ in MODE_FIELDS.get(mode_name, []):
            self._load_field_from_raw(typ, key, mode_raw, vars_dict)

    def _save_config(self) -> None:
        path = Path(self._config_var.get())
        try:
            path.write_text(self._build_toml(), encoding="utf-8")
            logger.info(f"Saved {path.name}")
        except Exception as e:
            logger.error(f"Save failed: {e}")

    def _build_toml(self) -> str:
        lines: list[str] = []

        gmax = self._intensity_var.get()
        lines += [f"global_max_intensity = {gmax}", ""]

        source_type = self._source_var.get()
        lines.append("[source]")
        lines.append(f'type = "{source_type}"')
        if source_type == "dolphin":
            dp = self._dolphin_path_var.get().strip()
            if dp:
                lines.append(f'path = "{dp}"')
            ip = self._iso_path_var.get().strip()
            if ip:
                lines.append(f'iso = "{ip}"')
        else:
            wii_ip = self._wii_ip_var.get().strip()
            if wii_ip:
                lines.append(f'ip = "{wii_ip}"')
            wii_port = self._wii_port_var.get().strip()
            if wii_port and wii_port != "51441":
                lines.append(f"port = {wii_port}")
        lines += [f"debug = {'true' if self._debug_var.get() else 'false'}", ""]

        for entry in self._global_mode_entries:
            mode_name = entry.name_var.get()
            lines += ["[[modes]]", f'name = "{mode_name}"']
            lines += self._mode_field_lines(mode_name, entry.params_vars)
            lines.append("")

        active = {p for p in range(1, 5) if self._player_vars[p].get() != "disabled"}
        for port in sorted(active):
            lines += [
                f"[players.{port}]",
                f'output_mode = "{self._player_vars[port].get()}"',
                "",
            ]
            for entry in self._player_mode_entries[port]:
                mode_name = entry.name_var.get()
                lines += [f"[[players.{port}.modes]]", f'name = "{mode_name}"']
                lines += self._mode_field_lines(mode_name, entry.params_vars)
                lines.append("")

        return "\n".join(lines)

    def _mode_field_lines(
        self, mode_name: str, vars_dict: dict[str, tk.Variable]
    ) -> list[str]:
        lines: list[str] = []
        for key, _, typ, _ in MODE_FIELDS[mode_name]:
            lines.extend(self._field_to_toml(typ, key, vars_dict))
        return lines

    # ── connect / stop ────────────────────────────────────────────────────────

    def _on_connect(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._connect_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")
        self._worker = threading.Thread(target=self._connect_worker, daemon=True)
        self._worker.start()

    def _on_stop(self) -> None:
        self._stop_btn.configure(state="disabled")
        if self._engine:
            threading.Thread(target=self._engine.stop, daemon=True).start()

    def _set_status(self, msg: str) -> None:
        self.after(0, lambda: self._status_var.set(msg))

    def _connect_worker(self) -> None:
        try:
            ports = {p for p in range(1, 5) if self._player_vars[p].get() != "disabled"}
            if not ports:
                logger.error("No players configured — enable at least one player")
                return

            players: dict[int, Player] = {}
            for port in sorted(ports):
                try:
                    modes = self._make_player_modes(port)
                except (ValueError, ValidationError) as e:
                    logger.error(f"P{port} mode settings: {e}")
                    return
                players[port] = Player(
                    output_mode=OutputMode(self._player_vars[port].get()), modes=modes
                )

            self._set_status("Looking for PiShock…")
            try:
                api = PiShockSerialAPI(players)
            except RuntimeError as e:
                logger.error(f"PiShock: {e}")
                return

            global_max = self._intensity_var.get()
            debug = self._debug_var.get()
            logging.getLogger().setLevel(logging.DEBUG if debug else logging.INFO)

            source_type = self._source_var.get()
            if source_type == "wii":
                wii_ip = self._wii_ip_var.get().strip()
                if not wii_ip:
                    logger.error("Wii IP address is required")
                    return
                try:
                    wii_port = int(self._wii_port_var.get().strip() or "51441")
                except ValueError:
                    logger.error("Wii port must be a number")
                    return
                self._set_status("Connecting to Wii…")
                self._source = WiiSource(ip=wii_ip, port=wii_port, debug=debug)
            else:
                dolphin_path = self._dolphin_path_var.get().strip() or None
                iso_path = self._iso_path_var.get().strip() or None
                self._set_status("Connecting to Dolphin…")
                self._source = DolphinSource(
                    dolphin_path=dolphin_path, iso_path=iso_path, debug=debug
                )

            try:
                self._source.connect()
            except RuntimeError as e:
                logger.error(f"Connect failed: {e}")
                return

            self._engine = Engine(
                self._source, players, api, global_max_intensity=global_max
            )
            self._set_status("● Running")
            self.after(0, self._ui_running)
            self._engine.run()

        except Exception:
            logger.exception("Unexpected error")
        finally:
            self.after(0, self._ui_stopped)

    def _populate_shockers(self) -> None:
        for w in self._shockers_frame.winfo_children():
            w.destroy()
        api = self._engine.api
        for i, (port, shocker_id) in enumerate(api.shocker_map.items()):
            row = ctk.CTkFrame(self._shockers_frame, fg_color="transparent")
            row.grid(row=i, column=0, columnspan=3, sticky="ew", padx=(20, 8), pady=2)
            ctk.CTkLabel(
                row, text=f"P{port}  →  #{shocker_id}", anchor="w", width=130
            ).pack(side="left", padx=(0, 8))
            ctk.CTkButton(
                row,
                text="Beep",
                width=65,
                command=lambda p=port: self._test_action(p, "beep"),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                row,
                text="Vibrate",
                width=65,
                command=lambda p=port: self._test_action(p, "vibrate"),
            ).pack(side="left", padx=2)
            ctk.CTkButton(
                row,
                text="Shock",
                width=65,
                command=lambda p=port: self._test_action(p, "shock"),
            ).pack(side="left", padx=2)

    def _clear_shockers(self) -> None:
        for w in self._shockers_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self._shockers_frame, text="Not connected", text_color="gray"
        ).grid(row=0, column=0, sticky="w", padx=(20, 8), pady=4)

    def _test_action(self, port: int, action: str) -> None:
        if not self._engine:
            return
        api = self._engine.api
        intensity = self._intensity_var.get()
        duration = 300

        def run() -> None:
            try:
                if action == "beep":
                    api.beep(port, duration)
                elif action == "vibrate":
                    api.vibrate(port, intensity, duration)
                elif action == "shock":
                    api.shock(port, intensity, duration)
            except Exception as e:
                logger.error(f"Test {action} P{port}: {e}")

        threading.Thread(target=run, daemon=True).start()

    def _all_lockable_widgets(self) -> list:
        widgets = list(self._lockable)
        for entry in self._global_mode_entries:
            widgets.extend(entry.lockable)
        for entries in self._player_mode_entries.values():
            for entry in entries:
                widgets.extend(entry.lockable)
        return widgets

    def _lock_settings(self) -> None:
        for w in self._all_lockable_widgets():
            try:
                w.configure(state="disabled")
            except Exception:
                pass

    def _unlock_settings(self) -> None:
        for w in self._all_lockable_widgets():
            try:
                w.configure(state="normal")
            except Exception:
                pass

    def _ui_running(self) -> None:
        self._lock_settings()
        self._stop_btn.configure(
            state="normal", fg_color="#c0392b", hover_color="#e74c3c"
        )
        self._populate_shockers()

    def _ui_stopped(self) -> None:
        self._unlock_settings()
        self._connect_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled", fg_color="#555", hover_color="#666")
        self._status_var.set("Stopped")
        self._clear_shockers()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def on_close(self) -> None:
        if self._engine:
            self._engine.stop()
        self.destroy()


def main() -> None:
    app = App()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    import multiprocessing

    multiprocessing.freeze_support()
    main()
