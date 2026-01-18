# Spawner Module

## Overview

The `spawner` module provides functionality for launching Claude CLI sessions in various terminal emulators. It supports both external terminal spawning (opening a new terminal window) and embedded PTY-based sessions (for in-application terminal integration).

## Purpose

This module abstracts the complexity of spawning Claude sessions across different terminal emulators and platforms, providing a unified interface for:

- Detecting available terminal emulators on the system
- Launching new Claude sessions in external terminals
- Resuming existing Claude sessions
- Creating PTY-based embedded terminal sessions for in-app integration

## Key Files

### `__init__.py`
Package initialization file that exports the public API:
- `spawn_session`: Launch a new Claude session in an external terminal
- `spawn_embedded`: Create an embedded Claude session with PTY
- `get_available_terminals`: Query available terminal emulators

### `terminal.py`
Core implementation file containing:
- Terminal detection logic
- Session spawning implementations for various terminal emulators
- PTY management for embedded terminals

## Core Classes and Functions

### `SpawnResult` (dataclass)

A data class representing the outcome of a spawn operation.

**Fields:**
- `success` (bool): Whether the spawn operation succeeded
- `pid` (int | None): Process ID of the spawned session (for embedded mode)
- `error` (str | None): Error message if spawn failed
- `master_fd` (int | None): Master file descriptor for PTY (embedded mode only)
- `slave_fd` (int | None): Slave file descriptor for PTY (embedded mode only)

### `get_available_terminals() -> list[str]`

Detects and returns available terminal emulators on the system, ordered by preference.

**Supported Terminals:**
- **macOS**: Warp.app (preferred), Terminal.app, iTerm2
- **Cross-platform**: wezterm, kitty, alacritty
- **Linux**: gnome-terminal, konsole, xterm

**Returns:** List of terminal names found on the system

**Example:**
```python
from claude_agent_tui.spawner import get_available_terminals

terminals = get_available_terminals()
# Returns: ['Warp.app', 'kitty', 'Terminal.app'] on macOS with those installed
```

### `spawn_session(cwd: str, terminal: str | None = None) -> SpawnResult`

Spawns a new Claude session in an external terminal window.

**Parameters:**
- `cwd`: Working directory where the Claude session should start
- `terminal`: Specific terminal to use (auto-detects if None)

**Returns:** `SpawnResult` indicating success or failure

**Behavior:**
- Validates that `claude` command exists in PATH
- Auto-detects terminal if not specified
- Uses platform-specific commands to launch terminal with Claude
- On macOS, uses AppleScript for Terminal.app, Warp.app, and iTerm2
- On Linux/other platforms, uses direct terminal commands

**Example:**
```python
from claude_agent_tui.spawner import spawn_session

result = spawn_session(
    cwd="/path/to/project",
    terminal="kitty"  # or None for auto-detect
)

if result.success:
    print("Claude session launched successfully")
else:
    print(f"Failed to launch: {result.error}")
```

### `spawn_resume_session(cwd: str, session_id: str, terminal: str | None = None) -> SpawnResult`

Spawns a Claude session that resumes an existing session by ID.

**Parameters:**
- `cwd`: Working directory for the session
- `session_id`: The session ID to resume
- `terminal`: Specific terminal to use (auto-detects if None)

**Returns:** `SpawnResult` indicating success or failure

**Usage:**
Similar to `spawn_session`, but executes `claude --resume <session_id>` instead of just `claude`.

**Example:**
```python
from claude_agent_tui.spawner import spawn_resume_session

result = spawn_resume_session(
    cwd="/path/to/project",
    session_id="abc123",
    terminal=None
)
```

### `spawn_embedded(cwd: str) -> SpawnResult`

Creates a Claude session for embedded terminal use with a PTY (pseudo-terminal).

**Parameters:**
- `cwd`: Working directory for the session

**Returns:** `SpawnResult` with PTY file descriptors and process ID

**Behavior:**
- Creates a pseudo-terminal pair (master/slave)
- Forks a new process
- Child process: Becomes session leader, redirects stdio to PTY, executes Claude
- Parent process: Closes slave FD, returns master FD for I/O

**Use Case:** This is designed for embedding a terminal in a GUI application, where you need direct control over the terminal's input/output.

