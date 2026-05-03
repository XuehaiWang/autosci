"""Terminal persistent session tools — PTY-backed shell sessions.

Provides five tools:
    terminal_start     — open a new persistent PTY session
    terminal_write     — send input and read back output
    terminal_read      — read pending output without sending input
    terminal_interrupt — send Ctrl-C and read output
    terminal_kill      — terminate and clean up a session
"""

import atexit
import itertools
import os
import pty
import select
import shutil
import signal
import struct
import subprocess
import termios
import threading
import time
from typing import Optional

from autosci.tools.registry import registry


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_BUFFER_LIMIT = 200_000
DEFAULT_OUTPUT_CHARS = 20_000
DEFAULT_YIELD_MS = 200
REPEAT_COLLAPSE_THRESHOLD = 3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_shell() -> str:
    return shutil.which("bash") or "/bin/bash"


def _set_terminal_size(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    try:
        import fcntl
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
    except (ImportError, OSError):
        pass


def _disable_echo(fd: int) -> None:
    try:
        attrs = termios.tcgetattr(fd)
        attrs[3] &= ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except termios.error:
        pass


def _collapse_repeated_lines(text: str) -> str:
    if not text:
        return text
    lines = text.splitlines(keepends=True)
    if not lines:
        return text
    collapsed: list[str] = []
    current = lines[0]
    count = 1
    for line in lines[1:]:
        if line == current:
            count += 1
            continue
        if count >= REPEAT_COLLAPSE_THRESHOLD:
            collapsed.append(current)
            collapsed.append(f"[previous line repeated {count - 1} additional times]\n")
        else:
            collapsed.extend([current] * count)
        current = line
        count = 1
    if count >= REPEAT_COLLAPSE_THRESHOLD:
        collapsed.append(current)
        collapsed.append(f"[previous line repeated {count - 1} additional times]\n")
    else:
        collapsed.extend([current] * count)
    return "".join(collapsed)


def _bounded_output(text: str, max_chars: int = DEFAULT_OUTPUT_CHARS) -> str:
    if not text:
        return text
    compressed = _collapse_repeated_lines(text)
    if len(compressed) <= max_chars:
        return compressed
    omitted = len(compressed) - max_chars
    suffix = f"\n[output truncated: omitted {omitted} chars]\n"
    keep = max(0, max_chars - len(suffix))
    return compressed[:keep] + suffix


# ── TerminalSession ────────────────────────────────────────────────────────────

class TerminalSession:
    """A persistent PTY-backed shell session."""

    def __init__(self, cwd: str, shell: str, rows: int, cols: int):
        self.cwd = cwd
        self.shell = shell
        self.rows = rows
        self.cols = cols
        self._buffer_limit = DEFAULT_BUFFER_LIMIT
        self._pending_output = ""
        self._dropped_output_chars = 0
        self._lock = threading.Lock()

        master_fd, slave_fd = pty.openpty()
        _set_terminal_size(slave_fd, rows, cols)
        _disable_echo(slave_fd)

        env = {**os.environ}
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("PS1", "")
        env.setdefault("PROMPT_COMMAND", "")

        self._proc = subprocess.Popen(
            [shell, "--noprofile", "--norc"],
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=cwd,
            env=env,
            text=False,
            close_fds=True,
            start_new_session=True,
        )
        os.close(slave_fd)
        self._master_fd = master_fd
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader.start()

    @property
    def pid(self) -> int:
        return self._proc.pid

    @property
    def alive(self) -> bool:
        return self._proc.poll() is None

    @property
    def returncode(self) -> Optional[int]:
        return self._proc.poll()

    def _reader_loop(self) -> None:
        while True:
            try:
                ready, _, _ = select.select([self._master_fd], [], [], 0.1)
            except (OSError, ValueError):
                break
            if not ready:
                if self._proc.poll() is not None:
                    break
                continue
            try:
                data = os.read(self._master_fd, 4096)
            except OSError:
                break
            if not data:
                if self._proc.poll() is not None:
                    break
                continue
            decoded = data.decode("utf-8", errors="replace")
            with self._lock:
                self._pending_output += decoded
                overflow = len(self._pending_output) - self._buffer_limit
                if overflow > 0:
                    self._pending_output = self._pending_output[overflow:]
                    self._dropped_output_chars += overflow
        try:
            os.close(self._master_fd)
        except OSError:
            pass

    def write(self, data: str) -> None:
        if not self.alive:
            raise RuntimeError("Session is not running")
        os.write(self._master_fd, data.encode("utf-8", errors="replace"))

    def read(self, yield_ms: int = DEFAULT_YIELD_MS, max_chars: int = DEFAULT_OUTPUT_CHARS) -> dict:
        if yield_ms > 0:
            time.sleep(yield_ms / 1000.0)
        with self._lock:
            output = self._pending_output[:max_chars]
            self._pending_output = self._pending_output[max_chars:]
            remaining = len(self._pending_output)
            dropped = self._dropped_output_chars
            self._dropped_output_chars = 0
        return {
            "alive": self.alive,
            "returncode": self.returncode,
            "output": output,
            "remaining_output_chars": remaining,
            "dropped_output_chars": dropped,
            "truncated": remaining > 0,
        }

    def interrupt(self, max_chars: int = DEFAULT_OUTPUT_CHARS) -> dict:
        if not self.alive:
            raise RuntimeError("Session is not running")
        os.write(self._master_fd, b"\x03")
        return self.read(yield_ms=DEFAULT_YIELD_MS, max_chars=max_chars)

    def terminate(self, force: bool = False) -> Optional[int]:
        if self.alive:
            try:
                os.killpg(os.getpgid(self.pid), signal.SIGKILL if force else signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError:
                self._proc.kill() if force else self._proc.terminate()
            try:
                self._proc.wait(timeout=2 if not force else 1)
            except subprocess.TimeoutExpired:
                if not force:
                    return self.terminate(force=True)
        return self.returncode


# ── TerminalSessionManager ────────────────────────────────────────────────────

class TerminalSessionManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._counter = itertools.count(1)
        self._sessions: dict[str, TerminalSession] = {}

    def start(self, cwd: str, shell: str, rows: int, cols: int) -> tuple[str, TerminalSession]:
        session = TerminalSession(cwd=cwd, shell=shell, rows=rows, cols=cols)
        session_id = f"term_{next(self._counter)}"
        with self._lock:
            self._sessions[session_id] = session
        return session_id, session

    def get(self, session_id: str) -> Optional[TerminalSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def pop(self, session_id: str) -> Optional[TerminalSession]:
        with self._lock:
            return self._sessions.pop(session_id, None)

    def cleanup(self) -> None:
        with self._lock:
            sessions = list(self._sessions.items())
            self._sessions.clear()
        for _, session in sessions:
            session.terminate(force=True)


_SESSION_MANAGER = TerminalSessionManager()
atexit.register(_SESSION_MANAGER.cleanup)


# ── Format helper ─────────────────────────────────────────────────────────────

def _fmt(prefix: str, session_id: str, payload: dict, **extra) -> str:
    lines = [prefix, f"session_id: {session_id}"]
    for key, val in extra.items():
        if val is not None:
            lines.append(f"{key}: {val}")
    if "alive" in payload:
        lines.append(f"alive: {str(payload['alive']).lower()}")
    if payload.get("returncode") is not None:
        lines.append(f"returncode: {payload['returncode']}")
    if "truncated" in payload:
        lines.append(f"truncated: {str(payload['truncated']).lower()}")
    if payload.get("remaining_output_chars"):
        lines.append(f"remaining_output_chars: {payload['remaining_output_chars']}")
    if payload.get("dropped_output_chars"):
        lines.append(f"dropped_output_chars: {payload['dropped_output_chars']}")
    if "output" in payload:
        bounded = _bounded_output(payload["output"])
        lines.append(f"output:\n{bounded}")
    return "\n".join(lines)


# ── Tool: terminal_start ──────────────────────────────────────────────────────

TERMINAL_START_SCHEMA = {
    "name": "terminal_start",
    "description": (
        "Start a persistent PTY terminal session. Returns a session_id for use with "
        "terminal_write, terminal_read, terminal_interrupt, and terminal_kill. "
        "Use this instead of execute_command when you need an interactive shell, "
        "long-running processes (training loops, servers), or stateful commands."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "working_dir": {
                "type": "string",
                "description": "Working directory for the session. Default: current directory",
            },
            "shell": {
                "type": "string",
                "description": "Shell executable. Default: bash",
            },
            "rows": {
                "type": "integer",
                "description": "Terminal rows. Default: 30",
            },
            "cols": {
                "type": "integer",
                "description": "Terminal columns. Default: 120",
            },
        },
        "required": [],
    },
}


def terminal_start(working_dir: str = None, shell: str = None, rows: int = 30, cols: int = 120) -> str:
    cwd = os.path.expanduser(working_dir) if working_dir else os.getcwd()
    if not os.path.isdir(cwd):
        return f"Error: directory not found: {cwd}"
    shell = shell or _default_shell()
    if not os.path.isfile(shell) and shutil.which(shell) is None:
        return f"Error: shell not found: {shell}"
    if rows <= 0 or cols <= 0:
        return "Error: rows and cols must be > 0"
    try:
        session_id, session = _SESSION_MANAGER.start(cwd=cwd, shell=shell, rows=rows, cols=cols)
    except (OSError, RuntimeError) as e:
        return f"Error: starting terminal session failed: {e}"
    return _fmt(
        "Started terminal session.",
        session_id,
        {"alive": session.alive, "returncode": session.returncode},
        pid=session.pid,
        cwd=cwd,
        shell=shell,
    )


registry.register("terminal_start", TERMINAL_START_SCHEMA, terminal_start, toolset="terminal")


# ── Tool: terminal_write ──────────────────────────────────────────────────────

TERMINAL_WRITE_SCHEMA = {
    "name": "terminal_write",
    "description": (
        "Send input to a terminal session and read back the resulting output. "
        "Use append_newline=true (default) to execute commands. "
        "Increase yield_time_ms for slow commands."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID returned by terminal_start",
            },
            "input": {
                "type": "string",
                "description": "Text to send to the terminal",
            },
            "append_newline": {
                "type": "boolean",
                "description": "Append newline after input to execute as command. Default: true",
            },
            "yield_time_ms": {
                "type": "integer",
                "description": "Milliseconds to wait before reading output. Default: 200",
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Maximum output characters to return. Default: 20000",
            },
        },
        "required": ["session_id", "input"],
    },
}


