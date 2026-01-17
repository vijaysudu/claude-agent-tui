"""CLI entry point for Claude Agent Visualizer."""

import click

from . import __version__


@click.group(invoke_without_command=True)
@click.option("--demo", is_flag=True, help="Run with demo data for testing")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.version_option(version=__version__)
@click.pass_context
def main(ctx, demo: bool, verbose: bool):
    """Claude Agent Visualizer - Monitor your Claude Code agents in real-time.

    This tool reads Claude Code's session files to display active and recent
    sessions with their tool uses and activity.

    Usage:
        claude-viz          Start the dashboard
        claude-viz --demo   Start with demo data for testing
    """
    # If no subcommand is given, run the dashboard
    if ctx.invoked_subcommand is None:
        _run_dashboard(demo=demo, verbose=verbose)


def _run_dashboard(demo: bool = False, verbose: bool = False) -> None:
    """Run the TUI dashboard."""
    from .logging import setup_logging
    from .tui.app import run_app

    setup_logging(verbose=verbose)

    if demo:
        from .demo import create_demo_state

        click.echo("Starting in demo mode...")
        state = create_demo_state()
        run_app(state=state)
    else:
        run_app()


@main.command()
@click.option("--demo", is_flag=True, help="Run with demo data for testing")
def run(demo: bool):
    """Start the agent visualizer dashboard."""
    _run_dashboard(demo=demo)


@main.command()
@click.option("--max-sessions", default=50, help="Maximum sessions to display")
@click.option("--max-age", default=24, help="Maximum session age in hours")
def scan(max_sessions: int, max_age: int):
    """Scan and list Claude Code sessions.

    Displays recent sessions found in ~/.claude/projects/
    """
    from .discovery import scan_sessions
    from datetime import datetime, timedelta

    sessions = scan_sessions()
    cutoff = datetime.now() - timedelta(hours=max_age)
    recent = [s for s in sessions if s.last_modified > cutoff][:max_sessions]

    if not recent:
        click.echo("No recent sessions found.")
        return

    click.echo(f"Found {len(recent)} sessions (last {max_age} hours):\n")

    for s in recent:
        age = datetime.now() - s.last_modified
        if age.total_seconds() < 60:
            age_str = "just now"
        elif age.total_seconds() < 3600:
            age_str = f"{int(age.total_seconds() // 60)}m ago"
        else:
            age_str = f"{int(age.total_seconds() // 3600)}h ago"

        click.echo(f"  {s.session_id[:8]}  {s.cwd[-40:]:40}  {age_str}")


@main.command()
@click.argument("cwd", default=".", type=click.Path(exists=True))
def spawn(cwd: str):
    """Spawn a new Claude Code session.

    Opens a new terminal window/tab with Claude Code running in the specified
    directory (defaults to current directory).
    """
    import os
    from .spawner import spawn_session, detect_terminal

    # Resolve to absolute path
    cwd = os.path.abspath(cwd)

    terminal = detect_terminal()
    if terminal.value == "unknown":
        click.echo("Error: No supported terminal found.", err=True)
        click.echo("Supported: iTerm2, Terminal.app, tmux", err=True)
        raise SystemExit(1)

    click.echo(f"Spawning Claude Code in {cwd} using {terminal.value}...")

    if spawn_session(cwd, terminal):
        click.echo("Session spawned successfully.")
    else:
        click.echo("Failed to spawn session.", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
