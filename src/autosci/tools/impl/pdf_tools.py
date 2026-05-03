"""PDF reading tool — extracts text (and image paths) from PDF files.

Requires the `structai` package. The MinerU token is resolved from:
1. The env var named in config["tools"]["mineru_token_env"] (default: MINERU_TOKEN)
2. Falls back to MINERU_TOKEN env var directly
"""

import os
import threading
from typing import Optional

# Thread-local storage for config injection (set by runner).
_local = threading.local()


def set_tools_config(config: dict) -> None:
    """Called by the runner to inject the tools config for this thread."""
    _local.tools_config = config


def _ensure_mineru_token() -> Optional[str]:
    """Ensure MINERU_TOKEN is set in os.environ, resolving from config if needed.

    Returns the token value or None if unavailable.
    """
    # Already set?
    if os.environ.get("MINERU_TOKEN"):
        return os.environ["MINERU_TOKEN"]

    # Try resolving from config
    tools_config = getattr(_local, "tools_config", None) or {}
    env_var = tools_config.get("mineru_token_env", "MINERU_TOKEN")
    token = os.environ.get(env_var)
    if token:
        # Inject so structai can find it
        os.environ["MINERU_TOKEN"] = token
        return token

    return None


def read_pdf(path: str, max_chars: int = 20000, max_image_paths: int = 20) -> str:
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return f"Error: file not found: {path}"
    if not path.lower().endswith(".pdf"):
        return f"Error: not a PDF file: {path}"
    if max_chars <= 0:
        return "Error: max_chars must be > 0"
    if max_image_paths <= 0:
        return "Error: max_image_paths must be > 0"

    try:
        from structai import read_pdf as structai_read_pdf
    except ImportError:
        return (
            "Error: missing optional dependency 'structai'. "
            "Install requirements and set MINERU_TOKEN to enable PDF reading."
        )

    if not _ensure_mineru_token():
        return (
            "Error: MINERU_TOKEN not configured. Set the MINERU_TOKEN environment variable "
            "or configure tools.mineru_token_env in config.yaml."
        )

    try:
        result = structai_read_pdf(str(path))
        if isinstance(result, list):
            result = result[0] if result else None
        if not isinstance(result, dict):
            raise ValueError(f"Unexpected result type: {type(result)}")
        text = result.get("text", "")
        if not isinstance(text, str):
            raise ValueError("PDF text must be a string")
        raw_img_paths: list = result.get("img_paths", []) or []
        if not isinstance(raw_img_paths, list):
            raise ValueError("PDF img_paths must be a list")
        if not text.strip() and not raw_img_paths:
            raise ValueError("PDF text is empty and no extracted images were found")
    except (OSError, ValueError, TypeError) as e:
        return f"Error: reading PDF failed: {e}"

    # Resolve image paths relative to the PDF directory
    pdf_dir = os.path.dirname(os.path.abspath(path))
    resolved_img_paths: list[str] = []
    for raw in raw_img_paths:
        if not isinstance(raw, str) or not raw.strip():
            continue
        candidate = os.path.expanduser(raw)
        if not os.path.isabs(candidate):
            candidate = os.path.join(pdf_dir, candidate)
        candidate = os.path.normpath(candidate)
        resolved_img_paths.append(candidate)

    truncated = len(text) > max_chars
    content = text[:max_chars] if truncated else text
    listed_imgs = resolved_img_paths[:max_image_paths]
    imgs_truncated = len(resolved_img_paths) > len(listed_imgs)

    lines = [
        f"path: {path}",
        f"total_chars: {len(text)}",
        f"total_lines: {len(text.splitlines())}",
        f"truncated: {str(truncated).lower()}",
        f"image_count: {len(resolved_img_paths)}",
        f"image_paths_listed: {len(listed_imgs)}",
        f"image_paths_truncated: {str(imgs_truncated).lower()}",
    ]
    output = "\n".join(lines)
    if listed_imgs:
        output += "\nimage_paths:\n" + "\n".join(listed_imgs)
    output += "\ncontent:\n" + content
    return output


