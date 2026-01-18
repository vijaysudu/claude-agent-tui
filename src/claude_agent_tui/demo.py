"""Demo data for Claude Agent Visualizer testing."""

from __future__ import annotations

from pathlib import Path

from .store.models import Session, ToolUse, ToolStatus


# Sample file contents for demo
SAMPLE_PYTHON_CONTENT = '''"""Authentication module for the application."""

from typing import Optional
import hashlib
import secrets


class AuthManager:
    """Manages user authentication."""

    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self._sessions: dict[str, dict] = {}

    def login(self, username: str, password: str) -> Optional[str]:
        """Authenticate a user and return a session token.

        Args:
            username: The username.
            password: The password.

        Returns:
            Session token if successful, None otherwise.
        """
        # Hash the password
        password_hash = self._hash_password(password)

        # Validate credentials (simplified)
        if self._validate_credentials(username, password_hash):
            token = secrets.token_urlsafe(32)
            self._sessions[token] = {"username": username}
            return token
        return None

    def _hash_password(self, password: str) -> str:
        """Hash a password with the secret key."""
        return hashlib.sha256(
            f"{password}{self.secret_key}".encode()
        ).hexdigest()

    def _validate_credentials(self, username: str, password_hash: str) -> bool:
        """Validate user credentials."""
        # In a real app, this would check against a database
        return True
'''

SAMPLE_BASH_OUTPUT = '''$ npm run build

> myapp@1.0.0 build
> tsc && vite build

vite v5.0.0 building for production...
transforming...
✓ 234 modules transformed.
rendering chunks...
computing gzip size...

dist/index.html                  0.42 kB │ gzip:  0.28 kB
dist/assets/index-a1b2c3d4.css  15.23 kB │ gzip:  4.21 kB
dist/assets/index-e5f6g7h8.js   89.45 kB │ gzip: 28.67 kB

✓ built in 3.24s
'''

SAMPLE_GREP_OUTPUT = '''src/auth/login.py:15:    def login(self, username: str, password: str):
src/auth/login.py:42:    async def login_async(self, username: str, password: str):
src/api/routes.py:28:@router.post("/login")
src/api/routes.py:29:async def handle_login(request: LoginRequest):
tests/test_auth.py:15:    def test_login_success(self):
tests/test_auth.py:34:    def test_login_failure(self):
'''

SAMPLE_GLOB_OUTPUT = '''src/auth/__init__.py
src/auth/login.py
src/auth/logout.py
src/auth/session.py
src/auth/middleware.py
src/auth/utils.py
'''


