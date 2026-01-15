"""Tests for the event models."""

from datetime import datetime

import pytest

from agent_blackbox_recorder.core.events import (
    TraceEvent,
    SpanEvent,
    LLMCallEvent,
    ToolCallEvent,
    StateSnapshot,
    TraceSession,
    EventType,
    EventStatus,
    TokenUsage,
)


class TestTokenUsage:
    """Tests for TokenUsage model."""
    
    def test_cost_estimate(self) -> None:
        """Test token cost estimation."""
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
        )
        
        # Expected: (1000 * 0.03 + 500 * 0.06) / 1000 = 0.06
        assert abs(usage.cost_estimate - 0.06) < 0.001


class TestTraceEvent:
    """Tests for TraceEvent model."""
    
    def test_create_event(self) -> None:
        """Test creating a basic event."""
        event = TraceEvent(
            trace_id="trace_123",
            event_type=EventType.SPAN,
            name="test_event",
        )
        
        assert event.id is not None
        assert event.trace_id == "trace_123"
        assert event.status == EventStatus.RUNNING
    
    def test_complete_event(self) -> None:
        """Test completing an event."""
        event = TraceEvent(
            trace_id="trace_123",
            event_type=EventType.SPAN,
            name="test_event",
        )
        
        event.complete(EventStatus.SUCCESS)
        
        assert event.status == EventStatus.SUCCESS
        assert event.end_timestamp is not None
        assert event.duration_ms is not None
    
    def test_fail_event(self) -> None:
        """Test failing an event."""
        event = TraceEvent(
            trace_id="trace_123",
            event_type=EventType.SPAN,
            name="test_event",
        )
        
        event.fail("Something went wrong")
        
        assert event.status == EventStatus.ERROR
        assert event.metadata["error"] == "Something went wrong"


class TestSpanEvent:
    """Tests for SpanEvent model."""
    
    def test_set_input_output(self) -> None:
        """Test setting input/output data."""
        span = SpanEvent(
            trace_id="trace_123",
            name="test_span",
        )
        
        span.set_input({"query": "test"})
        span.set_output({"result": 42})
        
        assert span.input_data == {"query": "test"}
        assert span.output_data == {"result": 42}


class TestLLMCallEvent:
    """Tests for LLMCallEvent model."""
    
    def test_create_llm_event(self) -> None:
        """Test creating an LLM call event."""
        event = LLMCallEvent(
            trace_id="trace_123",
            name="GPT-4 Call",
            model="gpt-4",
            prompt="Hello!",
        )
        
        assert event.event_type == EventType.LLM_CALL
        assert event.model == "gpt-4"
        assert event.provider == "openai"
    
    def test_set_response(self) -> None:
        """Test setting LLM response."""
        event = LLMCallEvent(
            trace_id="trace_123",
            name="GPT-4 Call",
            model="gpt-4",
        )
        
        event.set_response(
            response="Hello there!",
            tokens=TokenUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        
        assert event.response == "Hello there!"
        assert event.tokens_used.total_tokens == 15
        assert event.status == EventStatus.SUCCESS


class TestToolCallEvent:
    """Tests for ToolCallEvent model."""
    
    def test_create_tool_event(self) -> None:
        """Test creating a tool call event."""
        event = ToolCallEvent(
            trace_id="trace_123",
            name="Calculator",
            tool_name="calculator",
            arguments={"a": 1, "b": 2},
        )
        
        assert event.event_type == EventType.TOOL_CALL
        assert event.tool_name == "calculator"
    
    def test_set_result(self) -> None:
        """Test setting tool result."""
        event = ToolCallEvent(
            trace_id="trace_123",
            name="Calculator",
            tool_name="calculator",
            arguments={"a": 1, "b": 2},
        )
        
        event.set_result(3)
        
        assert event.result == 3
        assert event.result_type == "int"
        assert event.status == EventStatus.SUCCESS
    
    def test_set_error(self) -> None:
        """Test setting tool error."""
        event = ToolCallEvent(
            trace_id="trace_123",
            name="Calculator",
            tool_name="calculator",
            arguments={},
        )
        
        event.set_error(ValueError("Invalid input"))
        
        assert event.error_message == "Invalid input"
        assert event.error_type == "ValueError"
        assert event.status == EventStatus.ERROR


class TestTraceSession:
    """Tests for TraceSession model."""
    
    def test_create_session(self) -> None:
        """Test creating a session."""
        session = TraceSession(name="test_session")
        
        assert session.id is not None
        assert session.name == "test_session"
        assert session.status == EventStatus.RUNNING
    
    def test_add_events(self) -> None:
        """Test adding events to a session."""
        session = TraceSession(name="test_session")
        
        event1 = SpanEvent(trace_id="", name="span1")
        event2 = SpanEvent(trace_id="", name="span2", parent_id=event1.id)
        
        session.add_event(event1)
        session.add_event(event2)
        
        assert len(session.events) == 2
        assert session.events[0].trace_id == session.id
        assert session.root_event_id == event1.id
    
    def test_event_tree(self) -> None:
        """Test building event tree."""
        session = TraceSession(name="test_session")
        
        root = SpanEvent(trace_id="", name="root")
        child1 = SpanEvent(trace_id="", name="child1", parent_id=root.id)
        child2 = SpanEvent(trace_id="", name="child2", parent_id=root.id)
        
        session.add_event(root)
        session.add_event(child1)
        session.add_event(child2)
        
        tree = session.get_event_tree()
        
        assert "event" in tree
        assert len(tree["children"]) == 2
