"""
scanner.py — Recursive file system scanner.
Runs in a background thread and reports progress via callbacks.
"""

import os
import threading
import json
from pathlib import Path
from categorizer import categorize_folder

CACHE_FILE = "scan_cache.json"


class FolderNode:
    """Represents a scanned folder with size and metadata."""

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.basename(path) or path
        self.size = 0
        self.file_count = 0
        self.subfolder_count = 0
        self.children: list["FolderNode"] = []
        self.category = "unknown"
        self.category_reason = ""
        self.common_extensions: dict[str, int] = {}
        self.error = None

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "file_count": self.file_count,
            "subfolder_count": self.subfolder_count,
            "category": self.category,
            "category_reason": self.category_reason,
            "common_extensions": self.common_extensions,
            "children": [c.to_dict() for c in self.children],
        }

    @staticmethod
    def from_dict(d: dict) -> "FolderNode":
        node = FolderNode(d["path"])
        node.name = d["name"]
        node.size = d["size"]
        node.file_count = d["file_count"]
        node.subfolder_count = d["subfolder_count"]
        node.category = d["category"]
        node.category_reason = d["category_reason"]
        node.common_extensions = d.get("common_extensions", {})
        node.children = [FolderNode.from_dict(c) for c in d.get("children", [])]
        return node


class Scanner:
    """Scans a directory tree in a background thread."""

    def __init__(self, on_progress=None, on_complete=None, on_error=None):
        self.on_progress = on_progress  # callback(message: str, percent: float)
        self.on_complete = on_complete  # callback(root_node: FolderNode)
        self.on_error = on_error        # callback(error: str)
        self._thread = None
        self._cancel = False

    def start(self, root_path: str):
        self._cancel = False
        self._thread = threading.Thread(
            target=self._scan_thread, args=(root_path,), daemon=True
        )
        self._thread.start()

    def cancel(self):
        self._cancel = True

    def _scan_thread(self, root_path: str):
        try:
            self._report_progress(f"Starting scan of {root_path}...", 0.0)
            root_node = self._scan_folder(root_path, depth=0, max_depth=10)
            if not self._cancel:
                self._cache_results(root_path, root_node)
                if self.on_complete:
                    self.on_complete(root_node)
        except Exception as e:
            if self.on_error:
                self.on_error(str(e))

    def _scan_folder(self, path: str, depth: int, max_depth: int) -> FolderNode:
        node = FolderNode(path)
        if self._cancel:
            return node

        self._report_progress(f"Scanning: {os.path.basename(path)}", -1)

        extensions_found = set()
        files_seen = []

        try:
            entries = list(os.scandir(path))
        except PermissionError:
            node.error = "Permission denied"
            return node
        except Exception as e:
            node.error = str(e)
            return node

        for entry in entries:
            if self._cancel:
                break
            try:
                if entry.is_file(follow_symlinks=False):
                    size = entry.stat(follow_symlinks=False).st_size
                    node.size += size
                    node.file_count += 1
                    ext = Path(entry.name).suffix.lower()
                    if ext:
                        extensions_found.add(ext)
                        node.common_extensions[ext] = (
                            node.common_extensions.get(ext, 0) + 1
                        )
                    files_seen.append(entry.name)

                elif entry.is_dir(follow_symlinks=False):
                    node.subfolder_count += 1
                    if depth < max_depth:
                        child = self._scan_folder(entry.path, depth + 1, max_depth)
                        node.size += child.size
                        node.file_count += child.file_count
                        node.children.append(child)

            except (PermissionError, OSError):
                continue

        # Sort children by size descending
        node.children.sort(key=lambda n: n.size, reverse=True)

        # Apply categorization
        node.category, node.category_reason = categorize_folder(
            path, files_seen, extensions_found
        )

        return node

    def _report_progress(self, message: str, percent: float):
        if self.on_progress:
            self.on_progress(message, percent)

    def _cache_results(self, root_path: str, root_node: FolderNode):
        try:
            cache = {}
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
            cache[root_path] = root_node.to_dict()
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass  # Cache write failure is non-fatal

    @staticmethod
    def load_cache(root_path: str) -> "FolderNode | None":
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                if root_path in cache:
                    return FolderNode.from_dict(cache[root_path])
        except Exception:
            pass
        return None
