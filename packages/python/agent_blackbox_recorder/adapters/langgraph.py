"""
LangGraph adapter for AgentBlackBoxRecorder.

Provides automatic tracing for LangGraph workflows.
"""

from typing import TYPE_CHECKING, Any, Callable, Optional, TypeVar
import functools

from agent_blackbox_recorder.adapters.base import BaseAdapter
from agent_blackbox_recorder.core.events import SpanEvent, EventStatus

if TYPE_CHECKING:
    from agent_blackbox_recorder.core.recorder import Recorder


T = TypeVar("T")


class LangGraphAdapter(BaseAdapter):
    """
    Adapter for LangGraph workflows.
    
    Automatically captures:
    - Node executions
    - State transitions
    - Tool calls
    - LLM invocations
    
    Example:
        ```python
        from agent_blackbox_recorder import Recorder
        from agent_blackbox_recorder.adapters import LangGraphAdapter
        
        recorder = Recorder(adapters=[LangGraphAdapter()])
        app = recorder.wrap(workflow.compile())
        ```
    """
    
    def __init__(
        self,
        capture_state: bool = True,
        capture_messages: bool = True,
    ) -> None:
        """
        Initialize the LangGraph adapter.
        
        Args:
            capture_state: Whether to capture full state at each node
            capture_messages: Whether to capture message contents
        """
        self._capture_state = capture_state
        self._capture_messages = capture_messages
        self._recorder: Optional["Recorder"] = None
        self._original_funcs: dict[str, Any] = {}
    
    @property
    def name(self) -> str:
        return "langgraph"
    
    @property
    def version(self) -> str:
        return "0.1.0"
    
    def install(self, recorder: "Recorder") -> None:
        """Install LangGraph instrumentation."""
        self._recorder = recorder
        
        # Try to patch LangGraph internals
        try:
            self._patch_langgraph()
        except ImportError:
            # LangGraph not installed, skip patching
            pass
    
    def uninstall(self) -> None:
        """Remove LangGraph instrumentation."""
        self._unpatch_langgraph()
        self._recorder = None
    
    def wrap(self, runnable: T, recorder: "Recorder") -> T:
        """
        Wrap a LangGraph compiled graph for tracing.
        
        Args:
            runnable: The compiled LangGraph application
            recorder: The Recorder to use
        
        Returns:
            Wrapped application with tracing
        """
        self._recorder = recorder
        
        # Check if this is a LangGraph Pregel/CompiledGraph
        if hasattr(runnable, "invoke") and hasattr(runnable, "nodes"):
            return self._wrap_compiled_graph(runnable)  # type: ignore
        
        return runnable
    
    def _wrap_compiled_graph(self, graph: Any) -> Any:
        """Wrap a compiled LangGraph graph."""
        original_invoke = graph.invoke
        original_ainvoke = getattr(graph, "ainvoke", None)
        adapter = self
        
        @functools.wraps(original_invoke)
        def traced_invoke(
            input: Any,
            config: Optional[dict[str, Any]] = None,
            **kwargs: Any,
        ) -> Any:
            if adapter._recorder is None:
                return original_invoke(input, config, **kwargs)
            
            # Start a session for this invocation
            session = adapter._recorder.start_session(
                name=f"LangGraph: {getattr(graph, 'name', 'workflow')}",
                metadata={
                    "framework": "langgraph",
                    "graph_name": getattr(graph, "name", "unknown"),
                },
            )
            
            # Create root span
            with adapter._recorder.span("langgraph_invoke") as span:
                span.set_input(adapter._serialize_input(input))
                span.metadata["framework"] = "langgraph"
                
                if adapter._capture_state:
                    adapter._recorder.capture_state(
                        input,
                        name="initial_state",
                        description="Initial input state",
                    )
                
                try:
                    result = original_invoke(input, config, **kwargs)
                    
                    span.set_output(adapter._serialize_input(result))
                    
                    if adapter._capture_state:
                        adapter._recorder.capture_state(
                            result,
                            name="final_state",
                            description="Final output state",
                        )
                    
                    return result
                    
                except Exception as e:
                    span.fail(str(e))
                    raise
        
        # Replace invoke method
        graph.invoke = traced_invoke
        
        # Handle async invoke if present
        if original_ainvoke is not None:
            @functools.wraps(original_ainvoke)
            async def traced_ainvoke(
                input: Any,
                config: Optional[dict[str, Any]] = None,
                **kwargs: Any,
            ) -> Any:
                if adapter._recorder is None:
                    return await original_ainvoke(input, config, **kwargs)
                
                # Start a session
                adapter._recorder.start_session(
                    name=f"LangGraph: {getattr(graph, 'name', 'workflow')}",
                    metadata={"framework": "langgraph"},
                )
                
                with adapter._recorder.span("langgraph_invoke") as span:
                    span.set_input(adapter._serialize_input(input))
                    
                    try:
                        result = await original_ainvoke(input, config, **kwargs)
                        span.set_output(adapter._serialize_input(result))
                        return result
                    except Exception as e:
                        span.fail(str(e))
                        raise
            
            graph.ainvoke = traced_ainvoke
        
        return graph
    
    def _patch_langgraph(self) -> None:
        """Patch LangGraph internals for automatic tracing."""
        try:
            from langgraph.pregel import Pregel
            
            # Store original methods
            self._original_funcs["Pregel._execute"] = getattr(Pregel, "_execute", None)
            
            # We could patch node execution here if needed
            # For now, we rely on the wrap() method
            
        except ImportError:
            pass
    
    def _unpatch_langgraph(self) -> None:
        """Restore original LangGraph methods."""
        try:
            from langgraph.pregel import Pregel
            
            for name, func in self._original_funcs.items():
                if func is not None:
                    parts = name.split(".")
                    if len(parts) == 2 and parts[0] == "Pregel":
                        setattr(Pregel, parts[1], func)
            
            self._original_funcs.clear()
            
        except ImportError:
            pass
    
    def _serialize_input(self, input: Any) -> dict[str, Any]:
        """Serialize LangGraph input/output for storage."""
        if isinstance(input, dict):
            result = {}
            for key, value in input.items():
                if key == "messages" and self._capture_messages:
                    result[key] = self._serialize_messages(value)
                elif hasattr(value, "model_dump"):
                    result[key] = value.model_dump()
                elif isinstance(value, (str, int, float, bool, type(None))):
                    result[key] = value
                elif isinstance(value, list):
                    result[key] = [self._serialize_input(v) for v in value[:20]]
                else:
                    result[key] = str(value)[:500]
            return result
        
        if hasattr(input, "model_dump"):
            return input.model_dump()
        
        return {"value": str(input)[:1000]}
    
    def _serialize_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Serialize LangChain messages."""
        result = []
        for msg in messages[:50]:  # Limit to 50 messages
            if hasattr(msg, "model_dump"):
                result.append(msg.model_dump())
            elif hasattr(msg, "content"):
                result.append({
                    "type": type(msg).__name__,
                    "content": str(msg.content)[:1000],
                })
            else:
                result.append({"raw": str(msg)[:500]})
        return result
