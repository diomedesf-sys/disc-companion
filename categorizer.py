"""
categorizer.py — Rule-based folder categorization.
No AI involved — pure file signature detection.
"""

import os

# Category definitions: (category_id, label, badge_emoji)
CATEGORIES = {
    "system":   ("🔧", "System / App Data"),
    "code":     ("💻", "Code Project"),
    "games":    ("🎮", "Games"),
    "media":    ("🎵", "Media"),
    "docs":     ("📄", "Documents"),
    "archives": ("📦", "Archives & Backups"),
    "unknown":  ("❓", "Unknown / Mixed"),
}

# File signatures for each category
CODE_SIGNATURES = {
    "package.json", "requirements.txt", "pyproject.toml", "setup.py",
    "makefile", ".gitignore", "dockerfile", "pom.xml", "build.gradle",
    "cargo.toml", "go.mod", "composer.json", ".sln", "cmakelists.txt",
}
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".java",
    ".cpp", ".c", ".h", ".cs", ".rb", ".go", ".rs", ".php", ".swift",
    ".kt", ".vue", ".svelte",
}
MEDIA_EXTENSIONS = {
    ".mp3", ".mp4", ".wav", ".flac", ".aac", ".ogg", ".wav",
    ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".psd", ".ai", ".xcf", ".svg", ".raw", ".cr2", ".nef",
}
DOC_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
    ".txt", ".md", ".odt", ".rtf", ".epub", ".csv",
}
ARCHIVE_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    ".bak", ".iso", ".dmg",
}
GAME_EXTENSIONS = {".pak", ".vpk", ".gcf", ".wad", ".esm", ".esp"}
SYSTEM_PATHS = {
    "windows", "program files", "program files (x86)",
    "appdata", "programdata", "system32", "syswow64",
}
GAME_DIRS = {"steam", "steamapps", "epic games", "gog galaxy", "origin"}


def categorize_folder(
    path: str,
    files_seen: list[str],
    extensions_found: set[str],
) -> tuple[str, str]:
    """
    Returns (category_id, reason_string).
    Rules applied in priority order.
    """
    path_lower = path.lower().replace("\\", "/")
    files_lower = {f.lower() for f in files_seen}

    # 1. System paths (highest priority)
    for sys_path in SYSTEM_PATHS:
        if f"/{sys_path}/" in path_lower or path_lower.endswith(f"/{sys_path}"):
            return "system", f"Located inside a known system directory ({sys_path})"

    # 2. Code project — check for signature files
    for sig in CODE_SIGNATURES:
        if sig in files_lower:
            return "code", f"Contains '{sig}' → likely a code project"

    # Check if majority of extensions are code
    code_ext_count = sum(1 for e in extensions_found if e in CODE_EXTENSIONS)
    if code_ext_count >= 3 or (
        extensions_found and code_ext_count / len(extensions_found) > 0.5
    ):
        return "code", f"Majority of files have code extensions ({', '.join(list(extensions_found & CODE_EXTENSIONS)[:3])})"

    # 3. Games
    for game_dir in GAME_DIRS:
        if f"/{game_dir}/" in path_lower or path_lower.endswith(f"/{game_dir}"):
            return "games", f"Located inside known games directory ({game_dir})"
    if GAME_EXTENSIONS & extensions_found:
        matched = GAME_EXTENSIONS & extensions_found
        return "games", f"Contains game asset files ({', '.join(matched)})"

    # 4. Media — check if majority of extensions are media
    if extensions_found:
        media_ext_count = sum(1 for e in extensions_found if e in MEDIA_EXTENSIONS)
        if media_ext_count / len(extensions_found) > 0.5:
            matched = list(extensions_found & MEDIA_EXTENSIONS)[:3]
            return "media", f"Majority of files are media ({', '.join(matched)})"

    # 5. Documents
    if extensions_found:
        doc_ext_count = sum(1 for e in extensions_found if e in DOC_EXTENSIONS)
        if doc_ext_count / len(extensions_found) > 0.5:
            matched = list(extensions_found & DOC_EXTENSIONS)[:3]
            return "docs", f"Majority of files are documents ({', '.join(matched)})"

    # 6. Archives
    archive_matches = extensions_found & ARCHIVE_EXTENSIONS
    if archive_matches:
        return "archives", f"Contains archive/backup files ({', '.join(archive_matches)})"

    return "unknown", "No clear dominant file type or signature found"


def format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GB"


def get_category_badge(category_id: str) -> tuple[str, str]:
    """Returns (emoji, label) for a category id."""
    return CATEGORIES.get(category_id, CATEGORIES["unknown"])
