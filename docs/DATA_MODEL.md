# Data Model

## Overview

This document defines the event schema and data structures used throughout Claude Agent Visualizer.

---

## Event Types

All events emitted from Claude Code hooks follow a common envelope structure:

```python
@dataclass
class EventEnvelope:
    event_type: str          # Type of event (see below)
    timestamp: datetime      # When the event occurred
    session_id: str          # Claude Code session identifier
    payload: dict            # Event-specific data
```

### Event Type Hierarchy

```
events/
├── session/
│   ├── session_start
│   ├── session_end
│   └── session_error
├── agent/
│   ├── agent_start
│   ├── agent_update
│   ├── agent_complete
│   └── agent_error
├── tool/
│   ├── tool_start
│   ├── tool_complete
│   └── tool_error
└── input/
    ├── input_request
    ├── input_response
    └── input_timeout
```

---

## Session Events

### `session_start`

Emitted when a Claude Code session begins.

```python
@dataclass
class SessionStartEvent:
    session_id: str
    working_dir: str         # Absolute path to working directory
    pid: int                 # Process ID of Claude Code
    started_at: datetime
    user: str                # Username (for multi-user systems)
    claude_version: str      # Claude Code version
```

**Example:**

```json
{
  "event_type": "session_start",
  "timestamp": "2025-01-15T17:15:00Z",
  "session_id": "sess_abc123",
  "payload": {
    "working_dir": "/Users/vijay/projects/myapp",
    "pid": 12345,
    "started_at": "2025-01-15T17:15:00Z",
    "user": "vijay",
    "claude_version": "1.0.0"
  }
}
```

### `session_end`

Emitted when a Claude Code session ends normally.

```python
@dataclass
class SessionEndEvent:
    session_id: str
    ended_at: datetime
    duration_seconds: float
    total_agents: int        # Total agents spawned
    total_tokens: int        # Total tokens used
    exit_reason: str         # "user_exit", "completed", "error"
```

### `session_error`

Emitted when a session encounters an unrecoverable error.

```python
@dataclass
class SessionErrorEvent:
    session_id: str
    error_type: str
    error_message: str
    stack_trace: Optional[str]
```

---

## Agent Events

### `agent_start`

Emitted when a new agent is spawned via the Task tool.

```python
@dataclass
class AgentStartEvent:
    agent_id: str            # Unique identifier for this agent
    session_id: str          # Parent session
    parent_agent_id: Optional[str]  # Parent agent (None for root)
    agent_type: str          # "Explore", "Plan", "Bash", "general-purpose", etc.
    description: str         # Short description (from Task tool)
    prompt_preview: str      # First 200 chars of the prompt
    model: Optional[str]     # Model override if specified
    started_at: datetime
```

**Example:**

```json
{
  "event_type": "agent_start",
  "timestamp": "2025-01-15T17:15:30Z",
  "session_id": "sess_abc123",
  "payload": {
    "agent_id": "agent_def456",
    "session_id": "sess_abc123",
    "parent_agent_id": null,
    "agent_type": "Explore",
    "description": "Find auth files",
    "prompt_preview": "Search the codebase for authentication-related files...",
    "model": null,
    "started_at": "2025-01-15T17:15:30Z"
  }
}
```

### `agent_update`

Emitted periodically to update agent metrics.

```python
@dataclass
class AgentUpdateEvent:
    agent_id: str
    tokens_used: int         # Total tokens consumed so far
    messages_count: int      # Number of messages in context
    current_task: Optional[str]  # Current task description
    tools_used_count: int    # Number of tool calls made
```

### `agent_complete`

Emitted when an agent finishes execution.

```python
@dataclass
class AgentCompleteEvent:
    agent_id: str
    status: str              # "completed", "failed", "cancelled"
    ended_at: datetime
    duration_seconds: float
    tokens_used: int
    result_preview: Optional[str]  # First 200 chars of result
    error_message: Optional[str]   # If status is "failed"
```

### `agent_error`

Emitted when an agent encounters an error.

```python
@dataclass
class AgentErrorEvent:
    agent_id: str
    error_type: str
    error_message: str
    recoverable: bool        # Whether the agent can continue
```

---

## Tool Events

### `tool_start`

Emitted before a tool is executed.

