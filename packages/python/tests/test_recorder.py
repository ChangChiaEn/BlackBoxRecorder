"""Tests for the Recorder class."""

import tempfile
from pathlib import Path

import pytest

from agent_blackbox_recorder import Recorder
from agent_blackbox_recorder.core.events import EventStatus


class TestRecorder:
    """Test suite for the Recorder class."""
    
    def test_create_recorder(self) -> None:
        """Test creating a recorder instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            assert recorder is not None
            assert not recorder.is_recording
    
    def test_start_session(self) -> None:
        """Test starting a trace session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            session = recorder.start_session(name="test_session")
            
            assert session is not None
            assert session.name == "test_session"
            assert recorder.is_recording
    
    def test_end_session(self) -> None:
        """Test ending a trace session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="test_session")
            session = recorder.end_session()
            
            assert session is not None
            assert session.status == EventStatus.SUCCESS
            assert not recorder.is_recording
    
    def test_trace_decorator(self) -> None:
        """Test the @trace decorator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            
            @recorder.trace
            def my_function(x: int, y: int) -> int:
                return x + y
            
            result = my_function(2, 3)
            
            assert result == 5
            
            # Check session was created and saved
            sessions = recorder.list_sessions()
            assert len(sessions) == 1
    
    def test_span_context_manager(self) -> None:
        """Test the span context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="test_session")
            
            with recorder.span("my_span") as span:
                span.set_input({"key": "value"})
                span.set_output({"result": 42})
            
            # Session is auto-closed when root span ends
            sessions = recorder.list_sessions()
            assert len(sessions) == 1
            session = recorder.load_session(sessions[0]["id"])
            assert len(session.events) == 1
            assert session.events[0].name == "my_span"
    
    def test_nested_spans(self) -> None:
        """Test nested spans."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="test_session")
            
            with recorder.span("outer") as outer:
                with recorder.span("inner") as inner:
                    pass
            
            # Session is auto-closed when root span ends
            assert recorder.current_session is None
            
            sessions = recorder.list_sessions()
            assert len(sessions) == 1
            session = recorder.load_session(sessions[0]["id"])
            assert len(session.events) == 2
            
            # Check parent-child relationship
            events_by_id = {e.id: e for e in session.events}
            inner_event = next(e for e in session.events if e.name == "inner")
            # We need to find the outer event ID from the stored session
            outer_event = next(e for e in session.events if e.name == "outer")
            assert inner_event.parent_id == outer_event.id
    
    def test_capture_state(self) -> None:
        """Test state snapshot capture."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="test_session")
            
            state = {"counter": 1, "data": ["a", "b", "c"]}
            # Need a span or event context for snapshot? 
            # capture_state uses event_stack[-1] if available.
            
            snapshot = recorder.capture_state(state, name="checkpoint_1")
            
            assert snapshot is not None
            assert snapshot.checkpoint_name == "checkpoint_1"
            assert snapshot.restorable
    
    def test_session_persistence(self) -> None:
        """Test that sessions are saved and can be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create recorder and record a session
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="persistent_session")
            
            with recorder.span("test_span"):
                pass
            
            # Session should be auto-saved and closed
            assert recorder.current_session is None
            
            sessions = recorder.list_sessions()
            assert len(sessions) == 1
            session_id = sessions[0]["id"]
            
            # Create new recorder and load session
            recorder2 = Recorder(storage=tmpdir)
            loaded_session = recorder2.load_session(session_id)
            
            assert loaded_session.id == session_id
            assert loaded_session.name == "persistent_session"
            assert len(loaded_session.events) == 1
    
    def test_record_llm_call(self) -> None:
        """Test recording LLM calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="llm_test")
            
            recorder.record_llm_call(
                model="gpt-4",
                prompt="Hello, world!",
                response="Hi there!",
            )
            
            session = recorder.current_session
            assert session is not None
            assert len(session.events) == 1
            assert session.events[0].name == "LLM: gpt-4"
    
    def test_record_tool_call(self) -> None:
        """Test recording tool calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            recorder.start_session(name="tool_test")
            
            recorder.record_tool_call(
                tool_name="calculator",
                arguments={"operation": "add", "a": 1, "b": 2},
                result=3,
            )
            
            session = recorder.current_session
            assert session is not None
            assert len(session.events) == 1
            assert "calculator" in session.events[0].name


class TestAsyncRecorder:
    """Test async functionality."""
    
    @pytest.mark.asyncio
    async def test_async_trace_decorator(self) -> None:
        """Test the @trace decorator with async functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = Recorder(storage=tmpdir)
            
            @recorder.trace
            async def async_function(x: int) -> int:
                return x * 2
            
            result = await async_function(5)
            
            assert result == 10
            
            sessions = recorder.list_sessions()
            assert len(sessions) == 1
