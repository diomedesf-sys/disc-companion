"""
app.py — Main Disk Companion application window.
Built with CustomTkinter for a modern dark-mode desktop UI.
"""

import os
import string
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk

from scanner import Scanner, FolderNode
from categorizer import format_size, get_category_badge, CATEGORIES
from gemini_client import ask_gemini

# ── Theme ─────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Color palette
BG_DARK    = "#111827"   # main background
BG_PANEL   = "#1F2937"   # panel background
BG_ROW     = "#1F2937"   # tree row
BG_HOVER   = "#374151"   # row hover
ACCENT     = "#14B8A6"   # teal accent
ACCENT2    = "#6366F1"   # indigo for AI chat
TEXT_MAIN  = "#F9FAFB"
TEXT_DIM   = "#9CA3AF"
TEXT_TINY  = "#6B7280"
BORDER     = "#374151"

# Category badge colors
BADGE_COLORS = {
    "system":   "#EF4444",
    "code":     "#3B82F6",
    "games":    "#8B5CF6",
    "media":    "#F59E0B",
    "docs":     "#10B981",
    "archives": "#F97316",
    "unknown":  "#6B7280",
}


class DiskCompanion(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Disk Companion")
        self.geometry("1280x800")
        self.minsize(900, 600)
        self.configure(fg_color=BG_DARK)

        self.root_node: FolderNode | None = None
        self.scanner = Scanner(
            on_progress=self._on_scan_progress,
            on_complete=self._on_scan_complete,
            on_error=self._on_scan_error,
        )
        self._selected_node: FolderNode | None = None
        self._chat_messages: list[tuple[str, str]] = []  # (role, text)
        self._tree_nodes: dict[str, FolderNode] = {}  # tree_item_id → FolderNode

        self._build_ui()

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        self._build_main_area()
        self._build_status_bar()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=BG_PANEL, height=56, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Logo
        logo = ctk.CTkLabel(
            header,
            text="🗂  Disk Companion",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT_MAIN,
        )
        logo.pack(side="left", padx=20)

        # Right controls
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", padx=16)

        self.rescan_btn = ctk.CTkButton(
            controls,
            text="↺  Rescan",
            width=100,
            height=32,
            fg_color=ACCENT,
            hover_color="#0D9488",
            text_color=BG_DARK,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._trigger_rescan,
            corner_radius=8,
        )
        self.rescan_btn.pack(side="right", padx=(8, 0))

        self.drive_var = ctk.StringVar(value="Select a drive or folder…")
        self.drive_btn = ctk.CTkButton(
            controls,
            textvariable=self.drive_var,
            width=220,
            height=32,
            fg_color=BG_DARK,
            hover_color=BG_HOVER,
            text_color=TEXT_MAIN,
            border_width=1,
            border_color=BORDER,
            font=ctk.CTkFont(size=13),
            command=self._select_drive,
            corner_radius=8,
        )
        self.drive_btn.pack(side="right")

        # Quick drive shortcuts
        drives = self._get_available_drives()
        for drive in drives[:4]:
            btn = ctk.CTkButton(
                controls,
                text=drive,
                width=44,
                height=32,
                fg_color=BG_DARK,
                hover_color=BG_HOVER,
                text_color=TEXT_DIM,
                border_width=1,
                border_color=BORDER,
                font=ctk.CTkFont(size=12),
                command=lambda d=drive: self._start_scan(d),
                corner_radius=8,
            )
            btn.pack(side="right", padx=4)

    def _build_main_area(self):
        # Main container splits into left+right (top) and chat (bottom)
        main = ctk.CTkFrame(self, fg_color=BG_DARK)
        main.pack(fill="both", expand=True, padx=0, pady=0)

        # Top area: tree | detail
        top = ctk.CTkFrame(main, fg_color=BG_DARK)
        top.pack(fill="both", expand=True)

        # Folder Tree (left panel)
        self._build_tree_panel(top)

        # Detail Panel (right panel)
        self._build_detail_panel(top)

        # Chat Panel (bottom)
        self._build_chat_panel(main)

    def _build_tree_panel(self, parent):
        left = ctk.CTkFrame(parent, fg_color=BG_PANEL, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)

        # Panel header
        ph = ctk.CTkFrame(left, fg_color="transparent", height=40)
        ph.pack(fill="x", padx=12, pady=(10, 0))
        ph.pack_propagate(False)

        ctk.CTkLabel(
            ph, text="Folder Tree", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN,
        ).pack(side="left")

        # Search bar
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search_change)
        search = ctk.CTkEntry(
            left,
            placeholder_text="🔍  Search folders…",
            textvariable=self.search_var,
            height=32,
            fg_color=BG_DARK,
            border_color=BORDER,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_TINY,
            font=ctk.CTkFont(size=12),
            corner_radius=8,
        )
        search.pack(fill="x", padx=12, pady=8)

        # Category filter buttons
        filter_frame = ctk.CTkFrame(left, fg_color="transparent")
        filter_frame.pack(fill="x", padx=12, pady=(0, 6))

        self.active_filter = ctk.StringVar(value="all")
        filter_btn = ctk.CTkButton(
            filter_frame, text="All", width=40, height=24,
            fg_color=ACCENT, hover_color="#0D9488", text_color=BG_DARK,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=lambda: self._set_filter("all"),
        )
        filter_btn.pack(side="left", padx=(0, 4))

        for cat_id, (emoji, label) in list(CATEGORIES.items())[:6]:
            color = BADGE_COLORS.get(cat_id, "#6B7280")
            b = ctk.CTkButton(
                filter_frame, text=emoji, width=28, height=24,
                fg_color=color, hover_color=color,
                text_color="white", font=ctk.CTkFont(size=11),
                corner_radius=6,
                command=lambda c=cat_id: self._set_filter(c),
            )
            b.pack(side="left", padx=2)

        # Treeview with scrollbar
        tree_container = ctk.CTkFrame(left, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Disk.Treeview",
            background=BG_PANEL,
            foreground=TEXT_MAIN,
            fieldbackground=BG_PANEL,
            borderwidth=0,
            font=("Segoe UI", 11),
            rowheight=28,
        )
        style.configure("Disk.Treeview.Heading", background=BG_DARK, foreground=TEXT_DIM, font=("Segoe UI", 10))
        style.map("Disk.Treeview", background=[("selected", BG_HOVER)], foreground=[("selected", TEXT_MAIN)])

        self.tree = ttk.Treeview(
            tree_container,
            style="Disk.Treeview",
            columns=("size", "category"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Folder", anchor="w")
        self.tree.heading("size", text="Size", anchor="e")
        self.tree.heading("category", text="Type", anchor="w")
        self.tree.column("#0", width=260, minwidth=160, stretch=True)
        self.tree.column("size", width=90, minwidth=70, anchor="e", stretch=False)
        self.tree.column("category", width=120, minwidth=80, stretch=False)

        vsb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<<TreeviewOpen>>", self._on_tree_open)

        # Welcome message
        self.tree_placeholder = ctk.CTkLabel(
            left,
            text="Select a drive above to begin scanning.",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_TINY,
        )
        self.tree_placeholder.place(relx=0.5, rely=0.55, anchor="center")

    def _build_detail_panel(self, parent):
        right = ctk.CTkFrame(parent, fg_color=BG_PANEL, corner_radius=10, width=340)
        right.pack(side="right", fill="y", padx=(4, 8), pady=8)
        right.pack_propagate(False)

        ctk.CTkLabel(
            right, text="Folder Details",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_MAIN,
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.detail_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.detail_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._detail_placeholder = ctk.CTkLabel(
            self.detail_scroll,
            text="Click a folder\nto see details.",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_TINY,
        )
        self._detail_placeholder.pack(pady=60)

    def _build_chat_panel(self, parent):
        self.chat_frame = ctk.CTkFrame(parent, fg_color=BG_PANEL, corner_radius=10, height=220)
        self.chat_frame.pack(fill="x", padx=8, pady=(0, 8))
        self.chat_frame.pack_propagate(False)

        chat_header = ctk.CTkFrame(self.chat_frame, fg_color="transparent", height=36)
        chat_header.pack(fill="x", padx=12, pady=(4, 0))
        chat_header.pack_propagate(False)

        ctk.CTkLabel(
            chat_header, text="✨  Ask Gemini",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT_MAIN,
        ).pack(side="left")

        self.gemini_status = ctk.CTkLabel(
            chat_header, text="● ready",
            font=ctk.CTkFont(size=11),
            text_color=ACCENT,
        )
        self.gemini_status.pack(side="right")

        # Chat history
        self.chat_history = ctk.CTkTextbox(
            self.chat_frame,
            fg_color=BG_DARK,
            text_color=TEXT_MAIN,
            font=ctk.CTkFont(size=12, family="Segoe UI"),
            border_width=0,
            corner_radius=8,
            state="disabled",
        )
        self.chat_history.pack(fill="both", expand=True, padx=8, pady=(4, 4))

        # Input row
        input_row = ctk.CTkFrame(self.chat_frame, fg_color="transparent", height=40)
        input_row.pack(fill="x", padx=8, pady=(0, 8))
        input_row.pack_propagate(False)

        self.chat_input = ctk.CTkEntry(
            input_row,
            placeholder_text="Ask about your disk… e.g. 'What is the biggest folder?'",
            fg_color=BG_DARK,
            border_color=BORDER,
            text_color=TEXT_MAIN,
            placeholder_text_color=TEXT_TINY,
            font=ctk.CTkFont(size=12),
            corner_radius=8,
            height=36,
        )
        self.chat_input.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chat_input.bind("<Return>", lambda e: self._send_chat())

        send_btn = ctk.CTkButton(
            input_row,
            text="Send ↵",
            width=80,
            height=36,
            fg_color=ACCENT2,
            hover_color="#4F46E5",
            text_color="white",
            font=ctk.CTkFont(size=12, weight="bold"),
            corner_radius=8,
            command=self._send_chat,
        )
        send_btn.pack(side="right")

    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color=BG_PANEL, height=26, corner_radius=0)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            bar, text="Ready. Select a drive to start.",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_TINY,
        )
        self.status_label.pack(side="left", padx=12)

        self.progress_bar = ctk.CTkProgressBar(bar, width=160, height=6, corner_radius=3)
        self.progress_bar.pack(side="right", padx=12, pady=10)
        self.progress_bar.set(0)
        self.progress_bar.pack_forget()  # hidden until scan starts

    # ── Scanning ──────────────────────────────────────────────────────────────

    def _get_available_drives(self) -> list[str]:
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives

    def _select_drive(self):
        path = filedialog.askdirectory(title="Select a drive or folder to scan")
        if path:
            self._start_scan(path)

    def _trigger_rescan(self):
        if self.root_node:
            self._start_scan(self.root_node.path)
        else:
            self._select_drive()

    def _start_scan(self, path: str):
        self.root_node = None
        self._clear_tree()
        self.drive_var.set(f"📂  {os.path.basename(path) or path}")
        self.status_label.configure(text=f"Scanning {path}…")
        self.progress_bar.pack(side="right", padx=12, pady=10)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self.rescan_btn.configure(state="disabled")
        self.tree_placeholder.lift()

        # Try cache first
        from scanner import Scanner
        cached = Scanner.load_cache(path)
        if cached:
            self._on_scan_complete(cached)
            self.status_label.configure(text=f"Loaded from cache — {path}  (click ↺ Rescan to refresh)")
            return

        self.scanner.start(path)

    def _on_scan_progress(self, message: str, percent: float):
        self.after(0, lambda: self.status_label.configure(text=message))

    def _on_scan_complete(self, root_node: FolderNode):
        self.root_node = root_node

        def update():
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.rescan_btn.configure(state="normal")
            self.tree_placeholder.lower()
            self.status_label.configure(
                text=f"✓ Scan complete — {root_node.name}  |  "
                     f"Total: {format_size(root_node.size)}  |  "
                     f"Folders: {root_node.subfolder_count}"
            )
            self._populate_tree(root_node)

        self.after(0, update)

    def _on_scan_error(self, error: str):
        def update():
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.rescan_btn.configure(state="normal")
            self.status_label.configure(text=f"Error: {error}")
            messagebox.showerror("Scan Error", error)

        self.after(0, update)

    # ── Tree Population ───────────────────────────────────────────────────────

    def _clear_tree(self):
        self._tree_nodes.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _populate_tree(self, root_node: FolderNode, filter_cat: str = "all"):
        self._clear_tree()

        def insert_node(parent_id: str, node: FolderNode):
            emoji, label = get_category_badge(node.category)
            size_str = format_size(node.size)
            badge = f"{emoji} {label}"

            if filter_cat != "all" and node.category != filter_cat:
                # Still insert children that might match
                for child in node.children:
                    insert_node(parent_id, child)
                return

            item_id = self.tree.insert(
                parent_id, "end",
                text=f"  {'📂' if node.children else '📁'}  {node.name}",
                values=(size_str, badge),
                open=False,
            )
            self._tree_nodes[item_id] = node

            # Insert placeholder child so expand arrow appears
            if node.children:
                self.tree.insert(item_id, "end", text="__loading__", values=("", ""))

        for child in root_node.children[:200]:
            insert_node("", child)

    def _on_tree_open(self, event):
        item_id = self.tree.focus()
        node = self._tree_nodes.get(item_id)
        if not node:
            return

        children = self.tree.get_children(item_id)
        if children and self.tree.item(children[0], "text") == "__loading__":
            self.tree.delete(children[0])
            for child in node.children[:100]:
                emoji, label = get_category_badge(child.category)
                size_str = format_size(child.size)
                badge = f"{emoji} {label}"
                child_id = self.tree.insert(
                    item_id, "end",
                    text=f"  {'📂' if child.children else '📁'}  {child.name}",
                    values=(size_str, badge),
                    open=False,
                )
                self._tree_nodes[child_id] = child
                if child.children:
                    self.tree.insert(child_id, "end", text="__loading__", values=("", ""))

    def _on_tree_select(self, event):
        selection = self.tree.selection()
        if not selection:
            return
        item_id = selection[0]
        node = self._tree_nodes.get(item_id)
        if node:
            self._selected_node = node
            self._update_detail_panel(node)

    def _on_search_change(self, *args):
        query = self.search_var.get().lower().strip()
        if not self.root_node:
            return
        if not query:
            self._populate_tree(self.root_node)
            return

        self._clear_tree()

        def search_insert(parent_id: str, node: FolderNode):
            matches = query in node.name.lower()
            child_ids = []
            for child in node.children:
                cid = search_insert(parent_id if not matches else None, child)
                if cid:
                    child_ids.append(cid)

            if matches or child_ids:
                emoji, label = get_category_badge(node.category)
                item_id = self.tree.insert(
                    parent_id or "", "end",
                    text=f"  {'📂' if node.children else '📁'}  {node.name}",
                    values=(format_size(node.size), f"{emoji} {label}"),
                    open=True,
                )
                self._tree_nodes[item_id] = node
                return item_id
            return None

        for child in self.root_node.children:
            search_insert(None, child)

    def _set_filter(self, cat: str):
        self.active_filter.set(cat)
        if self.root_node:
            self._populate_tree(self.root_node, filter_cat=cat)

    # ── Detail Panel ─────────────────────────────────────────────────────────

    def _update_detail_panel(self, node: FolderNode):
        # Clear existing detail widgets
        for widget in self.detail_scroll.winfo_children():
            widget.destroy()

        emoji, label = get_category_badge(node.category)
        color = BADGE_COLORS.get(node.category, "#6B7280")

        # Folder name
        ctk.CTkLabel(
            self.detail_scroll,
            text=node.name,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=TEXT_MAIN,
            wraplength=290,
            anchor="w",
            justify="left",
        ).pack(anchor="w", padx=4, pady=(4, 2))

        # Path
        ctk.CTkLabel(
            self.detail_scroll,
            text=node.path,
            font=ctk.CTkFont(size=10, family="Consolas"),
            text_color=TEXT_TINY,
            wraplength=290,
            anchor="w",
            justify="left",
        ).pack(anchor="w", padx=4, pady=(0, 10))

        # Size (big)
        ctk.CTkLabel(
            self.detail_scroll,
            text=format_size(node.size),
            font=ctk.CTkFont(size=32, weight="bold"),
            text_color=ACCENT,
        ).pack(pady=(0, 4))

        # Stats grid
        stats = ctk.CTkFrame(self.detail_scroll, fg_color=BG_DARK, corner_radius=8)
        stats.pack(fill="x", padx=4, pady=(0, 10))
        self._stat_row(stats, "📄 Files", str(node.file_count))
        self._stat_row(stats, "📁 Subfolders", str(node.subfolder_count))

        # Category badge
        badge_row = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
        badge_row.pack(fill="x", padx=4, pady=(0, 12))

        badge_frame = ctk.CTkFrame(badge_row, fg_color=color, corner_radius=6)
        badge_frame.pack(side="left")
        ctk.CTkLabel(
            badge_frame,
            text=f"  {emoji}  {label}  ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white",
        ).pack(padx=4, pady=3)

        open_btn = ctk.CTkButton(
            badge_row,
            text="📁 Open Folder",
            width=100,
            height=30,
            fg_color=BG_DARK,
            hover_color=BG_HOVER,
            text_color=TEXT_MAIN,
            border_width=1,
            border_color=BORDER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._open_in_explorer(node.path),
            corner_radius=6,
        )
        open_btn.pack(side="right")

        # Reason
        ctk.CTkLabel(
            self.detail_scroll,
            text=node.category_reason,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_DIM,
            wraplength=290,
            anchor="w",
            justify="left",
        ).pack(anchor="w", padx=4, pady=(0, 12))

        # Top 5 subfolders
        if node.children:
            ctk.CTkLabel(
                self.detail_scroll,
                text="Top subfolders by size",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT_DIM,
            ).pack(anchor="w", padx=4, pady=(0, 4))

            max_size = node.children[0].size or 1
            for child in node.children[:5]:
                self._subfolder_row(self.detail_scroll, child, max_size)

        # Common file types
        if node.common_extensions:
            ctk.CTkLabel(
                self.detail_scroll,
                text="Common file types",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=TEXT_DIM,
            ).pack(anchor="w", padx=4, pady=(12, 4))

            sorted_ext = sorted(
                node.common_extensions.items(), key=lambda x: x[1], reverse=True
            )[:8]
            ext_frame = ctk.CTkFrame(self.detail_scroll, fg_color="transparent")
            ext_frame.pack(anchor="w", padx=4)
            for ext, count in sorted_ext:
                pill = ctk.CTkFrame(ext_frame, fg_color=BG_DARK, corner_radius=4)
                pill.pack(side="left", padx=(0, 4), pady=2)
                ctk.CTkLabel(
                    pill, text=f"{ext} ({count})",
                    font=ctk.CTkFont(size=10),
                    text_color=TEXT_DIM,
                ).pack(padx=6, pady=2)

    def _open_in_explorer(self, path: str):
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showerror("Error", f"Path not found: {path}")

    def _stat_row(self, parent, label: str, value: str):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=11), text_color=TEXT_DIM).pack(side="left")
        ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_MAIN).pack(side="right")

    def _subfolder_row(self, parent, node: FolderNode, max_size: int):
        row = ctk.CTkFrame(parent, fg_color=BG_DARK, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)

        ctk.CTkLabel(
            row, text=node.name,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MAIN,
            anchor="w",
        ).pack(side="left", padx=8, pady=4)

        ctk.CTkLabel(
            row, text=format_size(node.size),
            font=ctk.CTkFont(size=11),
            text_color=ACCENT,
        ).pack(side="right", padx=8)

        ratio = node.size / max_size if max_size else 0
        bar = ctk.CTkProgressBar(row, height=4, corner_radius=2, width=int(ratio * 120))
        bar.set(ratio)
        bar.pack(side="right", padx=(0, 4))

    # ── Chat Panel ────────────────────────────────────────────────────────────

    def _send_chat(self):
        question = self.chat_input.get().strip()
        if not question:
            return
        if not self.root_node:
            messagebox.showinfo("No scan", "Please scan a drive first before asking questions.")
            return

        self.chat_input.delete(0, "end")
        self._append_chat("You", question)
        self.gemini_status.configure(text="● thinking…", text_color=TEXT_DIM)

        ask_gemini(
            question=question,
            root_node=self.root_node,
            on_response=lambda r: self.after(0, lambda: self._on_gemini_response(r)),
            on_error=lambda e: self.after(0, lambda: self._on_gemini_error(e)),
        )

    def _on_gemini_response(self, response: str):
        self.gemini_status.configure(text="● ready", text_color=ACCENT)
        self._append_chat("Gemini", response)

    def _on_gemini_error(self, error: str):
        self.gemini_status.configure(text="● unavailable", text_color="#EF4444")
        self._append_chat("System", f"⚠ {error}")

    def _append_chat(self, role: str, text: str):
        self.chat_history.configure(state="normal")
        if self.chat_history.get("1.0", "end").strip():
            self.chat_history.insert("end", "\n\n")
        prefix = {"You": "▸ You: ", "Gemini": "✨ Gemini: ", "System": "⚠ "}.get(role, f"{role}: ")
        self.chat_history.insert("end", prefix + text)
        self.chat_history.configure(state="disabled")
        self.chat_history.see("end")
