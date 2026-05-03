"""File tools — read, write, list directory, glob, grep."""

import glob as glob_module
import os
import re

from autosci.tools.registry import registry


# === Read File ===

READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": (
        "Read the contents of a file. Returns the file content with line numbers. "
        "Use offset and limit for large files."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-based). Default: 1",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read. Default: 2000",
            },
        },
        "required": ["path"],
    },
}


def read_file(path: str, offset: int = 1, limit: int = 2000) -> str:
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return f"Error: file not found: {path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        total = len(lines)
        start = max(0, offset - 1)
        end = min(total, start + limit)
        selected = lines[start:end]
        numbered = [f"{start + i + 1}\t{line}" for i, line in enumerate(selected)]
        header = f"[{path}] lines {start + 1}-{end} of {total}\n"
        return header + "".join(numbered)
    except Exception as e:
        return f"Error: reading {path} failed: {e}"


registry.register("read_file", READ_FILE_SCHEMA, read_file, toolset="file")


# === Write File ===

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Write content to a file. Creates parent directories if needed. Overwrites existing files.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file",
            },
            "content": {
                "type": "string",
                "description": "The content to write",
            },
        },
        "required": ["path", "content"],
    },
}


def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        line_count = content.count("\n") + (1 if content and not content.endswith("\n") else 0)
        return f"Written {line_count} lines to {path}"
    except Exception as e:
        return f"Error: writing {path} failed: {e}"


registry.register("write_file", WRITE_FILE_SCHEMA, write_file, toolset="file")


# === List Directory ===

LIST_DIR_SCHEMA = {
    "name": "list_dir",
    "description": "List files and directories in a given path.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path to list. Default: current directory",
            },
        },
        "required": [],
    },
}


def list_dir(path: str = ".") -> str:
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        return f"Error: not a directory: {path}"
    try:
        entries = sorted(os.listdir(path))
        result = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                result.append(f"  {entry}/")
            else:
                size = os.path.getsize(full)
                result.append(f"  {entry} ({_format_size(size)})")
        header = f"[{path}] {len(entries)} entries:\n"
        return header + "\n".join(result)
    except Exception as e:
        return f"Error: listing {path} failed: {e}"


def _format_size(size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


registry.register("list_dir", LIST_DIR_SCHEMA, list_dir, toolset="file")


# === Glob ===

GLOB_SCHEMA = {
    "name": "glob",
    "description": "Find files matching a glob pattern (e.g. '**/*.py', 'src/**/*.md').",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern to match files",
            },
            "path": {
                "type": "string",
                "description": "Base directory. Default: current directory",
            },
        },
        "required": ["pattern"],
    },
}


def glob_files(pattern: str, path: str = ".") -> str:
    path = os.path.expanduser(path)
    full_pattern = os.path.join(path, pattern)
    try:
        matches = sorted(glob_module.glob(full_pattern, recursive=True))
        if not matches:
            return f"No files matching '{pattern}' in {path}"
        # Limit output
        display = matches[:100]
        result = "\n".join(display)
        if len(matches) > 100:
            result += f"\n... and {len(matches) - 100} more files"
        return f"Found {len(matches)} files:\n{result}"
    except Exception as e:
        return f"Error: {e}"


registry.register("glob", GLOB_SCHEMA, glob_files, toolset="file")


# === Grep ===

GREP_SCHEMA = {
    "name": "grep",
    "description": "Search file contents for a regex pattern. Returns matching lines with context.",
    "input_schema": {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Regex pattern to search for",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in. Default: current directory",
            },
            "file_pattern": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g. '*.py'). Default: all files",
            },
            "context": {
                "type": "integer",
                "description": "Number of context lines before and after each match. Default: 0",
            },
        },
        "required": ["pattern"],
    },
}


