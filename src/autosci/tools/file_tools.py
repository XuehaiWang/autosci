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
        return f"Error reading {path}: {e}"


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
        return f"Error writing {path}: {e}"


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
        return f"Error listing {path}: {e}"


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
        return f"Invalid regex: {e}"

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
