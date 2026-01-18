# TUI Screens Module

## Overview

This module contains the full-screen UI components (screens) for the Claude Agent Visualizer TUI application. These screens provide interactive interfaces for starting, resuming, and managing Claude AI agent sessions through both native terminal integration and embedded terminal widgets.

The screens module is built on top of Textual's Screen framework and provides modal and full-screen interfaces for different Claude session workflows.

## Key Files

### `__init__.py`
Package initialization file that exports the public screen classes:
- `TerminalScreen` - For starting new Claude sessions
- `NewSessionScreen` - Modal dialog for entering project directory

### `terminal_screen.py` - New Claude Session Screen
Full-screen interface for starting new Claude sessions with graceful process management.

**Purpose**: Provides an embedded terminal interface for running new Claude sessions with proper lifecycle management.

**Key Features**:
- Embedded ClaudeTerminal widget for interactive Claude sessions
- Graceful shutdown via `/exit` command
- Interrupt handling with double-press force quit (Ctrl+C)
- Process tracking for cleanup on app exit
- Status bar showing current directory and keybindings

**Class**: `TerminalScreen(Screen)`
- `__init__(cwd, name, id, classes)` - Initialize with working directory
- `action_close()` - Graceful shutdown sending `/exit` to Claude
- `action_interrupt()` - Send Ctrl+C (double-press within 2s to force kill)
- `action_force_close()` - Immediate SIGTERM termination

### `resume_terminal_screen.py` - Resume Existing Session Screen
Full-screen interface for resuming existing Claude sessions by session ID.

**Purpose**: Allows users to reconnect to previously started Claude sessions and optionally send an initial message.

**Key Features**:
- Resume sessions by session ID
- Optional initial message to send after session starts
- Same graceful shutdown and interrupt handling as TerminalScreen
- Process tracking and cleanup
- Session ID display in status bar and title

**Class**: `ResumeTerminalScreen(Screen)`
- `__init__(session_id, cwd, initial_message, name, id, classes)` - Initialize with session ID to resume
- Same action handlers as TerminalScreen for consistency

### `new_session_screen.py` - Project Directory Input Modal
Modal dialog for entering and validating a project directory before starting a new Claude session.

**Purpose**: Provides a user-friendly interface for selecting the working directory for new Claude sessions.

**Key Features**:
- Modal overlay with centered dialog
- Path input with validation
- Expands `~` and environment variables
- Validates path exists and is a directory
- Returns resolved absolute path
- Error message display for invalid paths
- Enter key or button click to submit

**Class**: `NewSessionScreen(ModalScreen[str | None])`
- `__init__(default_path)` - Initialize with optional default path (defaults to current directory)
- Returns `str` (validated path) on success, `None` on cancel
- `_validate_and_start()` - Internal validation and path resolution

### `embedded_terminal_screen.py` - External Terminal Integration (Deprecated)
Alternative implementation using the `textual-terminal` package for embedding Claude sessions.

**Status**: Not exported in `__init__.py`, appears to be deprecated or experimental

**Key Features**:
- Uses `textual-terminal.Terminal` widget if available
- Graceful handling if textual-terminal is not installed
- Builds shell commands to run `claude` CLI
- Simpler implementation but less control over process lifecycle

**Note**: This screen is not currently used in the main application. TerminalScreen and ResumeTerminalScreen use custom terminal widgets (ClaudeTerminal and ResumeTerminal) that provide better process management.

## Important Concepts

### Screen Types

1. **Full-Screen Screens** (`TerminalScreen`, `ResumeTerminalScreen`)
   - Take over the entire application viewport
   - Provide immersive terminal experience
   - Include header, footer, and status bar
   - Handle complex lifecycle and process management

2. **Modal Screens** (`NewSessionScreen`)
   - Overlay on top of existing content
   - Centered dialog-style interface
   - Block interaction with underlying content
   - Return values via `dismiss(result)`

### Process Lifecycle Management

All terminal screens implement robust process management:

1. **Session Start**: Track spawned PIDs via `app.state.track_spawned_pid()`
2. **Session End**: Untrack PIDs when process exits normally
3. **Graceful Shutdown**: Send `/exit` command and wait for clean exit
4. **Force Shutdown**: Send SIGTERM/SIGKILL for immediate termination
5. **App Exit Cleanup**: App ensures all tracked PIDs are killed on exit

### Interrupt Handling Pattern

Both TerminalScreen and ResumeTerminalScreen use a double-press interrupt pattern:
- **First Ctrl+C**: Sends interrupt to Claude (allows graceful handling)
- **Second Ctrl+C** (within 2 seconds): Force kills the session
- Timer reset after 2 seconds of inactivity

This prevents accidental force quits while allowing users to recover from hung sessions.

