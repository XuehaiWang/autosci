"""PDF reading tool — extracts text (and image paths) from PDF files.

Requires the `structai` package with a valid MINERU_TOKEN environment variable.
"""

import os
from typing import Optional

from autosci.tools.registry import registry


READ_PDF_SCHEMA = {
    "name": "read_pdf",
    "description": (
        "Read a local PDF file and return extracted text. "
        "When the PDF contains figures, also returns paths to extracted image files "
        "so you can inspect them with read_file or other tools. "
        "Requires structai (MINERU_TOKEN must be set)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the PDF file",
            },
            "max_chars": {
                "type": "integer",
                "description": "Maximum characters of text to return. Default: 20000",
            },
            "max_image_paths": {
                "type": "integer",
                "description": "Maximum number of extracted image paths to list. Default: 20",
            },
        },
        "required": ["path"],
    },
}


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


registry.register("read_pdf", READ_PDF_SCHEMA, read_pdf, toolset="file")