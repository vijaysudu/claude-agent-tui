# UI Design

## Overview

The Claude Agent Visualizer uses a responsive terminal UI built with Textual. The interface is designed for real-time monitoring with intuitive navigation and interaction.

---

## Layout Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ Header: Status Bar                                                         [1] │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌───────────────────────────────┐  ┌────────────────────────────────────────┐ │
│  │                               │  │                                        │ │
│  │                               │  │                                        │ │
│  │   Session Tree               │  │   Detail Panel                        │ │
│  │   (scrollable)               │  │   (context-sensitive)                 │ │
│  │                               │  │                                        │ │
│  │   [2]                        │  │   [3]                                  │ │
│  │                               │  │                                        │ │
│  │                               │  │                                        │ │
│  │                               │  │                                        │ │
│  └───────────────────────────────┘  └────────────────────────────────────────┘ │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│ Footer: Key Bindings                                                       [4] │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Regions:**
1. **Header/Status Bar** - Global stats and notifications
2. **Session Tree** - Hierarchical view (40% width)
3. **Detail Panel** - Agent details (60% width)
4. **Footer** - Available key bindings

---

## Component Details

### 1. Status Bar (Header)

Shows global statistics and notification indicators.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ ⬤ Claude Agent Visualizer    Sessions: 3    Agents: 12    ⚠ 2 awaiting input  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Elements:**
- **Logo/Title** - Application name with status dot (green = connected, red = error)
- **Session Count** - Number of active sessions
- **Agent Count** - Total running agents across sessions
- **Input Alert** - Pulsing indicator when inputs are pending

**Styling:**

```tcss
StatusBar {
    dock: top;
    height: 1;
    background: $surface;
    color: $text;
}

StatusBar .logo {
    color: $primary;
    text-style: bold;
}

StatusBar .alert {
    color: $warning;
    text-style: bold blink;
}
```

---

### 2. Session Tree (Left Panel)

Hierarchical tree showing sessions, agents, and their status.

```
┌─ Sessions ────────────────────────────────┐
│ ▼ ~/projects/myapp                  5m32s │
│   ├─● Root                    15.2k tok   │
│   │  ├─● Explore: Find auth       running │
│   │  │  └─○ Grep → 12 files     completed │
│   │  └─◐ Plan: Design login   ⚠ awaiting │
│   │       └─ ? "Which auth method?"       │
│   └─○ Bash: npm test            completed │
│                                           │
│ ▶ ~/projects/api                    2m15s │
│ ▶ ~/projects/docs                   0m45s │
└───────────────────────────────────────────┘
```

**Tree Node Types:**

| Icon | Meaning |
|------|---------|
| `▼` | Expanded session/agent |
| `▶` | Collapsed session/agent |
| `●` | Running agent (yellow) |
| `○` | Completed agent (green) |
| `✗` | Failed agent (red) |
| `◐` | Awaiting input (blue, pulsing) |
| `?` | Input request indicator |

**Node Label Format:**

```
Session:  {working_dir_short}                    {duration}
Agent:    {status_icon} {type}: {description}    {status_text}
Tool:     └─{result_icon} {tool_name} → {result} {status_text}
Input:    └─ ? "{prompt_preview}"
```

**Interactions:**

| Key | Action |
|-----|--------|
| `↑/↓` | Navigate tree |
| `Space` | Expand/collapse node |
| `Enter` | Select (show in detail panel) / Respond to input |
| `Tab` | Jump to next session |
| `Shift+Tab` | Jump to previous session |

**Tree Widget Implementation:**

