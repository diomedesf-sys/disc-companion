"""
gemini_client.py — Wrapper for calling Gemini CLI as a subprocess.
"""

import subprocess
import json
import threading
from scanner import FolderNode
from categorizer import format_size


def build_context_summary(root_node: FolderNode, max_folders: int = 50) -> str:
    """
    Builds a compact text summary of the scanned folder structure
    to inject into the Gemini prompt as context.
    """
    lines = []
    lines.append(f"Root: {root_node.path} (Total: {format_size(root_node.size)})")
    lines.append("")

    def walk(node: FolderNode, depth: int, count: list):
        if count[0] >= max_folders:
            return
        indent = "  " * depth
        lines.append(
            f"{indent}- {node.name}/ [{format_size(node.size)}] "
            f"[{node.category}] ({node.file_count} files)"
        )
        count[0] += 1
        for child in node.children[:10]:  # limit breadth
            walk(child, depth + 1, count)

    count = [0]
    for child in root_node.children:
        walk(child, 0, count)

    return "\n".join(lines)


SYSTEM_PROMPT = """You are a helpful assistant analyzing a user's disk and folder structure.
You help users understand what is taking up space, identify old or large folders, and answer questions in plain English.
Be concise, friendly, and clear. Use bullet points when listing multiple items.
Do not make up information — only answer based on the folder data provided."""


def ask_gemini(
    question: str,
    root_node: FolderNode,
    on_response=None,
    on_error=None,
):
    """
    Calls Gemini CLI in a background thread.
    on_response(answer: str) is called on success.
    on_error(error: str) is called on failure.
    """
    def _thread():
        context = build_context_summary(root_node)
        full_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Here is a summary of the user's scanned folders:\n\n"
            f"{context}\n\n"
            f"User question: \"{question}\"\n\n"
            f"Answer clearly and in plain language."
        )

        try:
            result = subprocess.run(
                ["gemini", full_prompt],
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode == 0 and result.stdout.strip():
                if on_response:
                    on_response(result.stdout.strip())
            else:
                error_msg = result.stderr.strip() or "Gemini CLI returned no output."
                if on_error:
                    on_error(f"Gemini CLI error: {error_msg}")
        except FileNotFoundError:
            if on_error:
                on_error(
                    "Gemini CLI not found. Make sure 'gemini' is installed and "
                    "available in your PATH."
                )
        except subprocess.TimeoutExpired:
            if on_error:
                on_error("Gemini CLI timed out after 30 seconds.")
        except Exception as e:
            if on_error:
                on_error(f"Unexpected error: {e}")

    threading.Thread(target=_thread, daemon=True).start()
