"""
Decorators for AgentBlackBoxRecorder.

Provides @trace and @checkpoint decorators for easy agent instrumentation.
"""

from functools import wraps
from typing import Any, Callable, Optional, TypeVar, ParamSpec, overload
import asyncio
import inspect

from agent_blackbox_recorder.core.events import SpanEvent, EventStatus

P = ParamSpec("P")
R = TypeVar("R")


from contextvars import ContextVar

# ContextVar for recorder reference (thread/task safe)
_recorder_ctx: ContextVar[Optional[Any]] = ContextVar("recorder", default=None)


def set_current_recorder(recorder: Any) -> None:
    """Set the current recorder for the current context."""
    _recorder_ctx.set(recorder)


def get_current_recorder() -> Optional[Any]:
    """Get the current recorder."""
    return _recorder_ctx.get()


@overload
def trace(func: Callable[P, R]) -> Callable[P, R]: ...


@overload
def trace(
    *,
    name: Optional[str] = None,
    capture_args: bool = True,
    capture_result: bool = True,
    tags: Optional[list[str]] = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def trace(
    func: Optional[Callable[P, R]] = None,
    *,
    name: Optional[str] = None,
    capture_args: bool = True,
    capture_result: bool = True,
    tags: Optional[list[str]] = None,
) -> Any:
    """
    Decorator to trace function execution.
    
    Can be used with or without arguments:
    
        @trace
        def my_function():
            pass
        
        @trace(name="custom_name", tags=["important"])
        def my_function():
            pass
    
    Args:
        func: The function to wrap (when used without parentheses)
        name: Custom name for the trace span (defaults to function name)
        capture_args: Whether to capture function arguments
        capture_result: Whether to capture the return value
        tags: Optional tags to attach to the span
    """
    
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        span_name = name or fn.__name__
        span_tags = tags or []
        
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                recorder = get_current_recorder()
                if recorder is None:
                    return await fn(*args, **kwargs)
                
                # Create span
                span = SpanEvent(
                    name=span_name,
                    trace_id="",  # Will be set by recorder
                    tags=span_tags,
                    metadata={
                        "function": fn.__name__,
                        "module": fn.__module__,
                        "is_async": True,
                    },
                )
                
                # Capture arguments
                if capture_args:
                    span.set_input(_serialize_args(fn, args, kwargs))
                
                # Record start
                recorder._record_span_start(span)
                
                try:
                    result = await fn(*args, **kwargs)
                    
                    # Capture result
                    if capture_result:
                        span.set_output({"result": _serialize_value(result)})
                    
                    span.complete(EventStatus.SUCCESS)
                    recorder._record_span_end(span)
                    return result
                    
                except Exception as e:
                    span.fail(str(e))
                    recorder._record_span_end(span)
                    raise
            
            return async_wrapper  # type: ignore
        
        else:
            @wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                recorder = get_current_recorder()
                if recorder is None:
                    return fn(*args, **kwargs)
                
                # Create span
                span = SpanEvent(
                    name=span_name,
                    trace_id="",  # Will be set by recorder
                    tags=span_tags,
                    metadata={
                        "function": fn.__name__,
                        "module": fn.__module__,
                        "is_async": False,
                    },
                )
                
                # Capture arguments
                if capture_args:
                    span.set_input(_serialize_args(fn, args, kwargs))
                
                # Record start
                recorder._record_span_start(span)
                
                try:
                    result = fn(*args, **kwargs)
                    
                    # Capture result
                    if capture_result:
                        span.set_output({"result": _serialize_value(result)})
                    
                    span.complete(EventStatus.SUCCESS)
                    recorder._record_span_end(span)
                    return result
                    
                except Exception as e:
                    span.fail(str(e))
                    recorder._record_span_end(span)
                    raise
            
            return sync_wrapper  # type: ignore
    
    # Handle both @trace and @trace(...) syntax
    if func is not None:
        return decorator(func)
    return decorator


def checkpoint(
    name: Optional[str] = None,
    *,
    description: Optional[str] = None,
    capture_state: bool = True,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator to mark a function as a checkpoint.
    
    Checkpoints capture a full state snapshot that can be used
    to restore execution in takeover mode.
    
    Args:
        name: Custom name for the checkpoint
        description: Description of what this checkpoint represents
        capture_state: Whether to capture state at this point
    """
    
    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        checkpoint_name = name or f"checkpoint_{fn.__name__}"
        
        if asyncio.iscoroutinefunction(fn):
            @wraps(fn)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                recorder = get_current_recorder()
                if recorder is None:
                    return await fn(*args, **kwargs)
                
                # Capture state before
                if capture_state:
                    recorder._capture_checkpoint(
                        name=checkpoint_name,
                        description=description,
                    )
                
                return await fn(*args, **kwargs)
            
            return async_wrapper  # type: ignore
        
        else:
            @wraps(fn)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                recorder = get_current_recorder()
                if recorder is None:
                    return fn(*args, **kwargs)
                
                # Capture state before
                if capture_state:
                    recorder._capture_checkpoint(
                        name=checkpoint_name,
                        description=description,
                    )
                
                return fn(*args, **kwargs)
            
            return sync_wrapper  # type: ignore
    
    return decorator


def _serialize_args(fn: Callable[..., Any], args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Serialize function arguments."""
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    
    serialized: dict[str, Any] = {}
    
    # Positional args
    for i, arg in enumerate(args):
        key = params[i] if i < len(params) else f"arg_{i}"
        serialized[key] = _serialize_value(arg)
    
    # Keyword args
    for key, value in kwargs.items():
        serialized[key] = _serialize_value(value)
    
    return serialized


def _serialize_value(value: Any, max_depth: int = 3, max_str_length: int = 1000) -> Any:
    """
    Serialize a value for storage.
    
    Handles common types and provides fallbacks for complex objects.
    """
    if max_depth <= 0:
        return f"<{type(value).__name__}: max depth reached>"
    
    # Primitives
    if value is None or isinstance(value, (bool, int, float)):
        return value
    
    # Strings (truncate if too long)
    if isinstance(value, str):
        if len(value) > max_str_length:
            return value[:max_str_length] + f"... (truncated, {len(value)} chars total)"
        return value
    
    # Lists
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v, max_depth - 1, max_str_length) for v in value[:100]]
    
    # Dicts
    if isinstance(value, dict):
        return {
            str(k): _serialize_value(v, max_depth - 1, max_str_length)
            for k, v in list(value.items())[:100]
        }
    
    # Pydantic models
    if hasattr(value, "model_dump"):
        try:
            return {
                "_type": type(value).__name__,
                **value.model_dump(),
            }
        except Exception:
            pass
    
    # Objects with __dict__
    if hasattr(value, "__dict__"):
        try:
            return {
                "_type": type(value).__name__,
                **{k: _serialize_value(v, max_depth - 1, max_str_length) 
                   for k, v in value.__dict__.items() 
                   if not k.startswith("_")},
            }
        except Exception:
            pass
    
    # Fallback: string representation
    try:
        return f"<{type(value).__name__}: {str(value)[:100]}>"
    except Exception:
        return f"<{type(value).__name__}: unserializable>"