### Key Bindings

Common across terminal screens:
- **ESC**: Graceful close (sends `/exit` command)
- **Ctrl+C**: Interrupt (double-press to force quit)
- **Ctrl+Q**: Immediate force quit (SIGTERM)

NewSessionScreen bindings:
- **ESC**: Cancel and close modal
- **Enter**: Submit path and start session

## Usage Examples

### Starting a New Session

```python
# From the main app, push the NewSessionScreen to get a directory
result = await self.push_screen_wait(NewSessionScreen(default_path="/home/user/project"))

if result:  # User provided a valid path
    # Push TerminalScreen with the selected directory
    self.push_screen(TerminalScreen(cwd=result))
```

### Resuming an Existing Session

```python
# Resume a session by ID
self.push_screen(
    ResumeTerminalScreen(
        session_id="abc123def456",
        cwd="/path/to/project",
        initial_message="Continue implementing the feature"
    )
)
```

### Custom Event Handling

```python
# In the parent screen/app, handle terminal events
def on_claude_terminal_session_started(self, event):
    """React to session start"""
    self.log(f"Session started with PID {event.pid}")

def on_claude_terminal_session_ended(self, event):
    """React to session end"""
    if event.exit_code == 0:
        self.notify("Session completed successfully")
    else:
        self.notify(f"Session exited with code {event.exit_code}", severity="warning")
```

## Dependencies

### Internal Dependencies

- `../widgets/claude_terminal.py` - ClaudeTerminal widget (used by TerminalScreen)
- `../widgets/resume_terminal.py` - ResumeTerminal widget (used by ResumeTerminalScreen)
- Parent `app.state` - For tracking spawned PIDs and cleanup

### External Dependencies

- `textual` - Core TUI framework
  - `textual.screen.Screen` - Base screen class
  - `textual.screen.ModalScreen` - Modal overlay screen
  - `textual.widgets` - Header, Footer, Static, Input, Button
  - `textual.containers.Container` - Layout container
  - `textual.binding.Binding` - Keyboard shortcuts
- `textual-terminal` (optional) - Used by EmbeddedTerminalScreen only

### System Dependencies

- `claude` CLI must be available in system PATH (for terminal screens)
- `bash` shell for running compound commands

## Relationship with Other Modules

### Widgets Module (`../widgets/`)
The screens module is a consumer of terminal widgets:
- **ClaudeTerminal**: Embedded terminal for new sessions (PTY-based)
- **ResumeTerminal**: Specialized terminal for resuming sessions
- Both widgets emit custom events (SessionStarted, SessionEnded) that screens handle

### App State (`app.state`)
Terminal screens interact with application state for process tracking:
- `track_spawned_pid(pid)` - Register process for cleanup
- `untrack_spawned_pid(pid)` - Deregister on normal exit
- App ensures all tracked processes are killed on exit

### Main Application
Screens are pushed onto the application's screen stack:
```python
# Modal - returns a result
path = await app.push_screen_wait(NewSessionScreen())

# Full-screen - no return value
app.push_screen(TerminalScreen(cwd=path))

# Pop to close
app.pop_screen()
```

## Design Patterns

### Screen Stack Navigation
Screens use Textual's screen stack for navigation:
- Push screens with `app.push_screen()` or `push_screen_wait()` for modals
- Pop screens with `app.pop_screen()` or `self.dismiss(result)` for modals
- Screens can be layered (modal on top of full-screen)

### Event Bubbling
Terminal widget events bubble up to screens, then to app:
1. Widget emits custom event (e.g., `SessionStarted`)
2. Screen handles event with `on_<widget>_<event>` method
3. Screen can stop propagation or let it bubble to app
4. App can react to events from any screen/widget

### Defensive Process Management
All terminal screens follow defensive practices:
- Always track spawned processes
- Always untrack on normal exit
- Provide multiple exit strategies (graceful, interrupt, force)
- Handle crashes and unexpected terminations
- Clean up on app exit via tracked PIDs

### Consistent UX Patterns
All terminal screens share:
- Same key bindings for consistency
- Similar status bar layouts
- Unified interrupt handling (double-press pattern)
- Consistent notification messages
- Similar CSS styling

## Future Considerations

1. **Unified Terminal Screen**: TerminalScreen and ResumeTerminalScreen share 90% of their code. Could be refactored into a single screen with a mode parameter.

2. **EmbeddedTerminalScreen**: Currently not used. Could be removed or updated to use the same pattern as TerminalScreen.

3. **Session History Integration**: NewSessionScreen could show recently used directories or suggest directories based on existing sessions.

4. **Path Auto-completion**: NewSessionScreen input could provide tab-completion for directory paths.

5. **Session Templates**: NewSessionScreen could offer preset configurations or templates for common project types.
