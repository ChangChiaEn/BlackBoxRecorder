"""
Base storage backend interface for AgentBlackBoxRecorder.
"""

from abc import ABC, abstractmethod
from typing import Any

from agent_blackbox_recorder.core.events import TraceSession


class StorageBackend(ABC):
    """
    Abstract base class for trace storage backends.
    
    Implementations can store traces in various formats:
    - JSON files (default)
    - SQLite database
    - Remote storage (S3, GCS, etc.)
    - OpenTelemetry exporters
    """
    
    @abstractmethod
    def save_session(self, session: TraceSession) -> str:
        """
        Save a trace session.
        
        Args:
            session: The TraceSession to save
        
        Returns:
            The session ID
        """
        ...
    
    @abstractmethod
    def load_session(self, session_id: str) -> TraceSession:
        """
        Load a trace session by ID.
        
        Args:
            session_id: The ID of the session to load
        
        Returns:
            The loaded TraceSession
        
        Raises:
            FileNotFoundError: If the session doesn't exist
        """
        ...
    
    @abstractmethod
    def list_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        List available trace sessions.
        
        Args:
            limit: Maximum number of sessions to return
        
        Returns:
            List of session metadata dictionaries
        """
        ...
    
    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a trace session.
        
        Args:
            session_id: The ID of the session to delete
        
        Returns:
            True if deleted, False if not found
        """
        ...
    
    def export_session(self, session_id: str, format: str = "json") -> bytes:
        """
        Export a session in the specified format.
        
        Args:
            session_id: The ID of the session to export
            format: Export format ("json", "otlp", etc.)
        
        Returns:
            Serialized session data
        """
        session = self.load_session(session_id)
        
        if format == "json":
            import json
            return json.dumps(session.model_dump(), indent=2, default=str).encode()
        else:
            raise ValueError(f"Unsupported export format: {format}")
