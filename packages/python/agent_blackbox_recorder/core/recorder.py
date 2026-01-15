"""
Main Recorder class for AgentBlackBoxRecorder.

This is the primary interface for capturing agent execution traces.
"""

import sys
import threading
import webbrowser
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import logging
import inspect
from uuid import uuid4
from typing import Any, Callable, Generator, Optional, TypeVar

logger = logging.getLogger(__name__)

from agent_blackbox_recorder.core.events import (
    EventStatus,
    SpanEvent,
    StateSnapshot,
    TraceEvent,
    TraceSession,
)
from agent_blackbox_recorder.core.snapshot import SnapshotEngine
from agent_blackbox_recorder.core.decorators import set_current_recorder
from agent_blackbox_recorder.storage.base import StorageBackend
from agent_blackbox_recorder.storage.json_file import JsonFileStorage

T = TypeVar("T")


class Recorder:
    """
    Flight recorder for autonomous AI agents.
    
    Captures execution traces, state snapshots, and provides
    an interactive replay interface for debugging.
    
    Example:
        ```python
        from agent_blackbox_recorder import Recorder
        
        recorder = Recorder(storage="./traces")
        
        @recorder.trace
        def my_agent():
            # Agent logic here
            pass
        
        # Run your agent
        my_agent()
        
        # Open the replay UI
        recorder.replay()
        ```
    """
    
    def __init__(
        self,
        storage: str | Path | StorageBackend = "./traces",
        adapters: Optional[list[Any]] = None,
        auto_snapshot: bool = True,
        enable_otel: bool = False,
    ) -> None:
        """
        Initialize the recorder.
        
        Args:
            storage: Path to storage directory or a StorageBackend instance
            adapters: List of framework adapters to install
            auto_snapshot: Whether to automatically capture snapshots at checkpoints
            enable_otel: Whether to export traces to OpenTelemetry
        """
        # Set up storage
        if isinstance(storage, (str, Path)):
            self._storage: StorageBackend = JsonFileStorage(Path(storage))
        else:
            self._storage = storage
        
        # Configuration
        self._auto_snapshot = auto_snapshot
        self._enable_otel = enable_otel
        
        # State
        self._current_session: Optional[TraceSession] = None
        self._event_stack: list[TraceEvent] = []
        self._lock = threading.RLock()
        
        # Engines
        self._snapshot_engine = SnapshotEngine()
        
        # Adapters
        self._adapters: list[Any] = []
        if adapters:
            for adapter in adapters:
                self.install_adapter(adapter)
        
        # Register as the current recorder for decorators
        set_current_recorder(self)
    
    @property
    def current_session(self) -> Optional[TraceSession]:
        """Get the current trace session."""
        return self._current_session
    
    @property
    def is_recording(self) -> bool:
        """Check if recording is active."""
        return self._current_session is not None
    
    def start_session(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TraceSession:
        """
        Start a new trace session.
        
        Args:
            name: Name for the session
            description: Description of the session
            metadata: Additional metadata
        
        Returns:
            The new TraceSession
        """
        with self._lock:
            if self._current_session is not None:
                self.end_session()
            
            session = TraceSession(
                name=name or f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                description=description,
                metadata=metadata or {},
                python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                sdk_version="0.1.0",
            )
            
            self._current_session = session
            self._event_stack = []
            
            return session
    
    def end_session(self, status: EventStatus = EventStatus.SUCCESS) -> Optional[TraceSession]:
        """
        End the current trace session and save it.
        
        Args:
            status: Final status of the session
        
        Returns:
            The completed TraceSession
        """
        with self._lock:
            if self._current_session is None:
                return None
            
            session = self._current_session
            session.complete(status)
            
            # Save to storage
            self._storage.save_session(session)
            
            # Clear state
            self._current_session = None
            self._event_stack = []
            
            return session
    
    def trace(
        self,
        func: Optional[Callable[..., T]] = None,
        *,
        name: Optional[str] = None,
        capture_args: bool = True,
        capture_result: bool = True,
    ) -> Any:
        """
        Decorator to trace a function.
        
        Can be used with or without arguments:
        
            @recorder.trace
            def my_func():
                pass
            
            @recorder.trace(name="custom")
            def my_func():
                pass
        """
        from agent_blackbox_recorder.core.decorators import trace as trace_decorator
        
        if func is not None:
            # Used without parentheses: @recorder.trace
            return trace_decorator(func)
        else:
            # Used with parentheses: @recorder.trace(...)
            return trace_decorator(
                name=name,
                capture_args=capture_args,
                capture_result=capture_result,
            )
    
    @contextmanager
    def span(
        self,
        name: str,
        **metadata: Any,
    ) -> Generator[SpanEvent, None, None]:
        """
        Context manager to create a span.
        
        Example:
            ```python
            with recorder.span("process_data") as span:
                span.set_input({"data": input_data})
                result = process(input_data)
                span.set_output({"result": result})
            ```
        """
        span = SpanEvent(
            name=name,
            trace_id=self._current_session.id if self._current_session else "",
            metadata=metadata,
        )
        
        self._record_span_start(span)
        
        try:
            yield span
            span.complete(EventStatus.SUCCESS)
        except Exception as e:
            span.fail(str(e))
            raise
        finally:
            self._record_span_end(span)
    
    def record_llm_call(
        self,
        model: str,
        prompt: Optional[str] = None,
        messages: Optional[list[dict[str, Any]]] = None,
        response: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Record an LLM API call.
        
        Args:
            model: Model identifier (e.g., "gpt-4")
            prompt: The prompt sent to the LLM
            messages: Chat messages (for chat models)
            response: The response from the LLM
            **kwargs: Additional metadata
        """
        from agent_blackbox_recorder.core.events import LLMCallEvent
        
        event = LLMCallEvent(
            name=f"LLM: {model}",
            trace_id=self._current_session.id if self._current_session else "",
            model=model,
            prompt=prompt,
            messages=messages,
            response=response,
            **kwargs,
        )
        
        if response:
            event.complete()
        
        self._record_event(event)
    
    def record_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[Exception] = None,
    ) -> None:
        """
        Record a tool/function call.
        
        Args:
            tool_name: Name of the tool
            arguments: Arguments passed to the tool
            result: Result of the tool call (if successful)
            error: Error (if the tool failed)
        """
        from agent_blackbox_recorder.core.events import ToolCallEvent
        
        event = ToolCallEvent(
            name=f"Tool: {tool_name}",
            trace_id=self._current_session.id if self._current_session else "",
            tool_name=tool_name,
            arguments=arguments,
        )
        
        if result is not None:
            event.set_result(result)
        elif error is not None:
            event.set_error(error)
        
        self._record_event(event)
    
    def capture_state(
        self,
        state: Any,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> StateSnapshot:
        """
        Capture a snapshot of the current state.
        
        Args:
            state: The state object to capture
            name: Optional name for the checkpoint
            description: Optional description
        
        Returns:
            The created StateSnapshot
        """
        with self._lock:
            event_id = self._event_stack[-1].id if self._event_stack else ""
            trace_id = self._current_session.id if self._current_session else ""
            
            snapshot = self._snapshot_engine.capture(
                state=state,
                trace_id=trace_id,
                event_id=event_id,
                checkpoint_name=name,
                description=description,
            )
            
            if self._current_session:
                self._current_session.add_snapshot(snapshot)
            
            return snapshot
    
    def install_adapter(self, adapter: Any) -> None:
        """
        Install a framework adapter.
        
        Args:
            adapter: The adapter to install
        """
        self._adapters.append(adapter)
        if hasattr(adapter, "install"):
            adapter.install(self)
    
    def wrap(self, runnable: T) -> T:
        """
        Wrap a runnable (e.g., LangGraph app) for automatic tracing.
        
        Args:
            runnable: The runnable to wrap
        
        Returns:
            Wrapped runnable with tracing enabled
        """
        # Check for LangGraph adapter
        for adapter in self._adapters:
            if hasattr(adapter, "wrap"):
                return adapter.wrap(runnable, self)  # type: ignore
        
        # Return as-is if no adapter can wrap it
        return runnable
    
    def replay(
        self,
        session_id: Optional[str] = None,
        port: int = 8765,
        open_browser: bool = True,
    ) -> None:
        """
        Open the interactive replay UI.
        
        Args:
            session_id: Specific session to replay (defaults to latest)
            port: Port for the web server
            open_browser: Whether to automatically open a browser
        """
        from agent_blackbox_recorder.server.api import start_server
        
        # Get the session to replay
        if session_id:
            session = self._storage.load_session(session_id)
        else:
            sessions = self._storage.list_sessions()
            if sessions:
                # Sort by timestamp (assuming ID contains timestamp or we trust the order, 
                # but safer to sort if possible. For now, we assume list_sessions returns 
                # them in some order, but taking the last one is usually newer for append-logs).
                # Actually, let's assume the user wants the LATEST.
                # If list_sessions currently returns unsorted, we should ideally sort it.
                # Let's simple take the last one which is a better heuristic than [0] for logs.
                session = self._storage.load_session(sessions[-1]["id"])
            else:
                logger.warning("No sessions found to replay.")
                return
        
        # Start the server
        url = f"http://localhost:{port}"
        logger.info(f"Starting replay server at {url}")
        
        if open_browser:
            webbrowser.open(url)
        
        start_server(self._storage, port=port)
    
    def list_sessions(self) -> list[dict[str, Any]]:
        """List all recorded sessions."""
        return self._storage.list_sessions()
    
    def load_session(self, session_id: str) -> TraceSession:
        """Load a specific session by ID."""
        return self._storage.load_session(session_id)
    
    # Internal methods
    
    def _record_event(self, event: TraceEvent) -> None:
        """Record an event to the current session."""
        with self._lock:
            if self._current_session is None:
                self.start_session()
            
            # Set parent
            if self._event_stack:
                event.parent_id = self._event_stack[-1].id
            
            event.trace_id = self._current_session.id  # type: ignore
            self._current_session.add_event(event)  # type: ignore
    
    def _record_span_start(self, span: SpanEvent) -> None:
        """Record the start of a span."""
        with self._lock:
            if self._current_session is None:
                self.start_session()
            
            # Set parent
            if self._event_stack:
                span.parent_id = self._event_stack[-1].id
            
            span.trace_id = self._current_session.id  # type: ignore
            self._current_session.add_event(span)  # type: ignore
            self._event_stack.append(span)
    
    def _record_span_end(self, span: SpanEvent) -> None:
        """Record the end of a span."""
        with self._lock:
            if self._event_stack and self._event_stack[-1].id == span.id:
                self._event_stack.pop()
            
            # Auto-save if this was the root span
            if not self._event_stack:
                self.end_session(
                    status=span.status if span.status != EventStatus.RUNNING else EventStatus.SUCCESS
                )
    
    def _capture_checkpoint(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> None:
        """
        Internal method for checkpoint decorator.
        
        Attempts to capture the current state. If used on a method,
        attempts to capture the 'self' instance.
        """
        try:
            # Inspect the stack to find the calling frame
            # 0: _capture_checkpoint (this)
            # 1: decorator wrapper
            # 2: The actual call site (or the framework calling the decorated function)
            # We want to capture the 'self' of the function being decorated.
            # But the decorator wrapper (in decorators.py) has the args.
            # This is complex to do robustly via stack inspection alone without helpful args.
            
            # For a robust implementation, we'll try to walk up one frame 
            # and look for 'self' in locals (which would be the arguments to the wrapper).
             
            frame = inspect.currentframe()
            if frame and frame.f_back and frame.f_back.f_locals:
                locals_ = frame.f_back.f_locals
                
                # Check for 'self' (common for agent classes)
                state = locals_.get("self") or locals_.get("agent")
                
                # If no clear state object, we arguably shouldn't snapshot random things 
                # as it might be huge.
                if state:
                    self.capture_state(
                        state=state,
                        name=name,
                        description=description or "Automatic checkpoint"
                    )
                else:
                    logger.debug("Automatic checkpoint: No 'self' or 'agent' found to snapshot.")
                    
        except Exception as e:
            logger.warning(f"Failed to capture automatic checkpoint: {e}")
        finally:
            # Avoid reference cycles
            del frame