def terminal_write(
    session_id: str,
    input: str,
    append_newline: bool = True,
    yield_time_ms: int = DEFAULT_YIELD_MS,
    max_output_chars: int = DEFAULT_OUTPUT_CHARS,
) -> str:
    session = _SESSION_MANAGER.get(session_id)
    if session is None:
        return f"Error: session not found: {session_id}"
    if max_output_chars <= 0:
        return "Error: max_output_chars must be > 0"
    if yield_time_ms < 0:
        return "Error: yield_time_ms must be >= 0"
    payload_input = input + ("\n" if append_newline else "")
    try:
        session.write(payload_input)
        payload = session.read(yield_ms=yield_time_ms, max_chars=max_output_chars)
    except (OSError, RuntimeError) as e:
        return f"Error: write to session {session_id} failed: {e}"
    return _fmt("Session updated.", session_id, payload)


registry.register("terminal_write", TERMINAL_WRITE_SCHEMA, terminal_write, toolset="terminal")


# ── Tool: terminal_read ───────────────────────────────────────────────────────

TERMINAL_READ_SCHEMA = {
    "name": "terminal_read",
    "description": "Read pending output from a terminal session without sending any input.",
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID returned by terminal_start",
            },
            "yield_time_ms": {
                "type": "integer",
                "description": "Milliseconds to wait before reading. Default: 200",
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Maximum output characters to return. Default: 20000",
            },
        },
        "required": ["session_id"],
    },
}


