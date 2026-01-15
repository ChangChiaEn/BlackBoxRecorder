"""
CLI for AgentBlackBoxRecorder.

Provides command-line tools for managing traces and starting the replay UI.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent_blackbox_recorder.storage.json_file import JsonFileStorage

app = typer.Typer(
    name="agentbox",
    help="Flight Recorder for Autonomous AI Agents",
    add_completion=False,
)

console = Console()


@app.command()
def replay(
    path: str = typer.Argument("./traces", help="Path to traces directory"),
    session: Optional[str] = typer.Option(None, "--session", "-s", help="Specific session ID to replay"),
    port: int = typer.Option(8765, "--port", "-p", help="Port for the web server"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
) -> None:
    """
    Start the interactive replay UI.
    
    Opens a web interface to visualize and debug your agent traces.
    """
    from agent_blackbox_recorder.server.api import start_server
    import webbrowser
    
    storage = JsonFileStorage(Path(path))
    
    # Check if there are any sessions
    sessions = storage.list_sessions()
    if not sessions:
        console.print("[yellow]No trace sessions found in[/yellow]", path)
        console.print("Run your agent with tracing enabled first.")
        raise typer.Exit(1)
    
    url = f"http://localhost:{port}"
    
    if session:
        url += f"?session={session}"
    
    console.print(f"\n[bold blue]AgentBlackBoxRecorder[/bold blue]")
    console.print(f"   Starting replay server at [link={url}]{url}[/link]\n")
    
    if not no_browser:
        webbrowser.open(url)
    
    start_server(storage, port=port)


@app.command()
def list(
    path: str = typer.Argument("./traces", help="Path to traces directory"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum sessions to show"),
) -> None:
    """
    List all recorded trace sessions.
    """
    storage = JsonFileStorage(Path(path))
    sessions = storage.list_sessions(limit=limit)
    
    if not sessions:
        console.print("[yellow]No trace sessions found.[/yellow]")
        raise typer.Exit(0)
    
    table = Table(title="Trace Sessions")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Events", justify="right")
    table.add_column("Started", style="dim")
    
    for s in sessions:
        status_color = "green" if s.get("status") == "success" else "red"
        table.add_row(
            s["id"][:8] + "...",
            s.get("name", "Unnamed"),
            f"[{status_color}]{s.get('status', 'unknown')}[/{status_color}]",
            str(s.get("event_count", 0)),
            s.get("start_time", "")[:19] if s.get("start_time") else "",
        )
    
    console.print(table)


@app.command()
def show(
    session_id: str = typer.Argument(..., help="Session ID to show"),
    path: str = typer.Option("./traces", "--path", "-p", help="Path to traces directory"),
) -> None:
    """
    Show details of a specific trace session.
    """
    storage = JsonFileStorage(Path(path))
    
    try:
        session = storage.load_session(session_id)
    except FileNotFoundError:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]Session:[/bold] {session.name}")
    console.print(f"[dim]ID:[/dim] {session.id}")
    console.print(f"[dim]Status:[/dim] {session.status}")
    console.print(f"[dim]Framework:[/dim] {session.framework or 'Unknown'}")
    console.print(f"[dim]Events:[/dim] {len(session.events)}")
    console.print(f"[dim]Snapshots:[/dim] {len(session.snapshots)}")
    console.print()
    
    # Show event summary
    table = Table(title="Events")
    table.add_column("Type", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Status", style="magenta")
    table.add_column("Duration", justify="right")
    
    for event in session.events[:20]:
        status_color = "green" if event.status == "success" else "red"
        duration = f"{event.duration_ms:.1f}ms" if event.duration_ms else "-"
        table.add_row(
            event.event_type,
            event.name[:40],
            f"[{status_color}]{event.status}[/{status_color}]",
            duration,
        )
    
    if len(session.events) > 20:
        table.add_row("...", f"({len(session.events) - 20} more)", "", "")
    
    console.print(table)


@app.command()
def delete(
    session_id: str = typer.Argument(..., help="Session ID to delete"),
    path: str = typer.Option("./traces", "--path", "-p", help="Path to traces directory"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """
    Delete a trace session.
    """
    storage = JsonFileStorage(Path(path))
    
    if not force:
        confirm = typer.confirm(f"Delete session {session_id}?")
        if not confirm:
            raise typer.Exit(0)
    
    deleted = storage.delete_session(session_id)
    
    if deleted:
        console.print(f"[green]Deleted session:[/green] {session_id}")
    else:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)


@app.command()
def export(
    session_id: str = typer.Argument(..., help="Session ID to export"),
    output: str = typer.Option("-", "--output", "-o", help="Output file (- for stdout)"),
    path: str = typer.Option("./traces", "--path", "-p", help="Path to traces directory"),
    format: str = typer.Option("json", "--format", "-f", help="Export format"),
) -> None:
    """
    Export a trace session to a file.
    """
    storage = JsonFileStorage(Path(path))
    
    try:
        data = storage.export_session(session_id, format=format)
    except FileNotFoundError:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]Export error:[/red] {e}")
        raise typer.Exit(1)
    
    if output == "-":
        console.print(data.decode())
    else:
        Path(output).write_bytes(data)
        console.print(f"[green]Exported to:[/green] {output}")


@app.command()
def version() -> None:
    """
    Show version information.
    """
    from agent_blackbox_recorder import __version__
    
    console.print(f"AgentBlackBoxRecorder v{__version__}")


if __name__ == "__main__":
    app()