def create_demo_sessions() -> list[Session]:
    """Create demo sessions with rich content for testing.

    Returns:
        List of demo sessions.
    """
    sessions = []

    # Session 1: Feature implementation
    session1 = Session(
        session_id="demo-feature-impl-abc123",
        session_path=Path("/demo/session1.jsonl"),
        message_count=15,
        start_time="2025-01-17T10:30:00Z",
        is_active=False,
    )

    session1.tool_uses = [
        ToolUse(
            tool_use_id="tool-001",
            tool_name="Glob",
            input_params={"pattern": "src/auth/**/*.py"},
            status=ToolStatus.COMPLETED,
            preview="src/auth/**/*.py",
            result_content=SAMPLE_GLOB_OUTPUT,
        ),
        ToolUse(
            tool_use_id="tool-002",
            tool_name="Read",
            input_params={"file_path": "src/auth/login.py"},
            status=ToolStatus.COMPLETED,
            preview="src/auth/login.py",
            result_content=SAMPLE_PYTHON_CONTENT,
        ),
        ToolUse(
            tool_use_id="tool-003",
            tool_name="Grep",
            input_params={"pattern": "def login", "path": "src/"},
            status=ToolStatus.COMPLETED,
            preview="def login in src/",
            result_content=SAMPLE_GREP_OUTPUT,
        ),
        ToolUse(
            tool_use_id="tool-004",
            tool_name="Edit",
            input_params={
                "file_path": "src/auth/login.py",
                "old_string": "    def login(self, username: str, password: str):",
                "new_string": "    def login(self, username: str, password: str, remember: bool = False):",
            },
            status=ToolStatus.COMPLETED,
            preview="src/auth/login.py (edit)",
            result_content="File edited successfully",
        ),
        ToolUse(
            tool_use_id="tool-005",
            tool_name="Bash",
            input_params={"command": "npm run build"},
            status=ToolStatus.COMPLETED,
            preview="npm run build",
            result_content=SAMPLE_BASH_OUTPUT,
        ),
    ]

    sessions.append(session1)

    # Session 2: Bug fix
    session2 = Session(
        session_id="demo-bugfix-def456",
        session_path=Path("/demo/session2.jsonl"),
        message_count=8,
        start_time="2025-01-17T11:45:00Z",
        is_active=True,
    )

    session2.tool_uses = [
        ToolUse(
            tool_use_id="tool-101",
            tool_name="Grep",
            input_params={"pattern": "TypeError", "path": "logs/"},
            status=ToolStatus.COMPLETED,
            preview="TypeError in logs/",
            result_content='''logs/error.log:2025-01-17 11:30:15 TypeError: Cannot read property 'id' of undefined
logs/error.log:2025-01-17 11:30:15     at processUser (src/api/users.js:45)
logs/error.log:2025-01-17 11:30:15     at async handleRequest (src/api/routes.js:23)
''',
        ),
        ToolUse(
            tool_use_id="tool-102",
            tool_name="Read",
            input_params={"file_path": "src/api/users.js"},
            status=ToolStatus.COMPLETED,
            preview="src/api/users.js",
            result_content='''// User API handlers
const processUser = async (user) => {
    // BUG: user might be undefined
    const userId = user.id;
    const profile = await fetchProfile(userId);
    return profile;
};

export { processUser };
''',
        ),
        ToolUse(
            tool_use_id="tool-103",
            tool_name="Edit",
            input_params={
                "file_path": "src/api/users.js",
                "old_string": "    const userId = user.id;",
                "new_string": "    if (!user) throw new Error('User is required');\n    const userId = user.id;",
            },
            status=ToolStatus.COMPLETED,
            preview="src/api/users.js (edit)",
            result_content="File edited successfully",
        ),
        ToolUse(
            tool_use_id="tool-104",
            tool_name="Bash",
            input_params={"command": "npm test"},
            status=ToolStatus.ERROR,
            preview="npm test",
            error_message='''FAIL src/api/__tests__/users.test.js
  ● User API › processUser › should handle null user

    expect(received).rejects.toThrow()

    Expected: Error with message 'User is required'
    Received: TypeError: Cannot read property 'id' of null

      45 |     expect(async () => {
      46 |       await processUser(null);
    > 47 |     }).rejects.toThrow('User is required');
         |                ^
''',
        ),
    ]

    sessions.append(session2)

    # Session 3: Code review
    session3 = Session(
        session_id="demo-review-ghi789",
        session_path=Path("/demo/session3.jsonl"),
        message_count=5,
        start_time="2025-01-17T09:00:00Z",
        is_active=False,
    )

    session3.tool_uses = [
        ToolUse(
            tool_use_id="tool-201",
            tool_name="Read",
            input_params={"file_path": "src/utils/validation.ts"},
            status=ToolStatus.COMPLETED,
            preview="src/utils/validation.ts",
            result_content='''import { z } from 'zod';

export const userSchema = z.object({
    id: z.string().uuid(),
    email: z.string().email(),
    name: z.string().min(1).max(100),
    age: z.number().int().min(0).max(150).optional(),
    role: z.enum(['admin', 'user', 'guest']),
    createdAt: z.date(),
});

export type User = z.infer<typeof userSchema>;

export const validateUser = (data: unknown): User => {
    return userSchema.parse(data);
};
''',
        ),
        ToolUse(
            tool_use_id="tool-202",
            tool_name="Task",
            input_params={
                "description": "Review validation logic",
                "prompt": "Review the validation schema for security issues",
            },
            status=ToolStatus.COMPLETED,
            preview="Review validation logic",
            result_content="Validation review completed. No critical issues found.",
        ),
    ]

    sessions.append(session3)

    return sessions