```python
@dataclass
class ToolStartEvent:
    tool_use_id: str         # Unique ID for this tool use
    agent_id: str            # Agent making the tool call
    tool_name: str           # "Read", "Write", "Bash", "Grep", etc.
    tool_category: str       # "builtin", "skill", "mcp", "command"
    parameters: dict         # Tool parameters (sanitized)
    started_at: datetime
```

**Tool Categories:**

| Category | Examples |
|----------|----------|
| `builtin` | Read, Write, Edit, Grep, Glob, Bash |
| `skill` | commit, review-pr, atlassian-cli |
| `mcp` | mcp__github__*, mcp__datadog__* |
| `command` | Task, AskUserQuestion |

**Example:**

```json
{
  "event_type": "tool_start",
  "timestamp": "2025-01-15T17:15:35Z",
  "session_id": "sess_abc123",
  "payload": {
    "tool_use_id": "tool_ghi789",
    "agent_id": "agent_def456",
    "tool_name": "Grep",
    "tool_category": "builtin",
    "parameters": {
      "pattern": "authentication",
      "path": "/Users/vijay/projects/myapp/src"
    },
    "started_at": "2025-01-15T17:15:35Z"
  }
}
```

### `tool_complete`

Emitted after a tool finishes execution.

```python
@dataclass
class ToolCompleteEvent:
    tool_use_id: str
    status: str              # "completed", "failed", "rejected"
    ended_at: datetime
    duration_ms: int
    result_preview: Optional[str]  # First 200 chars (sanitized)
    error_message: Optional[str]
```

---

## Input Events

### `input_request`

Emitted when an agent needs user input (via AskUserQuestion).

```python
@dataclass
class InputRequestEvent:
    request_id: str          # Unique ID for this request
    agent_id: str
    session_id: str
    request_type: str        # "question", "confirmation", "selection"
    prompt: str              # The question text
    options: Optional[List[InputOption]]  # For selection type
    timeout_seconds: Optional[int]        # Auto-timeout
    created_at: datetime

@dataclass
class InputOption:
    label: str               # Display text
    value: str               # Value to return
    description: Optional[str]
```

**Example:**

```json
{
  "event_type": "input_request",
  "timestamp": "2025-01-15T17:16:00Z",
  "session_id": "sess_abc123",
  "payload": {
    "request_id": "req_jkl012",
    "agent_id": "agent_def456",
    "session_id": "sess_abc123",
    "request_type": "selection",
    "prompt": "Which authentication method should we use?",
    "options": [
      {"label": "OAuth 2.0", "value": "oauth", "description": "Industry standard"},
      {"label": "JWT", "value": "jwt", "description": "Stateless tokens"},
      {"label": "Session-based", "value": "session", "description": "Traditional approach"}
    ],
    "timeout_seconds": 300,
    "created_at": "2025-01-15T17:16:00Z"
  }
}
```

### `input_response`

Emitted when a user responds to an input request.

```python
@dataclass
class InputResponseEvent:
    request_id: str
    response: str            # User's response text or selected value
    responded_at: datetime
    response_source: str     # "dashboard", "cli", "direct"
```

### `input_timeout`

Emitted when an input request times out.

```python
@dataclass
class InputTimeoutEvent:
    request_id: str
    timed_out_at: datetime
```

---

## Domain Models

These are the internal models used by the TUI application:

### Session

```python
@dataclass
class Session:
    id: str
    working_dir: str
    started_at: datetime
    ended_at: Optional[datetime]
    status: SessionStatus
    pid: int
    agents: List[Agent]

    @property
    def duration(self) -> timedelta:
        end = self.ended_at or datetime.now()
        return end - self.started_at

    @property
    def root_agent(self) -> Optional[Agent]:
        return next((a for a in self.agents if a.parent_id is None), None)

    @property
    def total_tokens(self) -> int:
        return sum(a.tokens_used for a in self.agents)

    @property
    def pending_inputs(self) -> List[InputRequest]:
        return [i for a in self.agents for i in a.input_requests if i.status == "pending"]


class SessionStatus(Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
```

### Agent