**Example:**
```python
from claude_agent_tui.spawner import spawn_embedded

result = spawn_embedded(cwd="/path/to/project")

if result.success:
    # Use result.master_fd for reading/writing to the terminal
    # result.pid contains the Claude process ID
    os.write(result.master_fd, b"Hello Claude\n")
    output = os.read(result.master_fd, 1024)
```

## Platform Support

### macOS
- **Preferred**: Warp.app (uses AppleScript automation)
- **Built-in**: Terminal.app (uses AppleScript)
- **Third-party**: iTerm2, wezterm, kitty, alacritty

### Linux
- **GNOME**: gnome-terminal
- **KDE**: konsole
- **Generic**: xterm, wezterm, kitty, alacritty

### Windows
Currently no Windows-specific support, but cross-platform terminals (wezterm, kitty, alacritty) may work if available.

## Implementation Details

### Terminal-Specific Commands

Each terminal emulator has different command-line arguments for setting working directory and executing commands:

- **Warp/Terminal/iTerm2**: Uses AppleScript for automation on macOS
- **wezterm**: `wezterm start --cwd <dir> -- claude`
- **kitty**: `kitty --directory <dir> claude`
- **alacritty**: `alacritty --working-directory <dir> -e claude`
- **gnome-terminal**: `gnome-terminal --working-directory=<dir> -- claude`
- **konsole**: `konsole --workdir <dir> -e claude`
- **xterm**: `xterm -e "cd <dir> && claude"`

### Process Management

Important note from the code comments:
> Don't use start_new_session=True - it causes orphaned processes when the terminal window closes

The module uses `subprocess.Popen()` without creating new session groups to ensure proper process cleanup when terminals close.

### PTY Configuration

For embedded sessions, the module:
1. Sets up a PTY pair using `pty.openpty()`
2. Forks the process with `os.fork()`
3. Child becomes session leader with `os.setsid()`
4. Redirects stdin/stdout/stderr to the slave PTY
5. Sets `TERM=xterm-256color` for proper terminal emulation
6. Executes Claude using `os.execvpe()`

## Dependencies

### Standard Library
- `os`: Process and file descriptor management
- `pty`: Pseudo-terminal creation
- `shutil`: Finding executables in PATH
- `subprocess`: Launching external processes
- `sys`: Platform detection

### External Requirements
- Claude CLI must be installed and available in PATH (`claude` command)
- At least one supported terminal emulator (for external spawning)

## Relationships with Other Modules

### Used By
This module is likely used by:
- TUI components that need to launch new sessions
- Session management screens
- Application startup/navigation flows

### Integration Points
- Requires Claude CLI to be installed in the system
- Interacts with the operating system's terminal applications
- Provides results that can be integrated into process monitoring or terminal widgets

## Error Handling

All spawn functions return a `SpawnResult` with detailed error information:

**Common Errors:**
- `"'claude' command not found in PATH"`: Claude CLI not installed
- `"No supported terminal emulator found"`: No compatible terminal available
- `"Unsupported terminal: <name>"`: Requested terminal not recognized
- Exception messages: Captured from subprocess/system calls

**Usage Pattern:**
```python
result = spawn_session(cwd="/path", terminal="kitty")
if not result.success:
    # Handle error
    print(f"Error: {result.error}")
    # Maybe try another terminal or show user message
```

## Best Practices

1. **Auto-detection**: Let the module auto-detect terminals when possible
   ```python
   spawn_session(cwd="/path")  # Auto-detects best terminal
   ```

2. **Error checking**: Always check `SpawnResult.success` before proceeding
   ```python
   if result.success:
       # Proceed with operation
   else:
       # Handle error appropriately
   ```

3. **Terminal availability**: Check available terminals before offering choices
   ```python
   terminals = get_available_terminals()
   if terminals:
       spawn_session(cwd="/path", terminal=terminals[0])
   ```

4. **Resource cleanup**: For embedded sessions, properly close file descriptors and handle child processes
   ```python
   result = spawn_embedded(cwd="/path")
   try:
       # Use result.master_fd
       pass
   finally:
       if result.master_fd:
           os.close(result.master_fd)
   ```

## Future Enhancements

Potential improvements that could be added:

- Windows terminal support (Windows Terminal, ConEmu, etc.)
- Configuration for terminal preferences
- Session lifecycle management (tracking spawned processes)
- Terminal capability detection (color support, fonts, etc.)
- Custom command arguments pass-through
- Environment variable customization
