# dataset_manager.py - Dataset Video Manager GUI (single-file dist)
# Metadata: .data/video_metadata.json, .data/history/, .data/previews/
# Run: python run_dataset_manager.py  or  bin\dataset_manager.bat

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
from typing import Dict, List, Optional

try:
    import cv2
except ImportError:
    cv2 = None
try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# --- metadata (was metadata_store) ---
DATA_DIR_NAME = ".data"
METADATA_FILENAME = "video_metadata.json"
HISTORY_DIR_NAME = "history"


def _get_metadata_path(dataset_dir: Path) -> Path:
    return dataset_dir / DATA_DIR_NAME / METADATA_FILENAME


def load_metadata(dataset_dir: Path) -> Dict[str, Dict[str, str]]:
    path = _get_metadata_path(dataset_dir)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    dataset_resolved = dataset_dir.resolve()
    for rel_key, v in data.items():
        if isinstance(v, dict):
            full_path = (dataset_resolved / rel_key).resolve()
            out[str(full_path)] = {"tags": v.get("tags", "") or "", "notes": v.get("notes", "") or ""}
    return out


def save_metadata(dataset_dir: Path, data: Dict[str, Dict[str, str]]) -> None:
    data_dir = dataset_dir / DATA_DIR_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    dataset_resolved = dataset_dir.resolve()
    out = {}
    for full_path_str, value in data.items():
        p = Path(full_path_str)
        try:
            rel = p.relative_to(dataset_resolved)
        except ValueError:
            rel = p
        out[str(rel)] = value
    path = _get_metadata_path(dataset_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    history_dir = data_dir / HISTORY_DIR_NAME
    history_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem, suffix = Path(METADATA_FILENAME).stem, Path(METADATA_FILENAME).suffix
    shutil.copy2(path, history_dir / f"{stem}_{timestamp}{suffix}")


def merge_with_video_list(
    video_paths: List[Path], metadata: Dict[str, Dict[str, str]]
) -> Dict[str, Dict[str, str]]:
    result = {}
    for p in video_paths:
        key = str(p.resolve())
        result[key] = metadata.get(key, {"tags": "", "notes": ""}).copy()
        result[key].setdefault("tags", "")
        result[key].setdefault("notes", "")
    return result


# --- app ---
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm"}
PREVIEWS_DIR = "previews"
PREVIEW_EXT = ".jpg"
PREVIEW_MAX_SIZE = (320, 240)


def normalize_tags(raw: str) -> str:
    if not raw or not raw.strip():
        return ""
    parts = re.split(r"[\s;,]+", raw.strip())
    return "; ".join(p.strip() for p in parts if p.strip())


def open_with_default_player(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("File not found: %s" % file_path)
    s = str(path.resolve())
    if sys.platform == "win32":
        os.startfile(s)
    elif sys.platform == "darwin":
        subprocess.run(["open", s], check=False)
    else:
        subprocess.run(["xdg-open", s], check=False)


def count_tags_in_metadata(metadata: Dict[str, Dict[str, str]]) -> Counter:
    c = Counter()
    for entry in metadata.values():
        for tag in (t.strip() for t in (entry.get("tags") or "").split(";") if t.strip()):
            c[tag] += 1
    return c


def scan_videos(dataset_dir: Path) -> List[Path]:
    if not dataset_dir.is_dir():
        return []
    return [f for f in dataset_dir.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]


def get_preview_path(dataset_dir: Path, video_path: Path) -> Path:
    try:
        rel = video_path.resolve().relative_to(dataset_dir.resolve())
    except ValueError:
        rel = video_path.name
    return dataset_dir / DATA_DIR_NAME / PREVIEWS_DIR / (hashlib.md5(str(rel).encode("utf-8")).hexdigest() + PREVIEW_EXT)


def generate_one_preview(video_path: Path, preview_path: Path) -> bool:
    if cv2 is None:
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
    cap.set(cv2.CAP_PROP_POS_MSEC, 500)
    ret, frame = cap.read()
    if not ret:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return False
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(preview_path), frame)
    return True


class EditDialog:
    def __init__(self, parent: tk.Widget, tags: str, notes: str, title: str = "Edit metadata"):
        self.result = None
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        self.win.transient(parent)
        self.win.grab_set()
        ttk.Label(self.win, text="Tags (semicolon, comma or space separated):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.tags_var = tk.StringVar(value=tags)
        ttk.Entry(self.win, textvariable=self.tags_var, width=50).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Label(self.win, text="Notes:").grid(row=1, column=0, sticky="nw", padx=5, pady=5)
        self.notes_text = tk.Text(self.win, width=50, height=6, wrap="word")
        self.notes_text.insert("1.0", notes)
        self.notes_text.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.win.columnconfigure(1, weight=1)
        self.win.rowconfigure(1, weight=1)
        btn_f = ttk.Frame(self.win)
        btn_f.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_f, text="OK", command=self._ok).pack(side="left", padx=5)
        ttk.Button(btn_f, text="Cancel", command=self._cancel).pack(side="left", padx=5)
        self.win.protocol("WM_DELETE_WINDOW", self._cancel)
        self.win.geometry("+%d+%d" % (parent.winfo_rootx() + 50, parent.winfo_rooty() + 50))

    def _ok(self):
        self.result = {"tags": normalize_tags(self.tags_var.get()), "notes": self.notes_text.get("1.0", "end").strip()}
        self.win.destroy()

    def _cancel(self):
        self.result = None
        self.win.destroy()

    def run(self):
        self.win.wait_window()
        return self.result


class DatasetManagerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dataset Video Manager")
        self.root.minsize(600, 400)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self._dataset_dir = None
        self._video_paths = []
        self._metadata = {}
        self._export_selected = set()
        self._inline_entry = None
        self._inline_iid = None
        self._inline_col = None
        self._preview_photo = None
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=5)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)
        ttk.Button(top, text="Select directory", command=self._on_select_dir).grid(row=0, column=0, padx=5, pady=5)
        self._dir_label = ttk.Label(top, text="(no directory selected)")
        self._dir_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(top, text="Refresh", command=self._on_refresh).grid(row=1, column=0, padx=5, pady=2)
        br = ttk.Frame(top)
        br.grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Button(br, text="Edit", command=self._on_edit).pack(side="left", padx=2)
        ttk.Button(br, text="Save", command=self._on_save).pack(side="left", padx=2)
        ttk.Button(br, text="Export", command=self._on_export).pack(side="left", padx=2)
        content = ttk.Frame(self.root, padding=5)
        content.grid(row=1, column=0, sticky="nsew")
        self.root.rowconfigure(1, weight=1)
        self.root.columnconfigure(0, weight=1)
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)
        table_f = ttk.Frame(content)
        table_f.grid(row=0, column=0, sticky="nsew")
        table_f.columnconfigure(0, weight=1)
        table_f.rowconfigure(0, weight=1)
        cols = ("check", "filename", "path", "tags", "notes")
        self._tree = ttk.Treeview(table_f, columns=cols, show="headings", selectmode="browse", height=20)
        self._tree.heading("check", text="")
        self._tree.heading("filename", text="Filename")
        self._tree.heading("path", text="Path (relative to selected folder)")
        self._tree.heading("tags", text="Tags (, or ; or space separated)")
        self._tree.heading("notes", text="Notes")
        self._tree.column("check", width=36)
        self._tree.column("filename", width=120)
        self._tree.column("path", width=280)
        self._tree.column("tags", width=150)
        self._tree.column("notes", width=200)
        self._tree.grid(row=0, column=0, sticky="nsew")
        self._tree.bind("<Button-1>", self._on_tree_click)
        self._tree.bind("<Double-1>", self._on_tree_double_click)
        sb = ttk.Scrollbar(table_f, orient="vertical", command=self._tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._tree.configure(yscrollcommand=sb.set)
        prev_f = ttk.LabelFrame(content, text="Preview", padding=5)
        prev_f.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        content.columnconfigure(1, weight=0, minsize=PREVIEW_MAX_SIZE[0] + 20)
        prev_f.columnconfigure(0, weight=1)
        prev_f.rowconfigure(1, weight=1)
        self._preview_label = ttk.Label(prev_f, text="Select a video.", anchor="center")
        self._preview_label.grid(row=0, column=0, pady=(0, 5))
        self._preview_image_label = tk.Label(prev_f, text="", bg="#e0e0e0", width=PREVIEW_MAX_SIZE[0] // 8, height=PREVIEW_MAX_SIZE[1] // 8)
        self._preview_image_label.grid(row=1, column=0, sticky="nsew")
        self._tree.bind("<<TreeviewSelect>>", lambda e: self._on_selection_change())
        status_f = ttk.Frame(self.root, padding=(5, 5))
        status_f.grid(row=2, column=0, sticky="ew")
        self.root.rowconfigure(2, minsize=110)
        status_f.columnconfigure(0, weight=1)
        for r in range(4):
            status_f.rowconfigure(r, minsize=20)
        ttk.Label(status_f, text="Tags: semicolon, comma or space separated. Stored as semicolon-separated.", font=("TkDefaultFont", 8)).grid(row=0, column=0, sticky="w", padx=0, pady=1)
        self._status = ttk.Label(status_f, text="Select a directory to list videos.")
        self._status.grid(row=1, column=0, sticky="w", padx=0, pady=1)
        self._status_tags = ttk.Label(status_f, text="", font=("TkDefaultFont", 8), wraplength=700)
        self._status_tags.grid(row=2, column=0, sticky="w", padx=0, pady=1)
        self._status_untagged = ttk.Label(status_f, text="", font=("TkDefaultFont", 8))
        self._status_untagged.grid(row=3, column=0, sticky="w", padx=0, pady=1)

    def _on_select_dir(self):
        path = filedialog.askdirectory(title="Select dataset directory")
        if path:
            self._dataset_dir = Path(path)
            self._dir_label.config(text=str(self._dataset_dir))
            self._refresh_table()

    def _refresh_table(self):
        for i in self._tree.get_children():
            self._tree.delete(i)
        if not self._dataset_dir or not self._dataset_dir.is_dir():
            self._status.config(text="Select a directory to list videos.")
            self._status_tags.config(text="")
            self._status_untagged.config(text="")
            self._preview_label.config(text="Select a video.")
            self._clear_preview_image()
            return
        self._export_selected.clear()
        self._video_paths = sorted(scan_videos(self._dataset_dir))
        self._metadata = merge_with_video_list(self._video_paths, load_metadata(self._dataset_dir))
        for p in self._video_paths:
            key = str(p.resolve())
            try:
                rp = p.relative_to(self._dataset_dir)
            except ValueError:
                rp = p
            m = self._metadata.get(key, {"tags": "", "notes": ""})
            check_mark = "\u2611" if key in self._export_selected else "\u2610"
            self._tree.insert("", "end", values=(check_mark, p.name, str(rp), m.get("tags", ""), m.get("notes", "")), iid=key)
        self._status.config(text="%d video(s) (including subfolders)." % len(self._video_paths))
        tc = count_tags_in_metadata(self._metadata)
        if tc:
            self._status_tags.config(text="Tag counts: " + ", ".join("%s (%d)" % (t, c) for t, c in sorted(tc.items(), key=lambda x: (-x[1], x[0]))))
        else:
            self._status_tags.config(text="Tag counts: (none)")
        n = sum(1 for v in self._metadata.values() if not (v.get("tags") or "").strip())
        self._status_untagged.config(text="Files without tags: %d" % n)
        self._start_preview_generation()

    def _on_selection_change(self):
        sel = self._tree.selection()
        if not sel or not self._dataset_dir:
            self._preview_label.config(text="Select a video.")
            self._clear_preview_image()
            return
        iid = sel[0]
        pp = get_preview_path(self._dataset_dir, Path(iid))
        if pp.exists():
            self._show_preview_image(str(pp))
            self._preview_label.config(text=Path(iid).name)
        else:
            self._preview_label.config(text=Path(iid).name + " (no preview yet)")
            self._clear_preview_image()

    def _show_preview_image(self, path: str):
        if Image is None or ImageTk is None:
            self._preview_image_label.config(image="", text="(PIL required)")
            return
        try:
            img = Image.open(path)
            img.thumbnail(PREVIEW_MAX_SIZE, getattr(Image, "LANCZOS", Image.BICUBIC))
            self._preview_photo = ImageTk.PhotoImage(img)
            self._preview_image_label.config(image=self._preview_photo, text="")
        except Exception:
            self._preview_image_label.config(image="", text="(load error)")

    def _clear_preview_image(self):
        self._preview_photo = None
        self._preview_image_label.config(image="", text="", bg="#e0e0e0")

    def _start_preview_generation(self):
        if not self._dataset_dir or not self._video_paths or cv2 is None:
            return
        dd, vps = self._dataset_dir, list(self._video_paths)
        def gen():
            for p in vps:
                pp = get_preview_path(dd, p)
                if pp.exists():
                    continue
                generate_one_preview(p, pp)
                self.root.after(0, lambda pth=pp: self._maybe_update_preview(pth))
        threading.Thread(target=gen, daemon=True).start()

    def _maybe_update_preview(self, new_path: Path):
        sel = self._tree.selection()
        if not sel or not self._dataset_dir:
            return
        iid = sel[0]
        if new_path.resolve() == get_preview_path(self._dataset_dir, Path(iid)).resolve():
            self._show_preview_image(str(new_path))
            self._preview_label.config(text=Path(iid).name)

    def _on_refresh(self):
        if self._dataset_dir:
            self._refresh_table()
        else:
            messagebox.showinfo("Info", "Please select a directory first.")

    def _on_tree_double_click(self, e):
        if self._tree.identify_region(e.x, e.y) != "cell":
            self._on_edit()
            return
        if self._tree.identify_column(e.x) == "#2":
            iid = self._tree.identify_row(e.y)
            if iid:
                try:
                    open_with_default_player(iid)
                except FileNotFoundError as ex:
                    messagebox.showerror("Error", str(ex))
                except OSError as ex:
                    messagebox.showerror("Error", "Failed to open: %s" % ex)
            return
        self._on_edit()

    def _on_tree_click(self, e):
        self._commit_inline()
        if self._tree.identify_region(e.x, e.y) != "cell":
            return
        iid = self._tree.identify_row(e.y)
        col = self._tree.identify_column(e.x)
        if col == "#1":
            if iid:
                vals = list(self._tree.item(iid)["values"])
                if iid in self._export_selected:
                    self._export_selected.discard(iid)
                    vals[0] = "\u2610"
                else:
                    self._export_selected.add(iid)
                    vals[0] = "\u2611"
                self._tree.item(iid, values=vals)
            return
        if col == "#4":
            self._start_inline_edit(iid, 3)
        elif col == "#5":
            self._start_inline_edit(iid, 4)

    def _start_inline_edit(self, iid: str, col_index: int):
        bbox = self._tree.bbox(iid, col_index)
        if not bbox:
            return
        vals = list(self._tree.item(iid)["values"])
        cur = vals[col_index] if col_index < len(vals) else ""
        self._inline_entry = tk.Entry(self._tree)
        self._inline_entry.insert(0, cur)
        self._inline_entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        self._inline_entry.focus_set()
        self._inline_entry.select_range(0, tk.END)
        self._inline_iid, self._inline_col = iid, col_index
        def on_ret(ev):
            self._commit_inline()
            return "break"
        def on_fo(ev):
            ew = self._inline_entry
            def d():
                if self._inline_entry is ew:
                    self._commit_inline()
            self.root.after(100, d)
        self._inline_entry.bind("<Return>", on_ret)
        self._inline_entry.bind("<Escape>", lambda ev: self._cancel_inline())
        self._inline_entry.bind("<FocusOut>", on_fo)

    def _commit_inline(self):
        if self._inline_entry is None:
            return
        val = self._inline_entry.get().strip()
        iid, col = self._inline_iid, self._inline_col
        self._inline_entry.destroy()
        self._inline_entry = self._inline_iid = self._inline_col = None
        self._metadata.setdefault(iid, {"tags": "", "notes": ""})
        if col == 3:
            val = normalize_tags(val)
            self._metadata[iid]["tags"] = val
        else:
            self._metadata[iid]["notes"] = val
        vals = list(self._tree.item(iid)["values"])
        while len(vals) <= col:
            vals.append("")
        vals[col] = val
        self._tree.item(iid, values=vals)

    def _cancel_inline(self):
        if self._inline_entry is None:
            return
        self._inline_entry.destroy()
        self._inline_entry = self._inline_iid = self._inline_col = None

    def _on_edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Select a row to edit.")
            return
        iid = sel[0]
        it = self._tree.item(iid)
        tags, notes = it["values"][3], it["values"][4]
        dlg = EditDialog(self.root, tags=tags, notes=notes, title="Edit tags and notes")
        res = dlg.run()
        if res is not None:
            self._metadata[iid] = res
            self._tree.item(iid, values=(it["values"][0], it["values"][1], it["values"][2], res["tags"], res["notes"]))

    def _on_save(self):
        if not self._dataset_dir:
            messagebox.showinfo("Info", "Please select a directory first.")
            return
        try:
            save_metadata(self._dataset_dir, self._metadata)
            tc = count_tags_in_metadata(self._metadata)
            if tc:
                print("Tag counts (saved):")
                for t, c in sorted(tc.items(), key=lambda x: (-x[1], x[0])):
                    print("  %s: %d" % (t, c))
            else:
                print("Tag counts (saved): (none)")
            sp = self._dataset_dir / DATA_DIR_NAME / METADATA_FILENAME
            self._status.config(text="Saved to %s" % sp)
            if tc:
                self._status_tags.config(text="Tag counts: " + ", ".join("%s (%d)" % (t, c) for t, c in sorted(tc.items(), key=lambda x: (-x[1], x[0]))))
            else:
                self._status_tags.config(text="Tag counts: (none)")
            n = sum(1 for v in self._metadata.values() if not (v.get("tags") or "").strip())
            self._status_untagged.config(text="Files without tags: %d" % n)
        except OSError as ex:
            messagebox.showerror("Error", "Failed to save: %s" % ex)

    def _on_export(self):
        if not self._export_selected:
            messagebox.showinfo("Info", "No files selected for export.")
            return
        path = filedialog.asksaveasfilename(
            title="Export selected file paths",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for p in sorted(self._export_selected):
                    f.write(p + "\n")
            messagebox.showinfo("Info", "Exported %d path(s) to %s" % (len(self._export_selected), path))
        except OSError as ex:
            messagebox.showerror("Error", "Failed to export: %s" % ex)

    def run(self):
        self.root.mainloop()


def run_dataset_manager():
    DatasetManagerApp().run()
