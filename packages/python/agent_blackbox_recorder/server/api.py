"""
FastAPI server for the AgentBlackBoxRecorder web UI.

Provides REST API endpoints for the React frontend.
"""

from pathlib import Path
from typing import Any, Optional
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_blackbox_recorder.storage.base import StorageBackend


def create_app(storage: StorageBackend) -> FastAPI:
    """
    Create the FastAPI application.
    
    Args:
        storage: The storage backend to use
    
    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="AgentBlackBoxRecorder",
        description="Flight Recorder for Autonomous AI Agents",
        version="0.1.0",
    )
    
    # CORS for frontend development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Store reference to storage
    app.state.storage = storage
    
    # Register routes
    register_routes(app)
    
    return app


def register_routes(app: FastAPI) -> None:
    """Register all API routes."""
    
    @app.get("/api/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "version": "0.1.0"}
    
    @app.get("/api/sessions")
    async def list_sessions(limit: int = 100) -> list[dict[str, Any]]:
        """List all trace sessions."""
        storage: StorageBackend = app.state.storage
        return storage.list_sessions(limit=limit)
    
    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str) -> dict[str, Any]:
        """Get a specific trace session."""
        storage: StorageBackend = app.state.storage
        try:
            session = storage.load_session(session_id)
            return session.model_dump()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    
    @app.get("/api/sessions/{session_id}/events")
    async def get_session_events(session_id: str) -> list[dict[str, Any]]:
        """Get all events for a session."""
        storage: StorageBackend = app.state.storage
        try:
            session = storage.load_session(session_id)
            return [e.model_dump() for e in session.events]
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    
    @app.get("/api/sessions/{session_id}/tree")
    async def get_session_tree(session_id: str) -> dict[str, Any]:
        """Get the event tree for a session (for DAG visualization)."""
        storage: StorageBackend = app.state.storage
        try:
            session = storage.load_session(session_id)
            return session.get_event_tree()
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    
    @app.get("/api/sessions/{session_id}/snapshots")
    async def get_session_snapshots(session_id: str) -> list[dict[str, Any]]:
        """Get all state snapshots for a session."""
        storage: StorageBackend = app.state.storage
        try:
            session = storage.load_session(session_id)
            return [s.model_dump() for s in session.snapshots]
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    
    @app.get("/api/sessions/{session_id}/export")
    async def export_session(session_id: str, format: str = "json") -> Any:
        """Export a session in the specified format."""
        storage: StorageBackend = app.state.storage
        try:
            data = storage.export_session(session_id, format=format)
            return json.loads(data)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @app.delete("/api/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, bool]:
        """Delete a trace session."""
        storage: StorageBackend = app.state.storage
        deleted = storage.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"deleted": True}
    
    # Takeover mode endpoints
    
    class TakeoverRequest(BaseModel):
        """Request to start takeover mode."""
        snapshot_id: str
        modified_state: Optional[dict[str, Any]] = None
    
    @app.post("/api/sessions/{session_id}/takeover")
    async def start_takeover(session_id: str, request: TakeoverRequest) -> dict[str, Any]:
        """
        Start takeover mode from a specific snapshot.
        
        This prepares the state for manual intervention.
        """
        storage: StorageBackend = app.state.storage
        try:
            session = storage.load_session(session_id)
            
            # Find the snapshot
            snapshot = None
            for s in session.snapshots:
                if s.id == request.snapshot_id:
                    snapshot = s
                    break
            
            if snapshot is None:
                raise HTTPException(status_code=404, detail="Snapshot not found")
            
            # Return the state for modification
            return {
                "session_id": session_id,
                "snapshot_id": snapshot.id,
                "state": snapshot.state,
                "restorable": snapshot.restorable,
                "checkpoint_name": snapshot.checkpoint_name,
            }
            
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Session not found")
    
    # Serve frontend (production)
    frontend_path = Path(__file__).parent.parent.parent.parent / "web" / "dist"
    if frontend_path.exists():
        app.mount("/assets", StaticFiles(directory=frontend_path / "assets"), name="assets")
        
        @app.get("/")
        async def serve_frontend() -> FileResponse:
            """Serve the frontend application."""
            return FileResponse(frontend_path / "index.html")
        
        @app.get("/{path:path}")
        async def serve_frontend_routes(path: str) -> FileResponse:
            """Serve frontend routes."""
            file_path = frontend_path / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(frontend_path / "index.html")
    else:
        @app.get("/")
        async def no_frontend() -> HTMLResponse:
            """Fallback when frontend is not built."""
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>AgentBlackBoxRecorder</title>
                    <style>
                        body {
                            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                            display: flex;
                            justify-content: center;
                            align-items: center;
                            height: 100vh;
                            margin: 0;
                            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                            color: #fff;
                        }
                        .container {
                            text-align: center;
                            padding: 2rem;
                        }
                        h1 { margin-bottom: 0.5rem; }
                        p { opacity: 0.8; }
                        code {
                            background: rgba(255,255,255,0.1);
                            padding: 0.2rem 0.5rem;
                            border-radius: 4px;
                        }
                        a {
                            color: #4da6ff;
                        }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🛫 AgentBlackBoxRecorder</h1>
                        <p>API Server is running!</p>
                        <p>Frontend not built. Run <code>npm run build</code> in packages/web</p>
                        <p><a href="/api/sessions">View Sessions API →</a></p>
                    </div>
                </body>
                </html>
                """,
                status_code=200,
            )


def start_server(
    storage: StorageBackend,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    """
    Start the API server.
    
    Args:
        storage: The storage backend to use
        host: Host to bind to
        port: Port to bind to
    """
    import uvicorn
    
    app = create_app(storage)
    uvicorn.run(app, host=host, port=port)