```python
class SessionTree(Tree[Union[Session, Agent, ToolUse, InputRequest]]):
    """Hierarchical tree of sessions and agents."""

    BINDINGS = [
        ("space", "toggle_node", "Expand/Collapse"),
        ("enter", "select_node", "Select"),
    ]

    def __init__(self):
        super().__init__("Sessions", id="session-tree")

    def build_tree(self, sessions: List[Session]):
        """Rebuild tree from session data."""
        self.clear()
        for session in sessions:
            session_node = self.root.add(
                self._session_label(session),
                data=session,
                expand=session.status == SessionStatus.ACTIVE
            )
            self._add_agents(session_node, session.root_agent)

    def _add_agents(self, parent_node: TreeNode, agent: Agent):
        """Recursively add agent nodes."""
        agent_node = parent_node.add(
            self._agent_label(agent),
            data=agent,
            expand=agent.status in (AgentStatus.RUNNING, AgentStatus.WAITING_INPUT)
        )

        # Add tool uses
        for tool in agent.tool_uses[-5:]:  # Last 5 tools
            parent_node.add_leaf(self._tool_label(tool), data=tool)

        # Add pending input requests
        for req in agent.input_requests:
            if req.status == InputRequestStatus.PENDING:
                agent_node.add_leaf(self._input_label(req), data=req)

        # Recurse for children
        for child in agent.children:
            self._add_agents(agent_node, child)

    def _session_label(self, session: Session) -> Text:
        """Format session node label."""
        dir_short = Path(session.working_dir).name
        duration = format_duration(session.duration)
        return Text.assemble(
            (dir_short, "bold"),
            " ",
            (duration, "dim"),
        )

    def _agent_label(self, agent: Agent) -> Text:
        """Format agent node label."""
        return Text.assemble(
            (agent.status_icon, agent.status_color),
            " ",
            (agent.agent_type, "bold"),
            ": ",
            (agent.description[:30], ""),
        )
```

---

### 3. Detail Panel (Right Panel)

Shows detailed information for the selected tree node.

**Agent Detail View:**

```
┌─ Agent Details ───────────────────────────────────────────────┐
│                                                               │
│  Type: Explore                     Status: ● Running          │
│  Started: 2 minutes ago            Duration: 2m 15s           │
│                                                               │
│  ┌─ Context ──────────────────────────────────────────────┐  │
│  │  Tokens: ████████░░░░░░░░░░ 15,234 / 100,000           │  │
│  │  Messages: 24                                           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Description ──────────────────────────────────────────┐  │
│  │  Find all authentication-related files in the codebase │  │
│  │  and document the authentication flow...               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Recent Tools ─────────────────────────────────────────┐  │
│  │  ○ Glob: **/*.py              → 45 files     completed │  │
│  │  ○ Grep: "auth"               → 12 matches   completed │  │
│  │  ● Read: src/auth/login.py                   running   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Session Detail View:**

```
┌─ Session Details ─────────────────────────────────────────────┐
│                                                               │
│  Directory: ~/projects/myapp                                  │
│  Started: 5 minutes ago            Status: ● Active           │
│  PID: 12345                                                   │
│                                                               │
│  ┌─ Statistics ───────────────────────────────────────────┐  │
│  │  Total Agents: 5     Active: 2     Completed: 3        │  │
│  │  Total Tokens: 45,678                                   │  │
│  │  Pending Inputs: 1                                      │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Agent Summary ────────────────────────────────────────┐  │
│  │  ● Explore (2)   ○ Plan (1)   ○ Bash (2)              │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

**Input Request Detail View:**

