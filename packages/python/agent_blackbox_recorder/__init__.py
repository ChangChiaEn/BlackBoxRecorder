"""
AgentBlackBoxRecorder - Flight Recorder for Autonomous AI Agents

A lightweight SDK for debugging AI agents with interactive trace replay
and takeover capabilities.
"""

from agent_blackbox_recorder.core.recorder import Recorder
from agent_blackbox_recorder.core.events import (
    TraceEvent,
    SpanEvent,
    LLMCallEvent,
    ToolCallEvent,
    StateSnapshot,
)
from agent_blackbox_recorder.core.decorators import trace, checkpoint

__version__ = "0.1.0"
__all__ = [
    "Recorder",
    "TraceEvent",
    "SpanEvent",
    "LLMCallEvent",
    "ToolCallEvent",
    "StateSnapshot",
    "trace",
    "checkpoint",
]
