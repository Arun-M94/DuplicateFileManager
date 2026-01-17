import tkinter as tk
from PIL import Image, ImageTk
from tkinter import ttk, filedialog, messagebox, font
from collections import defaultdict

from core.scanner import scan_for_duplicates
from core.actions import safe_delete, safe_move
from core.utils import choose_original, human_readable_size
from ui.tooltip import ToolTip
import os
import sys
import subprocess
import threading

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    base_dir = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base_dir, relative_path)


class DuplicateManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Duplicate File Manager")
        icon_path = resource_path("assets/duplicate_file_manager.ico")
        self.root.iconbitmap(icon_path)
        # Taskbar (modern Windows)
        img = Image.open(icon_path)
        photo = ImageTk.PhotoImage(img)
        self.root.iconphoto(True, photo)
        self.root.geometry("1000x600")
        self.path = tk.StringVar()
        self.status = tk.StringVar()
        self.stop_scan = False
        self.duplicates = {}
        self.column_percentages = {
            "group": 0.10,
            "name": 0.30,
            "size": 0.15,
            "path": 0.45
        }
        self.file_type_var = tk.StringVar(value="All")
        self.file_type_options = {
            "All": None,
            "Images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"),
            "Videos": (".mp4", ".avi", ".mkv", ".mov", ".wmv"),
            "Documents": (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"),
            "Others": "others"
        }
        self.message_var = tk.StringVar()
        self.message_label = ttk.Label(
            self.root,
            textvariable=self.message_var,
            anchor="w",
            relief="sunken",
            padding=(6, 4)
        )
        self.message_label.pack(fill="x", side="bottom")
        self._build_ui()

    def _build_ui(self):
        # ---------- TOP BAR ----------
        top = ttk.Frame(self.root)
        top.pack(fill='x', padx=10, pady=5)

        ttk.Entry(top, textvariable=self.path, width=60).pack(side='left')
        btn_browse = ttk.Button(top, text="Browse", command=self.browse)
        btn_browse.pack(side='left', padx=5)
        btn_scan = ttk.Button(top, text="Scan", command=self.scan)
        btn_scan.pack(side='left')
        ToolTip(btn_scan, "Search for Duplicate Files!", delay=300)
        ToolTip(btn_browse, "Select Folder or drive.",delay=300)

        self.file_type_combo = ttk.Combobox(
            top,
            textvariable=self.file_type_var,
            values=list(self.file_type_options.keys()),
            state="disabled",
            width=15
        )
        self.file_type_combo.pack(side="left", padx=5)
        self.file_type_combo.bind("<<ComboboxSelected>>", self.apply_file_type_filter)
        ToolTip(self.file_type_combo, "Filter results.",delay=300)
        
        # Close button (always visible)
        btn_close = ttk.Button(top, text="Exit", command=self.close_app, width=5)
        btn_close.pack(side="right")
        ToolTip(btn_close, "Exit Application.", delay=300)

        # ---------- TREEVIEW CONTAINER ----------
        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("group", "name", "size", "path")
        self.tree = ttk.Treeview(
            container,
            columns=cols,
            show='headings',
            selectmode='extended'
        )

        for c in cols:
            self.tree.heading(c, text=c.title())

        self.vsb = ttk.Scrollbar(
            container,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(yscrollcommand=self.on_treeview_scroll)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        self.tree.bind("<Double-1>", self.on_treeview_double_click)
        self.tree.bind("<Motion>", self.on_treeview_motion)
        self.tree.bind("<Configure>", self.on_treeview_resize)

        # ---------- BOTTOM BAR ----------
        bottom = ttk.Frame(self.root)
        bottom.pack(fill='x', padx=10, pady=5)

        btn_delete = ttk.Button(bottom, text="Delete", command=self.delete)
        btn_delete.pack(side='left')
        btn_move = ttk.Button(bottom, text="Move", command=self.move)
        btn_move.pack(side='left')
        ttk.Label(bottom, textvariable=self.status).pack(side='right')
        ToolTip(btn_delete, "Delete duplicates safely", delay=300)
        ToolTip(btn_move, "Move duplicates to common folder", delay=300)
        self.show_message("Welcome to Duplicate File Manager! Click Browse to choose the Directory.","info")
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.progress = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="indeterminate"
        )
        self.progress.pack(side="left", fill="x", expand=True)

        self.cancel_btn = ttk.Button(
            progress_frame,
            text="Cancel",
            command=self.cancel_scan,
            state="disabled",
            width=8
        )
        self.cancel_btn.pack(side="right", padx=(5, 0))
        ToolTip(self.cancel_btn, "Stop the Scanning.")



    def on_treeview_scroll(self, first, last):
        self.vsb.set(first, last)

        if float(first) <= 0.0 and float(last) >= 1.0:
            self.vsb.grid_remove()   # hide
        else:
            self.vsb.grid()          # show

    def browse(self):
        d = filedialog.askdirectory()
        if d:
            self.path.set(d)
            self.show_message(f"Directory set to {self.path.get()}!! Click Scan to list the Duplicate Files.")


    def scan(self):
        if not self.path.get():
            return
        self.tree.delete(*self.tree.get_children())
        self.show_message(f"Scanning {self.path.get()}...", "info")
        
        self.progress.start(10)
        self.stop_scan = False
        self.cancel_btn.config(state="normal")

        threading.Thread(target=self._scan_worker, daemon=True).start()        
        
        # result = scan_for_duplicates(self.path.get(), [], True, self.status.set)
        # self.duplicates = result
        # gid = 1
        # for (_, name, size), paths in result.items():
        #     for p in paths:
        #         self.tree.insert('', 'end', values=(gid, name, human_readable_size(size), p))
        #     gid += 1
        # self.all_rows_cache = [
        #     (iid, self.tree.item(iid, "values"))
        #     for iid in self.tree.get_children()
        # ]

        # self.file_type_combo.config(state="readonly")
        # all_filt = 'All'
        # # re-apply existing filter
        # if self.file_type_var.get():
        #     all_filt = self.apply_file_type_filter()


    def _scan_worker(self):
        result = scan_for_duplicates(
            self.path.get(),
            [],
            True,
            self.status.set,
            stop_callback=lambda: self.stop_scan
        )

        self.root.after(0, self._scan_complete, result)


    def _scan_complete(self, result):
        self.duplicates = result

        gid = 1
        for (_, name, size), paths in result.items():
            for p in paths:
                self.tree.insert(
                    '',
                    'end',
                    values=(gid, name, human_readable_size(size), p)
                )
            gid += 1

        self.all_rows_cache = [
            (iid, self.tree.item(iid, "values"))
            for iid in self.tree.get_children()
        ]

        self.file_type_combo.config(state="readonly")

        if self.file_type_var.get():
            self.apply_file_type_filter()

        self.progress.stop()
        self.progress["value"] = 0
        self.cancel_btn.config(state="disabled")

        # self.show_message("Scan completed", "success")


    def cancel_scan(self):
        self.stop_scan = True
        self.show_message("Scan cancelled", "warning")


    def _selected(self):
        return [self.tree.item(i)['values'] for i in self.tree.selection()]


    def _selectall(self):
        return [self.tree.item(iid, "values") for iid in self.tree.get_children()]


    def delete(self):
        sel = self._selected()
        if sel:
            to_delete = [p for _,_,_, p in sel]
            safe_delete(to_delete)
            self.scan()
            return
        
        selall = self._selectall()
        by_gid = defaultdict(list)
        for g, _, _, p in selall:
            by_gid[g].append(p)

        to_delete = []
        for gid, paths in by_gid.items():
            original, dups = choose_original(paths)
            to_delete.extend(dups)

        safe_delete(to_delete)
        self.scan()


    def move(self):
        dest = filedialog.askdirectory()
        if not dest:
            return
        
        sel = self._selected()
        if sel:
            paths = [p for _, _, _, p in sel]
            safe_move(paths, dest)
            self.scan()
            return
        
        selall = self._selectall()
        by_gid = defaultdict(list)
        for g, _, _, p in selall:
            by_gid[g].append(p)

        to_move = []
        for gid, paths in by_gid.items():
            original, dups = choose_original(paths)
            to_move.extend(dups)

        safe_move(to_move,dest)
        self.scan()


    def show_message(self, text, level="info"):
        self.message_var.set(text)

        style = {
            "info": "#1f2933",
            "warning": "#92400e",
            "error": "#991b1b"
        }

        self.message_label.configure(foreground=style.get(level, "#1f2933"))


    def apply_file_type_filter(self, event=None):
        selected = self.file_type_var.get()
        rule = self.file_type_options.get(selected)

        self.tree.delete(*self.tree.get_children())
        count = 0
        for _, values in self.all_rows_cache:
            path = values[self.tree["columns"].index("path")]
            ext = os.path.splitext(path)[1].lower()

            if rule is None:
                match = True
            elif rule == "others":
                match = ext not in sum(
                    (v for v in self.file_type_options.values() if isinstance(v, tuple)), ()
                )
            else:
                match = ext in rule

            if match:
                self.tree.insert("", "end", values=values)
                count += 1
                # self.show_message(f"Filter applied: {selected}", "info")
        # print(selected, ' : ', match)
        if selected != "All":
            if count > 0:
                self.show_message(f"Filter applied: {selected}", "info")
            else:
                self.show_message("No duplicates found for the applied filter", "info")
        else:
            if count > 0:
                self.show_message("Duplicate Items displayed!! Select Files to be Delete/Move or Simply Click Delete/Move button to process all the Duplicates.","info")
            else:
                self.show_message("No duplicates found!! Directory is clean.", "info")


    def autosize_single_column(self, col, padding=20, max_rows=200):
        tree_font = font.nametofont("TkDefaultFont")

        max_width = tree_font.measure(col)

        for item in self.tree.get_children()[:max_rows]:
            cell_value = self.tree.set(item, col)
            max_width = max(max_width, tree_font.measure(str(cell_value)))

        self.tree.column(col, width=max_width + padding)

    def apply_percentage_column_widths(self):
        total_width = self.tree.winfo_width()

        # Prevent zero-width on startup
        if total_width <= 1:
            self.root.after(100, self.apply_percentage_column_widths)
            return

        for col, pct in self.column_percentages.items():
            width = int(total_width * pct)
            self.tree.column(col, width=width, stretch=False)


    def on_treeview_resize(self, event):
        self.apply_percentage_column_widths()


    def on_treeview_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)

        if region == "separator":
            column_id = self.tree.identify_column(event.x)
            col_index = int(column_id.replace("#", "")) - 1
            col_name = self.tree["columns"][col_index]

            self.autosize_single_column(col_name)
        
        if region == "cell":
            item_id = self.tree.focus()
            if not item_id:
                return

            values = self.tree.item(item_id, "values")
            if not values or len(values) < 4:
                return

            file_path = values[3]  # path column

            if not os.path.exists(file_path):
                self.status.set("File not found.")
                self.show_message("File not found.","warning")
                return

            try:
                if sys.platform.startswith("win"):
                    os.startfile(file_path)   # Windows (best)
                elif sys.platform == "darwin":
                    subprocess.call(["open", file_path])
                else:
                    subprocess.call(["xdg-open", file_path])
            except Exception as e:
                self.status.set(f"Failed to open file: {e}")
                self.show_message(f"Failed to open file: {e}", "error")
        
        return


    def on_treeview_motion(self, event):
        region = self.tree.identify_region(event.x, event.y)
        cursor = "sb_h_double_arrow" if region == "separator" else ""
        self.tree.configure(cursor=cursor)


    def close_app(self):
        if messagebox.askokcancel("Exit", "Are you sure you want to exit?"):
            self.root.quit()
            self.root.destroy()
