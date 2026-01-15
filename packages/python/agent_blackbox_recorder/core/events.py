"""
Event models for AgentBlackBoxRecorder.

Defines the core data structures for capturing agent execution traces.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events that can be captured."""
    
    SPAN = "span"
    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    STATE_CHANGE = "state_change"
    ERROR = "error"
    CHECKPOINT = "checkpoint"


class EventStatus(str, Enum):
    """Status of an event."""
    
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


class TokenUsage(BaseModel):
    """Token usage statistics for LLM calls."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    @property
    def cost_estimate(self) -> float:
        """Rough cost estimate based on GPT-4 pricing."""
        # Simplified estimate: $0.03/1K input, $0.06/1K output
        return (self.prompt_tokens * 0.03 + self.completion_tokens * 0.06) / 1000


class TraceEvent(BaseModel):
    """Base event model for all trace events."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(description="ID of the parent trace session")
    parent_id: Optional[str] = Field(default=None, description="ID of the parent event")
    event_type: EventType = Field(description="Type of this event")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_timestamp: Optional[datetime] = Field(default=None)
    duration_ms: Optional[float] = Field(default=None)
    name: str = Field(description="Human-readable name for this event")
    status: EventStatus = Field(default=EventStatus.RUNNING)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    
    def complete(self, status: EventStatus = EventStatus.SUCCESS) -> None:
        """Mark the event as complete."""
        self.end_timestamp = datetime.now(timezone.utc)
        self.duration_ms = (self.end_timestamp - self.timestamp).total_seconds() * 1000
        self.status = status
    
    def fail(self, error: str) -> None:
        """Mark the event as failed."""
        self.metadata["error"] = error
        self.complete(EventStatus.ERROR)
    
    class Config:
        """Pydantic config."""
        
        use_enum_values = True


class SpanEvent(TraceEvent):
    """A span representing a unit of work."""
    
    event_type: EventType = Field(default=EventType.SPAN)
    input_data: Optional[dict[str, Any]] = Field(default=None)
    output_data: Optional[dict[str, Any]] = Field(default=None)
    
    def set_input(self, data: Any) -> None:
        """Set the input data for this span."""
        self.input_data = self._serialize(data)
    
    def set_output(self, data: Any) -> None:
        """Set the output data for this span."""
        self.output_data = self._serialize(data)
    
    @staticmethod
    def _serialize(data: Any) -> dict[str, Any]:
        """Serialize data to a dictionary."""
        if isinstance(data, dict):
            return data
        if isinstance(data, BaseModel):
            return data.model_dump()
        if hasattr(data, "__dict__"):
            return {"_type": type(data).__name__, **data.__dict__}
        return {"value": str(data)}


class LLMCallEvent(TraceEvent):
    """Event representing an LLM API call."""
    
    event_type: EventType = Field(default=EventType.LLM_CALL)
    model: str = Field(description="Model identifier (e.g., gpt-4)")
    provider: str = Field(default="openai", description="LLM provider")
    
    # Request
    prompt: Optional[str] = Field(default=None, description="The prompt sent to the LLM")
    messages: Optional[list[dict[str, Any]]] = Field(
        default=None, description="Chat messages (for chat models)"
    )
    system_prompt: Optional[str] = Field(default=None)
    temperature: Optional[float] = Field(default=None)
    max_tokens: Optional[int] = Field(default=None)
    
    # Response
    response: Optional[str] = Field(default=None, description="The LLM response")
    response_messages: Optional[list[dict[str, Any]]] = Field(default=None)
    tokens_used: TokenUsage = Field(default_factory=TokenUsage)
    
    # Tool calls (for function calling)
    tool_calls: Optional[list[dict[str, Any]]] = Field(default=None)
    
    def set_response(
        self,
        response: str,
        tokens: Optional[TokenUsage] = None,
        tool_calls: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        """Set the response from the LLM."""
        self.response = response
        if tokens:
            self.tokens_used = tokens
        if tool_calls:
            self.tool_calls = tool_calls
        self.complete()


class ToolCallEvent(TraceEvent):
    """Event representing a tool/function call."""
    
    event_type: EventType = Field(default=EventType.TOOL_CALL)
    tool_name: str = Field(description="Name of the tool being called")
    tool_description: Optional[str] = Field(default=None)
    
    # Call details
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: Optional[Any] = Field(default=None)
    result_type: Optional[str] = Field(default=None)
    
    # Error handling
    error_message: Optional[str] = Field(default=None)
    error_type: Optional[str] = Field(default=None)
    
    def set_result(self, result: Any) -> None:
        """Set the result of the tool call."""
        self.result = result
        self.result_type = type(result).__name__
        self.complete()
    
    def set_error(self, error: Exception) -> None:
        """Set an error for the tool call."""
        self.error_message = str(error)
        self.error_type = type(error).__name__
        self.fail(str(error))


class StateSnapshot(BaseModel):
    """A snapshot of agent state at a specific point in time."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    trace_id: str = Field(description="ID of the parent trace")
    event_id: str = Field(description="ID of the event this snapshot is associated with")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # State data
    state: dict[str, Any] = Field(default_factory=dict, description="The serialized state")
    state_type: str = Field(default="dict", description="Type of the original state object")
    
    # Metadata
    restorable: bool = Field(
        default=True,
        description="Whether this state can be restored for takeover mode",
    )
    checkpoint_name: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    
    # Serialization info
    serialization_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about fields that couldn't be fully serialized",
    )


class TraceSession(BaseModel):
    """A complete trace session containing all events."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(description="Name of this trace session")
    description: Optional[str] = Field(default=None)
    
    # Timing
    start_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = Field(default=None)
    
    # Events
    events: list[TraceEvent] = Field(default_factory=list)
    snapshots: list[StateSnapshot] = Field(default_factory=list)
    
    # Status
    status: EventStatus = Field(default=EventStatus.RUNNING)
    root_event_id: Optional[str] = Field(default=None)
    
    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
    framework: Optional[str] = Field(default=None, description="Agent framework used")
    python_version: Optional[str] = Field(default=None)
    sdk_version: Optional[str] = Field(default=None)
    
    def add_event(self, event: TraceEvent) -> None:
        """Add an event to the session."""
        event.trace_id = self.id
        self.events.append(event)
        if self.root_event_id is None and event.parent_id is None:
            self.root_event_id = event.id
    
    def add_snapshot(self, snapshot: StateSnapshot) -> None:
        """Add a state snapshot to the session."""
        snapshot.trace_id = self.id
        self.snapshots.append(snapshot)
    
    def complete(self, status: EventStatus = EventStatus.SUCCESS) -> None:
        """Mark the session as complete."""
        self.end_time = datetime.now(timezone.utc)
        self.status = status
    
    def get_event_tree(self) -> dict[str, Any]:
        """Build a tree structure of events for visualization."""
        events_by_id = {e.id: e for e in self.events}
        children: dict[str, list[TraceEvent]] = {}
        
        for event in self.events:
            parent_id = event.parent_id or "root"
            if parent_id not in children:
                children[parent_id] = []
            children[parent_id].append(event)
        
        def build_tree(event_id: str) -> dict[str, Any]:
            if event_id not in events_by_id:
                return {}
            event = events_by_id[event_id]
            return {
                "event": event.model_dump(),
                "children": [
                    build_tree(child.id) for child in children.get(event_id, [])
                ],
            }
        
        if self.root_event_id:
            return build_tree(self.root_event_id)
        return {"children": [build_tree(e.id) for e in children.get("root", [])]}