```python
@dataclass
class Agent:
    id: str
    session_id: str
    parent_id: Optional[str]
    agent_type: str
    description: str
    status: AgentStatus
    started_at: datetime
    ended_at: Optional[datetime]
    tokens_used: int
    messages_count: int
    tool_uses: List[ToolUse]
    input_requests: List[InputRequest]
    children: List[Agent]

    @property
    def duration(self) -> timedelta:
        end = self.ended_at or datetime.now()
        return end - self.started_at

    @property
    def status_icon(self) -> str:
        return {
            AgentStatus.RUNNING: "●",
            AgentStatus.COMPLETED: "○",
            AgentStatus.FAILED: "✗",
            AgentStatus.WAITING_INPUT: "◐",
        }[self.status]

    @property
    def status_color(self) -> str:
        return {
            AgentStatus.RUNNING: "yellow",
            AgentStatus.COMPLETED: "green",
            AgentStatus.FAILED: "red",
            AgentStatus.WAITING_INPUT: "blue",
        }[self.status]


class AgentStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_INPUT = "waiting_input"
```

### ToolUse

```python
@dataclass
class ToolUse:
    id: str
    agent_id: str
    tool_name: str
    tool_category: ToolCategory
    parameters: dict
    status: ToolStatus
    started_at: datetime
    ended_at: Optional[datetime]
    duration_ms: Optional[int]
    result_preview: Optional[str]
    error_message: Optional[str]

    @property
    def display_name(self) -> str:
        if self.tool_category == ToolCategory.MCP:
            # mcp__github__get_file → GitHub: get_file
            parts = self.tool_name.split("__")
            if len(parts) >= 3:
                return f"{parts[1].title()}: {parts[2]}"
        elif self.tool_category == ToolCategory.SKILL:
            return f"/{self.tool_name}"
        return self.tool_name


class ToolCategory(Enum):
    BUILTIN = "builtin"
    SKILL = "skill"
    MCP = "mcp"
    COMMAND = "command"


class ToolStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
```

### InputRequest

```python
@dataclass
class InputRequest:
    id: str
    agent_id: str
    session_id: str
    request_type: InputRequestType
    prompt: str
    options: Optional[List[InputOption]]
    status: InputRequestStatus
    response: Optional[str]
    created_at: datetime
    responded_at: Optional[datetime]
    timeout_at: Optional[datetime]

    @property
    def is_expired(self) -> bool:
        if self.timeout_at is None:
            return False
        return datetime.now() > self.timeout_at


class InputRequestType(Enum):
    QUESTION = "question"
    CONFIRMATION = "confirmation"
    SELECTION = "selection"


class InputRequestStatus(Enum):
    PENDING = "pending"
    RESPONDED = "responded"
    EXPIRED = "expired"
```

---

## Parameter Sanitization

Certain tool parameters may contain sensitive data that should not be stored:

```python
SENSITIVE_PATTERNS = [
    r"password",
    r"secret",
    r"token",
    r"api[_-]?key",
    r"auth",
    r"credential",
]

def sanitize_parameters(params: dict) -> dict:
    """Remove or mask sensitive parameter values."""
    sanitized = {}
    for key, value in params.items():
        if any(re.search(p, key, re.I) for p in SENSITIVE_PATTERNS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, str) and len(value) > 500:
            sanitized[key] = value[:500] + "...[truncated]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_parameters(value)
        else:
            sanitized[key] = value
    return sanitized
```

---

## Database Queries

### Get Active Sessions

```sql
SELECT
    s.*,
    COUNT(DISTINCT a.id) as agent_count,
    SUM(a.tokens_used) as total_tokens,
    COUNT(DISTINCT ir.id) FILTER (WHERE ir.status = 'pending') as pending_inputs
FROM sessions s
LEFT JOIN agents a ON a.session_id = s.id
LEFT JOIN input_requests ir ON ir.session_id = s.id
WHERE s.status = 'active'
GROUP BY s.id
ORDER BY s.started_at DESC;
```

### Get Agent Hierarchy

```sql
WITH RECURSIVE agent_tree AS (
    -- Base case: root agents
    SELECT
        a.*,
        0 as depth,
        a.id as path
    FROM agents a
    WHERE a.session_id = ? AND a.parent_id IS NULL

    UNION ALL

    -- Recursive case: child agents
    SELECT
        a.*,
        at.depth + 1,
        at.path || '/' || a.id
    FROM agents a
    JOIN agent_tree at ON a.parent_id = at.id
)
SELECT * FROM agent_tree ORDER BY path;
```

### Get Pending Input Requests

```sql
SELECT
    ir.*,
    a.agent_type,
    a.description as agent_description,
    s.working_dir
FROM input_requests ir
JOIN agents a ON ir.agent_id = a.id
JOIN sessions s ON ir.session_id = s.id
WHERE ir.status = 'pending'
ORDER BY ir.created_at ASC;
```