def grep(pattern: str, path: str = ".", file_pattern: str = None, context: int = 0) -> str:
    path = os.path.expanduser(path)
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex: {e}"

    # Collect files to search
    if os.path.isfile(path):
        files = [path]
    elif os.path.isdir(path):
        if file_pattern:
            files = sorted(glob_module.glob(os.path.join(path, "**", file_pattern), recursive=True))
        else:
            files = []
            for root, _, filenames in os.walk(path):
                for fname in sorted(filenames):
                    files.append(os.path.join(root, fname))
    else:
        return f"Error: path not found: {path}"

    results = []
    match_count = 0
    max_matches = 200

    for fpath in files:
        if match_count >= max_matches:
            break
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            continue

        file_matches = []
        for i, line in enumerate(lines):
            if regex.search(line):
                start = max(0, i - context)
                end = min(len(lines), i + context + 1)
                for j in range(start, end):
                    prefix = ">" if j == i else " "
                    file_matches.append(f"  {prefix} {j + 1}: {lines[j].rstrip()}")
                if context > 0:
                    file_matches.append("  ---")
                match_count += 1
                if match_count >= max_matches:
                    break

        if file_matches:
            results.append(f"{fpath}:\n" + "\n".join(file_matches))

    if not results:
        return f"No matches for '{pattern}' in {path}"

    header = f"Found {match_count} matches"
    if match_count >= max_matches:
        header += f" (showing first {max_matches})"
    return header + ":\n\n" + "\n\n".join(results)


registry.register("grep", GREP_SCHEMA, grep, toolset="file")


# === Edit File (unified diff) ===

EDIT_FILE_SCHEMA = {
    "name": "edit_file",
    "description": (
        "Edit a local text file using a unified diff patch. "
        "The patch must contain one or more hunks with @@ headers. "
        "Context lines are used to locate the edit position precisely."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to the file to edit",
            },
            "patch": {
                "type": "string",
                "description": (
                    "A unified diff patch with one or more hunks. "
                    "Each hunk starts with @@ -start,count +start,count @@ "
                    "followed by lines prefixed with ' ' (context), '-' (remove), or '+' (add)."
                ),
            },
        },
        "required": ["path", "patch"],
    },
}


def _parse_unified_patch(patch_text: str) -> list[dict]:
    """Parse unified diff patch text into a list of hunks."""
    lines = patch_text.splitlines()
    hunks: list[dict] = []
    current_hunk = None

    for line in lines:
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("@@ "):
            if current_hunk is not None:
                hunks.append(current_hunk)
            current_hunk = {"header": line, "lines": []}
            continue
        if current_hunk is None:
            continue
        if line.startswith((" ", "+", "-")):
            current_hunk["lines"].append((line[:1], line[1:]))
            continue
        if line == r"\ No newline at end of file":
            continue
        raise ValueError(f"Unsupported patch line: {line!r}")

    if current_hunk is not None:
        hunks.append(current_hunk)

    if not hunks:
        raise ValueError("No hunks found in patch")
    return hunks


def _apply_hunks(original_text: str, hunks: list[dict]) -> tuple[str, int]:
    """Apply parsed hunks to original text. Returns (updated_text, applied_count)."""
    original_lines = original_text.splitlines()
    ends_with_newline = original_text.endswith("\n")
    output_lines: list[str] = []
    cursor = 0

    for hunk_index, hunk in enumerate(hunks, start=1):
        old_block = []
        new_block = []
        for prefix, content in hunk["lines"]:
            if prefix in (" ", "-"):
                old_block.append(content)
            if prefix in (" ", "+"):
                new_block.append(content)

        # Find old_block starting at cursor
        start_pos = None
        max_start = len(original_lines) - len(old_block)
        for pos in range(cursor, max_start + 1):
            if original_lines[pos : pos + len(old_block)] == old_block:
                start_pos = pos
                break

        if start_pos is None:
            preview = "\n".join(old_block[:5])
            raise ValueError(f"Hunk #{hunk_index} context not found in file:\n{preview}")

        output_lines.extend(original_lines[cursor:start_pos])
        output_lines.extend(new_block)
        cursor = start_pos + len(old_block)

    output_lines.extend(original_lines[cursor:])
    updated = "\n".join(output_lines)
    if ends_with_newline:
        updated += "\n"
    return updated, len(hunks)


def edit_file(path: str, patch: str) -> str:
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        return f"Error: file not found: {path}"
    if not patch.strip():
        return "Error: patch must be a non-empty unified diff string"

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except OSError as e:
        return f"Error: reading {path} failed: {e}"

    try:
        hunks = _parse_unified_patch(patch)
        updated, applied = _apply_hunks(original, hunks)
    except ValueError as e:
        return f"Error: applying patch failed: {e}"

    if updated == original:
        return f"No changes applied to {path}"

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        return f"Applied {applied} hunk(s) to {path}"
    except OSError as e:
        return f"Error: writing {path} failed: {e}"


registry.register("edit_file", EDIT_FILE_SCHEMA, edit_file, toolset="file")
