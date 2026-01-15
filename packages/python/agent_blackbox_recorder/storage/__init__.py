"""Storage backends for AgentBlackBoxRecorder."""

from agent_blackbox_recorder.storage.base import StorageBackend
from agent_blackbox_recorder.storage.json_file import JsonFileStorage

__all__ = ["StorageBackend", "JsonFileStorage"]
