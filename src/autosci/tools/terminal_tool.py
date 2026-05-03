"""Terminal tool — execute shell commands."""

import os
import subprocess

from autosci.tools.registry import registry

EXECUTE_COMMAND_SCHEMA = {
    "name": "execute_command",
    "description": (
        "Execute a shell command and return its output. "
        "Use this for running programs, installing packages, git operations, etc. "
        "Commands run in the current working directory."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds. Default: 120",
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory for the command. Default: current directory",
            },
        },
        "required": ["command"],
    },
}


def execute_command(command: str, timeout: int = 120, working_dir: str = None) -> str:
    if working_dir:
        working_dir = os.path.expanduser(working_dir)
        if not os.path.isdir(working_dir):
            return f"Error: directory not found: {working_dir}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=working_dir,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        output_parts = []

        if result.stdout:
            output_parts.append(result.stdout)

        if result.stderr:
            output_parts.append(f"[stderr]\n{result.stderr}")

        if result.returncode != 0:
            output_parts.append(f"[exit code: {result.returncode}]")

        output = "\n".join(output_parts)

        # Truncate very long output
        max_chars = 50000
        if len(output) > max_chars:
            output = (
                output[:max_chars // 2]
                + f"\n\n... [truncated {len(output) - max_chars} chars] ...\n\n"
                + output[-max_chars // 2:]
            )

        return output if output else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error: command execution failed: {e}"


registry.register("execute_command", EXECUTE_COMMAND_SCHEMA, execute_command, toolset="terminal")