def terminal_read(
    session_id: str,
    yield_time_ms: int = DEFAULT_YIELD_MS,
    max_output_chars: int = DEFAULT_OUTPUT_CHARS,
) -> str:
    session = _SESSION_MANAGER.get(session_id)
    if session is None:
        return f"Error: session not found: {session_id}"
    if max_output_chars <= 0:
        return "Error: max_output_chars must be > 0"
    if yield_time_ms < 0:
        return "Error: yield_time_ms must be >= 0"
    payload = session.read(yield_ms=yield_time_ms, max_chars=max_output_chars)
    return _fmt("Session output.", session_id, payload)


registry.register("terminal_read", TERMINAL_READ_SCHEMA, terminal_read, toolset="terminal")


# ── Tool: terminal_interrupt ──────────────────────────────────────────────────

TERMINAL_INTERRUPT_SCHEMA = {
    "name": "terminal_interrupt",
    "description": "Send Ctrl-C (SIGINT) to a terminal session to interrupt the running command.",
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID returned by terminal_start",
            },
            "max_output_chars": {
                "type": "integer",
                "description": "Maximum output characters to return. Default: 20000",
            },
        },
        "required": ["session_id"],
    },
}


def terminal_interrupt(session_id: str, max_output_chars: int = DEFAULT_OUTPUT_CHARS) -> str:
    session = _SESSION_MANAGER.get(session_id)
    if session is None:
        return f"Error: session not found: {session_id}"
    if not session.alive:
        return f"Error: session {session_id} is not running"
    try:
        payload = session.interrupt(max_chars=max_output_chars)
    except (OSError, RuntimeError) as e:
        return f"Error: interrupt session {session_id} failed: {e}"
    return _fmt("Sent interrupt (Ctrl-C).", session_id, payload)


registry.register("terminal_interrupt", TERMINAL_INTERRUPT_SCHEMA, terminal_interrupt, toolset="terminal")


# ── Tool: terminal_kill ───────────────────────────────────────────────────────

TERMINAL_KILL_SCHEMA = {
    "name": "terminal_kill",
    "description": "Terminate and clean up a terminal session. The session_id becomes invalid after this call.",
    "input_schema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Session ID returned by terminal_start",
            },
        },
        "required": ["session_id"],
    },
}


def terminal_kill(session_id: str) -> str:
    session = _SESSION_MANAGER.pop(session_id)
    if session is None:
        return f"Error: session not found: {session_id}"
    returncode = session.terminate(force=False)
    return f"Terminated session {session_id} (returncode: {returncode})"


registry.register("terminal_kill", TERMINAL_KILL_SCHEMA, terminal_kill, toolset="terminal")