```
┌─ Input Request ───────────────────────────────────────────────┐
│                                                               │
│  Agent: Plan: Design login flow                               │
│  Session: ~/projects/myapp                                    │
│  Waiting: 45 seconds                                          │
│                                                               │
│  ┌─ Question ─────────────────────────────────────────────┐  │
│  │                                                         │  │
│  │  Which authentication method should we implement?       │  │
│  │                                                         │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  ┌─ Options ──────────────────────────────────────────────┐  │
│  │  [1] OAuth 2.0 - Industry standard for third-party     │  │
│  │  [2] JWT - Stateless token-based authentication        │  │
│  │  [3] Session-based - Traditional server-side sessions  │  │
│  │  [4] Other - Enter custom response                     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Press [Enter] to respond or [1-4] to quick-select           │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

### 4. Footer (Key Bindings)

Shows available keyboard shortcuts for current context.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│ [↑↓] Navigate  [Space] Expand  [Enter] Select/Respond  [Tab] Next  [q] Quit    │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Context-Sensitive Bindings:**

| Context | Extra Bindings |
|---------|----------------|
| Default | `[r] Refresh` `[/] Filter` `[?] Help` |
| Input Selected | `[Enter] Respond` `[1-9] Quick Select` |
| Agent Selected | `[c] Copy ID` `[l] View Logs` |

---

### 5. Input Modal (Overlay)

Modal dialog for responding to input requests.

```
┌────────────────────────────────────────────────────────────────┐
│                                                                │
│  ┌─ Respond to Input ───────────────────────────────────────┐ │
│  │                                                           │ │
│  │  Agent: Plan: Design login flow                          │ │
│  │  Session: ~/projects/myapp                               │ │
│  │                                                           │ │
│  │  Question:                                                │ │
│  │  Which authentication method should we implement?         │ │
│  │                                                           │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ > OAuth 2.0                                         │ │ │
│  │  │   JWT                                               │ │ │
│  │  │   Session-based                                     │ │ │
│  │  │   Other...                                          │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                           │ │
│  │  [Enter] Submit    [Esc] Cancel                          │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**For text input (no options):**

```
│  │  Question:                                                │ │
│  │  What should the function be named?                       │ │
│  │                                                           │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ authenticate_user█                                  │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
```

---

## Color Scheme

### Default Theme (Dark)

```tcss
$background: #1a1b26;
$surface: #24283b;
$surface-light: #414868;
$primary: #7aa2f7;
$secondary: #bb9af7;
$success: #9ece6a;
$warning: #e0af68;
$error: #f7768e;
$text: #c0caf5;
$text-muted: #565f89;
```

### Status Colors

```tcss
.status-running {
    color: $warning;
}

.status-completed {
    color: $success;
}

.status-failed {
    color: $error;
}

.status-waiting {
    color: $primary;
    text-style: bold;
}
```

### Syntax Highlighting (for code/logs)

```tcss
.syntax-keyword { color: #bb9af7; }
.syntax-string { color: #9ece6a; }
.syntax-number { color: #ff9e64; }
.syntax-comment { color: #565f89; }
```

---

## Animations

### Pulsing Indicator (Waiting for Input)

```tcss
@keyframes pulse {
    0% { opacity: 1.0; }
    50% { opacity: 0.5; }
    100% { opacity: 1.0; }
}

.waiting-indicator {
    animation: pulse 1s infinite;
}
```

### Progress Spinner

Using Textual's built-in `LoadingIndicator` or custom:

```
⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏  (Braille spinner)
```

---

## Responsive Behavior

### Narrow Terminal (< 80 cols)

- Hide detail panel
- Show full-width tree
- Expand selected node inline

```
┌─ Sessions ──────────────────────────────────┐
│ ▼ ~/myapp                            5m32s │
│   ├─● Explore: Find auth           running │
│   │                                         │
│   │  Tokens: 15,234  Msgs: 24              │
│   │  ─────────────────────────             │
│   │  Description: Find all                 │
│   │  authentication-related files...       │
│   │                                         │
└─────────────────────────────────────────────┘
```

### Wide Terminal (> 160 cols)

- Add third column for tool details
- Expand tree indentation

---

## Accessibility

1. **Keyboard-only navigation** - All features accessible via keyboard
2. **Screen reader support** - Meaningful labels for tree nodes
3. **High contrast mode** - Option for increased contrast
4. **No color-only indicators** - Icons + colors for status

---

## Textual Component Map

```python
# Main application structure
App
├── Static (logo)
├── Horizontal
│   ├── SessionTree (Tree)
│   └── Vertical
│       ├── AgentDetailPanel (Container)
│       │   ├── Static (type/status)
│       │   ├── ProgressBar (tokens)
│       │   └── DataTable (tools)
│       └── InputDetailPanel (Container)
│           ├── Static (question)
│           └── OptionList (options)
├── Footer
└── InputModal (ModalScreen)
    ├── Static (header)
    ├── OptionList or Input
    └── Horizontal (buttons)
```
