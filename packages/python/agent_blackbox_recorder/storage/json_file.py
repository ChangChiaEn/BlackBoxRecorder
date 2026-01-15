"""
JSON file storage backend for AgentBlackBoxRecorder.

Stores trace sessions as individual JSON files in a directory.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_blackbox_recorder.core.events import TraceSession
from agent_blackbox_recorder.storage.base import StorageBackend


class JsonFileStorage(StorageBackend):
    """
    File-based storage using JSON files.
    
    Each trace session is stored as a separate JSON file.
    This is the default storage backend, suitable for local development
    and small to medium workloads.
    
    Directory structure:
        traces/
        ├── index.json          # Session index for fast listing
        ├── session_abc123.json
        ├── session_def456.json
        └── ...
    """
    
    def __init__(self, directory: Path | str) -> None:
        """
        Initialize the JSON file storage.
        
        Args:
            directory: Path to the directory for storing traces
        """
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._index_path = self._directory / "index.json"
        
        # Initialize index if needed
        if not self._index_path.exists():
            self._save_index([])
    
    def save_session(self, session: TraceSession) -> str:
        """Save a trace session to a JSON file."""
        # Write the session file
        session_path = self._directory / f"session_{session.id}.json"
        
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(
                session.model_dump(),
                f,
                indent=2,
                default=self._json_serializer,
                ensure_ascii=False,
            )
        
        # Update the index
        index = self._load_index()
        
        # Remove existing entry if present
        index = [s for s in index if s["id"] != session.id]
        
        # Add new entry at the beginning
        index.insert(0, {
            "id": session.id,
            "name": session.name,
            "description": session.description,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "event_count": len(session.events),
            "snapshot_count": len(session.snapshots),
            "framework": session.framework,
        })
        
        self._save_index(index)
        
        return session.id
    
    def load_session(self, session_id: str) -> TraceSession:
        """Load a trace session from a JSON file."""
        session_path = self._directory / f"session_{session_id}.json"
        
        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        
        with open(session_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return TraceSession.model_validate(data)
    
    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        """List available trace sessions."""
        index = self._load_index()
        return index[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a trace session."""
        session_path = self._directory / f"session_{session_id}.json"
        
        if not session_path.exists():
            return False
        
        # Delete the file
        session_path.unlink()
        
        # Update the index
        index = self._load_index()
        index = [s for s in index if s["id"] != session_id]
        self._save_index(index)
        
        return True
    
    def _load_index(self) -> list[dict[str, Any]]:
        """Load the session index."""
        if not self._index_path.exists():
            return []
        
        with open(self._index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _save_index(self, index: list[dict[str, Any]]) -> None:
        """Save the session index."""
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, indent=2, default=self._json_serializer)
    
    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for non-standard types."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return str(obj)
